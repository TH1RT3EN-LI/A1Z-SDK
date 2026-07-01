#!/usr/bin/env python3

"""Sweep AnyGrasp TCP alignment candidates against a fixed AnyGrasp result."""

from __future__ import annotations

import argparse
import itertools
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
    ANYGRASP_ACTIVE_BINDING_LABEL,
    ContactGraspNetA1ZAdapter,
    ContactGraspNetA1ZAdapterConfig,
    anygrasp_item_to_grasp_pose_with_binding_label,
)


AXES = {
    "+x": np.array([1.0, 0.0, 0.0], dtype=np.float64),
    "-x": np.array([-1.0, 0.0, 0.0], dtype=np.float64),
    "+y": np.array([0.0, 1.0, 0.0], dtype=np.float64),
    "-y": np.array([0.0, -1.0, 0.0], dtype=np.float64),
    "+z": np.array([0.0, 0.0, 1.0], dtype=np.float64),
    "-z": np.array([0.0, 0.0, -1.0], dtype=np.float64),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep AnyGrasp TCP alignment candidates.")
    parser.add_argument("--result-json", required=True)
    parser.add_argument("--extrinsic-camera-to-base", required=True)
    parser.add_argument("--current-joints-rad", default="")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--binding-label", default=ANYGRASP_ACTIVE_BINDING_LABEL, help="How to interpret AnyGrasp raw rotation columns.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "runtime" / "anygrasp_tcp_scan"))
    parser.add_argument("--task-id", default="anygrasp-tcp-scan")
    parser.add_argument("--object-id", default="target-object")
    parser.add_argument("--backend", default="anygrasp_tcp_scan")
    parser.add_argument("--max-approach-deviation-deg", type=float, default=85.0)
    parser.add_argument("--min-joint-margin-deg", type=float, default=5.0)
    parser.add_argument("--pregrasp-offset-m", type=float, default=0.08)
    parser.add_argument("--lift-offset-m", type=float, default=0.10)
    parser.add_argument("--retreat-offset-m", type=float, default=0.04)
    parser.add_argument("--approach-linear-waypoint-count", type=int, default=0)
    parser.add_argument("--require-approach-downward", action="store_true")
    parser.add_argument(
        "--opening-axis-labels",
        default='["+x","-x","+y","-y","+z","-z"]',
        help="JSON list of axis labels to test for ee opening axis.",
    )
    parser.add_argument(
        "--approach-axis-labels",
        default='["+x","-x","+y","-y","+z","-z"]',
        help="JSON list of axis labels to test for ee approach axis.",
    )
    parser.add_argument(
        "--origin-x-values",
        default="[-0.08,-0.06,-0.04,0.0,0.04,0.06,0.0727,0.08]",
        help="JSON list of x offsets in arm_link6 frame.",
    )
    parser.add_argument(
        "--origin-y-values",
        default="[0.0]",
        help="JSON list of y offsets in arm_link6 frame.",
    )
    parser.add_argument(
        "--origin-z-values",
        default="[0.0,-0.02,0.02]",
        help="JSON list of z offsets in arm_link6 frame.",
    )
    parser.add_argument("--top-k-configs", type=int, default=20)
    return parser


def _parse_json_list(raw: str) -> list[Any]:
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"expected JSON list, got: {raw}")
    return value


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


