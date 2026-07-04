#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.runtime.ros_env import ensure_ros_logging_env
from a1z_ext.runtime.ros_tf import RosTransformResolver


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query one ROS TF as a JSON matrix payload.")
    parser.add_argument("--source-frame-id", default="d405_color_optical_frame")
    parser.add_argument("--target-frame-id", default="base_link")
    parser.add_argument("--timeout-s", type=float, default=5.0)
    parser.add_argument("--warmup-s", type=float, default=1.5)
    parser.add_argument("--cache-time-s", type=float, default=10.0)
    parser.add_argument("--allow-latest", action="store_true")
    parser.add_argument("--retry-count", type=int, default=3)
    parser.add_argument("--retry-sleep-s", type=float, default=0.5)
    parser.add_argument("--output", default="")
    return parser


def _matrix_payload(transform: np.ndarray) -> dict[str, object]:
    t = np.asarray(transform, dtype=np.float64)
    rot = t[:3, :3]
    sy = math.hypot(float(rot[0, 0]), float(rot[1, 0]))
    singular = sy < 1e-9
    if not singular:
        roll = math.degrees(math.atan2(float(rot[2, 1]), float(rot[2, 2])))
        pitch = math.degrees(math.atan2(float(-rot[2, 0]), sy))
        yaw = math.degrees(math.atan2(float(rot[1, 0]), float(rot[0, 0])))
    else:
        roll = math.degrees(math.atan2(float(-rot[1, 2]), float(rot[1, 1])))
        pitch = math.degrees(math.atan2(float(-rot[2, 0]), sy))
        yaw = 0.0
    return {
        "matrix": [[float(v) for v in row] for row in t.tolist()],
        "xyz_m": [float(v) for v in t[:3, 3].tolist()],
        "rpy_deg": [roll, pitch, yaw],
    }


def main() -> int:
    import rclpy
    from rclpy.node import Node

    args = _build_parser().parse_args()
    ensure_ros_logging_env()
    rclpy.init(args=None)
    node = Node("a1z_query_ros_tf_matrix")
    try:
        resolver = RosTransformResolver(node, cache_time_s=float(args.cache_time_s))
        warmup_deadline_ns = node.get_clock().now().nanoseconds + int(max(0.0, float(args.warmup_s)) * 1_000_000_000)
        while rclpy.ok() and node.get_clock().now().nanoseconds < warmup_deadline_ns:
            rclpy.spin_once(node, timeout_sec=0.1)
        last_error: Exception | None = None
        result = None
        retry_count = max(1, int(args.retry_count))
        retry_sleep_s = max(0.0, float(args.retry_sleep_s))
        for attempt_idx in range(retry_count):
            try:
                result = resolver.lookup_matrix(
                    target_frame_id=str(args.target_frame_id).strip(),
                    source_frame_id=str(args.source_frame_id).strip(),
                    timeout_s=float(args.timeout_s),
                    fallback_to_latest=bool(args.allow_latest),
                )
                break
            except Exception as exc:
                last_error = exc
                if attempt_idx + 1 >= retry_count:
                    raise
                sleep_deadline = time.monotonic() + retry_sleep_s
                while rclpy.ok() and time.monotonic() < sleep_deadline:
                    rclpy.spin_once(node, timeout_sec=min(0.1, max(0.0, sleep_deadline - time.monotonic())))
        if result is None:
            assert last_error is not None
            raise last_error
        report = {
            "source": "ros_tf",
            "source_frame_id": result.source_frame_id,
            "target_frame_id": result.target_frame_id,
            "lookup_mode": result.lookup_mode,
            "requested_stamp_ns": result.requested_stamp_ns,
            "resolved_stamp_ns": result.resolved_stamp_ns,
            "transform": _matrix_payload(result.transform_matrix),
        }
        payload = json.dumps(report, ensure_ascii=True, indent=2)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
