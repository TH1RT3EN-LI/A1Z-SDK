#!/usr/bin/env python3

"""Scan AnyGrasp frame-binding and camera-frame correction hypotheses."""

from __future__ import annotations

import argparse
import json
import math
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

from a1z.robots.kinematics import Kinematics
from a1z_ext.config import get_default_control_urdf_path
from a1z_ext.grasping import (
    ANYGRASP_ACTIVE_BINDING_LABEL,
    ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL,
    ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL,
    ANYGRASP_SUPPORTED_BINDINGS,
    anygrasp_item_to_grasp_pose_with_binding_label,
)
from a1z_ext.grasping.contact_graspnet_adapter import _invert_transform, _normalize, _rigidize_transform


AXES = {
    "+x": np.array([1.0, 0.0, 0.0], dtype=np.float64),
    "-x": np.array([-1.0, 0.0, 0.0], dtype=np.float64),
    "+y": np.array([0.0, 1.0, 0.0], dtype=np.float64),
    "-y": np.array([0.0, -1.0, 0.0], dtype=np.float64),
    "+z": np.array([0.0, 0.0, 1.0], dtype=np.float64),
    "-z": np.array([0.0, 0.0, -1.0], dtype=np.float64),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan AnyGrasp mapping hypotheses.")
    parser.add_argument("--result-json", required=True, help="Path to anygrasp_result.json")
    parser.add_argument("--extrinsic-camera-to-base", required=True, help="Path to extrinsic_camera_to_base.npy")
    parser.add_argument("--best-direct-result", required=True, help="Path to anygrasp_best_direct_result.json")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--grasp-rank", type=int, default=0)
    parser.add_argument("--binding-labels", default="", help="Optional JSON list of binding labels to test.")
    parser.add_argument("--camera-correction-labels", default="", help="Optional JSON list of camera correction labels to test.")
    parser.add_argument("--extrinsic-correction-labels", default="", help="Optional JSON list of camera-to-base correction labels to test.")
    parser.add_argument("--top-k", type=int, default=24)
    parser.add_argument("--end-effector-frame", default="arm_link6")
    parser.add_argument("--control-urdf", default=get_default_control_urdf_path())
    return parser


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _matrix(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).reshape(4, 4)


def _orientation_gap_deg(current: np.ndarray, target: np.ndarray) -> float:
    delta = current[:3, :3].T @ target[:3, :3]
    trace = float(np.trace(delta))
    cos_theta = max(-1.0, min(1.0, (trace - 1.0) * 0.5))
    return math.degrees(math.acos(cos_theta))


def _gap_payload(current: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    delta_xyz = target[:3, 3] - current[:3, 3]
    return {
        "target_xyz": target[:3, 3].astype(float).tolist(),
        "delta_xyz": delta_xyz.astype(float).tolist(),
        "delta_norm_m": float(np.linalg.norm(delta_xyz)),
        "orientation_gap_deg": float(_orientation_gap_deg(current, target)),
    }


def _correction_hypotheses() -> list[tuple[str, np.ndarray]]:
    labels = list(AXES.keys())
    rows: list[tuple[str, np.ndarray]] = []
    for x_label in labels:
        x_axis = AXES[x_label]
        for y_label in labels:
            y_axis = AXES[y_label]
            if abs(float(np.dot(x_axis, y_axis))) > 1e-9:
                continue
            z_axis = np.cross(x_axis, y_axis)
            for z_label, axis in AXES.items():
                if np.allclose(z_axis, axis):
                    rotation = np.column_stack([x_axis, y_axis, axis])
                    label = f"x={x_label},y={y_label},z={z_label}"
                    rows.append((label, rotation))
                    break
    unique: dict[str, np.ndarray] = {}
    for label, rotation in rows:
        unique[label] = rotation
    return [("identity", np.eye(3, dtype=np.float64))] + [
        (label, rot) for label, rot in unique.items() if label != "x=+x,y=+y,z=+z"
    ]


def _filter_corrections(raw: str) -> list[tuple[str, np.ndarray]]:
    rows = _correction_hypotheses()
    if not raw:
        return rows
    selected = {str(item) for item in json.loads(raw)}
    filtered = [(label, rot) for label, rot in rows if label in selected]
    if not filtered:
        raise ValueError(f"no correction hypotheses matched: {sorted(selected)}")
    return filtered


def main() -> int:
    args = build_parser().parse_args()
    result_payload = _load_json(args.result_json)
    top_grasps = result_payload.get("top_grasps")
    if not isinstance(top_grasps, list) or not top_grasps:
        raise ValueError(f"AnyGrasp result missing top_grasps: {args.result_json}")
    if args.grasp_rank < 0 or args.grasp_rank >= len(top_grasps):
        raise ValueError(f"grasp-rank out of range: {args.grasp_rank}")
    grasp_item = dict(top_grasps[int(args.grasp_rank)])

    best_direct = _load_json(args.best_direct_result)
    ee_to_grasp = _matrix(best_direct["ee_to_grasp_transform"])
    grasp_to_ee = _invert_transform(ee_to_grasp)
    current_q = np.asarray(best_direct.get("current_q_rad", []), dtype=np.float64).reshape(-1)
    if current_q.shape != (6,):
        raise ValueError(f"best_direct_result missing valid current_q_rad: {args.best_direct_result}")
    current_ee = np.asarray(
        Kinematics(str(args.control_urdf), end_effector_frame=str(args.end_effector_frame)).fk(
            current_q, frame_name=str(args.end_effector_frame)
        ),
        dtype=np.float64,
    ).reshape(4, 4)

    pregrasp_pose = _matrix(best_direct["tool_pregrasp_pose_matrix"])
    grasp_pose = _matrix(best_direct["tool_grasp_pose_matrix"])
    pregrasp_offset_m = float(np.linalg.norm(pregrasp_pose[:3, 3] - grasp_pose[:3, 3]))

    extrinsic = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic.shape != (4, 4):
        raise ValueError(f"extrinsic_camera_to_base must be 4x4, got {extrinsic.shape}")

    if args.binding_labels:
        binding_labels = [str(item) for item in json.loads(args.binding_labels)]
    else:
        binding_labels = list(ANYGRASP_SUPPORTED_BINDINGS.keys())
    if args.camera_correction_labels:
        camera_corrections = _filter_corrections(args.camera_correction_labels)
    else:
        camera_corrections = _filter_corrections(json.dumps([ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL]))
    extrinsic_corrections = _filter_corrections(args.extrinsic_correction_labels)

    hypotheses: list[dict[str, Any]] = []
    for extrinsic_correction_label, extrinsic_correction_rot in extrinsic_corrections:
        extrinsic_correction = np.eye(4, dtype=np.float64)
        extrinsic_correction[:3, :3] = extrinsic_correction_rot
        extrinsic_corrected = _rigidize_transform(extrinsic @ extrinsic_correction)
        for camera_correction_label, _ in camera_corrections:
            for binding_label in binding_labels:
                grasp_cam = anygrasp_item_to_grasp_pose_with_binding_label(
                    grasp_item,
                    binding_label=binding_label,
                    camera_correction_label=camera_correction_label,
                )
                grasp_base = _rigidize_transform(extrinsic_corrected @ grasp_cam)
                tool_grasp = _rigidize_transform(grasp_base @ grasp_to_ee)
                approach = _normalize(grasp_base[:3, 2])
                tool_pregrasp = tool_grasp.copy()
                tool_pregrasp[:3, 3] += (-approach) * pregrasp_offset_m
                pregrasp_gap = _gap_payload(current_ee, tool_pregrasp)
                grasp_gap = _gap_payload(current_ee, tool_grasp)
                hypotheses.append(
                    {
                        "binding_label": str(binding_label),
                        "camera_correction_label": str(camera_correction_label),
                        "extrinsic_correction_label": str(extrinsic_correction_label),
                        "extrinsic_correction_matrix": extrinsic_correction.astype(float).tolist(),
                        "tool_grasp_pose_xyz": tool_grasp[:3, 3].astype(float).tolist(),
                        "tool_pregrasp_pose_xyz": tool_pregrasp[:3, 3].astype(float).tolist(),
                        "pregrasp_gap": pregrasp_gap,
                        "grasp_gap": grasp_gap,
                    }
                )

    hypotheses.sort(
        key=lambda row: (
            float(row["grasp_gap"]["orientation_gap_deg"]),
            float(row["pregrasp_gap"]["orientation_gap_deg"]),
            float(row["grasp_gap"]["delta_norm_m"]),
            float(row["pregrasp_gap"]["delta_norm_m"]),
        )
    )

    output = {
        "result_json": str(Path(args.result_json).resolve()),
        "best_direct_result_json": str(Path(args.best_direct_result).resolve()),
        "extrinsic_camera_to_base": str(Path(args.extrinsic_camera_to_base).resolve()),
        "active_binding_label": str(best_direct.get("active_binding_label", ANYGRASP_ACTIVE_BINDING_LABEL)),
        "active_camera_correction_label": str(
            best_direct.get("active_camera_correction_label", ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL)
        ),
        "active_extrinsic_correction_label": str(
            best_direct.get("active_extrinsic_correction_label", ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL)
        ),
        "grasp_rank": int(args.grasp_rank),
        "current_ee_xyz": current_ee[:3, 3].astype(float).tolist(),
        "pregrasp_offset_m": pregrasp_offset_m,
        "hypothesis_count": len(hypotheses),
        "top_hypotheses": hypotheses[: max(1, int(args.top_k))],
        "all_hypotheses": hypotheses,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "hypothesis_count": len(hypotheses)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
