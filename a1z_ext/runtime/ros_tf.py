"""ROS 2 TF helpers for reusable camera-frame to target-frame resolution."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import numpy as np


def quaternion_xyzw_to_matrix(quaternion_xyzw: list[float] | tuple[float, float, float, float]) -> np.ndarray:
    x, y, z, w = [float(v) for v in quaternion_xyzw]
    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def transform_stamped_to_matrix(transform: Any) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = quaternion_xyzw_to_matrix(
        [
            transform.transform.rotation.x,
            transform.transform.rotation.y,
            transform.transform.rotation.z,
            transform.transform.rotation.w,
        ]
    )
    matrix[:3, 3] = np.array(
        [
            transform.transform.translation.x,
            transform.transform.translation.y,
            transform.transform.translation.z,
        ],
        dtype=np.float64,
    )
    return matrix


def _stamp_to_ns(stamp: Any | None) -> int | None:
    if stamp is None:
        return None
    if hasattr(stamp, "nanoseconds"):
        return int(stamp.nanoseconds)
    if hasattr(stamp, "sec") and hasattr(stamp, "nanosec"):
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    return None


def _coerce_time(stamp: Any | None):
    import rclpy

    if stamp is None:
        return rclpy.time.Time()
    if hasattr(stamp, "nanoseconds"):
        return stamp
    if hasattr(stamp, "sec") and hasattr(stamp, "nanosec"):
        return rclpy.time.Time.from_msg(stamp)
    if isinstance(stamp, (int, np.integer)):
        ns = int(stamp)
        sec = ns // 1_000_000_000
        nanosec = ns % 1_000_000_000
        return rclpy.time.Time(seconds=sec, nanoseconds=nanosec)
    raise TypeError(f"unsupported ROS time value: {type(stamp)!r}")


@dataclass(slots=True)
class LookupTransformResult:
    transform_matrix: np.ndarray
    source_frame_id: str
    target_frame_id: str
    lookup_mode: str
    requested_stamp_ns: int | None
    resolved_stamp_ns: int | None


class RosTransformResolver:
    """Resolve TF transforms into 4x4 matrices on a caller-managed ROS node."""

    def __init__(self, node: Any, *, cache_time_s: float = 10.0) -> None:
        from rclpy.duration import Duration
        from tf2_ros import Buffer, TransformListener

        self._node = node
        self._buffer = Buffer(cache_time=Duration(seconds=float(cache_time_s)))
        self._listener = TransformListener(self._buffer, node, spin_thread=False)

    def lookup_matrix(
        self,
        *,
        target_frame_id: str,
        source_frame_id: str,
        stamp: Any | None = None,
        timeout_s: float = 1.0,
        fallback_to_latest: bool = True,
    ) -> LookupTransformResult:
        import rclpy
        from rclpy.duration import Duration
        from tf2_ros import TransformException

        source = str(source_frame_id or "").strip()
        target = str(target_frame_id or "").strip()
        if not source:
            raise ValueError("source_frame_id must be non-empty")
        if not target:
            raise ValueError("target_frame_id must be non-empty")

        attempts: list[tuple[str, Any]] = []
        if stamp is not None:
            attempts.append(("exact_stamp", _coerce_time(stamp)))
        if fallback_to_latest or stamp is None:
            attempts.append(("latest", rclpy.time.Time()))

        timeout_s = max(0.0, float(timeout_s))
        deadline = time.monotonic() + timeout_s
        poll_timeout_s = 0.05
        errors_by_mode: dict[str, str] = {}
        first_pass = True

        while first_pass or time.monotonic() <= deadline:
            first_pass = False
            for mode, lookup_time in attempts:
                try:
                    transform = self._buffer.lookup_transform(
                        target,
                        source,
                        lookup_time,
                        timeout=Duration(seconds=0.0),
                    )
                except TransformException as exc:
                    errors_by_mode[mode] = str(exc)
                    continue

                return LookupTransformResult(
                    transform_matrix=transform_stamped_to_matrix(transform),
                    source_frame_id=source,
                    target_frame_id=target,
                    lookup_mode=mode,
                    requested_stamp_ns=_stamp_to_ns(stamp),
                    resolved_stamp_ns=_stamp_to_ns(transform.header.stamp),
                )

            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0.0 or not rclpy.ok():
                break
            rclpy.spin_once(self._node, timeout_sec=min(poll_timeout_s, remaining_s))

        errors = [f"{mode}: {errors_by_mode[mode]}" for mode, _ in attempts if mode in errors_by_mode]
        joined = "; ".join(errors) if errors else "no lookup attempts were made"
        raise RuntimeError(f"could not resolve TF {source!r} -> {target!r}: {joined}")
