"""ROS 2 RGB-D frame source for aligned color/depth captures."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time
from typing import Any

import numpy as np

from a1z_ext.interfaces.observation import RGBDObservation
from a1z_ext.runtime.ros_env import ensure_ros_logging_env
from a1z_ext.runtime.ros_tf import RosTransformResolver

from .base import FrameSource, RGBDFrameCapture


def _stamp_to_ns(stamp: Any) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def _camera_info_to_intrinsics(message: Any) -> dict[str, Any]:
    if len(message.k) >= 9 and float(message.k[0]) > 0.0 and float(message.k[4]) > 0.0:
        fx = float(message.k[0])
        fy = float(message.k[4])
        cx = float(message.k[2])
        cy = float(message.k[5])
    elif len(message.p) >= 12 and float(message.p[0]) > 0.0 and float(message.p[5]) > 0.0:
        fx = float(message.p[0])
        fy = float(message.p[5])
        cx = float(message.p[2])
        cy = float(message.p[6])
    else:
        raise ValueError("camera_info is missing valid pinhole intrinsics")
    return {
        "fx": fx,
        "fy": fy,
        "cx": cx,
        "cy": cy,
        "distortion_model": str(getattr(message, "distortion_model", "unknown") or "unknown"),
        "distortion_coeffs": [float(v) for v in getattr(message, "d", [])],
    }


def _decode_color_image(message: Any) -> np.ndarray:
    encoding = str(message.encoding).lower()
    width = int(message.width)
    height = int(message.height)
    step = int(message.step)
    data = memoryview(message.data)

    if width <= 0 or height <= 0:
        raise ValueError("color image width and height must be positive")

    if encoding == "rgb8":
        row_width = width * 3
        if step < row_width:
            raise ValueError(f"rgb8 step {step} is smaller than expected row width {row_width}")
        raw = np.frombuffer(data, dtype=np.uint8, count=step * height).reshape(height, step)
        return np.ascontiguousarray(raw[:, :row_width].reshape(height, width, 3))

    if encoding == "bgr8":
        row_width = width * 3
        if step < row_width:
            raise ValueError(f"bgr8 step {step} is smaller than expected row width {row_width}")
        raw = np.frombuffer(data, dtype=np.uint8, count=step * height).reshape(height, step)
        bgr = raw[:, :row_width].reshape(height, width, 3)
        return np.ascontiguousarray(bgr[:, :, ::-1])

    if encoding == "rgba8":
        row_width = width * 4
        if step < row_width:
            raise ValueError(f"rgba8 step {step} is smaller than expected row width {row_width}")
        raw = np.frombuffer(data, dtype=np.uint8, count=step * height).reshape(height, step)
        rgba = raw[:, :row_width].reshape(height, width, 4)
        return np.ascontiguousarray(rgba[:, :, :3])

    if encoding == "bgra8":
        row_width = width * 4
        if step < row_width:
            raise ValueError(f"bgra8 step {step} is smaller than expected row width {row_width}")
        raw = np.frombuffer(data, dtype=np.uint8, count=step * height).reshape(height, step)
        bgra = raw[:, :row_width].reshape(height, width, 4)
        return np.ascontiguousarray(bgra[:, :, [2, 1, 0]])

    if encoding in {"mono8", "8uc1"}:
        row_width = width
        if step < row_width:
            raise ValueError(f"mono8 step {step} is smaller than expected row width {row_width}")
        raw = np.frombuffer(data, dtype=np.uint8, count=step * height).reshape(height, step)
        gray = raw[:, :row_width].reshape(height, width)
        return np.repeat(gray[:, :, None], 3, axis=2)

    raise ValueError(f"unsupported color encoding: {message.encoding}")


def _decode_depth_image(message: Any, *, uint16_scale_m: float) -> np.ndarray:
    encoding = str(message.encoding).lower()
    width = int(message.width)
    height = int(message.height)
    step = int(message.step)
    data = memoryview(message.data)

    if width <= 0 or height <= 0:
        raise ValueError("depth image width and height must be positive")

    if encoding == "32fc1":
        item_size = 4
        row_width = width
        if step < row_width * item_size:
            raise ValueError(f"32FC1 step {step} is smaller than expected row width {row_width * item_size}")
        raw = np.frombuffer(data, dtype=np.float32, count=(step // item_size) * height).reshape(height, step // item_size)
        return np.ascontiguousarray(raw[:, :row_width].astype(np.float32, copy=False))

    if encoding in {"16uc1", "mono16"}:
        item_size = 2
        row_width = width
        if step < row_width * item_size:
            raise ValueError(f"16UC1 step {step} is smaller than expected row width {row_width * item_size}")
        raw = np.frombuffer(data, dtype=np.uint16, count=(step // item_size) * height).reshape(height, step // item_size)
        return np.ascontiguousarray(raw[:, :row_width].astype(np.float32) * float(uint16_scale_m))

    raise ValueError(f"unsupported depth encoding: {message.encoding}")


@dataclass(slots=True)
class RosRGBDFrameSource(FrameSource):
    color_topic: str = "/a1z/d405/color/image_raw"
    depth_topic: str = "/a1z/d405/depth/image_rect"
    color_camera_info_topic: str = "/a1z/d405/color/camera_info"
    depth_camera_info_topic: str = "/a1z/d405/depth/camera_info"
    timeout_s: float = 10.0
    sync_slop_s: float = 0.25
    depth_uint16_scale_m: float = 0.001
    source_backend: str = "ros2_rgbd"
    sensor_model: str = "ros_rgbd"
    calibration_version: str = "ros_runtime_unknown"
    target_frame_id: str = "robot_base_frame"
    tf_lookup_timeout_s: float = 1.0
    tf_cache_time_s: float = 10.0
    fail_if_tf_unavailable: bool = False

    def capture(self) -> RGBDFrameCapture:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import (
            DurabilityPolicy,
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
        )
        from sensor_msgs.msg import CameraInfo, Image

        color_topic = self.color_topic
        depth_topic = self.depth_topic
        color_info_topic = self.color_camera_info_topic
        depth_info_topic = self.depth_camera_info_topic
        timeout_s = float(self.timeout_s)
        sync_slop_ns = int(float(self.sync_slop_s) * 1_000_000_000)

        class OneShotRGBDNode(Node):
            def __init__(self) -> None:
                super().__init__("a1z_rgbd_capture")
                self.color_msgs: deque[Image] = deque(maxlen=8)
                self.depth_msgs: deque[Image] = deque(maxlen=8)
                self.color_info_msg: CameraInfo | None = None
                self.depth_info_msg: CameraInfo | None = None
                self.tf_resolver = RosTransformResolver(self, cache_time_s=self_outer.tf_cache_time_s)
                qos = QoSProfile(
                    history=HistoryPolicy.KEEP_LAST,
                    depth=1,
                    reliability=ReliabilityPolicy.BEST_EFFORT,
                    durability=DurabilityPolicy.VOLATILE,
                )
                self.color_sub = self.create_subscription(Image, color_topic, self._handle_color, qos)
                self.depth_sub = self.create_subscription(Image, depth_topic, self._handle_depth, qos)
                self.color_info_sub = self.create_subscription(
                    CameraInfo,
                    color_info_topic,
                    self._handle_color_info,
                    qos,
                )
                self.depth_info_sub = self.create_subscription(
                    CameraInfo,
                    depth_info_topic,
                    self._handle_depth_info,
                    qos,
                )

            def _handle_color(self, message: Image) -> None:
                self.color_msgs.append(message)

            def _handle_depth(self, message: Image) -> None:
                self.depth_msgs.append(message)

            def _handle_color_info(self, message: CameraInfo) -> None:
                self.color_info_msg = message

            def _handle_depth_info(self, message: CameraInfo) -> None:
                self.depth_info_msg = message

            def synchronized_sample(self) -> dict[str, Any] | None:
                if (
                    not self.color_msgs
                    or not self.depth_msgs
                    or self.color_info_msg is None
                    or self.depth_info_msg is None
                ):
                    return None
                best_pair: tuple[Image, Image] | None = None
                best_delta_ns: int | None = None
                for color_msg in reversed(self.color_msgs):
                    color_stamp_ns = _stamp_to_ns(color_msg.header.stamp)
                    for depth_msg in reversed(self.depth_msgs):
                        delta_ns = abs(color_stamp_ns - _stamp_to_ns(depth_msg.header.stamp))
                        if delta_ns > sync_slop_ns:
                            continue
                        if best_delta_ns is None or delta_ns < best_delta_ns:
                            best_pair = (color_msg, depth_msg)
                            best_delta_ns = delta_ns
                if best_pair is None:
                    return None
                color_msg, depth_msg = best_pair
                return {
                    "color_msg": color_msg,
                    "depth_msg": depth_msg,
                    "color_info_msg": self.color_info_msg,
                    "depth_info_msg": self.depth_info_msg,
                }

        self_outer = self
        ensure_ros_logging_env()
        rclpy.init(args=None)
        node = OneShotRGBDNode()
        deadline = time.monotonic() + timeout_s
        try:
            sample = None
            while rclpy.ok() and sample is None and time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.2)
                sample = node.synchronized_sample()
            if sample is None:
                raise TimeoutError(
                    "timed out waiting for synchronized RGB-D sample "
                    f"on {color_topic} + {depth_topic}"
                )

            color_msg = sample["color_msg"]
            depth_msg = sample["depth_msg"]
            color_info_msg = sample["color_info_msg"]
            depth_info_msg = sample["depth_info_msg"]

            rgb = _decode_color_image(color_msg)
            depth_m = _decode_depth_image(depth_msg, uint16_scale_m=self.depth_uint16_scale_m)
            if rgb.shape[:2] != depth_m.shape[:2]:
                raise ValueError(
                    f"RGB/depth shape mismatch: rgb={rgb.shape[:2]} depth={depth_m.shape[:2]}"
                )

            intrinsics = _camera_info_to_intrinsics(color_info_msg)
            color_stamp_ns = _stamp_to_ns(color_msg.header.stamp)
            depth_stamp_ns = _stamp_to_ns(depth_msg.header.stamp)
            camera_frame_id = str(color_msg.header.frame_id or "camera_color_frame")
            tf_target_frame_id = str(self.target_frame_id or camera_frame_id)

            transform_matrix = np.eye(4, dtype=np.float64)
            resolved_target_frame_id = camera_frame_id
            tf_lookup_status = "identity"
            tf_lookup_mode = "not_requested"
            tf_resolved_stamp_ns: int | None = None
            tf_error = ""
            if tf_target_frame_id and tf_target_frame_id != camera_frame_id:
                try:
                    tf_result = None
                    tf_deadline = time.monotonic() + max(0.1, float(self.tf_lookup_timeout_s))
                    last_tf_error: Exception | None = None
                    while time.monotonic() < tf_deadline:
                        rclpy.spin_once(node, timeout_sec=min(0.1, max(0.0, tf_deadline - time.monotonic())))
                        try:
                            tf_result = node.tf_resolver.lookup_matrix(
                                target_frame_id=tf_target_frame_id,
                                source_frame_id=camera_frame_id,
                                stamp=color_msg.header.stamp,
                                timeout_s=0.0,
                                fallback_to_latest=True,
                            )
                            break
                        except Exception as exc:
                            last_tf_error = exc
                    if tf_result is None:
                        if last_tf_error is not None:
                            raise last_tf_error
                        raise RuntimeError(
                            f"could not resolve TF {camera_frame_id!r} -> {tf_target_frame_id!r}"
                        )
                    transform_matrix = tf_result.transform_matrix
                    resolved_target_frame_id = tf_result.target_frame_id
                    tf_lookup_status = "resolved"
                    tf_lookup_mode = tf_result.lookup_mode
                    tf_resolved_stamp_ns = tf_result.resolved_stamp_ns
                except Exception as exc:
                    tf_error = str(exc)
                    if self.fail_if_tf_unavailable:
                        raise
                    resolved_target_frame_id = camera_frame_id
                    tf_lookup_status = "unavailable_fallback_identity"
                    tf_lookup_mode = "fallback_identity"

            observation = RGBDObservation.create(
                source_backend=self.source_backend,
                width=int(rgb.shape[1]),
                height=int(rgb.shape[0]),
                camera_frame_id=camera_frame_id,
                target_frame_id=resolved_target_frame_id,
                intrinsics=intrinsics,
                extrinsic_camera_to_target=transform_matrix,
                rgb_encoding=str(color_msg.encoding),
                depth_encoding=str(depth_msg.encoding),
                calibration_version=self.calibration_version,
                sensor_model=self.sensor_model,
                scene_context={
                    "depth_frame_id": str(depth_msg.header.frame_id or ""),
                    "color_camera_info_frame_id": str(color_info_msg.header.frame_id or ""),
                    "depth_camera_info_frame_id": str(depth_info_msg.header.frame_id or ""),
                    "color_topic": color_topic,
                    "depth_topic": depth_topic,
                    "color_camera_info_topic": color_info_topic,
                    "depth_camera_info_topic": depth_info_topic,
                    "color_stamp_ns": color_stamp_ns,
                    "depth_stamp_ns": depth_stamp_ns,
                    "requested_target_frame_id": tf_target_frame_id,
                    "tf_lookup_status": tf_lookup_status,
                    "tf_lookup_mode": tf_lookup_mode,
                    "tf_resolved_stamp_ns": tf_resolved_stamp_ns,
                    "tf_error": tf_error,
                },
                timestamp_ns=min(color_stamp_ns, depth_stamp_ns),
            )
            capture = RGBDFrameCapture(
                observation=observation,
                rgb=rgb,
                depth_m=depth_m,
                source_info={
                    "source_backend": self.source_backend,
                    "color_topic": color_topic,
                    "depth_topic": depth_topic,
                    "color_camera_info_topic": color_info_topic,
                    "depth_camera_info_topic": depth_info_topic,
                    "color_frame_id": str(color_msg.header.frame_id or ""),
                    "depth_frame_id": str(depth_msg.header.frame_id or ""),
                    "color_encoding": str(color_msg.encoding),
                    "depth_encoding": str(depth_msg.encoding),
                    "color_stamp_ns": color_stamp_ns,
                    "depth_stamp_ns": depth_stamp_ns,
                    "requested_target_frame_id": tf_target_frame_id,
                    "resolved_target_frame_id": resolved_target_frame_id,
                    "tf_lookup_status": tf_lookup_status,
                    "tf_lookup_mode": tf_lookup_mode,
                    "tf_resolved_stamp_ns": tf_resolved_stamp_ns,
                    "tf_error": tf_error,
                    "width": int(rgb.shape[1]),
                    "height": int(rgb.shape[0]),
                    "sync_slop_s": float(self.sync_slop_s),
                    "depth_uint16_scale_m": float(self.depth_uint16_scale_m),
                },
            )
            capture.validate()
            return capture
        finally:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


def capture_ros_rgbd_frame(
    *,
    color_topic: str = "/a1z/d405/color/image_raw",
    depth_topic: str = "/a1z/d405/depth/image_rect",
    color_camera_info_topic: str = "/a1z/d405/color/camera_info",
    depth_camera_info_topic: str = "/a1z/d405/depth/camera_info",
    timeout_s: float = 10.0,
    sync_slop_s: float = 0.25,
    depth_uint16_scale_m: float = 0.001,
    target_frame_id: str = "robot_base_frame",
    tf_lookup_timeout_s: float = 1.0,
    tf_cache_time_s: float = 10.0,
    fail_if_tf_unavailable: bool = False,
) -> RGBDFrameCapture:
    return RosRGBDFrameSource(
        color_topic=color_topic,
        depth_topic=depth_topic,
        color_camera_info_topic=color_camera_info_topic,
        depth_camera_info_topic=depth_camera_info_topic,
        timeout_s=timeout_s,
        sync_slop_s=sync_slop_s,
        depth_uint16_scale_m=depth_uint16_scale_m,
        target_frame_id=target_frame_id,
        tf_lookup_timeout_s=tf_lookup_timeout_s,
        tf_cache_time_s=tf_cache_time_s,
        fail_if_tf_unavailable=fail_if_tf_unavailable,
    ).capture()
