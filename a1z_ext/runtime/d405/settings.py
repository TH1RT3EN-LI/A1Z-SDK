from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from a1z_ext.config.d405 import load_d405_config


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_d405_mesh_path() -> str:
    return str(_repo_root() / "assets" / "realsense_d405" / "d405.stl")


def _default_status_path() -> str:
    return str(_repo_root() / "runtime" / "logs" / "d405-link-camera.status")


_D405_CONFIG = load_d405_config()
_STAGE_FRAMES = dict(_D405_CONFIG["stage_frames"])
_COMPUTE_FRAMES = dict(_D405_CONFIG["compute_frames"])

DEFAULT_D405_STAGE_RECTIFY_RPY_DEG = tuple(_STAGE_FRAMES["rectify_rpy_deg"])
DEFAULT_D405_STAGE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M = tuple(
    _STAGE_FRAMES["rectified_to_optical_offset_xyz_m"]
)
DEFAULT_D405_STAGE_RECTIFIED_TO_OPTICAL_RPY_DEG = tuple(
    _STAGE_FRAMES["rectified_to_optical_rpy_deg"]
)
DEFAULT_D405_COMPUTE_INSTALL_RPY_DEG = tuple(_COMPUTE_FRAMES["install_rpy_deg"])
DEFAULT_D405_COMPUTE_RECTIFY_RPY_DEG = tuple(_COMPUTE_FRAMES["rectify_rpy_deg"])
DEFAULT_D405_COMPUTE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M = tuple(
    _COMPUTE_FRAMES["rectified_to_optical_offset_xyz_m"]
)
DEFAULT_D405_BODY_VISUAL_RPY_DEG = tuple(_D405_CONFIG["body_visual_rpy_deg"])


@dataclass(frozen=True)
class D405AssetSettings:
    enabled: bool = True
    parent_prim: str = "/World/A1Z_G1Z/Geometry"
    fallback_parent_prim: str = "/World"
    mount_name: str = "D405_LinkCamera"
    mesh_path: str = _default_d405_mesh_path()
    rectify_rpy_deg: tuple[float, float, float] = DEFAULT_D405_STAGE_RECTIFY_RPY_DEG
    rectified_to_optical_offset_xyz_m: tuple[float, float, float] = DEFAULT_D405_STAGE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M
    rectified_to_optical_rpy_deg: tuple[float, float, float] = DEFAULT_D405_STAGE_RECTIFIED_TO_OPTICAL_RPY_DEG
    body_visual_rpy_deg: tuple[float, float, float] = DEFAULT_D405_BODY_VISUAL_RPY_DEG
    center_on_axis: bool = True
    center_mesh_y: bool = True
    camera_prims_enabled: bool = True
    fk_frame: str = "arm_link6"
    status_path: str = _default_status_path()

    @classmethod
    def from_env(cls) -> "D405AssetSettings":
        return cls(
            enabled=_env_flag("A1Z_D405_ENABLED", True),
            parent_prim=os.environ.get("A1Z_D405_PARENT_PRIM", "/World/A1Z_G1Z/Geometry"),
            fallback_parent_prim=os.environ.get("A1Z_D405_FALLBACK_PARENT_PRIM", "/World"),
            mount_name=os.environ.get("A1Z_D405_MOUNT_NAME", "D405_LinkCamera"),
            mesh_path=os.environ.get("A1Z_D405_MESH_PATH", _default_d405_mesh_path()),
            rectify_rpy_deg=DEFAULT_D405_STAGE_RECTIFY_RPY_DEG,
            rectified_to_optical_offset_xyz_m=DEFAULT_D405_STAGE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M,
            rectified_to_optical_rpy_deg=DEFAULT_D405_STAGE_RECTIFIED_TO_OPTICAL_RPY_DEG,
            body_visual_rpy_deg=DEFAULT_D405_BODY_VISUAL_RPY_DEG,
            center_on_axis=_env_flag("A1Z_D405_CENTER_ON_AXIS", True),
            center_mesh_y=_env_flag("A1Z_D405_CENTER_MESH_Y", True),
            camera_prims_enabled=_env_flag("A1Z_D405_CAMERA_PRIMS_ENABLED", True),
            fk_frame=os.environ.get("A1Z_D405_FK_FRAME", "arm_link6"),
            status_path=os.environ.get("A1Z_D405_STATUS_PATH", _default_status_path()),
        )


@dataclass(frozen=True)
class D405ComputeSettings:
    install_rpy_deg: tuple[float, float, float] = DEFAULT_D405_COMPUTE_INSTALL_RPY_DEG
    rectify_rpy_deg: tuple[float, float, float] = DEFAULT_D405_COMPUTE_RECTIFY_RPY_DEG
    rectified_to_optical_offset_xyz_m: tuple[float, float, float] = DEFAULT_D405_COMPUTE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M

    @classmethod
    def from_env(cls) -> "D405ComputeSettings":
        return cls(
            install_rpy_deg=DEFAULT_D405_COMPUTE_INSTALL_RPY_DEG,
            rectify_rpy_deg=DEFAULT_D405_COMPUTE_RECTIFY_RPY_DEG,
            rectified_to_optical_offset_xyz_m=DEFAULT_D405_COMPUTE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M,
        )


@dataclass(frozen=True)
class D405Ros2Settings:
    enabled: bool = True
    graph_path: str = "/ActionGraph/D405Ros2Publishers"
    namespace: str = "/a1z/d405"
    rectified_frame_id: str = "d405_rectified_link"
    color_frame_id: str = "d405_color_optical_frame"
    depth_frame_id: str = "d405_depth_optical_frame"
    width: int = 320
    height: int = 240
    frame_skip_count: int = 1

    @classmethod
    def from_env(cls) -> "D405Ros2Settings":
        return cls(
            enabled=_env_flag("A1Z_D405_ROS2_ENABLED", True),
            graph_path=os.environ.get("A1Z_D405_ROS2_GRAPH_PATH", "/ActionGraph/D405Ros2Publishers"),
            namespace=os.environ.get("A1Z_D405_ROS2_NAMESPACE", "/a1z/d405").strip(),
            rectified_frame_id=os.environ.get("A1Z_D405_RECTIFIED_FRAME_ID", "d405_rectified_link"),
            color_frame_id=os.environ.get("A1Z_D405_COLOR_FRAME_ID", "d405_color_optical_frame"),
            depth_frame_id=os.environ.get("A1Z_D405_DEPTH_FRAME_ID", "d405_depth_optical_frame"),
            width=_env_int("A1Z_D405_WIDTH", 320),
            height=_env_int("A1Z_D405_HEIGHT", 240),
            frame_skip_count=_env_int("A1Z_D405_FRAME_SKIP_COUNT", 1),
        )
