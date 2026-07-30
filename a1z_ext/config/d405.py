from __future__ import annotations

from functools import lru_cache
import json
import math
import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    env_root = os.environ.get("A1Z_REPO_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    resolved = Path(__file__).resolve()
    for parent in resolved.parents:
        if (parent / "config" / "d405.json").is_file():
            return parent
    return resolved.parents[2]


REPO_ROOT = _repo_root()
D405_CONFIG_PATH = REPO_ROOT / "config" / "d405.json"


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def _vector(payload: dict[str, Any], key: str, count: int = 3) -> tuple[float, ...]:
    values = payload.get(key)
    if not isinstance(values, list) or len(values) != count:
        raise ValueError(f"{key} must contain exactly {count} numbers")
    return tuple(_number(value, f"{key}[{index}]") for index, value in enumerate(values))


def _hole_pair(payload: dict[str, Any], key: str) -> tuple[tuple[float, ...], ...]:
    values = payload.get(key)
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError(f"{key} must contain exactly two 3D points")
    points = []
    for index, point in enumerate(values):
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError(f"{key}[{index}] must contain exactly three numbers")
        points.append(
            tuple(_number(value, f"{key}[{index}][{axis}]") for axis, value in enumerate(point))
        )
    return tuple(points)


def _validate_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("d405.json must contain a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError("d405.json schema_version must be 1")
    if not isinstance(payload.get("enabled"), bool):
        raise ValueError("d405.json enabled must be a boolean")
    parent_link = payload.get("parent_link")
    if not isinstance(parent_link, str) or not parent_link.strip():
        raise ValueError("d405.json parent_link must be a non-empty string")

    mesh_scale = _vector(payload, "mesh_scale")
    if any(value <= 0.0 for value in mesh_scale):
        raise ValueError("d405.json mesh_scale values must be positive")
    if _number(payload.get("mass_kg"), "mass_kg") <= 0.0:
        raise ValueError("d405.json mass_kg must be positive")
    _vector(payload, "mount_offset_xyz_m")
    _vector(payload, "mount_rpy_deg")
    _vector(payload, "body_visual_rpy_deg")

    rear = payload.get("rear_mount_datum")
    if not isinstance(rear, dict):
        raise ValueError("d405.json rear_mount_datum must be an object")
    _hole_pair(rear, "hole_centers_mesh_mm")
    _vector(rear, "outward_normal_mesh")
    if _number(rear.get("hole_diameter_mm"), "hole_diameter_mm") <= 0.0:
        raise ValueError("d405.json hole_diameter_mm must be positive")
    if _number(rear.get("hole_depth_mm"), "hole_depth_mm") <= 0.0:
        raise ValueError("d405.json hole_depth_mm must be positive")

    target = payload.get("target_bracket_datum")
    if not isinstance(target, dict):
        raise ValueError("d405.json target_bracket_datum must be an object")
    _hole_pair(target, "hole_centers_parent_m")
    _vector(target, "downward_outward_normal_parent")

    stage = payload.get("stage_frames")
    if not isinstance(stage, dict):
        raise ValueError("d405.json stage_frames must be an object")
    _vector(stage, "rectify_rpy_deg")
    _vector(stage, "rectified_to_optical_offset_xyz_m")
    _vector(stage, "rectified_to_optical_rpy_deg")

    compute = payload.get("compute_frames")
    if not isinstance(compute, dict):
        raise ValueError("d405.json compute_frames must be an object")
    _vector(compute, "install_rpy_deg")
    _vector(compute, "rectify_rpy_deg")
    _vector(compute, "rectified_to_optical_offset_xyz_m")
    return payload


@lru_cache(maxsize=1)
def load_d405_config() -> dict[str, Any]:
    if not D405_CONFIG_PATH.is_file():
        raise FileNotFoundError(f"D405 config not found: {D405_CONFIG_PATH}")
    payload = json.loads(D405_CONFIG_PATH.read_text(encoding="utf-8"))
    return _validate_config(payload)
