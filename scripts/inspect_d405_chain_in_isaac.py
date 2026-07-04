#!/usr/bin/env python3

"""Inspect the Isaac-stage D405 transform chain with the runtime rig attached."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from isaacsim import SimulationApp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect A1Z D405 transform chain in Isaac.")
    parser.add_argument(
        "--stage-path",
        default=os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd"),
        help="World USD path to open.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=20,
        help="Frames to advance after opening the stage.",
    )
    return parser


SIM_APP = SimulationApp({"headless": True})

import omni.usd  # noqa: E402
from pxr import Usd, UsdGeom  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from a1z_ext.runtime.d405 import attach_d405_wrist_camera  # noqa: E402
from a1z_ext.runtime.d405.settings import D405AssetSettings  # noqa: E402


def _update_app(frames: int = 5) -> None:
    for _ in range(max(0, int(frames))):
        SIM_APP.update()


def _gf_matrix_to_np(matrix) -> np.ndarray:
    return np.array([[float(matrix[row][col]) for col in range(4)] for row in range(4)], dtype=np.float64).T


def _rigidize(transform: np.ndarray) -> np.ndarray:
    rigid = np.asarray(transform, dtype=np.float64).copy()
    rotation_scale = rigid[:3, :3]
    u, _, vh = np.linalg.svd(rotation_scale)
    rotation = u @ vh
    if np.linalg.det(rotation) < 0.0:
        u[:, -1] *= -1.0
        rotation = u @ vh
    rigid[:3, :3] = rotation
    rigid[3, :] = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return rigid


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


def _world_transform(stage: Usd.Stage, prim_path: str) -> np.ndarray:
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"Invalid prim path: {prim_path}")
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    return _rigidize(_gf_matrix_to_np(cache.GetLocalToWorldTransform(prim)))


def _find_descendant_prim_path(stage: Usd.Stage, *, root_path: str, prim_name: str) -> str | None:
    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        return None
    for prim in Usd.PrimRange(root):
        if prim.GetName() == prim_name:
            return prim.GetPath().pathString
    return None


def _resolve_named_prim(stage: Usd.Stage, prim_name: str) -> str:
    for root_path in ("/World/A1Z_G1Z/Geometry", "/World/A1Z_G1Z", "/World"):
        found = _find_descendant_prim_path(stage, root_path=root_path, prim_name=prim_name)
        if found:
            return found
    raise RuntimeError(f"Could not resolve prim named '{prim_name}'")


def _relative_transform(stage: Usd.Stage, parent_path: str, child_path: str) -> np.ndarray:
    t_world_parent = _world_transform(stage, parent_path)
    t_world_child = _world_transform(stage, child_path)
    return np.linalg.inv(t_world_parent) @ t_world_child


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


def _xyz_rpy_deg_to_matrix(
    x: float,
    y: float,
    z: float,
    roll_deg: float,
    pitch_deg: float,
    yaw_deg: float,
) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = _rpy_deg_to_matrix(roll_deg, pitch_deg, yaw_deg)
    matrix[:3, 3] = np.array([x, y, z], dtype=np.float64)
    return matrix


def _origin_matrix_from_urdf_joint(urdf_path: Path, joint_name: str) -> np.ndarray:
    root = ET.parse(urdf_path).getroot()
    for joint in root.findall("joint"):
        if joint.get("name") != joint_name:
            continue
        origin = joint.find("origin")
        if origin is None:
            return np.eye(4, dtype=np.float64)
        xyz = [float(part) for part in origin.get("xyz", "0 0 0").split()]
        rpy_rad = [float(part) for part in origin.get("rpy", "0 0 0").split()]
        rpy_deg = [math.degrees(v) for v in rpy_rad]
        return _xyz_rpy_deg_to_matrix(xyz[0], xyz[1], xyz[2], rpy_deg[0], rpy_deg[1], rpy_deg[2])
    raise RuntimeError(f"Joint '{joint_name}' not found in URDF: {urdf_path}")


def main() -> int:
    args = _build_parser().parse_args()
    stage_path = args.stage_path
    if not os.path.isfile(stage_path):
        raise FileNotFoundError(stage_path)

    ctx = omni.usd.get_context()
    if not ctx.open_stage(stage_path):
        raise RuntimeError(f"Failed to open stage: {stage_path}")
    _update_app(args.warmup_frames)

    stage = ctx.get_stage()
    if stage is None:
        raise RuntimeError("No active stage")

    attachment = attach_d405_wrist_camera(stage)
    if attachment is None:
        raise RuntimeError("attach_d405_wrist_camera returned None")
    attachment.update(np.zeros(6, dtype=np.float64))
    _update_app(5)

    arm_link6_body_prim_path = _resolve_named_prim(stage, "arm_link6")
    d405_link_path = attachment.tracked_mount_path.pathString
    mount_path = attachment.mount_path.pathString
    link_frame_path = mount_path
    rectified_frame_path = link_frame_path + "/RectifiedFrame"
    color_optical_path = rectified_frame_path + "/ColorOpticalFrame"
    color_camera_path = attachment.camera_paths.get("color", "")
    control_urdf_path = ROOT_DIR / "build" / "robot_packages" / "A1Z_G1Z" / "urdf" / "A1Z_G1Z_control.urdf"
    urdf_arm_link6_to_d405_link = _origin_matrix_from_urdf_joint(control_urdf_path, "d405_mount_joint")
    urdf_d405_link_to_rectified = _origin_matrix_from_urdf_joint(control_urdf_path, "d405_rectified_joint")
    asset_settings = D405AssetSettings.from_env()
    optical_xyz = list(asset_settings.rectified_to_optical_offset_xyz_m)
    optical_rpy = list(asset_settings.rectified_to_optical_rpy_deg)
    rectified_to_color_optical = _xyz_rpy_deg_to_matrix(*optical_xyz, *optical_rpy)
    expected_arm_link6_to_color_optical = urdf_arm_link6_to_d405_link @ urdf_d405_link_to_rectified @ rectified_to_color_optical
    stage_arm_link6_to_d405_link = _relative_transform(stage, arm_link6_body_prim_path, d405_link_path)
    stage_d405_link_to_runtime_link = _relative_transform(stage, d405_link_path, link_frame_path)
    stage_runtime_link_to_rectified = _relative_transform(stage, link_frame_path, rectified_frame_path)
    stage_rectified_to_color_optical = _relative_transform(stage, rectified_frame_path, color_optical_path)
    stage_arm_link6_to_color_optical = _relative_transform(stage, arm_link6_body_prim_path, color_optical_path)
    expected_vs_stage = np.linalg.inv(expected_arm_link6_to_color_optical) @ stage_arm_link6_to_color_optical

    report = {
        "stage_path": stage_path,
        "arm_link6_body_prim_path": arm_link6_body_prim_path,
        "d405_link_path": d405_link_path,
        "mount_path": mount_path,
        "runtime_link_frame_path": link_frame_path,
        "runtime_rectified_frame_path": rectified_frame_path,
        "color_optical_path": color_optical_path,
        "color_camera_path": color_camera_path,
        "note": (
            "USD arm_link6 body prim pose is not the authoritative URDF arm_link6 frame. "
            "Use urdf_* plus configured residual optical transform for math shared by ROS/runtime."
        ),
        "urdf_arm_link6_to_d405_link": _matrix_payload(urdf_arm_link6_to_d405_link),
        "urdf_d405_link_to_rectified": _matrix_payload(urdf_d405_link_to_rectified),
        "config_rectified_to_color_optical_effective": _matrix_payload(rectified_to_color_optical),
        "expected_arm_link6_to_color_optical": _matrix_payload(expected_arm_link6_to_color_optical),
        "usd_arm_link6_body_prim_world": _matrix_payload(_world_transform(stage, arm_link6_body_prim_path)),
        "d405_link_world": _matrix_payload(_world_transform(stage, d405_link_path)),
        "mount_world": _matrix_payload(_world_transform(stage, mount_path)),
        "color_optical_world": _matrix_payload(_world_transform(stage, color_optical_path)),
        "stage_arm_link6_body_to_d405_link": _matrix_payload(stage_arm_link6_to_d405_link),
        "stage_d405_link_to_runtime_link": _matrix_payload(stage_d405_link_to_runtime_link),
        "stage_runtime_link_to_rectified": _matrix_payload(stage_runtime_link_to_rectified),
        "stage_rectified_to_color_optical": _matrix_payload(stage_rectified_to_color_optical),
        "stage_arm_link6_body_to_color_optical": _matrix_payload(stage_arm_link6_to_color_optical),
        "expected_vs_stage_delta": _matrix_payload(expected_vs_stage),
    }
    if color_camera_path:
        report["color_camera_world"] = _matrix_payload(_world_transform(stage, color_camera_path))
        report["color_optical_to_color_camera"] = _matrix_payload(
            _relative_transform(stage, color_optical_path, color_camera_path)
        )

    payload = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    exit_code = 0
    try:
        raise SystemExit(main())
    finally:
        SIM_APP.close()