def _load_anygrasp_result(path: str | Path, *, binding_label: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    top_grasps = payload.get("top_grasps", [])
    if not isinstance(top_grasps, list) or not top_grasps:
        raise ValueError(f"AnyGrasp result missing top_grasps: {path}")
    pred_grasps: list[np.ndarray] = []
    scores: list[float] = []
    openings: list[float] = []
    for item in top_grasps:
        pred_grasps.append(anygrasp_item_to_grasp_pose_with_binding_label(item, binding_label=binding_label))
        scores.append(float(item["score"]))
        openings.append(float(item["width_m"]))
    return (
        np.stack(pred_grasps, axis=0),
        np.asarray(scores, dtype=np.float64),
        np.asarray(openings, dtype=np.float64),
    )


def _is_parallel(a: np.ndarray, b: np.ndarray) -> bool:
    return abs(float(np.dot(a, b))) > 0.999


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pred_grasps_cam, scores, openings = _load_anygrasp_result(args.result_json, binding_label=str(args.binding_label))
    current_q = _load_current_joints(args.current_joints_rad, socket_path=args.socket_path)
    extrinsic_camera_to_base = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError(f"extrinsic_camera_to_base must be 4x4, got {extrinsic_camera_to_base.shape}")

    opening_labels = [str(item) for item in _parse_json_list(args.opening_axis_labels)]
    approach_labels = [str(item) for item in _parse_json_list(args.approach_axis_labels)]
    origin_x_values = [float(item) for item in _parse_json_list(args.origin_x_values)]
    origin_y_values = [float(item) for item in _parse_json_list(args.origin_y_values)]
    origin_z_values = [float(item) for item in _parse_json_list(args.origin_z_values)]

    scan_rows: list[dict[str, Any]] = []
    for opening_label, approach_label, ox, oy, oz in itertools.product(
        opening_labels,
        approach_labels,
        origin_x_values,
        origin_y_values,
        origin_z_values,
    ):
        opening_axis = AXES[opening_label]
        approach_axis = AXES[approach_label]
        if _is_parallel(opening_axis, approach_axis):
            continue
        config = ContactGraspNetA1ZAdapterConfig(
            pregrasp_offset_m=args.pregrasp_offset_m,
            lift_offset_m=args.lift_offset_m,
            retreat_offset_m=args.retreat_offset_m,
            max_approach_deviation_deg=args.max_approach_deviation_deg,
            min_joint_margin_deg=args.min_joint_margin_deg,
            approach_linear_waypoint_count=args.approach_linear_waypoint_count,
            require_approach_downward=bool(args.require_approach_downward),
            ee_grasp_origin_xyz_m=(ox, oy, oz),
            ee_opening_axis_xyz=tuple(float(v) for v in opening_axis.tolist()),
            ee_approach_axis_xyz=tuple(float(v) for v in approach_axis.tolist()),
        )
        adapter = ContactGraspNetA1ZAdapter(config=config)
        result = adapter.plan(
            pred_grasps_cam=pred_grasps_cam,
            scores=scores,
            gripper_openings_m=openings,
            contact_points_cam=pred_grasps_cam[:, :3, 3],
            extrinsic_camera_to_base=extrinsic_camera_to_base,
            current_q=current_q,
            task_id=args.task_id,
            object_id=args.object_id,
            backend=args.backend,
            source_model="anygrasp",
        )
        failure_hist: dict[str, int] = {}
        for candidate in result.candidates:
            for reason in candidate.failure_reasons:
                failure_hist[reason] = failure_hist.get(reason, 0) + 1
        selected_rank = None
        if result.selected_plan is not None:
            selected_id = result.selected_plan.selected_grasp_candidate_id
            selected = next((c for c in result.candidates if c.candidate_id == selected_id), None)
            selected_rank = None if selected is None else int(selected.rank)
        scan_rows.append(
            {
                "active_binding_label": str(args.binding_label),
                "ee_grasp_origin_xyz_m": [ox, oy, oz],
                "ee_opening_axis_label": opening_label,
                "ee_approach_axis_label": approach_label,
                "summary": result.summary,
                "selected_rank": selected_rank,
                "failure_histogram": failure_hist,
            }
        )

    scan_rows.sort(
        key=lambda row: (
            int(row["summary"].get("executable_count", 0)),
            1 if row["summary"].get("selected_candidate_id") else 0,
            -len(row["failure_histogram"]),
        ),
        reverse=True,
    )
    payload = {
        "result_json": str(Path(args.result_json).resolve()),
        "extrinsic_camera_to_base": str(Path(args.extrinsic_camera_to_base).resolve()),
        "active_binding_label": str(args.binding_label),
        "config_count": len(scan_rows),
        "top_configs": scan_rows[: max(1, int(args.top_k_configs))],
        "all_configs_path": str((output_dir / "all_configs.json").resolve()),
    }
    (output_dir / "all_configs.json").write_text(json.dumps(scan_rows, ensure_ascii=True, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
