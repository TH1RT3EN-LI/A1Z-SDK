#!/usr/bin/env python3

"""Capture one ROS image frame to disk using the shared image-input helper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.runtime.image_input import resolve_image_input


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture one ROS image frame to disk.")
    parser.add_argument("--ros-topic", required=True, help="ROS image topic.")
    parser.add_argument("--output", required=True, help="Output PNG path.")
    parser.add_argument("--timeout-s", type=float, default=10.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = resolve_image_input(
        image_arg="",
        ros_topic=args.ros_topic,
        ros_timeout_s=args.timeout_s,
        capture_path_arg=args.output,
        default_capture_path=args.output,
    )
    print(
        json.dumps(
            {
                "image_path": str(result.image_path),
                "width": int(result.width),
                "height": int(result.height),
                "source_metadata": result.source_metadata,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
