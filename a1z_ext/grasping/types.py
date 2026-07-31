"""Shared grasping contracts for robot-executable grasp candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4


REQUIRED_PLAN_SAFETY_CHECKS = (
    "topdown_ok",
    "table_clearance_ok",
    "camera_keepout_ok",
    "joint_margin_ok",
    "continuity_ok",
)
PLAN_SEGMENT_ORDER = {
    "move_to_pregrasp": 0,
    "approach_waypoint": 1,
    "approach": 2,
    "lift": 3,
    "retreat": 4,
}
REQUIRED_PHYSICAL_SEGMENTS = (
    "move_to_pregrasp",
    "approach",
    "lift",
    "retreat",
)


def _uuid() -> str:
    return str(uuid4())


@dataclass(slots=True)
class Pose3D:
    position_xyz: list[float]
    quaternion_xyzw: list[float]


@dataclass(slots=True)
class JointTrajectorySegment:
    segment_type: str
    target_joint_rad: list[float]
    timeout_s: float


@dataclass(slots=True)
class GraspExecutionCandidate:
    candidate_id: str
    object_id: str
    source_model: str
    frame_id: str
    rank: int
    source_group_id: str
    source_index: int
    raw_score: float
    overall_score: float
    grasp_mode: str
    pregrasp_pose: Pose3D
    grasp_pose: Pose3D
    lift_pose: Pose3D
    retreat_pose: Pose3D
    approach_vector_xyz: list[float]
    retreat_vector_xyz: list[float]
    gripper_opening_m: float
    gripper_command_open: float
    gripper_command_close: float
    grasp_depth_m: float = 0.0
    contact_point_xyz: list[float] | None = None
    source_grasp_pose_matrix: list[list[float]] = field(default_factory=list)
    tool_pregrasp_pose_matrix: list[list[float]] = field(default_factory=list)
    tool_grasp_pose_matrix: list[list[float]] = field(default_factory=list)
    tool_lift_pose_matrix: list[list[float]] = field(default_factory=list)
    tool_retreat_pose_matrix: list[list[float]] = field(default_factory=list)
    joint_targets_rad: dict[str, list[float] | None] = field(default_factory=dict)
    ik_summary: dict[str, bool] = field(default_factory=dict)
    safety_summary: dict[str, bool] = field(default_factory=dict)
    failure_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_name: str = "GraspExecutionCandidate"
    schema_version: str = "v1"


@dataclass(slots=True)
class ExecutablePlan:
    plan_id: str
    task_id: str
    selected_grasp_candidate_id: str
    backend: str
    frame_id: str
    joint_trajectory_segments: list[JointTrajectorySegment]
    gripper_commands: dict[str, float]
    ik_summary: dict[str, bool]
    safety_summary: dict[str, bool]
    candidate_rank: int
    execution_policy: dict[str, Any] = field(default_factory=dict)
    source_model: str = "contact_graspnet"
    schema_name: str = "ExecutablePlan"
    schema_version: str = "v1"


@dataclass(slots=True)
class ContactGraspNetPlanResult:
    task_id: str
    object_id: str
    backend: str
    frame_id: str
    transform_source: str
    selected_plan: ExecutablePlan | None
    candidates: list[GraspExecutionCandidate]
    summary: dict[str, Any] = field(default_factory=dict)
    schema_name: str = "ContactGraspNetPlanResult"
    schema_version: str = "v1"


def make_candidate_id() -> str:
    return _uuid()


def make_plan_id() -> str:
    return _uuid()


def normalize_plan_segments(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw_segments = plan.get("joint_trajectory_segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise ValueError("plan must contain non-empty joint_trajectory_segments")

    normalized: list[dict[str, Any]] = []
    previous_order = -1
    approach_count = 0
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            raise ValueError(f"segment {index} must be an object")
        segment_type = str(raw.get("segment_type", ""))
        order = PLAN_SEGMENT_ORDER.get(segment_type)
        if order is None:
            raise ValueError(
                f"segment {index} has unsupported type {segment_type!r}"
            )
        if order < previous_order:
            raise ValueError(f"segment {index} is out of execution order")
        previous_order = order
        approach_count += int(segment_type == "approach")

        raw_target = raw.get("target_joint_rad")
        if not isinstance(raw_target, list) or len(raw_target) != 6:
            raise ValueError(
                f"segment {index} target_joint_rad must contain 6 values"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in raw_target
        ):
            raise ValueError(
                f"segment {index} joint target values must be JSON numbers"
            )
        raw_timeout = raw.get("timeout_s", 0.0)
        if isinstance(raw_timeout, bool) or not isinstance(
            raw_timeout,
            (int, float),
        ):
            raise ValueError(f"segment {index} timeout_s must be a JSON number")
        try:
            target = [float(value) for value in raw_target]
            timeout_s = float(raw_timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"segment {index} contains non-numeric values") from exc
        if not all(math.isfinite(value) for value in target):
            raise ValueError(f"segment {index} joint target must be finite")
        if not math.isfinite(timeout_s) or not 0.0 < timeout_s <= 600.0:
            raise ValueError(
                f"segment {index} timeout_s must be finite and in (0, 600]"
            )
        normalized.append(
            {
                "segment_type": segment_type,
                "target_joint_rad": target,
                "timeout_s": timeout_s,
            }
        )
    if approach_count != 1:
        raise ValueError("plan must contain exactly one approach segment")
    return normalized


def validate_physical_segment_sequence(
    segments: list[dict[str, Any]],
) -> None:
    primary = [
        str(segment["segment_type"])
        for segment in segments
        if segment["segment_type"] != "approach_waypoint"
    ]
    if tuple(primary) != REQUIRED_PHYSICAL_SEGMENTS:
        raise ValueError(
            "physical execution requires move_to_pregrasp, approach, lift, "
            "and retreat exactly once in order"
        )


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(to_dict(value), fh, ensure_ascii=True, indent=2)
