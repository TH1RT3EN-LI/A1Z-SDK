"""Shared configuration helpers for the ROS 2 A1Z motion stack."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_vec3(name: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = os.environ.get(name)
    if not raw:
        return default
    parts = [part.strip() for part in raw.replace(",", " ").split()]
    if len(parts) != 3:
        raise ValueError(f"{name} must contain exactly 3 numbers, got: {raw}")
    return float(parts[0]), float(parts[1]), float(parts[2])


def _repo_root() -> Path:
    env_root = os.environ.get("A1Z_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    resolved = Path(__file__).resolve()
    for parent in resolved.parents:
        if (parent / "vendor" / "GALAXEA-A1Z" / "a1z").is_dir():
            return parent
    return resolved.parents[4]


@dataclass(frozen=True)
class MotionConfig:
    repo_root: Path
    control_urdf: Path
    sdk_root: Path
    tcp_host: str
    tcp_port: int
    world_frame: str
    robot_base_frame: str
    tool_link_frame: str
    tool_frame: str
    d405_link_frame: str
    d405_color_optical_frame: str
    d405_depth_optical_frame: str
    d405_optical_offset_xyz_m: tuple[float, float, float]
    d405_optical_rpy_deg: tuple[float, float, float]
    poll_hz: float


def load_motion_config() -> MotionConfig:
    repo_root = _repo_root()
    control_urdf = Path(
        os.environ.get(
            "A1Z_CONTROL_URDF",
            repo_root / "build" / "robot_packages" / "A1Z_G1Z" / "urdf" / "A1Z_G1Z_control.urdf",
        )
    )
    return MotionConfig(
        repo_root=repo_root,
        control_urdf=control_urdf,
        sdk_root=Path(os.environ.get("A1Z_SDK_DIR", repo_root / "vendor" / "GALAXEA-A1Z")),
        tcp_host=os.environ.get("A1Z_TCP_HOST", "127.0.0.1"),
        tcp_port=int(os.environ.get("A1Z_TCP_PORT", "18080")),
        world_frame=os.environ.get("A1Z_WORLD_FRAME", "world_frame"),
        robot_base_frame=os.environ.get("A1Z_ROBOT_BASE_FRAME", "robot_base_frame"),
        tool_link_frame=os.environ.get("A1Z_TOOL_LINK_FRAME", "arm_link6"),
        tool_frame=os.environ.get("A1Z_TOOL_FRAME", "tool_frame"),
        d405_link_frame=os.environ.get("A1Z_D405_LINK_FRAME", "d405_link"),
        d405_color_optical_frame=os.environ.get("A1Z_D405_COLOR_FRAME_ID", "d405_color_optical_frame"),
        d405_depth_optical_frame=os.environ.get("A1Z_D405_DEPTH_FRAME_ID", "d405_depth_optical_frame"),
        d405_optical_offset_xyz_m=_env_vec3("A1Z_D405_OPTICAL_OFFSET_XYZ_M", (0.009, 0.0, -0.0038)),
        d405_optical_rpy_deg=_env_vec3("A1Z_D405_CAMERA_OPTICAL_RPY_DEG", (0.0, 180.0, 0.0)),
        poll_hz=float(os.environ.get("A1Z_ROS_POLL_HZ", "10.0")),
    )
