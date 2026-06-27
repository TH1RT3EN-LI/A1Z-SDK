"""Encode ROS Image messages into PNG data URLs for VLM requests."""

from __future__ import annotations

from binascii import crc32
import struct
import zlib

from sensor_msgs.msg import Image

from a1z_ext.llm.images import bytes_to_data_url


class ImageEncodingError(ValueError):
    """Raised when a ROS image cannot be encoded for a VLM request."""


def ros_image_to_png_data_url(message: Image) -> str:
    png = ros_image_to_png_bytes(message)
    return bytes_to_data_url(png, mime_type="image/png")


def ros_image_to_png_bytes(message: Image) -> bytes:
    encoding = message.encoding.lower()
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

    raise ImageEncodingError(f"unsupported ROS image encoding for VLM request: {message.encoding}")


def _extract_rows(message: Image, *, channels: int) -> list[bytes]:
    width = int(message.width)
    height = int(message.height)
    row_size = width * channels
    step = int(message.step)
    data = bytes(message.data)

    if width <= 0 or height <= 0:
        raise ImageEncodingError("image width and height must be positive")
    if step < row_size:
        raise ImageEncodingError(
            f"image step {step} is smaller than expected row size {row_size}"
        )
    if len(data) < step * height:
        raise ImageEncodingError("image data is shorter than step * height")

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
    if len(rows) != height:
        raise ImageEncodingError("row count does not match image height")

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
