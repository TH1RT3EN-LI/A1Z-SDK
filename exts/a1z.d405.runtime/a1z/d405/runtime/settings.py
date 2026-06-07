from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_vec3(name: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = os.environ.get(name)
    if not raw:
        return default
    parts = [p.strip() for p in raw.replace(",", " ").split()]
    if len(parts) != 3:
        raise ValueError(f"{name} must contain exactly 3 numbers, got: {raw}")
    return float(parts[0]), float(parts[1]), float(parts[2])


def _env_optional_vec3(name: str) -> tuple[float, float, float] | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    return _env_vec3(name, (0.0, 0.0, 0.0))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _default_d405_mesh_path() -> str:
    return str(_repo_root() / "assets" / "realsense_d405" / "d405.stl")


def _default_status_path() -> str:
    return str(_repo_root() / "logs" / "d405-wrist-camera.status")


@dataclass(frozen=True)
class D405AssetSettings:
    enabled: bool = True
    parent_prim: str = "/World"
    fallback_parent_prim: str = "/World"
    mount_name: str = "D405_Wrist"
    mesh_path: str = _default_d405_mesh_path()
    mount_offset: tuple[float, float, float] = (0.135, 0.0, 0.075)
    target_offset: tuple[float, float, float] = (0.085, 0.0, -0.020)
    mount_rpy_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    camera_optical_rpy_deg: tuple[float, float, float] = (0.0, 90.0, 0.0)
    center_on_axis: bool = True
    center_mesh_y: bool = True
    camera_prims_enabled: bool = True
    fk_frame: str = "arm_link6"
    target_world_translate: tuple[float, float, float] | None = None
    target_world_rotate_deg: tuple[float, float, float] | None = None
    target_world_scale: tuple[float, float, float] = (0.001, 0.001, 0.001)
    target_world_pose_applies_to: str = "body"
    status_path: str = _default_status_path()

    @classmethod
    def from_env(cls) -> "D405AssetSettings":
        return cls(
            enabled=_env_flag("A1Z_D405_ENABLED", True),
            parent_prim=os.environ.get("A1Z_D405_PARENT_PRIM", "/World"),
            fallback_parent_prim=os.environ.get("A1Z_D405_FALLBACK_PARENT_PRIM", "/World"),
            mount_name=os.environ.get("A1Z_D405_MOUNT_NAME", "D405_Wrist"),
            mesh_path=os.environ.get("A1Z_D405_MESH_PATH", _default_d405_mesh_path()),
            mount_offset=_env_vec3("A1Z_D405_MOUNT_OFFSET", (0.135, 0.0, 0.075)),
            target_offset=_env_vec3("A1Z_D405_TARGET_OFFSET", (0.085, 0.0, -0.020)),
            mount_rpy_deg=_env_vec3("A1Z_D405_MOUNT_RPY_DEG", (0.0, 0.0, 0.0)),
            camera_optical_rpy_deg=_env_vec3("A1Z_D405_CAMERA_OPTICAL_RPY_DEG", (0.0, 90.0, 0.0)),
            center_on_axis=_env_flag("A1Z_D405_CENTER_ON_AXIS", True),
            center_mesh_y=_env_flag("A1Z_D405_CENTER_MESH_Y", True),
            camera_prims_enabled=_env_flag("A1Z_D405_CAMERA_PRIMS_ENABLED", True),
            fk_frame=os.environ.get("A1Z_D405_FK_FRAME", "arm_link6"),
            target_world_translate=_env_optional_vec3("A1Z_D405_TARGET_WORLD_TRANSLATE"),
            target_world_rotate_deg=_env_optional_vec3("A1Z_D405_TARGET_WORLD_ROTATE_DEG"),
            target_world_scale=_env_vec3("A1Z_D405_TARGET_WORLD_SCALE", (0.001, 0.001, 0.001)),
            target_world_pose_applies_to=os.environ.get("A1Z_D405_TARGET_WORLD_POSE_APPLIES_TO", "body").strip(),
            status_path=os.environ.get("A1Z_D405_STATUS_PATH", _default_status_path()),
        )


@dataclass(frozen=True)
class D405Ros2Settings:
    enabled: bool = True
    graph_path: str = "/ActionGraph/D405Ros2Publishers"
    namespace: str = "/a1z/d405"
    color_frame_id: str = "d405_color_optical_frame"
    depth_frame_id: str = "d405_depth_optical_frame"
    width: int = 1280
    height: int = 720
    frame_skip_count: int = 1

    @classmethod
    def from_env(cls) -> "D405Ros2Settings":
        return cls(
            enabled=_env_flag("A1Z_D405_ROS2_ENABLED", True),
            graph_path=os.environ.get("A1Z_D405_ROS2_GRAPH_PATH", "/ActionGraph/D405Ros2Publishers"),
            namespace=os.environ.get("A1Z_D405_ROS2_NAMESPACE", "/a1z/d405").strip(),
            color_frame_id=os.environ.get("A1Z_D405_COLOR_FRAME_ID", "d405_color_optical_frame"),
            depth_frame_id=os.environ.get("A1Z_D405_DEPTH_FRAME_ID", "d405_depth_optical_frame"),
            width=_env_int("A1Z_D405_WIDTH", 1280),
            height=_env_int("A1Z_D405_HEIGHT", 720),
            frame_skip_count=_env_int("A1Z_D405_FRAME_SKIP_COUNT", 1),
        )
