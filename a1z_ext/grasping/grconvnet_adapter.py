"""Bridge GR-ConvNet grasp maps to A1Z robot-executable plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from a1z_ext.grasping.contact_graspnet_adapter import (
    ContactGraspNetA1ZAdapter,
    ContactGraspNetA1ZAdapterConfig,
    ContactGraspNetPlanResult,
    _normalize,
    _rigidize_transform,
)


@dataclass(slots=True)
class GRConvNetA1ZAdapterConfig(ContactGraspNetA1ZAdapterConfig):
    crop_size_px: int = 224
    crop_center_mode: str = "image_center"
    min_depth_m: float = 0.05
    max_depth_m: float = 1.5
    max_grasp_width_m: float = 0.096
    width_scale_crop_px: float = 150.0
    grasp_z_offset_m: float = 0.0
    topdown_binormal_base: tuple[float, float, float] = (0.0, 1.0, 0.0)


class GRConvNetA1ZAdapter:
    """Convert top-down GR-ConvNet outputs into A1Z candidates and plans."""

    def __init__(self, config: GRConvNetA1ZAdapterConfig | None = None, *, kinematics: Any | None = None) -> None:
        self.config = config or GRConvNetA1ZAdapterConfig()
        self._contact_adapter = ContactGraspNetA1ZAdapter(config=self.config, kinematics=kinematics)

    def plan_from_grasp_maps(
        self,
        *,
        quality_map: np.ndarray,
        angle_map_rad: np.ndarray,
        width_map_px: np.ndarray,
        depth_m: np.ndarray,
        intrinsics: dict[str, float],
        extrinsic_camera_to_base: np.ndarray,
        current_q: np.ndarray | list[float],
        task_id: str,
        object_id: str,
        backend: str = "unknown",
        mask: np.ndarray | None = None,
        top_k: int = 20,
        min_quality: float = 0.1,
        peak_local_max_min_distance: int = 12,
    ) -> ContactGraspNetPlanResult:
        grasps_cam, scores, openings_m, contact_points_cam = self._grasp_maps_to_camera_grasps(
            quality_map=quality_map,
            angle_map_rad=angle_map_rad,
            width_map_px=width_map_px,
            depth_m=depth_m,
            intrinsics=intrinsics,
            mask=mask,
            top_k=top_k,
            min_quality=min_quality,
            peak_local_max_min_distance=peak_local_max_min_distance,
        )
        return self._contact_adapter.plan(
            pred_grasps_cam=grasps_cam,
            scores=scores,
            gripper_openings_m=openings_m,
            contact_points_cam=contact_points_cam,
            extrinsic_camera_to_base=extrinsic_camera_to_base,
            current_q=current_q,
            task_id=task_id,
            object_id=object_id,
            backend=backend,
        )

    def _grasp_maps_to_camera_grasps(
        self,
        *,
        quality_map: np.ndarray,
        angle_map_rad: np.ndarray,
        width_map_px: np.ndarray,
        depth_m: np.ndarray,
        intrinsics: dict[str, float],
        mask: np.ndarray | None,
        top_k: int,
        min_quality: float,
        peak_local_max_min_distance: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        quality_map = np.asarray(quality_map, dtype=np.float32)
        angle_map_rad = np.asarray(angle_map_rad, dtype=np.float32)
        width_map_px = np.asarray(width_map_px, dtype=np.float32)
        depth_m = np.asarray(depth_m, dtype=np.float32)
        if quality_map.shape != angle_map_rad.shape or quality_map.shape != width_map_px.shape:
            raise ValueError("quality_map, angle_map_rad, width_map_px must share the same shape")
        if quality_map.shape != depth_m.shape:
            raise ValueError("grasp maps and depth_m must share the same shape")

        valid = np.isfinite(depth_m) & (depth_m >= float(self.config.min_depth_m)) & (depth_m <= float(self.config.max_depth_m))
        if mask is not None:
            mask_bool = np.asarray(mask, dtype=bool)
            if mask_bool.shape != quality_map.shape:
                raise ValueError("mask shape must match grasp map shape")
            valid &= mask_bool
        candidate_quality = quality_map.copy()
        candidate_quality[~valid] = 0.0

        peaks = _peak_local_max_2d(
            candidate_quality,
            min_distance=max(1, int(peak_local_max_min_distance)),
            threshold_abs=float(min_quality),
            num_peaks=max(1, int(top_k)),
        )
        if peaks.size == 0:
            flat_index = int(np.argmax(candidate_quality))
            if float(candidate_quality.reshape(-1)[flat_index]) <= 0.0:
                raise ValueError("no valid GR-ConvNet grasp peaks found")
            peaks = np.asarray(np.unravel_index(flat_index, candidate_quality.shape)).reshape(2, 1).T

        scores: list[float] = []
        grasps_cam: list[np.ndarray] = []
        openings_m: list[float] = []
        contact_points_cam: list[np.ndarray] = []
        for row_px, col_px in peaks[:top_k]:
            z = float(depth_m[row_px, col_px])
            if not np.isfinite(z):
                continue
            center_cam = self._pixel_to_camera_xyz(
                u=float(col_px),
                v=float(row_px),
                z=z,
                intrinsics=intrinsics,
            )
            theta = float(angle_map_rad[row_px, col_px])
            opening_dir_cam = self._opening_axis_from_angle(theta)
            approach_dir_cam = np.array([0.0, 0.0, -1.0], dtype=np.float64)
            binormal_dir_cam = _normalize(np.cross(approach_dir_cam, opening_dir_cam))

            grasp_cam = np.eye(4, dtype=np.float64)
            grasp_cam[:3, 0] = opening_dir_cam
            grasp_cam[:3, 1] = binormal_dir_cam
            grasp_cam[:3, 2] = approach_dir_cam
            grasp_cam[:3, 3] = center_cam + approach_dir_cam * float(self.config.grasp_z_offset_m)
            grasp_cam = _rigidize_transform(grasp_cam)

            opening_m = self._width_px_to_meters(
                width_px=float(width_map_px[row_px, col_px]),
                depth_m=z,
                intrinsics=intrinsics,
            )
            contact_point = center_cam + opening_dir_cam * (0.5 * opening_m)

            grasps_cam.append(grasp_cam)
            scores.append(float(candidate_quality[row_px, col_px]))
            openings_m.append(opening_m)
            contact_points_cam.append(contact_point.astype(np.float64))

        if not grasps_cam:
            raise ValueError("no valid GR-ConvNet grasp candidates survived depth/mask filtering")
        return (
            np.stack(grasps_cam, axis=0),
            np.asarray(scores, dtype=np.float64),
            np.asarray(openings_m, dtype=np.float64),
            np.asarray(contact_points_cam, dtype=np.float64),
        )

    def _pixel_to_camera_xyz(
        self,
        *,
        u: float,
        v: float,
        z: float,
        intrinsics: dict[str, float],
    ) -> np.ndarray:
        fx = float(intrinsics["fx"])
        fy = float(intrinsics["fy"])
        cx = float(intrinsics["cx"])
        cy = float(intrinsics["cy"])
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy
        return np.array([x, y, z], dtype=np.float64)

    def _opening_axis_from_angle(self, theta: float) -> np.ndarray:
        axis = np.array([-np.sin(theta), np.cos(theta), 0.0], dtype=np.float64)
        return _normalize(axis)

    def _width_px_to_meters(self, *, width_px: float, depth_m: float, intrinsics: dict[str, float]) -> float:
        fx = float(intrinsics["fx"])
        width_m = abs(float(width_px)) * depth_m / fx
        return float(np.clip(width_m, 0.0, self.config.max_grasp_width_m))


def default_grconvnet_checkpoint_path(repo_root: str | Path) -> Path:
    return (
        Path(repo_root).resolve()
        / "runtime"
        / "models"
        / "grconvnet"
        / "jacquard-rgbd-grconvnet3-drop0-ch32"
        / "epoch_48_iou_0.93"
    )


def _peak_local_max_2d(
    image: np.ndarray,
    *,
    min_distance: int,
    threshold_abs: float,
    num_peaks: int,
) -> np.ndarray:
    image = np.asarray(image, dtype=np.float32)
    if image.ndim != 2:
        raise ValueError(f"expected 2D image, got shape {image.shape}")

    candidates = np.argwhere(image >= float(threshold_abs))
    if candidates.size == 0:
        return np.empty((0, 2), dtype=np.int64)

    scores = image[candidates[:, 0], candidates[:, 1]]
    order = np.argsort(scores)[::-1]
    radius_sq = int(min_distance) * int(min_distance)

    selected: list[np.ndarray] = []
    for idx in order:
        point = candidates[idx]
        if any(int((point[0] - kept[0]) ** 2 + (point[1] - kept[1]) ** 2) < radius_sq for kept in selected):
            continue
        selected.append(point)
        if len(selected) >= int(num_peaks):
            break

    if not selected:
        return np.empty((0, 2), dtype=np.int64)
    return np.asarray(selected, dtype=np.int64)
