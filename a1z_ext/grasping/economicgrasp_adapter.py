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
    ) -> ContactGraspNetPlanResult:
        grasps_cam, scores, openings_m, contact_points_cam = self._predictions_to_camera_grasps(predictions)
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
            source_model="economicgrasp",
        )

    def _predictions_to_camera_grasps(
        self,
        predictions: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        rows = np.asarray(predictions, dtype=np.float64).reshape(-1, 17)
        grasps_cam: list[np.ndarray] = []
        scores: list[float] = []
        openings_m: list[float] = []
        contact_points_cam: list[np.ndarray] = []

        for row in rows:
            score = float(row[0])
            width_m = float(row[1])
            height_m = float(row[2])
            depth_m = float(row[3])
            rotation = row[4:13].reshape(3, 3)
            center_xyz = row[13:16].reshape(3)

            approach_dir = _normalize(rotation[:, 0])
            opening_dir = _normalize(rotation[:, 1])
            binormal_dir = _normalize(rotation[:, 2])

            grasp_cam = np.eye(4, dtype=np.float64)
            grasp_cam[:3, 0] = opening_dir
            grasp_cam[:3, 1] = binormal_dir
            grasp_cam[:3, 2] = approach_dir

            grasp_center_cam = center_xyz.copy()
            if not self.config.grasp_center_is_contact_center:
                grasp_center_cam = grasp_center_cam + approach_dir * (0.5 * depth_m)
            if abs(float(self.config.depth_bias_m)) > 1e-9:
                grasp_center_cam = grasp_center_cam + approach_dir * float(self.config.depth_bias_m)

            grasp_cam[:3, 3] = grasp_center_cam
            grasp_cam = _rigidize_transform(grasp_cam)

            contact_point_cam = grasp_center_cam + approach_dir * (0.5 * height_m * 0.0)

            grasps_cam.append(grasp_cam)
            scores.append(score)
            openings_m.append(width_m)
            contact_points_cam.append(contact_point_cam.astype(np.float64))

        if not grasps_cam:
            raise ValueError("EconomicGrasp prediction set is empty")
        return (
            np.stack(grasps_cam, axis=0),
            np.asarray(scores, dtype=np.float64),
            np.asarray(openings_m, dtype=np.float64),
            np.asarray(contact_points_cam, dtype=np.float64),
        )
