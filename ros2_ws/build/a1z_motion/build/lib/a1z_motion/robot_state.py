"""Joint-state and TF publisher for the Docker-first A1Z motion stack."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster

from a1z_ext.runtime.d405.geometry import (
    d405_install_rotation_matrix,
    d405_rectified_to_optical_transform,
)
from .config import load_motion_config
from .kinematics_bridge import KinematicsBridge
from .socket_client import A1ZSocketClient
from .transforms import matrix_to_transform_stamped, xyz_rpy_deg_to_matrix


class A1ZRobotStateNode(Node):
    def __init__(self) -> None:
        super().__init__("a1z_robot_state")
        self._cfg = load_motion_config()
        self._client = A1ZSocketClient(
            tcp_host=self._cfg.tcp_host,
            tcp_port=self._cfg.tcp_port,
        )
        self._kinematics = KinematicsBridge(self._cfg)
        self._joint_state_pub = self.create_publisher(JointState, "/joint_states", 10)
        self._tf_pub = TransformBroadcaster(self)
        self._static_tf_pub = StaticTransformBroadcaster(self)
        self._joint_names = [f"arm_joint{i}" for i in range(1, 7)]
        self._publish_static_transforms()
        period_s = 1.0 / max(1.0, self._cfg.poll_hz)
        self.create_timer(period_s, self._poll_state)

    def _publish_static_transforms(self) -> None:
        stamp = self.get_clock().now().to_msg()
        identity = np.eye(4, dtype=np.float64)
        static_tfs = []
        if self._cfg.robot_base_frame != self._cfg.base_link_frame:
            static_tfs.append(
                matrix_to_transform_stamped(
                    identity,
                    parent_frame=self._cfg.base_link_frame,
                    child_frame=self._cfg.robot_base_frame,
                    stamp=stamp,
                )
            )
        if self._cfg.tool_frame != self._cfg.tool_link_frame:
            static_tfs.append(
                matrix_to_transform_stamped(
                    identity,
                    parent_frame=self._cfg.tool_link_frame,
                    child_frame=self._cfg.tool_frame,
                    stamp=stamp,
                )
            )

        d405_rel = self._kinematics.fixed_relative_transform(
            parent_frame=self._cfg.tool_link_frame,
            child_frame=self._cfg.d405_link_frame,
        )
        d405_rel = np.asarray(d405_rel, dtype=np.float64).copy()
        d405_rel[:3, :3] = d405_rel[:3, :3] @ d405_install_rotation_matrix(self._cfg.d405_install_rpy_deg)
        d405_mount = matrix_to_transform_stamped(
            d405_rel,
            parent_frame=self._cfg.tool_link_frame,
            child_frame=self._cfg.d405_link_frame,
            stamp=stamp,
        )

        rectify_rel = xyz_rpy_deg_to_matrix(
            (
                0.0,
                0.0,
                0.0,
                self._cfg.d405_rectify_rpy_deg[0],
                self._cfg.d405_rectify_rpy_deg[1],
                self._cfg.d405_rectify_rpy_deg[2],
            )
        )
        d405_rectified = matrix_to_transform_stamped(
            rectify_rel,
            parent_frame=self._cfg.d405_link_frame,
            child_frame=self._cfg.d405_rectified_frame,
            stamp=stamp,
        )
        optical_rel = d405_rectified_to_optical_transform(
            offset_xyz_m=self._cfg.d405_rectified_to_optical_offset_xyz_m,
        )
        color_optical = matrix_to_transform_stamped(
            optical_rel,
            parent_frame=self._cfg.d405_rectified_frame,
            child_frame=self._cfg.d405_color_optical_frame,
            stamp=stamp,
        )
        depth_optical = matrix_to_transform_stamped(
            optical_rel,
            parent_frame=self._cfg.d405_rectified_frame,
            child_frame=self._cfg.d405_depth_optical_frame,
            stamp=stamp,
        )

        static_tfs.extend([d405_mount, d405_rectified, color_optical, depth_optical])
        self._static_tf_pub.sendTransform(static_tfs)

    def _poll_state(self) -> None:
        try:
            status = self._client.call("status")
        except Exception as exc:
            self.get_logger().warn(f"Could not query A1Z state: {exc}")
            return

        joint_deg = status.get("pos_deg", [])
        if len(joint_deg) < 6:
            self.get_logger().warn(f"Unexpected joint state payload: {status}")
            return
        q = np.deg2rad(np.asarray(joint_deg[:6], dtype=np.float64))
        now = self.get_clock().now().to_msg()

        joint_state = JointState()
        joint_state.header.stamp = now
        joint_state.name = list(self._joint_names)
        joint_state.position = q.astype(float).tolist()
        joint_state.velocity = [float(v) for v in status.get("vel_rad_s", [0.0] * 6)[:6]]
        joint_state.effort = [float(v) for v in status.get("torque_nm", [0.0] * 6)[:6]]
        self._joint_state_pub.publish(joint_state)

        tool_in_base = self._kinematics.fk(q, frame_name=self._cfg.tool_link_frame)
        tool_tf = matrix_to_transform_stamped(
            tool_in_base,
            parent_frame=self._cfg.base_link_frame,
            child_frame=self._cfg.tool_link_frame,
            stamp=now,
        )
        self._tf_pub.sendTransform(tool_tf)


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    node = A1ZRobotStateNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
