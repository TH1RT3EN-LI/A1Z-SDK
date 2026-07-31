"""Expose the profile-selected ROS RGB-D contract to the desktop console.

The bridge consumes ROS topics instead of opening ``/dev/video*`` nodes.  This
keeps simulation and physical cameras on one GUI path and leaves device
discovery/ownership to the selected ROS camera adapter.
"""

from __future__ import annotations

import base64
from collections import deque
from dataclasses import dataclass
import json
import os
import socket
import threading
import time
from typing import Any, Callable

import numpy as np

from a1z_ext.runtime.frame_sources.ros_rgbd import (
    _camera_info_to_intrinsics,
    _decode_color_image,
    _decode_depth_image,
    _stamp_to_ns,
)
from a1z_ext.runtime.image_input import _encode_png
from a1z_ext.runtime.ros_tf import RosTransformResolver

try:
    from rclpy.node import Node as _RosNode
except ImportError:  # Allow pure helpers to be tested outside a ROS install.
    _RosNode = object  # type: ignore[assignment,misc]


@dataclass(frozen=True, slots=True)
class ConsoleBridgeConfig:
    profile: str
    camera_source: str
    host: str
    port: int
    color_topic: str
    depth_topic: str
    color_info_topic: str
    depth_info_topic: str
    target_frame_id: str
    sync_slop_s: float
    stale_after_s: float
    depth_uint16_scale_m: float
    preview_max_width: int
    preview_depth_min_m: float
    preview_depth_max_m: float

    @classmethod
    def from_env(cls) -> "ConsoleBridgeConfig":
        config = cls(
            profile=os.environ.get("A1Z_PROFILE", "sim").strip(),
            camera_source=os.environ.get("A1Z_CAMERA_SOURCE", "unknown").strip(),
            host=os.environ.get("A1Z_CAMERA_BRIDGE_HOST", "127.0.0.1").strip(),
            port=int(os.environ.get("A1Z_CAMERA_BRIDGE_PORT", "37203")),
            color_topic=os.environ.get(
                "A1Z_RGBD_COLOR_TOPIC", "/a1z/d405/color/image_raw"
            ).strip(),
            depth_topic=os.environ.get(
                "A1Z_RGBD_DEPTH_TOPIC", "/a1z/d405/depth/image_rect"
            ).strip(),
            color_info_topic=os.environ.get(
                "A1Z_RGBD_COLOR_INFO_TOPIC", "/a1z/d405/color/camera_info"
            ).strip(),
            depth_info_topic=os.environ.get(
                "A1Z_RGBD_DEPTH_INFO_TOPIC", "/a1z/d405/depth/camera_info"
            ).strip(),
            target_frame_id=os.environ.get(
                "A1Z_RGBD_TARGET_FRAME", "base_link"
            ).strip(),
            sync_slop_s=float(
                os.environ.get("A1Z_CAMERA_BRIDGE_SYNC_SLOP_S", "0.25")
            ),
            stale_after_s=float(
                os.environ.get("A1Z_CAMERA_BRIDGE_STALE_AFTER_S", "2.0")
            ),
            depth_uint16_scale_m=float(
                os.environ.get("A1Z_DEPTH_UINT16_SCALE_M", "0.001")
            ),
            preview_max_width=int(
                os.environ.get("A1Z_CAMERA_PREVIEW_MAX_WIDTH", "960")
            ),
            preview_depth_min_m=float(
                os.environ.get("A1Z_CAMERA_PREVIEW_DEPTH_MIN_M", "0.05")
            ),
            preview_depth_max_m=float(
                os.environ.get("A1Z_CAMERA_PREVIEW_DEPTH_MAX_M", "3.0")
            ),
        )
        if (
            not np.isfinite(config.preview_depth_min_m)
            or not np.isfinite(config.preview_depth_max_m)
            or config.preview_depth_min_m < 0.0
            or config.preview_depth_max_m
            <= config.preview_depth_min_m + 1e-6
        ):
            raise ValueError(
                "A1Z camera preview depth range must be finite and increasing"
            )
        return config


