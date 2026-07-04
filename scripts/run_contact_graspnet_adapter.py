#!/usr/bin/env python3

"""Adapt Contact-GraspNet predictions into A1Z grasp candidates and plans."""

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
    ContactGraspNetA1ZAdapter,
    ContactGraspNetA1ZAdapterConfig,
    KeepoutSphere,
    to_dict,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Contact-GraspNet outputs into A1Z executable grasp plans."
    )
    parser.add_argument(
        "--predictions",
        required=True,
        help="Path to Contact-GraspNet .npz result file containing pred_grasps_cam/scores/contact_pts.",
    )
    parser.add_argument(
        "--extrinsic-camera-to-base",
        required=True,
        help="Path to 4x4 extrinsic_camera_to_base.npy.",
    )
    parser.add_argument(
        "--current-joints-rad",
        default="",
        help="Optional JSON/NPY path or inline JSON list with the current 6-joint arm configuration in radians.",
    )
    parser.add_argument(
        "--socket-path",
        default=get_socket_path(),
        help="A1Z control socket for reading live current joints when --current-joints-rad is omitted.",
    )
    parser.add_argument("--task-id", default="contact-graspnet-pick")
    parser.add_argument("--object-id", default="target-object")
    parser.add_argument("--backend", default="unknown")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "runtime" / "contact_graspnet_adapter"),
        help="Directory for candidate/plan JSON artifacts.",
    )
    parser.add_argument("--frame-id", default="robot_base_frame")
    parser.add_argument("--transform-source", default="extrinsic_camera_to_base")
    parser.add_argument("--end-effector-frame", default="grasp_tcp")
    parser.add_argument("--pregrasp-offset-m", type=float, default=0.15)
    parser.add_argument("--lift-offset-m", type=float, default=0.10)
    parser.add_argument("--retreat-offset-m", type=float, default=0.04)
    parser.add_argument("--table-height-m", type=float, default=0.0)
    parser.add_argument("--min-tool-height-above-table-m", type=float, default=0.005)
    parser.add_argument("--max-approach-deviation-deg", type=float, default=55.0)
    parser.add_argument("--max-gripper-opening-m", type=float, default=0.096)
    parser.add_argument("--pregrasp-opening-margin-m", type=float, default=0.008)
    parser.add_argument("--min-joint-margin-deg", type=float, default=5.0)
    parser.add_argument("--max-waypoint-delta-rad", type=float, default=2.5)
    parser.add_argument(
        "--ee-grasp-origin-xyz-m",
        default="[0.0, 0.0, 0.0]",
        help="Grasp center expressed in the end-effector frame.",
    )
    parser.add_argument(
        "--ee-opening-axis-xyz",
        default="[0.0, 1.0, 0.0]",
        help="Parallel-jaw opening axis expressed in the end-effector frame.",
    )
    parser.add_argument(
        "--ee-approach-axis-xyz",
        default="[1.0, 0.0, 0.0]",
        help="Tool forward/approach axis expressed in the end-effector frame.",
    )
    parser.add_argument(
        "--keepout-sphere",
        action="append",
        default=[],
        help="Optional keepout sphere as JSON: {\"center_xyz\":[x,y,z],\"radius_m\":r,\"label\":\"cam\"}",
    )
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


def _load_predictions(path: str | Path) -> dict[str, Any]:
    prediction_file = Path(path)
    if prediction_file.suffix.lower() != ".npz":
        raise ValueError(f"predictions file must be .npz, got: {prediction_file}")
    data = np.load(prediction_file, allow_pickle=True)
    payload = {key: data[key] for key in data.files}
    if "pred_grasps_cam" not in payload or "scores" not in payload:
        raise ValueError(f"{prediction_file} must contain pred_grasps_cam and scores")
    return payload


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


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions = _load_predictions(args.predictions)
    current_q = _load_current_joints(args.current_joints_rad, socket_path=args.socket_path)
    extrinsic_camera_to_base = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError(
            f"extrinsic_camera_to_base must be 4x4, got {extrinsic_camera_to_base.shape}"
        )

    config = ContactGraspNetA1ZAdapterConfig(
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
        pregrasp_opening_margin_m=args.pregrasp_opening_margin_m,
        min_joint_margin_deg=args.min_joint_margin_deg,
        max_waypoint_delta_rad=args.max_waypoint_delta_rad,
        ee_grasp_origin_xyz_m=tuple(_parse_json_value(args.ee_grasp_origin_xyz_m, expected_len=3)),
        ee_opening_axis_xyz=tuple(_parse_json_value(args.ee_opening_axis_xyz, expected_len=3)),
        ee_approach_axis_xyz=tuple(_parse_json_value(args.ee_approach_axis_xyz, expected_len=3)),
        keepout_spheres=_parse_keepout_spheres(args.keepout_sphere),
    )
    adapter = ContactGraspNetA1ZAdapter(config=config)
    result = adapter.plan(
        pred_grasps_cam=predictions["pred_grasps_cam"],
        scores=predictions["scores"],
        gripper_openings_m=predictions.get("gripper_openings", predictions.get("widths")),
        contact_points_cam=predictions.get("contact_pts"),
        extrinsic_camera_to_base=extrinsic_camera_to_base,
        current_q=current_q,
        task_id=args.task_id,
        object_id=args.object_id,
        backend=args.backend,
    )

    result_path = output_dir / "contact_graspnet_adapter_result.json"
    write_json(result_path, result)
    print(json.dumps({"result_path": str(result_path), "summary": result.summary}, ensure_ascii=True))
    if result.selected_plan is not None:
        plan_path = output_dir / "selected_plan.json"
        write_json(plan_path, result.selected_plan)
    return 0 if result.selected_plan is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
