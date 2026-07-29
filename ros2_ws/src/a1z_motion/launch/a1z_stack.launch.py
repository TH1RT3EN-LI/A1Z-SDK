"""Launch robot-state integration plus the selected RGB-D device adapter."""

from __future__ import annotations

import os

from launch import LaunchDescription
from launch_ros.actions import Node


def _real_d405_node() -> Node:
    width = int(os.environ.get("A1Z_D405_WIDTH", "640"))
    height = int(os.environ.get("A1Z_D405_HEIGHT", "480"))
    fps = int(os.environ.get("A1Z_D405_FPS", "30"))
    profile = f"{width}x{height}x{fps}"
    serial = os.environ.get("A1Z_D405_SERIAL_NO", "").strip()
    parameters = {
        "device_type": "d405",
        "enable_color": True,
        "enable_depth": True,
        "enable_sync": True,
        "align_depth.enable": True,
        "publish_tf": False,
        "initial_reset": True,
        "depth_module.depth_profile": profile,
        "depth_module.color_profile": profile,
    }
    if serial:
        parameters["serial_no"] = serial
    return Node(
        package="realsense2_camera",
        executable="realsense2_camera_node",
        namespace="a1z",
        name="d405",
        parameters=[parameters],
        output="screen",
    )


def generate_launch_description() -> LaunchDescription:
    camera_source = os.environ.get("A1Z_CAMERA_SOURCE", "").strip()
    if camera_source == "isaac":
        camera_node = Node(
            package="a1z_d405",
            executable="isaac_d405_bridge",
            name="a1z_isaac_d405_bridge",
            output="screen",
        )
    elif camera_source == "realsense":
        camera_node = _real_d405_node()
    else:
        raise RuntimeError(
            "A1Z_CAMERA_SOURCE must be 'isaac' or 'realsense'; "
            f"got {camera_source!r}"
        )

    return LaunchDescription(
        [
            camera_node,
            Node(
                package="a1z_motion",
                executable="robot_state",
                name="a1z_robot_state",
                output="screen",
            ),
            Node(
                package="a1z_motion",
                executable="motion_executor",
                name="a1z_motion_executor",
                output="screen",
            ),
        ]
    )
