from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            Node(
                package="a1z_d405",
                executable="d405_bridge",
                name="a1z_d405_bridge",
                output="screen",
            ),
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
