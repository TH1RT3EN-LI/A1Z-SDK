#!/usr/bin/env python3

"""Resolve one ROS TF edge into a reusable 4x4 transform artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.runtime.ros_tf import RosTransformResolver


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve ROS TF into a .npy matrix.")
    parser.add_argument("--source-frame-id", default="")
    parser.add_argument("--target-frame-id", default="robot_base_frame")
    parser.add_argument("--observation-json", default="")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--timeout-s", type=float, default=2.0)
    parser.add_argument("--cache-time-s", type=float, default=10.0)
    parser.add_argument("--allow-latest", action="store_true")
    return parser


def _load_observation(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    import rclpy
    from rclpy.node import Node

    args = build_parser().parse_args()
    observation = None
    source_frame_id = str(args.source_frame_id or "").strip()
    target_frame_id = str(args.target_frame_id or "").strip()
    stamp = None

    if args.observation_json:
        observation = _load_observation(Path(args.observation_json))
        if not source_frame_id:
            source_frame_id = str(observation.get("camera_frame_id", "") or "").strip()
        if not target_frame_id:
            target_frame_id = str(observation.get("target_frame_id", "") or "").strip()
        timestamp_ns = observation.get("timestamp_ns")
        if timestamp_ns is not None:
            stamp = int(timestamp_ns)

    if not source_frame_id:
        raise ValueError("source_frame_id is required, either directly or via --observation-json")
    if not target_frame_id:
        raise ValueError("target_frame_id is required")

    rclpy.init(args=None)
    node = Node("a1z_resolve_ros_tf")
    try:
        resolver = RosTransformResolver(node, cache_time_s=float(args.cache_time_s))
        deadline_ns = node.get_clock().now().nanoseconds + int(max(0.1, float(args.timeout_s)) * 1_000_000_000)
        while rclpy.ok() and node.get_clock().now().nanoseconds < deadline_ns:
            rclpy.spin_once(node, timeout_sec=0.1)
        result = resolver.lookup_matrix(
            target_frame_id=target_frame_id,
            source_frame_id=source_frame_id,
            stamp=stamp,
            timeout_s=float(args.timeout_s),
            fallback_to_latest=bool(args.allow_latest),
        )
        output_path = Path(args.output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, result.transform_matrix.astype(np.float64))
        print(
            json.dumps(
                {
                    "output_path": str(output_path),
                    "source_frame_id": result.source_frame_id,
                    "target_frame_id": result.target_frame_id,
                    "lookup_mode": result.lookup_mode,
                    "requested_stamp_ns": result.requested_stamp_ns,
                    "resolved_stamp_ns": result.resolved_stamp_ns,
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
