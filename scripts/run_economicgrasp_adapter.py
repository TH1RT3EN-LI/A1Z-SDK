#!/usr/bin/env python3

"""Adapt EconomicGrasp predictions into A1Z grasp candidates and plans."""

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
    EconomicGraspA1ZAdapter,
    EconomicGraspA1ZAdapterConfig,
    KeepoutSphere,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adapt EconomicGrasp outputs to A1Z plans.")
    parser.add_argument("--predictions", required=True, help="Path to EconomicGrasp raw_predictions.npy")
    parser.add_argument("--extrinsic-camera-to-base", required=True, help="Path to 4x4 extrinsic_camera_to_base.npy")
    parser.add_argument("--current-joints-rad", default="")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--task-id", default="economicgrasp-pick")
    parser.add_argument("--object-id", default="target-object")
    parser.add_argument("--backend", default="unknown")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "runtime" / "economicgrasp_adapter"))
    parser.add_argument("--frame-id", default="robot_base_frame")
    parser.add_argument("--transform-source", default="extrinsic_camera_to_base")
    parser.add_argument("--end-effector-frame", default="arm_link6")
    parser.add_argument("--pregrasp-offset-m", type=float, default=0.08)
    parser.add_argument("--lift-offset-m", type=float, default=0.10)
    parser.add_argument("--retreat-offset-m", type=float, default=0.04)
    parser.add_argument("--table-height-m", type=float, default=0.0)
    parser.add_argument("--min-tool-height-above-table-m", type=float, default=0.005)
    parser.add_argument("--max-approach-deviation-deg", type=float, default=85.0)
    parser.add_argument("--max-gripper-opening-m", type=float, default=0.096)
    parser.add_argument("--pregrasp-opening-margin-m", type=float, default=0.008)
    parser.add_argument("--min-joint-margin-deg", type=float, default=5.0)
    parser.add_argument("--max-waypoint-delta-rad", type=float, default=2.5)
    parser.add_argument("--ik-dt", type=float, default=0.01)
    parser.add_argument("--ik-pos-threshold-m", type=float, default=5e-4)
    parser.add_argument("--ik-ori-threshold-rad", type=float, default=5e-3)
    parser.add_argument("--ik-damping", type=float, default=1e-6)
    parser.add_argument("--ik-max-iters", type=int, default=800)
    parser.add_argument("--approach-linear-waypoint-count", type=int, default=2)
    parser.add_argument("--ee-grasp-origin-xyz-m", default="[0.0727, 0.0, 0.0]")
    parser.add_argument("--ee-opening-axis-xyz", default="[0.0, 1.0, 0.0]")
    parser.add_argument("--ee-approach-axis-xyz", default="[1.0, 0.0, 0.0]")
    parser.add_argument("--keepout-sphere", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=64)
    parser.add_argument("--depth-bias-m", type=float, default=0.0)
    parser.add_argument("--grasp-center-is-contact-center", action="store_true")
    parser.add_argument("--require-approach-downward", action="store_true")
    parser.add_argument("--intrinsics", default="", help="Optional intrinsics.json used for mask filtering")
    parser.add_argument("--mask", default="", help="Optional selected_mask.npy used to keep only target-object grasps")
    parser.add_argument(
        "--approach-axis-modes",
        default='["c2", "c0"]',
        help='EconomicGrasp approach-axis variants, e.g. ["c2","mc2","c0"]',
    )
    parser.add_argument(
        "--opening-axis-modes",
        default='["mc1", "c1"]',
        help='EconomicGrasp opening-axis variants, e.g. ["mc1","c1"]',
    )
    parser.add_argument(
        "--center-shift-depth-scales",
        default="[0.0, 0.5, 1.0, -0.5, -1.0]",
        help="Shift grasp center along approach axis by scale * depth_m.",
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


def _load_intrinsics(path_arg: str) -> dict[str, float] | None:
    if not path_arg:
        return None
    payload = json.loads(Path(path_arg).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"intrinsics must be a JSON object: {path_arg}")
    required = ("fx", "fy", "cx", "cy")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"intrinsics missing required keys {missing}: {path_arg}")
    return {key: float(payload[key]) for key in required}


