"""Project-local configuration helpers for A1Z extensions."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any


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
