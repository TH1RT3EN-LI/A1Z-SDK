"""Shared grasping contracts for robot-executable grasp candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


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


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(to_dict(value), fh, ensure_ascii=True, indent=2)