def _load_mask_array(path_arg: str) -> np.ndarray:
    mask = np.load(Path(path_arg))
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")
    return np.asarray(mask, dtype=bool)


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions = np.load(Path(args.predictions)).astype(np.float64, copy=False).reshape(-1, 17)
    predictions = predictions[np.argsort(predictions[:, 0])[::-1]]
    if args.top_k > 0:
        predictions = predictions[: int(args.top_k)]

    current_q = _load_current_joints(args.current_joints_rad, socket_path=args.socket_path)
    extrinsic_camera_to_base = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError(f"extrinsic_camera_to_base must be 4x4, got {extrinsic_camera_to_base.shape}")
    intrinsics = _load_intrinsics(args.intrinsics)
    mask = _load_mask_array(args.mask) if args.mask else None

    config = EconomicGraspA1ZAdapterConfig(
        end_effector_frame=args.end_effector_frame,
        frame_id=args.frame_id,
        transform_source=args.transform_source,
        pregrasp_offset_m=args.pregrasp_offset_m,
        lift_offset_m=args.lift_offset_m,
        retreat_offset_m=args.retreat_offset_m,
        table_height_m=args.table_height_m,
        min_tool_height_above_table_m=args.min_tool_height_above_table_m,
        require_approach_downward=bool(args.require_approach_downward),
        max_approach_deviation_deg=args.max_approach_deviation_deg,
        max_gripper_opening_m=args.max_gripper_opening_m,
        pregrasp_opening_margin_m=args.pregrasp_opening_margin_m,
        min_joint_margin_deg=args.min_joint_margin_deg,
        max_waypoint_delta_rad=args.max_waypoint_delta_rad,
        ik_dt=args.ik_dt,
        ik_pos_threshold_m=args.ik_pos_threshold_m,
        ik_ori_threshold_rad=args.ik_ori_threshold_rad,
        ik_damping=args.ik_damping,
        ik_max_iters=args.ik_max_iters,
        approach_linear_waypoint_count=args.approach_linear_waypoint_count,
        ee_grasp_origin_xyz_m=tuple(_parse_json_value(args.ee_grasp_origin_xyz_m, expected_len=3)),
        ee_opening_axis_xyz=tuple(_parse_json_value(args.ee_opening_axis_xyz, expected_len=3)),
        ee_approach_axis_xyz=tuple(_parse_json_value(args.ee_approach_axis_xyz, expected_len=3)),
        keepout_spheres=_parse_keepout_spheres(args.keepout_sphere),
        grasp_center_is_contact_center=bool(args.grasp_center_is_contact_center),
        depth_bias_m=args.depth_bias_m,
        approach_axis_modes=tuple(str(item) for item in json.loads(args.approach_axis_modes)),
        opening_axis_modes=tuple(str(item) for item in json.loads(args.opening_axis_modes)),
        center_shift_depth_scales=tuple(float(item) for item in json.loads(args.center_shift_depth_scales)),
    )
    adapter = EconomicGraspA1ZAdapter(config=config)
    result = adapter.plan_from_predictions(
        predictions=predictions,
        extrinsic_camera_to_base=extrinsic_camera_to_base,
        current_q=current_q,
        task_id=args.task_id,
        object_id=args.object_id,
        backend=args.backend,
        intrinsics=intrinsics,
        mask=mask,
    )

    result_path = output_dir / "economicgrasp_adapter_result.json"
    write_json(result_path, result)
    print(json.dumps({"result_path": str(result_path), "summary": result.summary}, ensure_ascii=True))
    if result.selected_plan is not None:
        plan_path = output_dir / "selected_plan.json"
        write_json(plan_path, result.selected_plan)
    return 0 if result.selected_plan is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
