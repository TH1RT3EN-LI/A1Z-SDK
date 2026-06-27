"""Schema objects for the non-grasping open-vocabulary perception pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def _uuid() -> str:
    return str(uuid4())


@dataclass(slots=True)
class TargetObjectSpec:
    text: str
    attributes: list[str] = field(default_factory=list)
    negative_constraints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskSpec:
    task_id: str
    action_type: str
    target_object: TargetObjectSpec
    target_part: str | None = None
    preferred_grasp_mode: str = "top_down"
    preferred_approach_axis: str = "table_normal_negative"
    gripper_opening_hint_m: float | None = None
    position_tolerance_m: float = 0.02
    orientation_tolerance_rad: float = 0.26
    timeout_s: float = 20.0
    safety_profile: str = "tabletop_default"
    confidence: float = 1.0
    schema_name: str = "TaskSpec"
    schema_version: str = "v1"

    @classmethod
    def from_text(cls, instruction: str, *, attributes: list[str] | None = None) -> "TaskSpec":
        attrs = attributes or []
        return cls(
            task_id=_uuid(),
            action_type="pick",
            target_object=TargetObjectSpec(text=instruction, attributes=attrs),
        )


@dataclass(slots=True)
class GroundingCandidate:
    candidate_id: str
    task_id: str
    source_model: str
    text_prompt: str
    bbox_xyxy: list[int] | None
    point_xy: list[int] | None
    score: float
    rank: int
    frame_id: str = "camera_color_frame"
    schema_name: str = "GroundingCandidate"
    schema_version: str = "v1"


@dataclass(slots=True)
class MaskCandidate:
    mask_id: str
    candidate_id: str
    source_model: str
    prompt_type: str
    mask_path: str
    bbox_xyxy: list[int]
    mask_area_px: int
    stability_score: float
    mask_score: float
    depth_valid_ratio: float
    boundary_touch_ratio: float
    rank: int
    schema_name: str = "MaskCandidate"
    schema_version: str = "v1"


@dataclass(slots=True)
class PrincipalAxes:
    axis_1: list[float]
    axis_2: list[float]
    axis_3: list[float]


@dataclass(slots=True)
class Object3DDescriptor:
    object_id: str
    mask_id: str
    frame_id: str
    point_count: int
    centroid_xyz: list[float]
    top_point_xyz: list[float]
    support_plane_height_m: float
    support_plane_normal_xyz: list[float]
    local_surface_normal_xyz: list[float]
    principal_axes: PrincipalAxes
    bbox_extent_xyz_m: list[float]
    workspace_margin_ok: bool
    point_cloud_quality: float
    pose_confidence: float
    schema_name: str = "Object3DDescriptor"
    schema_version: str = "v1"


@dataclass(slots=True)
class PipelineBundle:
    task: TaskSpec
    grounding_candidates: list[GroundingCandidate]
    mask_candidates: list[MaskCandidate]
    object_descriptors: list[Object3DDescriptor]
    schema_name: str = "PipelineBundle"
    schema_version: str = "v1"


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(to_dict(value), fh, ensure_ascii=True, indent=2)

