#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
SDK_DIR = ROOT_DIR / "vendor" / "GALAXEA-A1Z"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from a1z.robots.kinematics import Kinematics
from a1z_ext.runtime.d405.geometry import (
    d405_install_rotation_matrix,
    d405_rectified_to_optical_transform,
)
from a1z_ext.runtime.d405.settings import D405ComputeSettings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute D405 camera->base extrinsic from saved joints and static config.")
    parser.add_argument("--joint-pos-rad-json", required=True)
    parser.add_argument("--target-frame-id", default="base_link")
    parser.add_argument(
        "--control-urdf",
        default=os.environ.get(
            "A1Z_CONTROL_URDF",
            str(ROOT_DIR / "build" / "robot_packages" / "A1Z_G1Z" / "urdf" / "A1Z_G1Z_control.urdf"),
        ),
    )
    parser.add_argument("--tool-link-frame", default=os.environ.get("A1Z_TOOL_LINK_FRAME", "grasp_tcp"))
    parser.add_argument("--output", default="")
    return parser


def _rpy_deg_to_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cr = math.cos(roll)
    sr = math.sin(roll)
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=np.float64,
    )


def _xyz_rpy_to_matrix(xyz: list[float], rpy_deg: list[float]) -> np.ndarray:
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = _rpy_deg_to_matrix(rpy_deg[0], rpy_deg[1], rpy_deg[2])
    out[:3, 3] = np.asarray(xyz, dtype=np.float64)
    return out


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
    args = _build_parser().parse_args()
    q = np.asarray(json.loads(Path(args.joint_pos_rad_json).read_text(encoding="utf-8")), dtype=np.float64).reshape(-1)
    if q.shape[0] < 6:
        raise ValueError("joint-pos-rad-json must contain at least 6 values")
    q = q[:6]

    d405_compute = D405ComputeSettings.from_env()
    kin = Kinematics(str(args.control_urdf), end_effector_frame=str(args.tool_link_frame))
    t_base_tool = kin.fk(q, frame_name=str(args.tool_link_frame))
    t_tool_d405 = np.linalg.inv(kin.fk(np.zeros(6, dtype=np.float64), frame_name=str(args.tool_link_frame))) @ kin.fk(
        np.zeros(6, dtype=np.float64), frame_name="d405_link"
    )

    t_tool_d405 = np.asarray(t_tool_d405, dtype=np.float64).copy()
    t_tool_d405[:3, :3] = t_tool_d405[:3, :3] @ d405_install_rotation_matrix(d405_compute.install_rpy_deg)
    t_d405_rectified = _xyz_rpy_to_matrix([0.0, 0.0, 0.0], list(d405_compute.rectify_rpy_deg))
    t_rectified_optical = d405_rectified_to_optical_transform(
        offset_xyz_m=d405_compute.rectified_to_optical_offset_xyz_m
    )
    t_base_camera = t_base_tool @ t_tool_d405 @ t_d405_rectified @ t_rectified_optical

    report = {
        "source": "isaac_semantic_fk_from_capture",
        "target_frame_id": str(args.target_frame_id),
        "joint_pos_rad_json": str(Path(args.joint_pos_rad_json).resolve()),
        "control_urdf": str(Path(args.control_urdf).resolve()),
        "tool_link_frame": str(args.tool_link_frame),
        "transform": _matrix_payload(t_base_camera),
        "segments": {
            "base_to_tool": _matrix_payload(t_base_tool),
            "tool_to_d405_link": _matrix_payload(t_tool_d405),
            "d405_link_to_rectified": _matrix_payload(t_d405_rectified),
            "rectified_to_optical": _matrix_payload(t_rectified_optical),
        },
    }
    payload = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
