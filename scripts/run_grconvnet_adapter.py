#!/usr/bin/env python3

"""Adapt GR-ConvNet grasp maps into A1Z grasp candidates and plans."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = REPO_ROOT / "vendor" / "GALAXEA-A1Z"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from a1z_ext.config import get_socket_path
from a1z_ext.grasping import (
    GRConvNetA1ZAdapter,
    GRConvNetA1ZAdapterConfig,
    KeepoutSphere,
    to_dict,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adapt GR-ConvNet grasp maps to A1Z plans.")
    parser.add_argument("--quality-map", required=True)
    parser.add_argument("--angle-map-rad", required=True)
    parser.add_argument("--width-map-px", required=True)
    parser.add_argument("--crop-top", type=int, required=True)
    parser.add_argument("--crop-left", type=int, required=True)
    parser.add_argument("--crop-bottom", type=int, required=True)
    parser.add_argument("--crop-right", type=int, required=True)
    parser.add_argument("--depth", required=True)
    parser.add_argument("--intrinsics", required=True)
    parser.add_argument("--extrinsic-camera-to-base", required=True)
    parser.add_argument("--mask", default="")
    parser.add_argument("--current-joints-rad", default="")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--task-id", default="grconvnet-pick")
    parser.add_argument("--object-id", default="target-object")
    parser.add_argument("--backend", default="unknown")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "runtime" / "grconvnet_adapter"))
    parser.add_argument("--frame-id", default="robot_base_frame")
    parser.add_argument("--transform-source", default="extrinsic_camera_to_base")
    parser.add_argument("--end-effector-frame", default="arm_link6")
    parser.add_argument("--pregrasp-offset-m", type=float, default=0.08)
    parser.add_argument("--lift-offset-m", type=float, default=0.10)
    parser.add_argument("--retreat-offset-m", type=float, default=0.04)
    parser.add_argument("--table-height-m", type=float, default=0.0)
    parser.add_argument("--min-tool-height-above-table-m", type=float, default=0.005)
    parser.add_argument("--max-approach-deviation-deg", type=float, default=55.0)
    parser.add_argument("--max-gripper-opening-m", type=float, default=0.096)
    parser.add_argument("--pregrasp-opening-margin-m", type=float, default=0.008)
    parser.add_argument("--min-joint-margin-deg", type=float, default=5.0)
    parser.add_argument("--max-waypoint-delta-rad", type=float, default=2.5)
    parser.add_argument("--ee-grasp-origin-xyz-m", default="[-0.06, 0.0, 0.0]")
    parser.add_argument("--ee-opening-axis-xyz", default="[0.0, 0.8115343414514943, -0.5843047258450759]")
    parser.add_argument("--ee-approach-axis-xyz", default="[-1.0, 0.0, 0.0]")
    parser.add_argument("--keepout-sphere", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--min-quality", type=float, default=0.1)
    parser.add_argument("--peak-min-distance", type=int, default=12)
    return parser


def _parse_json_value(raw: str, *, expected_len: int | None = None) -> list[float]:
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"expected JSON list, got: {raw}")
    result = [float(item) for item in value]
    if expected_len is not None and len(result) != expected_len:
        raise ValueError(f"expected length {expected_len}, got {len(result)} from {raw}")
    return result


def _send_socket_request(socket_path: str, cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    request = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    try:
        sock.connect(socket_path)
        sock.sendall(request.encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        sock.close()
    if not data:
        raise RuntimeError(f"no response from A1Z server on {socket_path}")
    payload = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("error", "unknown server error")))
    return dict(payload.get("data", {}))


def _load_current_joints(value: str, *, socket_path: str) -> np.ndarray:
    if value:
        candidate = Path(value)
        if candidate.is_file():
            if candidate.suffix.lower() == ".npy":
                joints = np.load(candidate)
            else:
                joints = np.asarray(json.loads(candidate.read_text(encoding="utf-8")), dtype=np.float64)
        else:
            joints = np.asarray(json.loads(value), dtype=np.float64)
        joints = joints.reshape(-1)
        if joints.shape[0] != 6:
            raise ValueError(f"expected 6 current joints, got shape {joints.shape}")
        return joints.astype(np.float64)

    status = _send_socket_request(socket_path, "status")
    pos_deg = status.get("pos_deg")
    if not isinstance(pos_deg, list) or len(pos_deg) < 6:
        raise RuntimeError(f"unexpected status payload: {status}")
    return np.deg2rad(np.asarray(pos_deg[:6], dtype=np.float64))


def _parse_keepout_spheres(raw_values: list[str]) -> list[KeepoutSphere]:
    spheres: list[KeepoutSphere] = []
    for raw in raw_values:
        payload = json.loads(raw)
        center = payload.get("center_xyz")
        radius = payload.get("radius_m")
        if not isinstance(center, list) or len(center) != 3 or radius is None:
            raise ValueError(f"invalid keepout sphere: {raw}")
        spheres.append(
            KeepoutSphere(
                center_xyz=(float(center[0]), float(center[1]), float(center[2])),
                radius_m=float(radius),
                label=str(payload.get("label", "keepout")),
            )
        )
    return spheres


def _load_mask_array(path: str | Path) -> np.ndarray:
    mask = np.load(Path(path))
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")
    return mask.astype(bool)


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    quality_map = np.load(Path(args.quality_map)).astype(np.float32, copy=False)
    angle_map_rad = np.load(Path(args.angle_map_rad)).astype(np.float32, copy=False)
    width_map_px = np.load(Path(args.width_map_px)).astype(np.float32, copy=False)
    depth_m_full = np.load(Path(args.depth)).astype(np.float32, copy=False)
    intrinsics = json.loads(Path(args.intrinsics).read_text(encoding="utf-8"))
    extrinsic_camera_to_base = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError(
            f"extrinsic_camera_to_base must be 4x4, got {extrinsic_camera_to_base.shape}"
        )

    crop_top = int(args.crop_top)
    crop_left = int(args.crop_left)
    crop_bottom = int(args.crop_bottom)
    crop_right = int(args.crop_right)
    depth_m = depth_m_full[crop_top:crop_bottom, crop_left:crop_right]
    mask = None
    if args.mask:
        mask_full = _load_mask_array(args.mask)
        mask = mask_full[crop_top:crop_bottom, crop_left:crop_right]

    current_q = _load_current_joints(args.current_joints_rad, socket_path=args.socket_path)

    config = GRConvNetA1ZAdapterConfig(
        end_effector_frame=args.end_effector_frame,
        frame_id=args.frame_id,
        transform_source=args.transform_source,
        pregrasp_offset_m=args.pregrasp_offset_m,
        lift_offset_m=args.lift_offset_m,
        retreat_offset_m=args.retreat_offset_m,
        table_height_m=args.table_height_m,
        min_tool_height_above_table_m=args.min_tool_height_above_table_m,
        max_approach_deviation_deg=args.max_approach_deviation_deg,
        max_gripper_opening_m=args.max_gripper_opening_m,
        max_grasp_width_m=args.max_gripper_opening_m,
        pregrasp_opening_margin_m=args.pregrasp_opening_margin_m,
        min_joint_margin_deg=args.min_joint_margin_deg,
        max_waypoint_delta_rad=args.max_waypoint_delta_rad,
        ee_grasp_origin_xyz_m=tuple(_parse_json_value(args.ee_grasp_origin_xyz_m, expected_len=3)),
        ee_opening_axis_xyz=tuple(_parse_json_value(args.ee_opening_axis_xyz, expected_len=3)),
        ee_approach_axis_xyz=tuple(_parse_json_value(args.ee_approach_axis_xyz, expected_len=3)),
        keepout_spheres=_parse_keepout_spheres(args.keepout_sphere),
    )
    adapter = GRConvNetA1ZAdapter(config=config)
    result = adapter.plan_from_grasp_maps(
        quality_map=quality_map,
        angle_map_rad=angle_map_rad,
        width_map_px=width_map_px,
        depth_m=depth_m,
        intrinsics={
            "fx": float(intrinsics["fx"]),
            "fy": float(intrinsics["fy"]),
            "cx": float(intrinsics["cx"]) - float(crop_left),
            "cy": float(intrinsics["cy"]) - float(crop_top),
        },
        extrinsic_camera_to_base=extrinsic_camera_to_base,
        current_q=current_q,
        task_id=args.task_id,
        object_id=args.object_id,
        backend=args.backend,
        mask=mask,
        top_k=args.top_k,
        min_quality=args.min_quality,
        peak_local_max_min_distance=args.peak_min_distance,
    )

    result_path = output_dir / "grconvnet_adapter_result.json"
    write_json(result_path, result)
    print(json.dumps({"result_path": str(result_path), "summary": result.summary}, ensure_ascii=True))
    return 0 if result.selected_plan is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
