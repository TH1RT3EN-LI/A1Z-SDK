"""Bridge EconomicGrasp predictions to A1Z robot-executable plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from a1z_ext.grasping.contact_graspnet_adapter import (
    ContactGraspNetA1ZAdapter,
    ContactGraspNetA1ZAdapterConfig,
    ContactGraspNetPlanResult,
    _normalize,
    _rigidize_transform,
)


@dataclass(slots=True)
class EconomicGraspA1ZAdapterConfig(ContactGraspNetA1ZAdapterConfig):
    grasp_center_is_contact_center: bool = True
    depth_bias_m: float = 0.0
    require_approach_downward: bool = False
    max_approach_deviation_deg: float = 85.0
    approach_axis_modes: tuple[str, ...] = ("c2", "c0")
    opening_axis_modes: tuple[str, ...] = ("mc1", "c1")
    center_shift_depth_scales: tuple[float, ...] = (0.0, 0.5, 1.0, -0.5, -1.0)


@dataclass(slots=True)
class _EconomicVariant:
    original_index: int
    variant_index: int
    score: float
    width_m: float
    height_m: float
    depth_m: float
    center_xyz_cam: np.ndarray
    grasp_center_xyz_cam: np.ndarray
    projected_uv: tuple[int, int] | None
    approach_axis_mode: str
    opening_axis_mode: str
    center_shift_depth_scale: float

    def to_metadata(self) -> dict[str, Any]:
        return {
            "economicgrasp_original_index": int(self.original_index),
            "economicgrasp_variant_index": int(self.variant_index),
            "economicgrasp_projected_uv": None
            if self.projected_uv is None
            else [int(self.projected_uv[0]), int(self.projected_uv[1])],
            "economicgrasp_variant": {
                "approach_axis_mode": self.approach_axis_mode,
                "opening_axis_mode": self.opening_axis_mode,
                "center_shift_depth_scale": float(self.center_shift_depth_scale),
                "center_xyz_cam": self.center_xyz_cam.astype(float).tolist(),
                "grasp_center_xyz_cam": self.grasp_center_xyz_cam.astype(float).tolist(),
                "width_m": float(self.width_m),
                "height_m": float(self.height_m),
                "depth_m": float(self.depth_m),
            },
        }


class EconomicGraspA1ZAdapter:
    """Convert EconomicGrasp outputs into A1Z candidates and plans."""

    def __init__(self, config: EconomicGraspA1ZAdapterConfig | None = None, *, kinematics: Any | None = None) -> None:
        self.config = config or EconomicGraspA1ZAdapterConfig()
        self._contact_adapter = ContactGraspNetA1ZAdapter(config=self.config, kinematics=kinematics)

    def plan_from_predictions(
        self,
        *,
        predictions: np.ndarray,
        extrinsic_camera_to_base: np.ndarray,
        current_q: Sequence[float],
        task_id: str,
        object_id: str,
        backend: str = "unknown",
        intrinsics: dict[str, float] | None = None,
        mask: np.ndarray | None = None,
    ) -> ContactGraspNetPlanResult:
        (
            grasps_cam,
            scores,
            openings_m,
            contact_points_cam,
            variants,
            variant_summary,
        ) = self._predictions_to_camera_grasps(
            predictions,
            intrinsics=intrinsics,
            mask=mask,
        )
        result = self._contact_adapter.plan(
            pred_grasps_cam=grasps_cam,
            scores=scores,
            gripper_openings_m=openings_m,
            contact_points_cam=contact_points_cam,
            extrinsic_camera_to_base=extrinsic_camera_to_base,
            current_q=current_q,
            task_id=task_id,
            object_id=object_id,
            backend=backend,
            source_model="economicgrasp",
        )
        for candidate, variant in zip(result.candidates, variants, strict=True):
            candidate.source_group_id = f"economicgrasp:{variant.original_index}"
            candidate.source_index = int(variant.variant_index)
            candidate.metadata = {
                **candidate.metadata,
                **variant.to_metadata(),
            }
        result.summary.update(variant_summary)
        return result

    def _predictions_to_camera_grasps(
        self,
        predictions: np.ndarray,
        *,
        intrinsics: dict[str, float] | None,
        mask: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[_EconomicVariant], dict[str, Any]]:
        rows = np.asarray(predictions, dtype=np.float64).reshape(-1, 17)
        mask_bool = None if mask is None else np.asarray(mask, dtype=bool)
        if mask_bool is not None:
            if mask_bool.ndim != 2:
                raise ValueError(f"mask must be 2D, got shape {mask_bool.shape}")
            if intrinsics is None:
                raise ValueError("intrinsics are required when mask filtering is enabled")

        grasps_cam: list[np.ndarray] = []
        scores: list[float] = []
        openings_m: list[float] = []
        contact_points_cam: list[np.ndarray] = []
        variants: list[_EconomicVariant] = []

        rows_kept_by_mask = 0
        rows_skipped_by_mask = 0
        variant_index = 0
        for row_index, row in enumerate(rows):
            score = float(row[0])
            width_m = float(row[1])
            height_m = float(row[2])
            depth_m = float(row[3])
            rotation = row[4:13].reshape(3, 3)
            center_xyz = row[13:16].reshape(3)

            projected_uv = None
            if mask_bool is not None:
                projected_uv = self._project_point_to_image(center_xyz, intrinsics)
                if projected_uv is None or not self._mask_contains(mask_bool, projected_uv):
                    rows_skipped_by_mask += 1
                    continue
                rows_kept_by_mask += 1

            for approach_axis_mode in self.config.approach_axis_modes:
                approach_dir = self._resolve_axis(rotation, approach_axis_mode)
                for opening_axis_mode in self.config.opening_axis_modes:
                    opening_seed = self._resolve_axis(rotation, opening_axis_mode)
                    opening_dir = opening_seed - float(np.dot(opening_seed, approach_dir)) * approach_dir
                    if float(np.linalg.norm(opening_dir)) <= 1e-6:
                        continue
                    opening_dir = _normalize(opening_dir)
                    height_dir = _normalize(np.cross(approach_dir, opening_dir))
                    opening_dir = _normalize(np.cross(height_dir, approach_dir))

                    base_center_cam = center_xyz.copy()
                    if not self.config.grasp_center_is_contact_center:
                        base_center_cam = base_center_cam + approach_dir * (0.5 * depth_m)
                    if abs(float(self.config.depth_bias_m)) > 1e-9:
                        base_center_cam = base_center_cam + approach_dir * float(self.config.depth_bias_m)

                    for shift_scale in self.config.center_shift_depth_scales:
                        grasp_center_cam = base_center_cam + approach_dir * (float(shift_scale) * depth_m)
                        grasp_cam = np.eye(4, dtype=np.float64)
                        grasp_cam[:3, 0] = opening_dir
                        grasp_cam[:3, 1] = height_dir
                        grasp_cam[:3, 2] = approach_dir
                        grasp_cam[:3, 3] = grasp_center_cam
                        grasp_cam = _rigidize_transform(grasp_cam)

                        grasps_cam.append(grasp_cam)
                        scores.append(score)
                        openings_m.append(width_m)
                        contact_points_cam.append(grasp_center_cam.astype(np.float64))
                        variants.append(
                            _EconomicVariant(
                                original_index=row_index,
                                variant_index=variant_index,
                                score=score,
                                width_m=width_m,
                                height_m=height_m,
                                depth_m=depth_m,
                                center_xyz_cam=center_xyz.copy(),
                                grasp_center_xyz_cam=grasp_center_cam.copy(),
                                projected_uv=projected_uv,
                                approach_axis_mode=approach_axis_mode,
                                opening_axis_mode=opening_axis_mode,
                                center_shift_depth_scale=float(shift_scale),
                            )
                        )
                        variant_index += 1

        if not grasps_cam:
            raise ValueError("EconomicGrasp prediction set is empty after mask/variant expansion")
        summary = {
            "economicgrasp_input_prediction_count": int(rows.shape[0]),
            "economicgrasp_mask_filtered_prediction_count": None if mask_bool is None else int(rows_kept_by_mask),
            "economicgrasp_mask_skipped_prediction_count": None if mask_bool is None else int(rows_skipped_by_mask),
            "economicgrasp_variant_count": int(len(variants)),
            "economicgrasp_axis_modes": {
                "approach_axis_modes": [str(item) for item in self.config.approach_axis_modes],
                "opening_axis_modes": [str(item) for item in self.config.opening_axis_modes],
                "center_shift_depth_scales": [float(item) for item in self.config.center_shift_depth_scales],
            },
        }
        return (
            np.stack(grasps_cam, axis=0),
            np.asarray(scores, dtype=np.float64),
            np.asarray(openings_m, dtype=np.float64),
            np.asarray(contact_points_cam, dtype=np.float64),
            variants,
            summary,
        )

    def _resolve_axis(self, rotation: np.ndarray, mode: str) -> np.ndarray:
        token = str(mode).strip()
        sign = 1.0
        if token.startswith("m"):
            sign = -1.0
            token = token[1:]
        if not token.startswith("c"):
            raise ValueError(f"unsupported EconomicGrasp axis mode: {mode!r}")
        axis_index = int(token[1:])
        if axis_index < 0 or axis_index >= 3:
            raise ValueError(f"axis index out of range in mode {mode!r}")
        return sign * _normalize(np.asarray(rotation[:, axis_index], dtype=np.float64).reshape(3))

    def _project_point_to_image(
        self,
        point_xyz: np.ndarray,
        intrinsics: dict[str, float] | None,
    ) -> tuple[int, int] | None:
        if intrinsics is None:
            return None
        x, y, z = [float(value) for value in np.asarray(point_xyz, dtype=np.float64).reshape(3)]
        if z <= 1e-9 or not np.isfinite(z):
            return None
        fx = float(intrinsics["fx"])
        fy = float(intrinsics["fy"])
        cx = float(intrinsics["cx"])
        cy = float(intrinsics["cy"])
        u = int(round(fx * x / z + cx))
        v = int(round(fy * y / z + cy))
        return (u, v)

    def _mask_contains(self, mask: np.ndarray, uv: tuple[int, int]) -> bool:
        u, v = int(uv[0]), int(uv[1])
        return 0 <= v < mask.shape[0] and 0 <= u < mask.shape[1] and bool(mask[v, u])