def _resize_nearest(image: np.ndarray, *, max_width: int) -> np.ndarray:
    height, width = image.shape[:2]
    if width <= max_width:
        return np.ascontiguousarray(image)
    scale = float(max_width) / float(width)
    output_height = max(1, round(height * scale))
    x_indices = np.minimum(
        width - 1,
        np.floor(np.arange(max_width, dtype=np.float64) / scale).astype(np.int64),
    )
    y_indices = np.minimum(
        height - 1,
        np.floor(np.arange(output_height, dtype=np.float64) / scale).astype(np.int64),
    )
    return np.ascontiguousarray(image[y_indices[:, None], x_indices[None, :]])


def _depth_colormap(
    depth_m: np.ndarray,
    *,
    depth_range_m: tuple[float, float] | None = None,
) -> np.ndarray:
    depth = np.asarray(depth_m, dtype=np.float32)
    valid = np.isfinite(depth) & (depth > 0.0)
    output = np.full((*depth.shape, 3), 14, dtype=np.uint8)
    if not np.any(valid):
        return output

    values = depth[valid]
    if depth_range_m is None:
        low, high = np.percentile(values, [2.0, 98.0])
        if not np.isfinite(low) or not np.isfinite(high) or high <= low + 1e-6:
            low = float(np.min(values))
            high = max(low + 1e-3, float(np.max(values)))
    else:
        low, high = (float(value) for value in depth_range_m)
        if (
            not np.isfinite(low)
            or not np.isfinite(high)
            or high <= low + 1e-6
        ):
            raise ValueError("depth_range_m must be finite and increasing")
    normalized = np.where(
        valid,
        np.clip((depth - low) / (high - low), 0.0, 1.0),
        0.0,
    )
    # Near is warm, far is cool. The fixed anchors keep this dependency-free.
    anchors = np.array(
        [
            [255.0, 232.0, 76.0],
            [54.0, 207.0, 126.0],
            [35.0, 126.0, 181.0],
            [68.0, 1.0, 84.0],
        ],
        dtype=np.float32,
    )
    position = normalized * float(len(anchors) - 1)
    left = np.floor(position).astype(np.int64)
    right = np.minimum(left + 1, len(anchors) - 1)
    fraction = (position - left)[..., None]
    colored = anchors[left] * (1.0 - fraction) + anchors[right] * fraction
    output[valid] = np.clip(colored[valid], 0.0, 255.0).astype(np.uint8)
    return output


def compose_rgbd_preview_png(
    rgb: np.ndarray,
    depth_m: np.ndarray,
    *,
    max_width: int = 960,
    depth_range_m: tuple[float, float] | None = None,
) -> bytes:
    """Return a side-by-side RGB/depth PNG suitable for a QML data URL."""

    color = np.asarray(rgb, dtype=np.uint8)
    depth = np.asarray(depth_m, dtype=np.float32)
    if color.ndim != 3 or color.shape[2] < 3:
        raise ValueError(f"RGB preview must be HxWx3, got {color.shape}")
    if depth.ndim != 2:
        raise ValueError(f"depth preview must be HxW, got {depth.shape}")
    if color.shape[:2] != depth.shape:
        raise ValueError(
            f"RGB/depth preview shape mismatch: {color.shape[:2]} vs {depth.shape}"
        )

    separator_width = 8
    panel_width = max(1, (max(64, int(max_width)) - separator_width) // 2)
    color_panel = _resize_nearest(color[:, :, :3], max_width=panel_width)
    depth_panel = _resize_nearest(
        _depth_colormap(depth, depth_range_m=depth_range_m),
        max_width=panel_width,
    )
    height = min(color_panel.shape[0], depth_panel.shape[0])
    color_panel = color_panel[:height]
    depth_panel = depth_panel[:height]
    separator = np.full((height, separator_width, 3), 22, dtype=np.uint8)
    mosaic = np.concatenate((color_panel, separator, depth_panel), axis=1)
    rows = [mosaic[row].tobytes() for row in range(mosaic.shape[0])]
    return _encode_png(
        width=int(mosaic.shape[1]),
        height=int(mosaic.shape[0]),
        rows=rows,
        color_type=2,
    )


class _JsonLineServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        handler: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._host = host
        self._port = int(port)
        self._handler = handler
        self._stop = threading.Event()
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self._host, self._port))
        listener.listen(8)
        listener.settimeout(0.5)
        self._listener = listener
        self._thread = threading.Thread(
            target=self._serve,
            name="a1z-camera-console-bridge",
            daemon=True,
        )
        self._thread.start()

    def _serve(self) -> None:
        listener = self._listener
        if listener is None:
            return
        while not self._stop.is_set():
            try:
                connection, _address = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                connection.settimeout(3.0)
                response: dict[str, Any]
                try:
                    raw = bytearray()
                    while b"\n" not in raw:
                        chunk = connection.recv(65536)
                        if not chunk:
                            break
                        raw.extend(chunk)
                        if len(raw) > 64 * 1024:
                            raise ValueError("request exceeds 64 KiB")
                    request = json.loads(
                        bytes(raw).split(b"\n", 1)[0].decode("utf-8")
                    )
                    command = str(request.get("cmd", ""))
                    args = request.get("args", {})
                    if not isinstance(args, dict):
                        raise ValueError("args must be an object")
                    response = {"ok": True, "data": self._handler(command, args)}
                except Exception as exc:
                    response = {"ok": False, "error": str(exc)}
                try:
                    connection.sendall(
                        (
                            json.dumps(response, ensure_ascii=True, separators=(",", ":"))
                            + "\n"
                        ).encode("utf-8")
                    )
                except OSError:
                    pass

    def close(self) -> None:
        self._stop.set()
        if self._listener is not None:
            try:
                self._listener.close()
            except OSError:
                pass
            self._listener = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None


