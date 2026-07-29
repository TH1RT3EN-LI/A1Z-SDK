"""Isaac-specific adapter publishing the shared ROS RGB-D topic contract."""

from __future__ import annotations

from typing import Optional

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Header

from .config import load_config
from .decode import decode_array
from .socket_client import A1ZCameraClient


def _camera_info_message(
    *,
    header: Header,
    width: int,
    height: int,
    intrinsics: dict,
    distortion_model: str = "plumb_bob",
) -> CameraInfo:
    fx = float(intrinsics["fx"])
    fy = float(intrinsics["fy"])
    cx = float(intrinsics["cx"])
    cy = float(intrinsics["cy"])
    msg = CameraInfo()
    msg.header = header
    msg.width = int(width)
    msg.height = int(height)
    msg.distortion_model = distortion_model
    msg.d = [0.0] * 5
    msg.k = [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
    msg.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    msg.p = [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
    return msg


def _image_message(*, header: Header, array: np.ndarray, encoding: str) -> Image:
    array = np.ascontiguousarray(array)
    msg = Image()
    msg.header = header
    msg.height = int(array.shape[0])
    msg.width = int(array.shape[1])
    msg.encoding = encoding
    msg.is_bigendian = False
    msg.step = int(array.strides[0])
    msg.data = array.tobytes()
    return msg


class A1ZD405BridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("a1z_d405_bridge")
        self._cfg = load_config()
        self._client = A1ZCameraClient(
            tcp_host=self._cfg.tcp_host,
            tcp_port=self._cfg.tcp_port,
        )
        ns = self._cfg.namespace
        sensor_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._color_pub = self.create_publisher(Image, f"{ns}/color/image_raw", sensor_qos)
        self._color_info_pub = self.create_publisher(CameraInfo, f"{ns}/color/camera_info", sensor_qos)
        self._depth_pub = self.create_publisher(Image, f"{ns}/depth/image_rect", sensor_qos)
        self._depth_info_pub = self.create_publisher(CameraInfo, f"{ns}/depth/camera_info", sensor_qos)
        self._last_source_timestamp_ns: int | None = None

        period_s = 1.0 / max(1.0, self._cfg.poll_hz)
        self._timer = self.create_timer(period_s, self._poll_and_publish)
        self.get_logger().info(
            f"Publishing D405 RGB-D topics under {ns} from tcp://{self._cfg.tcp_host}:{self._cfg.tcp_port}"
        )

    def _poll_and_publish(self) -> None:
        if not rclpy.ok():
            return
        try:
            # Isaac continuously captures at the sensor's own render cadence.
            # Consume the newest complete RGB-D pair without blocking this ROS
            # timer while Kit waits for an additional render generation.
            payload = self._client.call("camera_capture", {"fresh": False})
            source_timestamp_ns = int(payload["timestamp_ns"])
            if (
                self._last_source_timestamp_ns is not None
                and source_timestamp_ns <= self._last_source_timestamp_ns
            ):
                return
            self._last_source_timestamp_ns = source_timestamp_ns

            rgb = decode_array(payload["rgb"]).astype(np.uint8, copy=False)
            depth = decode_array(payload["depth"]).astype(np.float32, copy=False)

            stamp = self.get_clock().now().to_msg()
            color_header = Header()
            color_header.stamp = stamp
            color_header.frame_id = str(payload.get("camera_frame_id", self._cfg.color_frame_id))
            depth_header = Header()
            depth_header.stamp = stamp
            depth_header.frame_id = str(payload.get("depth_frame_id", self._cfg.depth_frame_id))
            intrinsics = dict(payload["intrinsics"])

            self._color_pub.publish(_image_message(header=color_header, array=rgb, encoding="rgb8"))
            self._color_info_pub.publish(
                _camera_info_message(
                    header=color_header,
                    width=int(payload["width"]),
                    height=int(payload["height"]),
                    intrinsics=intrinsics,
                )
            )
            self._depth_pub.publish(_image_message(header=depth_header, array=depth, encoding="32FC1"))
            self._depth_info_pub.publish(
                _camera_info_message(
                    header=depth_header,
                    width=int(payload["width"]),
                    height=int(payload["height"]),
                    intrinsics=intrinsics,
                )
            )
        except Exception as exc:
            if rclpy.ok():
                self.get_logger().warn(f"Could not publish D405 frame: {exc}")


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    node = A1ZD405BridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
