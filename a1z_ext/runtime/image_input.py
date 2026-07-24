"""Shared image input helpers for file- and ROS-backed VLM workflows."""

from __future__ import annotations

from binascii import crc32
from dataclasses import dataclass
import os
from pathlib import Path
import struct
import time
from typing import Any

from a1z_ext.llm import LLMImage
from a1z_ext.llm.images import bytes_to_data_url


@dataclass(frozen=True, slots=True)
class ResolvedImageInput:
    image_path: Path
    width: int
    height: int
    data_url: str
    source_metadata: dict[str, Any]


def load_env_file(path: str | Path) -> None:
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def read_image_size(path: str | Path) -> tuple[int, int]:
    data = Path(path).read_bytes()
    if len(data) < 24:
        raise ValueError(f"image file too small: {path}")

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)

    if data[:2] == b"\xff\xd8":
        index = 2
        length = len(data)
        while index + 9 < length:
            while index < length and data[index] == 0xFF:
                index += 1
            if index >= length:
                break
            marker = data[index]
            index += 1
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if index + 2 > length:
                break
            segment_size = struct.unpack(">H", data[index : index + 2])[0]
            if segment_size < 2 or index + segment_size > length:
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                if index + 7 > length:
                    break
                height, width = struct.unpack(">HH", data[index + 3 : index + 7])
                return int(width), int(height)
            index += segment_size
        raise ValueError(f"could not parse JPEG size: {path}")

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height

    raise ValueError(f"unsupported image format for size probing: {path}")


def capture_ros_image_png_bytes(
    *,
    ros_topic: str,
    timeout_s: float,
) -> tuple[bytes, dict[str, Any]]:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import (
        DurabilityPolicy,
        HistoryPolicy,
        QoSProfile,
        ReliabilityPolicy,
    )
    from sensor_msgs.msg import Image as RosImage

    class OneShotImageNode(Node):
        def __init__(self) -> None:
            super().__init__("a1z_image_capture")
            self.message: RosImage | None = None
            qos = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                reliability=ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.VOLATILE,
            )
            self.subscription = self.create_subscription(
                RosImage,
                ros_topic,
                self._handle_image,
                qos,
            )

        def _handle_image(self, message: RosImage) -> None:
            self.message = message

    rclpy.init(args=None)
    node = OneShotImageNode()
    deadline = time.monotonic() + timeout_s
    try:
        while rclpy.ok() and node.message is None and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
        if node.message is None:
            raise TimeoutError(f"timed out waiting for ROS image on topic {ros_topic}")
        message = node.message
        png_bytes = ros_image_to_png_bytes(message)
        metadata = {
            "source": "ros_topic",
            "ros_topic": ros_topic,
            "encoding": message.encoding,
            "width": int(message.width),
            "height": int(message.height),
            "step": int(message.step),
            "header": {
                "frame_id": str(message.header.frame_id),
                "stamp_sec": int(message.header.stamp.sec),
                "stamp_nanosec": int(message.header.stamp.nanosec),
            },
        }
        return png_bytes, metadata
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def ros_image_to_png_bytes(message: Any) -> bytes:
    encoding = str(message.encoding).lower()
    if encoding in {"rgb8", "bgr8"}:
        rows = _extract_rows(message, channels=3)
        if encoding == "bgr8":
            rows = [_bgr_to_rgb(row) for row in rows]
        return _encode_png(width=message.width, height=message.height, rows=rows, color_type=2)

    if encoding in {"rgba8", "bgra8"}:
        rows = _extract_rows(message, channels=4)
        if encoding == "bgra8":
            rows = [_bgra_to_rgba(row) for row in rows]
        return _encode_png(width=message.width, height=message.height, rows=rows, color_type=6)

    if encoding in {"mono8", "8uc1"}:
        rows = _extract_rows(message, channels=1)
        return _encode_png(width=message.width, height=message.height, rows=rows, color_type=0)

    raise ValueError(f"unsupported ROS image encoding for PNG conversion: {message.encoding}")


def _extract_rows(message: Any, *, channels: int) -> list[bytes]:
    width = int(message.width)
    height = int(message.height)
    row_size = width * channels
    step = int(message.step)
    data = bytes(message.data)

    if width <= 0 or height <= 0:
        raise ValueError("image width and height must be positive")
    if step < row_size:
        raise ValueError(f"image step {step} is smaller than expected row size {row_size}")
    if len(data) < step * height:
        raise ValueError("image data is shorter than step * height")

    return [data[y * step : y * step + row_size] for y in range(height)]


def _bgr_to_rgb(row: bytes) -> bytes:
    converted = bytearray(len(row))
    for idx in range(0, len(row), 3):
        converted[idx] = row[idx + 2]
        converted[idx + 1] = row[idx + 1]
        converted[idx + 2] = row[idx]
    return bytes(converted)


def _bgra_to_rgba(row: bytes) -> bytes:
    converted = bytearray(len(row))
    for idx in range(0, len(row), 4):
        converted[idx] = row[idx + 2]
        converted[idx + 1] = row[idx + 1]
        converted[idx + 2] = row[idx]
        converted[idx + 3] = row[idx + 3]
    return bytes(converted)


def _encode_png(*, width: int, height: int, rows: list[bytes], color_type: int) -> bytes:
    import zlib

    if len(rows) != height:
        raise ValueError("row count does not match image height")
    raw = b"".join(b"\x00" + row for row in rows)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(
                b"IHDR",
                struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0),
            ),
            _png_chunk(b"IDAT", zlib.compress(raw)),
            _png_chunk(b"IEND", b""),
        ]
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def resolve_image_input(
    *,
    image_arg: str,
    ros_topic: str,
    ros_timeout_s: float,
    capture_path_arg: str,
    default_capture_path: str | Path,
) -> ResolvedImageInput:
    has_file = bool(image_arg.strip())
    has_ros = bool(ros_topic.strip())
    if has_file == has_ros:
        raise ValueError("exactly one of --image or --ros-topic must be provided")

    if has_file:
        image_path = Path(image_arg).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"image not found: {image_path}")
        width, height = read_image_size(image_path)
        return ResolvedImageInput(
            image_path=image_path,
            width=width,
            height=height,
            data_url=LLMImage.from_file(image_path).data_url,
            source_metadata={
                "source": "file",
                "image_path": str(image_path),
            },
        )

    png_bytes, ros_metadata = capture_ros_image_png_bytes(
        ros_topic=ros_topic.strip(),
        timeout_s=ros_timeout_s,
    )
    capture_path = (
        Path(capture_path_arg).resolve()
        if capture_path_arg.strip()
        else Path(default_capture_path).resolve()
    )
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    capture_path.write_bytes(png_bytes)
    ros_metadata["image_path"] = str(capture_path)
    return ResolvedImageInput(
        image_path=capture_path,
        width=int(ros_metadata["width"]),
        height=int(ros_metadata["height"]),
        data_url=bytes_to_data_url(png_bytes, mime_type="image/png"),
        source_metadata=ros_metadata,
    )
