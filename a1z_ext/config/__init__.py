"""Project-local configuration helpers for A1Z extensions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArmMotionSpeedLimits:
    minimum: float
    default: float
    maximum: float

    def validate(self, value: float) -> float:
        speed = float(value)
        if not self.minimum <= speed <= self.maximum:
            raise ValueError(
                "机械臂速度必须位于 "
                f"[{self.minimum:g}, {self.maximum:g}] rad/s，当前为 {speed:g}"
            )
        return speed


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_default_control_urdf_path() -> str:
    override = os.environ.get("A1Z_CONTROL_URDF")
    if override:
        return override
    return str(_repo_root() / "build" / "robot_packages" / "A1Z_G1Z" / "urdf" / "A1Z_G1Z_control.urdf")


@lru_cache(maxsize=1)
def get_control_defaults() -> dict[str, Any]:
    config_path = files("a1z_ext.config").joinpath("control_defaults.json")
    with config_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    data["default_control_urdf_path"] = get_default_control_urdf_path()
    return data


def get_default_can_channel() -> str:
    return os.environ.get("A1Z_CAN_CHANNEL", get_control_defaults()["default_can_channel"])


def get_socket_path() -> str:
    return os.environ.get("A1Z_SOCKET_PATH", get_control_defaults()["socket_path"])


def get_tcp_host() -> str:
    return os.environ.get("A1Z_TCP_HOST", get_control_defaults()["tcp_host"])


def get_tcp_port() -> int:
    return int(os.environ.get("A1Z_TCP_PORT", str(get_control_defaults()["tcp_port"])))


def get_default_backend() -> str:
    return os.environ.get("A1Z_BACKEND", get_control_defaults()["default_backend"])


def get_control_frequency_hz() -> int:
    return int(os.environ.get("A1Z_CONTROL_FREQ_HZ", "250"))


def get_min_control_frequency_hz() -> float:
    return float(os.environ.get("A1Z_MIN_CONTROL_FREQ_HZ", "80"))


def get_gripper_max_torque_nm() -> float:
    return float(os.environ.get("A1Z_GRIPPER_MAX_TORQUE", "0.5"))


def get_gripper_empty_close_threshold() -> float:
    return float(os.environ.get("A1Z_GRIPPER_EMPTY_CLOSE_THRESHOLD", "0.04"))


def get_arm_motion_speed_limits() -> ArmMotionSpeedLimits:
    values = get_control_defaults()["arm_motion_speed_rad_s"]
    limits = ArmMotionSpeedLimits(
        minimum=float(values["minimum"]),
        default=float(values["default"]),
        maximum=float(values["maximum"]),
    )
    if not 0.0 < limits.minimum <= limits.default <= limits.maximum:
        raise ValueError(f"Invalid arm_motion_speed_rad_s configuration: {values!r}")
    return limits


def validate_arm_motion_speed(value: float) -> float:
    return get_arm_motion_speed_limits().validate(value)
