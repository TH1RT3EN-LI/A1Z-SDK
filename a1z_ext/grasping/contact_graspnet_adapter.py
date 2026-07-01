"""Bridge Contact-GraspNet grasp proposals to A1Z robot-executable plans."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

import numpy as np

from a1z_ext.config import get_default_control_urdf_path
from a1z_ext.grasping.types import (
    ContactGraspNetPlanResult,
    ExecutablePlan,
    GraspExecutionCandidate,
    JointTrajectorySegment,
    Pose3D,
    make_candidate_id,
    make_plan_id,
)


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-9:
        raise ValueError("zero-length vector is not allowed")
    return vector / norm


def _rigidize_transform(transform: np.ndarray) -> np.ndarray:
    rigid = np.asarray(transform, dtype=np.float64).reshape(4, 4).copy()
    rotation = rigid[:3, :3]
    u, _, vh = np.linalg.svd(rotation)
    rotation = u @ vh
    if np.linalg.det(rotation) < 0.0:
        u[:, -1] *= -1.0
        rotation = u @ vh
    rigid[:3, :3] = rotation
    rigid[3, :] = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return rigid


def _invert_transform(transform: np.ndarray) -> np.ndarray:
    transform = np.asarray(transform, dtype=np.float64).reshape(4, 4)
    inv = np.eye(4, dtype=np.float64)
    rotation = transform[:3, :3]
    translation = transform[:3, 3]
    inv[:3, :3] = rotation.T
    inv[:3, 3] = -(rotation.T @ translation)
    return inv


def _transform_point(transform: np.ndarray, point_xyz: Sequence[float]) -> np.ndarray:
    point = np.asarray(point_xyz, dtype=np.float64).reshape(3)
    return (transform @ np.array([point[0], point[1], point[2], 1.0], dtype=np.float64))[:3]


def _matrix_to_quaternion_xyzw(rotation: np.ndarray) -> list[float]:
    matrix = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    trace = float(matrix[0, 0] + matrix[1, 1] + matrix[2, 2])
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (matrix[2, 1] - matrix[1, 2]) / s
        y = (matrix[0, 2] - matrix[2, 0]) / s
        z = (matrix[1, 0] - matrix[0, 1]) / s
    elif matrix[0, 0] > matrix[1, 1] and matrix[0, 0] > matrix[2, 2]:
        s = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
        w = (matrix[2, 1] - matrix[1, 2]) / s
        x = 0.25 * s
        y = (matrix[0, 1] + matrix[1, 0]) / s
        z = (matrix[0, 2] + matrix[2, 0]) / s
    elif matrix[1, 1] > matrix[2, 2]:
        s = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
        w = (matrix[0, 2] - matrix[2, 0]) / s
        x = (matrix[0, 1] + matrix[1, 0]) / s
        y = 0.25 * s
        z = (matrix[1, 2] + matrix[2, 1]) / s
    else:
        s = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
        w = (matrix[1, 0] - matrix[0, 1]) / s
        x = (matrix[0, 2] + matrix[2, 0]) / s
        y = (matrix[1, 2] + matrix[2, 1]) / s
        z = 0.25 * s
    quaternion = np.array([x, y, z, w], dtype=np.float64)
    quaternion /= np.linalg.norm(quaternion)
    return quaternion.astype(float).tolist()


def _matrix_to_pose(transform: np.ndarray) -> Pose3D:
    transform = np.asarray(transform, dtype=np.float64).reshape(4, 4)
    return Pose3D(
        position_xyz=transform[:3, 3].astype(float).tolist(),
        quaternion_xyzw=_matrix_to_quaternion_xyzw(transform[:3, :3]),
    )


def _matrix_to_list(transform: np.ndarray) -> list[list[float]]:
    return np.asarray(transform, dtype=np.float64).reshape(4, 4).astype(float).tolist()


def _as_scalar_array(value: Any, *, expected_len: int, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64).reshape(-1)
    if array.shape[0] != expected_len:
        raise ValueError(f"{name} length mismatch: expected {expected_len}, got {array.shape[0]}")
    return array


def _sort_group_keys(mapping: Mapping[Any, Any]) -> list[Any]:
    keys = list(mapping.keys())
    try:
        return sorted(keys)
    except TypeError:
        return sorted(keys, key=lambda item: str(item))


def _unwrap_npz_object(value: Any) -> Any:
    if isinstance(value, np.ndarray) and value.dtype == object and value.shape == ():
        return value.item()
    return value


def _recover_opening_from_contact(
    *,
    grasp_cam: np.ndarray,
    contact_point_cam: np.ndarray,
    gripper_depth_m: float = 0.1034,
) -> float:
    grasp_cam = np.asarray(grasp_cam, dtype=np.float64).reshape(4, 4)
    contact_point_cam = np.asarray(contact_point_cam, dtype=np.float64).reshape(3)
    base_dir = _normalize(grasp_cam[:3, 0])
    approach_dir = _normalize(grasp_cam[:3, 2])
    origin = grasp_cam[:3, 3]
    width = 2.0 * float(np.dot(contact_point_cam - origin + gripper_depth_m * approach_dir, base_dir))
    return max(0.0, width)


def _joint_margin_score(q: np.ndarray, lower: np.ndarray, upper: np.ndarray, margin_rad: float) -> tuple[bool, float]:
    slack = np.minimum(q - lower, upper - q)
    min_slack = float(np.min(slack))
    margin_ok = bool(np.all(slack >= margin_rad))
    if margin_rad <= 1e-9:
        normalized = 1.0 if margin_ok else 0.0
    else:
        normalized = float(np.clip(min_slack / margin_rad, 0.0, 1.0))
    return margin_ok, normalized


@dataclass(slots=True)
class KeepoutSphere:
    center_xyz: tuple[float, float, float]
    radius_m: float
    label: str = "keepout"


@dataclass(slots=True)
class ContactGraspNetA1ZAdapterConfig:
    urdf_path: str = field(default_factory=get_default_control_urdf_path)
    end_effector_frame: str = "arm_link6"
    frame_id: str = "robot_base_frame"
    transform_source: str = "extrinsic_camera_to_base"
    grasp_mode: str = "top_down_parallel_jaw"
    pregrasp_offset_m: float = 0.08
    lift_offset_m: float = 0.10
    retreat_offset_m: float = 0.04
    table_height_m: float = 0.0
    min_tool_height_above_table_m: float = 0.005
    require_approach_downward: bool = True
    max_approach_deviation_deg: float = 55.0
    table_normal_base: tuple[float, float, float] = (0.0, 0.0, 1.0)
    max_gripper_opening_m: float = 0.096
    pregrasp_opening_margin_m: float = 0.008
    close_gripper_command: float = 0.0
    min_joint_margin_deg: float = 5.0
    max_waypoint_delta_rad: float = 2.5
    use_ik: bool = True
    approach_linear_waypoint_count: int = 0
    ik_dt: float = 0.01
    ik_pos_threshold_m: float = 5e-4
    ik_ori_threshold_rad: float = 5e-3
    ik_damping: float = 1e-6
    ik_max_iters: int = 800
    keepout_spheres: list[KeepoutSphere] = field(default_factory=list)
    ee_grasp_origin_xyz_m: tuple[float, float, float] = (0.04, 0.0, 0.0)
    ee_opening_axis_xyz: tuple[float, float, float] = (0.0, 0.0, 1.0)
    ee_approach_axis_xyz: tuple[float, float, float] = (0.0, -1.0, 0.0)
    segment_timeouts_s: dict[str, float] = field(
        default_factory=lambda: {
            "move_to_pregrasp": 5.0,
            "approach": 3.0,
            "lift": 4.0,
            "retreat": 3.0,
        }
    )

    def ee_to_grasp_transform(self) -> np.ndarray:
        opening = _normalize(np.asarray(self.ee_opening_axis_xyz, dtype=np.float64))
        approach = np.asarray(self.ee_approach_axis_xyz, dtype=np.float64)
        approach = approach - float(np.dot(approach, opening)) * opening
        approach = _normalize(approach)
        binormal = _normalize(np.cross(approach, opening))
        approach = _normalize(np.cross(opening, binormal))
        transform = np.eye(4, dtype=np.float64)
        transform[:3, 0] = opening
        transform[:3, 1] = binormal
        transform[:3, 2] = approach
        transform[:3, 3] = np.asarray(self.ee_grasp_origin_xyz_m, dtype=np.float64)
        return transform

    @property
    def min_joint_margin_rad(self) -> float:
        return math.radians(float(self.min_joint_margin_deg))

    @property
    def max_approach_deviation_rad(self) -> float:
        return math.radians(float(self.max_approach_deviation_deg))


@dataclass(slots=True)
class _FlatPrediction:
    group_id: str
    source_index: int
    grasp_cam: np.ndarray
    score: float
    gripper_opening_m: float
    contact_point_cam: np.ndarray | None


class ContactGraspNetA1ZAdapter:
    """Convert Contact-GraspNet proposals into A1Z candidates and plans."""

    def __init__(self, config: ContactGraspNetA1ZAdapterConfig | None = None, *, kinematics: Any | None = None) -> None:
        self.config = config or ContactGraspNetA1ZAdapterConfig()
        self._kinematics = kinematics
        if self.config.use_ik and self._kinematics is None:
            from a1z.robots.kinematics import Kinematics

            self._kinematics = Kinematics(
                self.config.urdf_path,
                end_effector_frame=self.config.end_effector_frame,
            )
        self._ee_to_grasp = self.config.ee_to_grasp_transform()
        self._grasp_to_ee = _invert_transform(self._ee_to_grasp)

    def plan(
        self,
        *,
        pred_grasps_cam: Any,
        scores: Any,
        gripper_openings_m: Any,
        extrinsic_camera_to_base: np.ndarray,
        current_q: Sequence[float],
        task_id: str,
        object_id: str,
        backend: str = "unknown",
        contact_points_cam: Any | None = None,
        source_model: str = "contact_graspnet",
    ) -> ContactGraspNetPlanResult:
        current_q_array = np.asarray(current_q, dtype=np.float64).reshape(-1)
        if current_q_array.shape[0] != 6:
            raise ValueError(f"current_q must contain 6 joints, got shape {current_q_array.shape}")
        camera_to_base = _rigidize_transform(np.asarray(extrinsic_camera_to_base, dtype=np.float64).reshape(4, 4))
        flat_predictions = self._flatten_predictions(
            pred_grasps_cam=pred_grasps_cam,
            scores=scores,
            gripper_openings_m=gripper_openings_m,
            contact_points_cam=contact_points_cam,
        )
        candidates = self._build_candidates(
            flat_predictions=flat_predictions,
            camera_to_base=camera_to_base,
            current_q=current_q_array,
            object_id=object_id,
            source_model=source_model,
        )
        selected_plan = self._select_best_plan(
            task_id=task_id,
            backend=backend,
            candidates=candidates,
            source_model=source_model,
        )
        executable_count = sum(
            1
            for candidate in candidates
            if all(candidate.ik_summary.get(stage, False) for stage in ("pregrasp", "grasp", "lift", "retreat"))
            and not candidate.failure_reasons
        )
        summary = {
            "candidate_count": len(candidates),
            "executable_count": executable_count,
            "selected_candidate_id": selected_plan.selected_grasp_candidate_id if selected_plan is not None else None,
            "ee_to_grasp_transform": _matrix_to_list(self._ee_to_grasp),
            "source_model": source_model,
        }
        return ContactGraspNetPlanResult(
            task_id=task_id,
            object_id=object_id,
            backend=backend,
            frame_id=self.config.frame_id,
            transform_source=self.config.transform_source,
            selected_plan=selected_plan,
            candidates=candidates,
            summary=summary,
        )

    def _flatten_predictions(
        self,
        *,
        pred_grasps_cam: Any,
        scores: Any,
        gripper_openings_m: Any,
        contact_points_cam: Any | None,
    ) -> list[_FlatPrediction]:
        pred_grasps_cam = _unwrap_npz_object(pred_grasps_cam)
        scores = _unwrap_npz_object(scores)
        gripper_openings_m = _unwrap_npz_object(gripper_openings_m)
        contact_points_cam = _unwrap_npz_object(contact_points_cam)

        if isinstance(pred_grasps_cam, Mapping):
            if not isinstance(scores, Mapping):
                raise ValueError("scores must be a mapping when pred_grasps_cam is a mapping")
            if gripper_openings_m is not None and not isinstance(gripper_openings_m, Mapping):
                raise ValueError("gripper_openings_m must be a mapping when pred_grasps_cam is a mapping")
            contact_map = contact_points_cam if isinstance(contact_points_cam, Mapping) else {}
            flattened: list[_FlatPrediction] = []
            for group_key in _sort_group_keys(pred_grasps_cam):
                grasp_group = np.asarray(pred_grasps_cam[group_key], dtype=np.float64).reshape(-1, 4, 4)
                score_group = _as_scalar_array(scores[group_key], expected_len=len(grasp_group), name=f"scores[{group_key!r}]")
                contact_group_raw = contact_map.get(group_key)
                contact_group = None
                if contact_group_raw is not None:
                    contact_group = np.asarray(contact_group_raw, dtype=np.float64).reshape(-1, 3)
                    if contact_group.shape[0] != len(grasp_group):
                        raise ValueError(
                            f"contact_points_cam[{group_key!r}] length mismatch: "
                            f"expected {len(grasp_group)}, got {contact_group.shape[0]}"
                        )
                if gripper_openings_m is not None and group_key in gripper_openings_m:
                    opening_group = _as_scalar_array(
                        gripper_openings_m[group_key],
                        expected_len=len(grasp_group),
                        name=f"gripper_openings_m[{group_key!r}]",
                    )
                elif contact_group is not None:
                    opening_group = np.asarray(
                        [
                            _recover_opening_from_contact(
                                grasp_cam=grasp_group[index],
                                contact_point_cam=contact_group[index],
                            )
                            for index in range(len(grasp_group))
                        ],
                        dtype=np.float64,
                    )
                else:
                    raise ValueError(
                        "gripper_openings_m is missing and cannot be recovered without contact_points_cam"
                    )
                for index in range(len(grasp_group)):
                    flattened.append(
                        _FlatPrediction(
                            group_id=str(group_key),
                            source_index=index,
                            grasp_cam=_rigidize_transform(grasp_group[index]),
                            score=float(score_group[index]),
                            gripper_opening_m=float(opening_group[index]),
                            contact_point_cam=None if contact_group is None else contact_group[index].copy(),
                        )
                    )
            return flattened

        grasp_array = np.asarray(pred_grasps_cam, dtype=np.float64).reshape(-1, 4, 4)
        score_array = _as_scalar_array(scores, expected_len=len(grasp_array), name="scores")
        contact_array = None
        if contact_points_cam is not None:
            contact_array = np.asarray(contact_points_cam, dtype=np.float64).reshape(-1, 3)
            if contact_array.shape[0] != len(grasp_array):
                raise ValueError(
                    f"contact_points_cam length mismatch: expected {len(grasp_array)}, got {contact_array.shape[0]}"
                )
        if gripper_openings_m is not None:
            opening_array = _as_scalar_array(gripper_openings_m, expected_len=len(grasp_array), name="gripper_openings_m")
        elif contact_array is not None:
            opening_array = np.asarray(
                [
                    _recover_opening_from_contact(
                        grasp_cam=grasp_array[index],
                        contact_point_cam=contact_array[index],
                    )
                    for index in range(len(grasp_array))
                ],
                dtype=np.float64,
            )
        else:
            raise ValueError("gripper_openings_m is missing and cannot be recovered without contact_points_cam")
        return [
            _FlatPrediction(
                group_id="-1",
                source_index=index,
                grasp_cam=_rigidize_transform(grasp_array[index]),
                score=float(score_array[index]),
                gripper_opening_m=float(opening_array[index]),
                contact_point_cam=None if contact_array is None else contact_array[index].copy(),
            )
            for index in range(len(grasp_array))
        ]

    def _build_candidates(
        self,
        *,
        flat_predictions: list[_FlatPrediction],
        camera_to_base: np.ndarray,
        current_q: np.ndarray,
        object_id: str,
        source_model: str,
    ) -> list[GraspExecutionCandidate]:
        if not flat_predictions:
            return []

        sorted_predictions = sorted(flat_predictions, key=lambda item: item.score, reverse=True)
        table_normal = _normalize(np.asarray(self.config.table_normal_base, dtype=np.float64))
        downward_alignment_threshold = math.cos(self.config.max_approach_deviation_rad)
        lower = upper = None
        if self._kinematics is not None:
            lower = np.asarray(self._kinematics._model.lowerPositionLimit, dtype=np.float64).reshape(-1)
            upper = np.asarray(self._kinematics._model.upperPositionLimit, dtype=np.float64).reshape(-1)

        candidates: list[GraspExecutionCandidate] = []
        for rank, prediction in enumerate(sorted_predictions):
            grasp_base = _rigidize_transform(camera_to_base @ prediction.grasp_cam)
            approach = _normalize(grasp_base[:3, 2])
            retreat = -approach
            approach_alignment = float(np.clip(-np.dot(approach, table_normal), -1.0, 1.0))
            topdown_ok = (not self.config.require_approach_downward) or (approach_alignment >= downward_alignment_threshold)

            tool_grasp = _rigidize_transform(grasp_base @ self._grasp_to_ee)
            tool_pregrasp = tool_grasp.copy()
            tool_pregrasp[:3, 3] += retreat * float(self.config.pregrasp_offset_m)
            tool_lift = tool_grasp.copy()
            tool_lift[:3, 3] += table_normal * float(self.config.lift_offset_m)
            tool_retreat = tool_lift.copy()
            tool_retreat[:3, 3] += retreat * float(self.config.retreat_offset_m)
            poses = {
                "pregrasp": _rigidize_transform(tool_pregrasp),
                "grasp": _rigidize_transform(tool_grasp),
                "lift": _rigidize_transform(tool_lift),
                "retreat": _rigidize_transform(tool_retreat),
            }

            opening_m = float(np.clip(prediction.gripper_opening_m, 0.0, self.config.max_gripper_opening_m))
            open_command = float(
                np.clip(
                    (opening_m + self.config.pregrasp_opening_margin_m) / self.config.max_gripper_opening_m,
                    0.0,
                    1.0,
                )
            )
            close_command = float(np.clip(self.config.close_gripper_command, 0.0, 1.0))
            table_clearance_ok = all(
                float(pose[2, 3]) >= (self.config.table_height_m + self.config.min_tool_height_above_table_m)
                for pose in poses.values()
            )
            camera_keepout_ok = self._camera_keepout_ok(poses)

            ik_summary = {stage: False for stage in ("pregrasp", "grasp", "lift", "retreat")}
            joint_targets: dict[str, list[float] | None] = {stage: None for stage in ("pregrasp", "grasp", "lift", "retreat")}
            joint_margin_ok = False
            continuity_ok = False
            min_margin_score = 0.0

            if self._kinematics is not None:
                solutions = self._solve_waypoint_sequence(
                    current_q=current_q,
                    poses=poses,
                    lower=lower,
                    upper=upper,
                )
                ik_summary.update({stage: solved for stage, (solved, _) in solutions.items()})
                joint_targets = {
                    stage: None if q is None else q.astype(float).tolist()
                    for stage, (_, q) in solutions.items()
                }
                margin_flags: list[bool] = []
                margin_scores: list[float] = []
                for stage in ("pregrasp", "grasp", "lift", "retreat"):
                    solved, q = solutions[stage]
                    if not solved or q is None:
                        continue
                    margin_ok_stage, margin_score = _joint_margin_score(
                        q=q,
                        lower=lower,
                        upper=upper,
                        margin_rad=self.config.min_joint_margin_rad,
                    )
                    margin_flags.append(margin_ok_stage)
                    margin_scores.append(margin_score)
                joint_margin_ok = bool(margin_flags) and all(margin_flags)
                min_margin_score = min(margin_scores) if margin_scores else 0.0
                continuity_ok = self._continuity_ok(joint_targets)

            safety_summary = {
                "topdown_ok": bool(topdown_ok),
                "table_clearance_ok": bool(table_clearance_ok),
                "camera_keepout_ok": bool(camera_keepout_ok),
                "joint_margin_ok": bool(joint_margin_ok),
                "continuity_ok": bool(continuity_ok),
            }
            failure_reasons = self._failure_reasons(
                ik_summary=ik_summary,
                safety_summary=safety_summary,
            )
            overall_score = float(prediction.score * (0.75 + 0.25 * max(0.0, approach_alignment)) * (0.5 + 0.5 * min_margin_score))
            contact_point_xyz = (
                None
                if prediction.contact_point_cam is None
                else _transform_point(camera_to_base, prediction.contact_point_cam).astype(float).tolist()
            )

            candidates.append(
                GraspExecutionCandidate(
                    candidate_id=make_candidate_id(),
                    object_id=object_id,
                    source_model=source_model,
                    frame_id=self.config.frame_id,
                    rank=rank,
                    source_group_id=prediction.group_id,
                    source_index=prediction.source_index,
                    raw_score=float(prediction.score),
                    overall_score=overall_score,
                    grasp_mode=self.config.grasp_mode,
                    pregrasp_pose=_matrix_to_pose(poses["pregrasp"]),
                    grasp_pose=_matrix_to_pose(poses["grasp"]),
                    lift_pose=_matrix_to_pose(poses["lift"]),
                    retreat_pose=_matrix_to_pose(poses["retreat"]),
                    approach_vector_xyz=approach.astype(float).tolist(),
                    retreat_vector_xyz=retreat.astype(float).tolist(),
                    gripper_opening_m=opening_m,
                    gripper_command_open=open_command,
                    gripper_command_close=close_command,
                    contact_point_xyz=contact_point_xyz,
                    source_grasp_pose_matrix=_matrix_to_list(grasp_base),
                    tool_pregrasp_pose_matrix=_matrix_to_list(poses["pregrasp"]),
                    tool_grasp_pose_matrix=_matrix_to_list(poses["grasp"]),
                    tool_lift_pose_matrix=_matrix_to_list(poses["lift"]),
                    tool_retreat_pose_matrix=_matrix_to_list(poses["retreat"]),
                    joint_targets_rad=joint_targets,
                    ik_summary=ik_summary,
                    safety_summary=safety_summary,
                    failure_reasons=failure_reasons,
                    metadata={
                        "transform_source": self.config.transform_source,
                        "approach_down_alignment": approach_alignment,
                        "min_joint_margin_score": min_margin_score,
                    },
                )
            )
        return candidates

    def _solve_waypoint_sequence(
        self,
        *,
        current_q: np.ndarray,
        poses: Mapping[str, np.ndarray],
        lower: np.ndarray,
        upper: np.ndarray,
    ) -> dict[str, tuple[bool, np.ndarray | None]]:
        assert self._kinematics is not None
        solutions: dict[str, tuple[bool, np.ndarray | None]] = {}
        seed = current_q.copy()
        for stage in ("pregrasp", "grasp", "lift", "retreat"):
            converged, q = self._kinematics.ik(
                poses[stage],
                init_q=seed,
                frame_name=self.config.end_effector_frame,
                dt=float(self.config.ik_dt),
                pos_threshold=float(self.config.ik_pos_threshold_m),
                ori_threshold=float(self.config.ik_ori_threshold_rad),
                damping=float(self.config.ik_damping),
                max_iters=int(self.config.ik_max_iters),
            )
            if not converged:
                solutions[stage] = (False, None)
                continue
            q = np.asarray(q, dtype=np.float64).reshape(-1)
            if np.any(q < lower - 1e-6) or np.any(q > upper + 1e-6):
                solutions[stage] = (False, None)
                continue
            q = np.clip(q, lower, upper)
            solutions[stage] = (True, q)
            seed = q
        return solutions

    def _continuity_ok(self, joint_targets: Mapping[str, list[float] | None]) -> bool:
        previous = None
        for stage in ("pregrasp", "grasp", "lift", "retreat"):
            target = joint_targets.get(stage)
            if target is None:
                return False
            q = np.asarray(target, dtype=np.float64).reshape(-1)
            if previous is not None:
                if float(np.max(np.abs(q - previous))) > self.config.max_waypoint_delta_rad:
                    return False
            previous = q
        return True

    def _camera_keepout_ok(self, poses: Mapping[str, np.ndarray]) -> bool:
        if not self.config.keepout_spheres:
            return True
        for pose in poses.values():
            position = pose[:3, 3]
            for sphere in self.config.keepout_spheres:
                center = np.asarray(sphere.center_xyz, dtype=np.float64)
                if float(np.linalg.norm(position - center)) < float(sphere.radius_m):
                    return False
        return True

    def _failure_reasons(
        self,
        *,
        ik_summary: Mapping[str, bool],
        safety_summary: Mapping[str, bool],
    ) -> list[str]:
        reasons: list[str] = []
        if not safety_summary.get("topdown_ok", True):
            reasons.append("approach_not_downward_enough")
        if not safety_summary.get("table_clearance_ok", True):
            reasons.append("table_clearance_violation")
        if not safety_summary.get("camera_keepout_ok", True):
            reasons.append("camera_keepout_violation")
        if not safety_summary.get("joint_margin_ok", True):
            reasons.append("joint_margin_violation")
        if not safety_summary.get("continuity_ok", True):
            reasons.append("joint_discontinuity")
        for stage in ("pregrasp", "grasp", "lift", "retreat"):
            if not ik_summary.get(stage, False):
                reasons.append(f"{stage}_ik_unsolved")
        return reasons

    def _select_best_plan(
        self,
        *,
        task_id: str,
        backend: str,
        candidates: list[GraspExecutionCandidate],
        source_model: str,
    ) -> ExecutablePlan | None:
        if not candidates:
            return None
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                len(candidate.failure_reasons) == 0,
                candidate.overall_score,
                candidate.raw_score,
            ),
            reverse=True,
        )
        for candidate in ordered:
            if candidate.failure_reasons:
                continue
            approach_segments = self._build_approach_segments(candidate)
            if approach_segments is None:
                continue
            segments = [
                JointTrajectorySegment(
                    segment_type="move_to_pregrasp",
                    target_joint_rad=candidate.joint_targets_rad["pregrasp"] or [],
                    timeout_s=float(self.config.segment_timeouts_s["move_to_pregrasp"]),
                ),
                *approach_segments,
                JointTrajectorySegment(
                    segment_type="lift",
                    target_joint_rad=candidate.joint_targets_rad["lift"] or [],
                    timeout_s=float(self.config.segment_timeouts_s["lift"]),
                ),
                JointTrajectorySegment(
                    segment_type="retreat",
                    target_joint_rad=candidate.joint_targets_rad["retreat"] or [],
                    timeout_s=float(self.config.segment_timeouts_s["retreat"]),
                ),
            ]
            return ExecutablePlan(
                plan_id=make_plan_id(),
                task_id=task_id,
                selected_grasp_candidate_id=candidate.candidate_id,
                backend=backend,
                frame_id=self.config.frame_id,
                joint_trajectory_segments=segments,
                gripper_commands={
                    "open_before_grasp": float(candidate.gripper_command_open),
                    "close_after_approach": float(candidate.gripper_command_close),
                },
                ik_summary=dict(candidate.ik_summary),
                safety_summary=dict(candidate.safety_summary),
                candidate_rank=int(candidate.rank),
                source_model=source_model,
                )
        return None

    def _build_approach_segments(self, candidate: GraspExecutionCandidate) -> list[JointTrajectorySegment] | None:
        waypoint_count = max(0, int(self.config.approach_linear_waypoint_count))
        final_grasp = candidate.joint_targets_rad.get("grasp") or []
        if waypoint_count <= 0 or self._kinematics is None:
            return [
                JointTrajectorySegment(
                    segment_type="approach",
                    target_joint_rad=final_grasp,
                    timeout_s=float(self.config.segment_timeouts_s["approach"]),
                )
            ]

        pregrasp_q_raw = candidate.joint_targets_rad.get("pregrasp")
        if pregrasp_q_raw is None:
            return None
        pregrasp_pose = np.asarray(candidate.tool_pregrasp_pose_matrix, dtype=np.float64).reshape(4, 4)
        grasp_pose = np.asarray(candidate.tool_grasp_pose_matrix, dtype=np.float64).reshape(4, 4)
        pregrasp_q = np.asarray(pregrasp_q_raw, dtype=np.float64).reshape(-1)
        grasp_q = np.asarray(final_grasp, dtype=np.float64).reshape(-1)
        lower = np.asarray(self._kinematics._model.lowerPositionLimit, dtype=np.float64).reshape(-1)
        upper = np.asarray(self._kinematics._model.upperPositionLimit, dtype=np.float64).reshape(-1)

        segments: list[JointTrajectorySegment] = []
        seed = pregrasp_q.copy()
        timeout_total = float(self.config.segment_timeouts_s["approach"])
        timeout_each = timeout_total / float(waypoint_count + 1)
        prev_q = pregrasp_q

        for waypoint_idx in range(waypoint_count):
            alpha = float(waypoint_idx + 1) / float(waypoint_count + 1)
            pose = grasp_pose.copy()
            pose[:3, 3] = (1.0 - alpha) * pregrasp_pose[:3, 3] + alpha * grasp_pose[:3, 3]
            converged, q = self._kinematics.ik(
                pose,
                init_q=seed,
                frame_name=self.config.end_effector_frame,
                dt=float(self.config.ik_dt),
                pos_threshold=float(self.config.ik_pos_threshold_m),
                ori_threshold=float(self.config.ik_ori_threshold_rad),
                damping=float(self.config.ik_damping),
                max_iters=int(self.config.ik_max_iters),
            )
            if not converged or q is None:
                return None
            q = np.asarray(q, dtype=np.float64).reshape(-1)
            if np.any(q < lower - 1e-6) or np.any(q > upper + 1e-6):
                return None
            q = np.clip(q, lower, upper)
            if float(np.max(np.abs(q - prev_q))) > self.config.max_waypoint_delta_rad:
                return None
            segments.append(
                JointTrajectorySegment(
                    segment_type="approach_waypoint",
                    target_joint_rad=q.astype(float).tolist(),
                    timeout_s=timeout_each,
                )
            )
            seed = q
            prev_q = q

        if grasp_q.shape != prev_q.shape:
            return None
        if float(np.max(np.abs(grasp_q - prev_q))) > self.config.max_waypoint_delta_rad:
            return None
        segments.append(
            JointTrajectorySegment(
                segment_type="approach",
                target_joint_rad=grasp_q.astype(float).tolist(),
                timeout_s=timeout_each,
            )
        )
        return segments
