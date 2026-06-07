from __future__ import annotations

from .asset import attach_d405_wrist_camera
from .ros2_publish import setup_d405_ros2_publishers as _setup_d405_ros2_publishers


def attach_d405_asset(stage):
    return attach_d405_wrist_camera(stage)


def setup_d405_ros2_publishers(attachment):
    return _setup_d405_ros2_publishers(attachment)