class A1ZCameraConsoleBridgeNode(_RosNode):
    def __init__(self) -> None:
        if _RosNode is object:
            raise RuntimeError("ROS 2 Python modules are required")
        super().__init__("a1z_camera_console_bridge")

        from rclpy.qos import (
            DurabilityPolicy,
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
        )
        from sensor_msgs.msg import CameraInfo, Image

        self._cfg = ConsoleBridgeConfig.from_env()
        self._lock = threading.Lock()
        self._color_messages: deque[Any] = deque(maxlen=8)
        self._depth_messages: deque[Any] = deque(maxlen=8)
        self._color_info: Any | None = None
        self._depth_info: Any | None = None
        self._last_color_monotonic = 0.0
        self._last_depth_monotonic = 0.0
        self._extrinsic: dict[str, Any] | None = None
        self._extrinsic_error = "尚未收到可解析的相机 TF"
        self._tf_resolver = RosTransformResolver(self, cache_time_s=10.0)

        sensor_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._subscriptions = (
            self.create_subscription(
                Image, self._cfg.color_topic, self._on_color, sensor_qos
            ),
            self.create_subscription(
                Image, self._cfg.depth_topic, self._on_depth, sensor_qos
            ),
            self.create_subscription(
                CameraInfo,
                self._cfg.color_info_topic,
                self._on_color_info,
                sensor_qos,
            ),
            self.create_subscription(
                CameraInfo,
                self._cfg.depth_info_topic,
                self._on_depth_info,
                sensor_qos,
            ),
        )
        self.create_timer(1.0, self._refresh_extrinsic)
        self._server = _JsonLineServer(
            host=self._cfg.host,
            port=self._cfg.port,
            handler=self._handle_request,
        )
        self._server.start()
        self.get_logger().info(
            "A1Z camera console bridge listening on "
            f"tcp://{self._cfg.host}:{self._cfg.port}; "
            f"RGB={self._cfg.color_topic}, depth={self._cfg.depth_topic}"
        )

    def _on_color(self, message: Any) -> None:
        with self._lock:
            self._color_messages.append(message)
            self._last_color_monotonic = time.monotonic()

    def _on_depth(self, message: Any) -> None:
        with self._lock:
            self._depth_messages.append(message)
            self._last_depth_monotonic = time.monotonic()

    def _on_color_info(self, message: Any) -> None:
        with self._lock:
            self._color_info = message

    def _on_depth_info(self, message: Any) -> None:
        with self._lock:
            self._depth_info = message

    def _synchronized_messages(
        self,
    ) -> tuple[Any, Any, Any, Any, int] | None:
        with self._lock:
            colors = list(self._color_messages)
            depths = list(self._depth_messages)
            color_info = self._color_info
            depth_info = self._depth_info
        if not colors or not depths or color_info is None or depth_info is None:
            return None
        slop_ns = int(self._cfg.sync_slop_s * 1_000_000_000)
        best: tuple[Any, Any, int] | None = None
        for color in reversed(colors):
            color_ns = _stamp_to_ns(color.header.stamp)
            for depth in reversed(depths):
                delta_ns = abs(color_ns - _stamp_to_ns(depth.header.stamp))
                if delta_ns <= slop_ns and (
                    best is None or delta_ns < best[2]
                ):
                    best = (color, depth, delta_ns)
        if best is None:
            return None
        return best[0], best[1], color_info, depth_info, best[2]

    def _base_payload(self) -> dict[str, Any]:
        return {
            "protocol_version": 1,
            "profile": self._cfg.profile,
            "camera_source": self._cfg.camera_source,
            "source_backend": f"{self._cfg.camera_source}_ros2",
            "bridge_endpoint": f"{self._cfg.host}:{self._cfg.port}",
            "color_topic": self._cfg.color_topic,
            "depth_topic": self._cfg.depth_topic,
            "color_camera_info_topic": self._cfg.color_info_topic,
            "depth_camera_info_topic": self._cfg.depth_info_topic,
            "target_frame_id": self._cfg.target_frame_id,
        }

    def _status_payload(self) -> dict[str, Any]:
        pair = self._synchronized_messages()
        with self._lock:
            color_age_s = (
                None
                if self._last_color_monotonic <= 0.0
                else max(0.0, time.monotonic() - self._last_color_monotonic)
            )
            depth_age_s = (
                None
                if self._last_depth_monotonic <= 0.0
                else max(0.0, time.monotonic() - self._last_depth_monotonic)
            )
            extrinsic_ready = self._extrinsic is not None
            extrinsic_error = self._extrinsic_error
        fresh = (
            color_age_s is not None
            and depth_age_s is not None
            and color_age_s <= self._cfg.stale_after_s
            and depth_age_s <= self._cfg.stale_after_s
        )
        payload = self._base_payload()
        payload.update(
            {
                "ready": pair is not None and fresh,
                "synchronized": pair is not None,
                "color_age_s": color_age_s,
                "depth_age_s": depth_age_s,
                "sync_delta_ms": None if pair is None else pair[4] / 1_000_000.0,
                "extrinsic_ready": extrinsic_ready,
                "extrinsic_error": extrinsic_error,
            }
        )
        if pair is not None:
            color, depth, _color_info, _depth_info, _delta = pair
            payload.update(
                {
                    "width": int(color.width),
                    "height": int(color.height),
                    "camera_frame_id": str(color.header.frame_id or ""),
                    "depth_frame_id": str(depth.header.frame_id or ""),
                    "rgb_encoding": str(color.encoding),
                    "depth_encoding": str(depth.encoding),
                }
            )
        return payload

    def _capture_payload(self, args: dict[str, Any]) -> dict[str, Any]:
        pair = self._synchronized_messages()
        if pair is None:
            raise RuntimeError(
                "尚未收到同步的 RGB、Depth 和 CameraInfo；请检查 ROS 相机主题"
            )
        with self._lock:
            now = time.monotonic()
            color_age_s = (
                float("inf")
                if self._last_color_monotonic <= 0.0
                else max(0.0, now - self._last_color_monotonic)
            )
            depth_age_s = (
                float("inf")
                if self._last_depth_monotonic <= 0.0
                else max(0.0, now - self._last_depth_monotonic)
            )
        if (
            color_age_s > self._cfg.stale_after_s
            or depth_age_s > self._cfg.stale_after_s
        ):
            raise RuntimeError(
                "RGB-D 帧已过期 "
                f"(RGB {color_age_s:.1f}s，Depth {depth_age_s:.1f}s)；"
                "请检查相机连接"
            )
        color_msg, depth_msg, color_info, _depth_info, delta_ns = pair
        rgb = _decode_color_image(color_msg)
        depth_m = _decode_depth_image(
            depth_msg,
            uint16_scale_m=self._cfg.depth_uint16_scale_m,
        )
        if rgb.shape[:2] != depth_m.shape:
            raise RuntimeError(
                f"RGB/depth 尺寸不一致：{rgb.shape[:2]} vs {depth_m.shape}"
            )
        requested_width = int(
            args.get("preview_max_width", self._cfg.preview_max_width)
        )
        requested_width = min(1600, max(320, requested_width))
        preview_png = compose_rgbd_preview_png(
            rgb,
            depth_m,
            max_width=requested_width,
            depth_range_m=(
                self._cfg.preview_depth_min_m,
                self._cfg.preview_depth_max_m,
            ),
        )
        valid_depth = depth_m[np.isfinite(depth_m) & (depth_m > 0.0)]
        payload = self._base_payload()
        payload.update(
            {
                "ready": True,
                "timestamp_ns": min(
                    _stamp_to_ns(color_msg.header.stamp),
                    _stamp_to_ns(depth_msg.header.stamp),
                ),
                "width": int(rgb.shape[1]),
                "height": int(rgb.shape[0]),
                "camera_frame_id": str(color_msg.header.frame_id or ""),
                "depth_frame_id": str(depth_msg.header.frame_id or ""),
                "rgb_encoding": str(color_msg.encoding),
                "depth_encoding": str(depth_msg.encoding),
                "sync_delta_ms": delta_ns / 1_000_000.0,
                "intrinsics": _camera_info_to_intrinsics(color_info),
                "valid_depth_ratio": float(valid_depth.size / depth_m.size),
                "depth_range_m": (
                    None
                    if valid_depth.size == 0
                    else [
                        float(np.min(valid_depth)),
                        float(np.max(valid_depth)),
                    ]
                ),
                "preview_depth_range_m": [
                    self._cfg.preview_depth_min_m,
                    self._cfg.preview_depth_max_m,
                ],
                "preview_mime": "image/png",
                "preview_png_b64": base64.b64encode(preview_png).decode("ascii"),
            }
        )
        return payload

    def _refresh_extrinsic(self) -> None:
        pair = self._synchronized_messages()
        if pair is None:
            return
        color_msg = pair[0]
        source_frame = str(color_msg.header.frame_id or "").strip()
        target_frame = self._cfg.target_frame_id
        if not source_frame or not target_frame:
            return
        try:
            if source_frame == target_frame:
                matrix = np.eye(4, dtype=np.float64)
                lookup_mode = "identity"
                resolved_stamp_ns = _stamp_to_ns(color_msg.header.stamp)
            else:
                result = self._tf_resolver.lookup_matrix(
                    target_frame_id=target_frame,
                    source_frame_id=source_frame,
                    stamp=color_msg.header.stamp,
                    timeout_s=0.0,
                    fallback_to_latest=True,
                )
                matrix = result.transform_matrix
                lookup_mode = result.lookup_mode
                resolved_stamp_ns = result.resolved_stamp_ns
            payload = self._base_payload()
            payload.update(
                {
                    "ready": True,
                    "timestamp_ns": _stamp_to_ns(color_msg.header.stamp),
                    "camera_frame_id": source_frame,
                    "target_frame_id": target_frame,
                    "lookup_mode": lookup_mode,
                    "resolved_stamp_ns": resolved_stamp_ns,
                    "extrinsic_camera_to_target": matrix.astype(float).tolist(),
                }
            )
            with self._lock:
                self._extrinsic = payload
                self._extrinsic_error = ""
        except Exception as exc:
            with self._lock:
                self._extrinsic_error = str(exc)

    def _handle_request(
        self,
        command: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        if command == "camera_status":
            return self._status_payload()
        if command == "camera_capture":
            return self._capture_payload(args)
        if command == "camera_extrinsic":
            with self._lock:
                payload = None if self._extrinsic is None else dict(self._extrinsic)
                error = self._extrinsic_error
            if payload is None:
                raise RuntimeError(error or "相机外参尚未就绪")
            return payload
        raise ValueError(f"unsupported camera bridge command: {command}")

    def destroy_node(self) -> bool:
        self._server.close()
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    import rclpy

    rclpy.init(args=args)
    node = A1ZCameraConsoleBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
