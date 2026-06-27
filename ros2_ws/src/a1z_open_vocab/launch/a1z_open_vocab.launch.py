"""Launch the A1Z VLM request bridge."""

from __future__ import annotations

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from pathlib import Path


def generate_launch_description() -> LaunchDescription:
    default_config = str(
        Path(get_package_share_directory("a1z_open_vocab")) / "config" / "vlm.yaml"
    )

    launch_args = [
        DeclareLaunchArgument(
            "config",
            default_value=default_config,
            description="YAML parameter file for the VLM request node.",
        ),
        DeclareLaunchArgument("llm_provider", default_value="openai"),
        DeclareLaunchArgument("llm_model", default_value=""),
        DeclareLaunchArgument("llm_base_url", default_value=""),
        DeclareLaunchArgument("llm_api_key_env", default_value=""),
    ]

    node = Node(
        package="a1z_open_vocab",
        executable="vision_request",
        name="a1z_vlm_request",
        output="screen",
        parameters=[
            LaunchConfiguration("config"),
            {
                "llm_provider": LaunchConfiguration("llm_provider"),
                "llm_model": LaunchConfiguration("llm_model"),
                "llm_base_url": LaunchConfiguration("llm_base_url"),
                "llm_api_key_env": LaunchConfiguration("llm_api_key_env"),
            },
        ],
    )

    return LaunchDescription([*launch_args, node])
