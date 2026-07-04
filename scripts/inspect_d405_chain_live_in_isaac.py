#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from isaacsim import SimulationApp

SIM_APP = SimulationApp({"headless": True})

import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from pxr import Usd, UsdGeom  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT_DIR / "vendor" / "GALAXEA-A1Z"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from a1z_ext.runtime.d405 import attach_d405_wrist_camera  # noqa: E402
from a1z_ext.robots.get_robot import get_a1z_isaacsim_robot  # noqa: E402
from a1z.robots.kinematics import Kinematics  # noqa: E402


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


def _relative_transform(stage: Usd.Stage, parent_path: str, child_path: str) -> np.ndarray:
    return np.linalg.inv(_world_transform(stage, parent_path)) @ _world_transform(stage, child_path)


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


def _snapshot(
    stage: Usd.Stage,
    arm_link6_body_prim_path: str,
    d405_link_path: str,
    mount_path: str,
    color_optical_path: str,
    *,
    q_rad: np.ndarray,
    kin: Kinematics,
):
    control_base_to_arm_link6 = kin.fk(q_rad, frame_name="arm_link6")
    control_base_to_d405_link = kin.fk(q_rad, frame_name="d405_link")
    return {
        "control_q_rad": [float(v) for v in np.asarray(q_rad, dtype=np.float64).tolist()],
        "control_base_to_arm_link6": _matrix_payload(control_base_to_arm_link6),
        "control_base_to_d405_link": _matrix_payload(control_base_to_d405_link),
        "control_arm_link6_to_d405_link": _matrix_payload(
            np.linalg.inv(control_base_to_arm_link6) @ control_base_to_d405_link
        ),
        "usd_arm_link6_body_prim_world": _matrix_payload(_world_transform(stage, arm_link6_body_prim_path)),
        "d405_link_world": _matrix_payload(_world_transform(stage, d405_link_path)),
        "mount_world": _matrix_payload(_world_transform(stage, mount_path)),
        "color_optical_world": _matrix_payload(_world_transform(stage, color_optical_path)),
        "usd_arm_link6_body_prim_to_d405_link": _matrix_payload(
            _relative_transform(stage, arm_link6_body_prim_path, d405_link_path)
        ),
        "d405_link_to_runtime_mount": _matrix_payload(_relative_transform(stage, d405_link_path, mount_path)),
        "runtime_mount_to_color_optical": _matrix_payload(_relative_transform(stage, mount_path, color_optical_path)),
    }


def main() -> int:
    stage_path = os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd")
    output_path = Path(os.environ.get("A1Z_D405_LIVE_INSPECT_OUTPUT", "/workspace/A1Z/runtime/d405_chain_live_inspect.json"))
    ctx = omni.usd.get_context()
    if not ctx.open_stage(stage_path):
        raise RuntimeError(f"Failed to open stage: {stage_path}")
    _update_app(20)
    stage = ctx.get_stage()
    if stage is None:
        raise RuntimeError("No active stage")

    attachment = attach_d405_wrist_camera(stage)
    if attachment is None:
        raise RuntimeError("attach_d405_wrist_camera returned None")

    arm_link6_body_prim_path = _resolve_named_prim(stage, "arm_link6")
    d405_link_path = attachment.tracked_mount_path.pathString
    mount_path = attachment.mount_path.pathString
    color_optical_path = mount_path + "/RectifiedFrame/ColorOpticalFrame"
    kin = Kinematics(str(ROOT_DIR / "build" / "robot_packages" / "A1Z_G1Z" / "urdf" / "A1Z_G1Z_control.urdf"))
    q_zero = np.zeros(6, dtype=np.float64)

    report = {
        "stage_path": stage_path,
        "arm_link6_body_prim_path": arm_link6_body_prim_path,
        "d405_link_path": d405_link_path,
        "mount_path": mount_path,
        "color_optical_path": color_optical_path,
        "note": (
            "USD arm_link6 body prim pose is not the authoritative URDF arm_link6 frame. "
            "Use control_* entries for math shared by IK/ROS/SDK."
        ),
        "before_robot_start": _snapshot(
            stage,
            arm_link6_body_prim_path,
            d405_link_path,
            mount_path,
            color_optical_path,
            q_rad=q_zero,
            kin=kin,
        ),
    }

    world = World(stage_units_in_meters=1.0)
    world.reset()
    robot = get_a1z_isaacsim_robot(
        control_freq_hz=int(os.environ.get("A1Z_ISAAC_CONTROL_FREQ_HZ", "60")),
        with_gripper=True,
        articulation_root_prim=os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", "/World/A1Z_G1Z/Geometry"),
        zero_gravity_mode=False,
    )
    robot.start()
    _update_app(5)
    robot.process_pending()
    joint_pos = robot.get_joint_state()["pos"]
    attachment.update(joint_pos)
    _update_app(5)
    report["after_robot_start"] = _snapshot(
        stage,
        arm_link6_body_prim_path,
        d405_link_path,
        mount_path,
        color_optical_path,
        q_rad=np.asarray(joint_pos, dtype=np.float64),
        kin=kin,
    )
    report["joint_pos"] = [float(v) for v in np.asarray(joint_pos).tolist()]
    robot.stop()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        SIM_APP.close()
