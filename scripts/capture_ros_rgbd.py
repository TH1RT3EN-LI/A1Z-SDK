#!/usr/bin/env python3

"""Capture one ROS RGB-D frame and persist reusable artifacts to disk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.interfaces.schemas import write_json
from a1z_ext.config import get_socket_path, get_tcp_host, get_tcp_port
from a1z_ext.control_client import send_control_request
from a1z_ext.runtime.frame_sources import RosRGBDFrameSource
from a1z_ext.runtime.image_input import _encode_png


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture one ROS RGB-D frame to disk.")
    parser.add_argument("--color-topic", default="/a1z/d405/color/image_raw")
    parser.add_argument("--depth-topic", default="/a1z/d405/depth/image_rect")
    parser.add_argument("--color-camera-info-topic", default="/a1z/d405/color/camera_info")
    parser.add_argument("--depth-camera-info-topic", default="/a1z/d405/depth/camera_info")
    parser.add_argument("--target-frame-id", default="base_link")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--sync-slop-s", type=float, default=0.25)
    parser.add_argument("--depth-uint16-scale-m", type=float, default=0.001)
    parser.add_argument("--tf-lookup-timeout-s", type=float, default=1.0)
    parser.add_argument("--tf-cache-time-s", type=float, default=10.0)
    parser.add_argument("--fail-if-tf-unavailable", action="store_true")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--tcp-host", default=get_tcp_host())
    parser.add_argument("--tcp-port", type=int, default=get_tcp_port())
    parser.add_argument("--output-dir", required=True, help="Directory for color/depth/intrinsics artifacts.")
    return parser


def _write_rgb_png(path: Path, rgb: np.ndarray) -> None:
    array = np.ascontiguousarray(rgb.astype(np.uint8, copy=False))
    rows = [array[row_idx].tobytes() for row_idx in range(array.shape[0])]
    path.write_bytes(
        _encode_png(
            width=int(array.shape[1]),
            height=int(array.shape[0]),
            rows=rows,
            color_type=2,
        )
    )


def _capture_current_joints_rad(socket_path: str, *, tcp_host: str, tcp_port: int) -> list[float] | None:
    try:
        status = send_control_request(
            "status",
            socket_path=socket_path,
            tcp_host=tcp_host,
            tcp_port=tcp_port,
        )
    except Exception:
        return None
    pos_deg = status.get("pos_deg")
    if not isinstance(pos_deg, list) or len(pos_deg) < 6:
        return None
    joints = np.deg2rad(np.asarray(pos_deg[:6], dtype=np.float64))
    return joints.astype(float).tolist()


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    capture = RosRGBDFrameSource(
        color_topic=args.color_topic,
        depth_topic=args.depth_topic,
        color_camera_info_topic=args.color_camera_info_topic,
        depth_camera_info_topic=args.depth_camera_info_topic,
        timeout_s=args.timeout_s,
        sync_slop_s=args.sync_slop_s,
        depth_uint16_scale_m=args.depth_uint16_scale_m,
        sensor_model="ros_d405",
        target_frame_id=args.target_frame_id,
        tf_lookup_timeout_s=args.tf_lookup_timeout_s,
        tf_cache_time_s=args.tf_cache_time_s,
        fail_if_tf_unavailable=bool(args.fail_if_tf_unavailable),
    ).capture()

    rgb_png_path = output_dir / "color.png"
    rgb_npy_path = output_dir / "rgb.npy"
    depth_npy_path = output_dir / "depth_m.npy"
    intrinsics_path = output_dir / "intrinsics.json"
    observation_path = output_dir / "observation.json"
    metadata_path = output_dir / "capture_metadata.json"
    extrinsic_target_path = output_dir / "extrinsic_camera_to_target.npy"
    extrinsic_base_path = output_dir / "extrinsic_camera_to_base.npy"
    current_joints_path = output_dir / "current_joints_rad.json"

    _write_rgb_png(rgb_png_path, capture.rgb[:, :, :3])
    np.save(rgb_npy_path, capture.rgb[:, :, :3])
    np.save(depth_npy_path, capture.depth_m.astype(np.float32, copy=False))
    extrinsic_matrix = capture.observation.extrinsic_matrix()
    np.save(extrinsic_target_path, extrinsic_matrix)
    if capture.observation.target_frame_id in {"robot_base_frame", "base_link"}:
        np.save(extrinsic_base_path, extrinsic_matrix)
    intrinsics_path.write_text(
        json.dumps(capture.observation.intrinsics_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    write_json(observation_path, capture.observation)
    metadata_path.write_text(json.dumps(capture.source_info, ensure_ascii=True, indent=2), encoding="utf-8")
    current_joints_rad = _capture_current_joints_rad(
        args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
    )
    if current_joints_rad is not None:
        current_joints_path.write_text(json.dumps(current_joints_rad, ensure_ascii=True, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "rgb_png_path": str(rgb_png_path),
                "rgb_npy_path": str(rgb_npy_path),
                "depth_npy_path": str(depth_npy_path),
                "intrinsics_path": str(intrinsics_path),
                "observation_path": str(observation_path),
                "metadata_path": str(metadata_path),
                "extrinsic_target_path": str(extrinsic_target_path),
                "extrinsic_base_path": str(extrinsic_base_path) if extrinsic_base_path.is_file() else None,
                "current_joints_path": str(current_joints_path) if current_joints_path.is_file() else None,
                "width": int(capture.rgb.shape[1]),
                "height": int(capture.rgb.shape[0]),
                "camera_frame_id": capture.observation.camera_frame_id,
                "target_frame_id": capture.observation.target_frame_id,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
