#!/usr/bin/env python3

"""Summarize current end-effector gap to AnyGrasp best-direct tool targets."""

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize EE pose gap to AnyGrasp best-direct target.")
    parser.add_argument("--best-direct-result", required=True)
    parser.add_argument("--output", required=True)
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


def _vec3(transform: np.ndarray) -> list[float]:
    return transform[:3, 3].astype(float).tolist()


def _orientation_gap_deg(current: np.ndarray, target: np.ndarray) -> float:
    delta = current[:3, :3].T @ target[:3, :3]
    trace = float(np.trace(delta))
    cos_theta = max(-1.0, min(1.0, (trace - 1.0) * 0.5))
    return math.degrees(math.acos(cos_theta))


def _gap_payload(current: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    delta_xyz = target[:3, 3] - current[:3, 3]
    return {
        "target_xyz": _vec3(target),
        "delta_xyz": delta_xyz.astype(float).tolist(),
        "delta_norm_m": float(np.linalg.norm(delta_xyz)),
        "orientation_gap_deg": float(_orientation_gap_deg(current, target)),
    }


def main() -> int:
    args = build_parser().parse_args()
    payload = _load_json(args.best_direct_result)
    current_q = np.asarray(payload.get("current_q_rad", []), dtype=np.float64).reshape(-1)
    if current_q.shape != (6,):
        raise ValueError(f"best_direct_result missing valid current_q_rad: {args.best_direct_result}")

    kin = Kinematics(str(args.control_urdf), end_effector_frame=str(args.end_effector_frame))
    current_ee = np.asarray(kin.fk(current_q, frame_name=str(args.end_effector_frame)), dtype=np.float64).reshape(4, 4)
    pregrasp = _matrix(payload["tool_pregrasp_pose_matrix"])
    grasp = _matrix(payload["tool_grasp_pose_matrix"])

    summary = {
        "best_direct_result_path": str(Path(args.best_direct_result).resolve()),
        "control_urdf": str(Path(args.control_urdf).resolve()),
        "end_effector_frame": str(args.end_effector_frame),
        "current_q_rad": current_q.astype(float).tolist(),
        "current_ee_pose_matrix": current_ee.astype(float).tolist(),
        "current_ee_xyz": _vec3(current_ee),
        "pregrasp_gap": _gap_payload(current_ee, pregrasp),
        "grasp_gap": _gap_payload(current_ee, grasp),
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
