"""ROS runtime environment helpers."""

from __future__ import annotations

import os
from pathlib import Path


def ensure_ros_logging_env() -> None:
    home = (os.environ.get("HOME") or "").strip()
    if not home:
        home = f"/tmp/a1z-home-{os.getuid()}"
        os.environ["HOME"] = home
    home_path = Path(home)
    ros_dir = home_path / ".ros"
    log_dir = Path(os.environ.get("ROS_LOG_DIR") or ros_dir / "log")
    ros_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("ROS_LOG_DIR", str(log_dir))
