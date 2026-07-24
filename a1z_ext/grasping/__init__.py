"""Reusable grasping adapters and contracts for A1Z."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .types import (
    ContactGraspNetPlanResult,
    ExecutablePlan,
    GraspExecutionCandidate,
    JointTrajectorySegment,
    Pose3D,
    to_dict,
    write_json,
)
from .interfaces import ParallelJawActuator, PhysicalContactObserver
from .contact_reducer import reduce_contact_impulses
from .parallel_jaw import ParallelJawMapping, rate_limit_parallel_jaw_setpoint
from .physical_fsm import PhysicalGraspFSM
from .physical_types import (
    ContactSnapshot,
    DriveProfile,
    GraspCommand,
    GraspPhase,
    GripperSnapshot,
    PhysicalGraspConfig,
    PhysicalGraspStatus,
)


_LAZY_EXPORT_MODULES = {
    "ContactGraspNetA1ZAdapter": "contact_graspnet_adapter",
    "ContactGraspNetA1ZAdapterConfig": "contact_graspnet_adapter",
    "KeepoutSphere": "contact_graspnet_adapter",
    "ANYGRASP_ACTIVE_BINDING_LABEL": "anygrasp_frames",
    "ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL": "anygrasp_frames",
    "ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL": "anygrasp_frames",
    "ANYGRASP_PLANNER_FRAME_CONVENTION": "anygrasp_frames",
    "ANYGRASP_RAW_FRAME_CONVENTION": "anygrasp_frames",
    "ANYGRASP_SUPPORTED_BINDINGS": "anygrasp_frames",
    "ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS": "anygrasp_frames",
    "anygrasp_camera_correction_transform": "anygrasp_frames",
    "anygrasp_extrinsic_correction_transform": "anygrasp_frames",
    "anygrasp_item_to_grasp_pose": "anygrasp_frames",
    "anygrasp_item_to_grasp_pose_with_binding_label": "anygrasp_frames",
    "anygrasp_rotation_to_planner_rotation": "anygrasp_frames",
    "anygrasp_rotation_to_planner_rotation_with_binding_label": "anygrasp_frames",
    "GRConvNetA1ZAdapter": "grconvnet_adapter",
    "GRConvNetA1ZAdapterConfig": "grconvnet_adapter",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "ContactGraspNetA1ZAdapter",
    "ContactGraspNetA1ZAdapterConfig",
    "ANYGRASP_ACTIVE_BINDING_LABEL",
    "ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL",
    "ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL",
    "ANYGRASP_PLANNER_FRAME_CONVENTION",
    "ANYGRASP_RAW_FRAME_CONVENTION",
    "ANYGRASP_SUPPORTED_BINDINGS",
    "ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS",
    "GRConvNetA1ZAdapter",
    "GRConvNetA1ZAdapterConfig",
    "KeepoutSphere",
    "anygrasp_camera_correction_transform",
    "anygrasp_extrinsic_correction_transform",
    "anygrasp_item_to_grasp_pose",
    "anygrasp_item_to_grasp_pose_with_binding_label",
    "anygrasp_rotation_to_planner_rotation",
    "anygrasp_rotation_to_planner_rotation_with_binding_label",
    "ContactGraspNetPlanResult",
    "ExecutablePlan",
    "GraspExecutionCandidate",
    "JointTrajectorySegment",
    "Pose3D",
    "to_dict",
    "write_json",
    "ContactSnapshot",
    "DriveProfile",
    "GraspCommand",
    "GraspPhase",
    "GripperSnapshot",
    "PhysicalGraspConfig",
    "PhysicalGraspFSM",
    "PhysicalGraspStatus",
    "ParallelJawActuator",
    "PhysicalContactObserver",
    "ParallelJawMapping",
    "rate_limit_parallel_jaw_setpoint",
    "reduce_contact_impulses",
]
