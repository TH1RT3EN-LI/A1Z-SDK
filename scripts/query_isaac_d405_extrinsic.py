#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from isaacsim import SimulationApp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query live Isaac D405 camera extrinsics.")
    parser.add_argument(
        "--stage-path",
        default=os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd"),
    )
    parser.add_argument(
        "--articulation-root",
        default=os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", "/World/A1Z_G1Z/Geometry"),
    )
    parser.add_argument(
        "--target-frame-id",
        default=os.environ.get("A1Z_BASE_LINK_FRAME", "base_link"),
    )
    parser.add_argument(
        "--secondary-target-frame-id",
        default="",
    )
    parser.add_argument("--output", default="")
    parser.add_argument("--warmup-frames", type=int, default=20)
    parser.add_argument(
        "--joint-pos-rad-json",
        default="",
        help="Optional JSON file with at least 6 arm joint positions in radians. If provided, skip control-server status.",
    )
    return parser


SIM_APP = SimulationApp({"headless": True})

import omni.usd  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT_DIR / "vendor" / "GALAXEA-A1Z"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from a1z_ext.control_client import send_control_request  # noqa: E402
from a1z_ext.config import get_control_defaults  # noqa: E402
from a1z_ext.runtime.d405 import attach_d405_wrist_camera  # noqa: E402
from a1z_ext.runtime.d405.pose import camera_to_target_matrix_from_usd  # noqa: E402
from a1z_ext.robots.isaacsim_robot import IsaacSimArmRobot  # noqa: E402


def _update_app(frames: int) -> None:
    for _ in range(max(0, int(frames))):
        SIM_APP.update()


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


def _append_trace(trace_path: Path | None, message: str) -> None:
    if trace_path is None:
        return
    try:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except Exception:
        pass


def _query_live_status() -> dict[str, object]:
    payload = send_control_request(
        "status",
        socket_path=os.environ.get("A1Z_SOCKET_PATH", ""),
        tcp_host=os.environ.get("A1Z_TCP_HOST", ""),
        tcp_port=int(os.environ.get("A1Z_TCP_PORT", "18080")),
    )
    return dict(payload)


def _build_isaac_robot(*, articulation_root: str) -> IsaacSimArmRobot:
    control_defaults = get_control_defaults()
    isaac_cfg = control_defaults["isaacsim"]
    return IsaacSimArmRobot(
        num_joints=int(control_defaults["num_joints"]),
        with_gripper=True,
        control_freq_hz=60,
        articulation_root_prim=articulation_root,
        default_kp=np.asarray(isaac_cfg["position_hold_kp"], dtype=np.float64),
        default_kd=np.asarray(isaac_cfg["position_hold_kd"], dtype=np.float64),
        urdf_path=os.environ.get("A1Z_CONTROL_URDF", ""),
        gravity_comp_factor=1.0,
        zero_gravity_mode=False,
        gravity_torque_scale=np.asarray(control_defaults["gravity_torque_scale"], dtype=np.float64),
        max_gravity_torque=np.asarray(control_defaults["max_gravity_torque"], dtype=np.float64),
        torque_clip=np.asarray(control_defaults["torque_clip"], dtype=np.float64),
    )


def main() -> int:
    args = _build_parser().parse_args()
    output_path = Path(args.output) if args.output else None
    trace_path = output_path.with_suffix(output_path.suffix + ".trace.txt") if output_path is not None else None
    _append_trace(trace_path, "start")
    stage_path = args.stage_path
    if not os.path.isfile(stage_path):
        raise FileNotFoundError(stage_path)

    ctx = omni.usd.get_context()
    if not ctx.open_stage(stage_path):
        raise RuntimeError(f"Failed to open stage: {stage_path}")
    _append_trace(trace_path, f"stage_opened:{stage_path}")
    _append_trace(trace_path, f"warmup_begin:{int(args.warmup_frames)}")
    _update_app(args.warmup_frames)
    _append_trace(trace_path, "warmup_done")

    stage = ctx.get_stage()
    if stage is None:
        raise RuntimeError("No active USD stage")

    _append_trace(trace_path, "attach_begin")
    attachment = attach_d405_wrist_camera(stage)
    if attachment is None:
        raise RuntimeError("attach_d405_wrist_camera returned None")
    _append_trace(trace_path, f"attachment_ready:{attachment.mount_path}")

    joint_json = str(args.joint_pos_rad_json or "").strip()
    if joint_json:
        _append_trace(trace_path, f"joint_source:file:{joint_json}")
        q_loaded = json.loads(Path(joint_json).read_text(encoding="utf-8"))
        q_rad = np.asarray(q_loaded, dtype=np.float64).reshape(-1)
        if q_rad.shape[0] < 6:
            raise RuntimeError(f"joint-pos-rad-json must contain at least 6 values: {joint_json}")
        q_rad = q_rad[:6]
        joint_deg = np.rad2deg(q_rad)
    else:
        _append_trace(trace_path, "joint_source:tcp_status_begin")
        status = _query_live_status()
        _append_trace(trace_path, "joint_source:tcp_status_done")
        joint_deg = status.get("pos_deg", [])
        if len(joint_deg) < 6:
            raise RuntimeError(f"Unexpected control-server status payload: {status}")
        q_rad = np.deg2rad(np.asarray(joint_deg[:6], dtype=np.float64))

    _append_trace(trace_path, "world_begin")
    from isaacsim.core.api import World

    world = World(stage_units_in_meters=1.0)
    _append_trace(trace_path, "world_created")
    world.reset()
    _append_trace(trace_path, "world_reset_done")
    _update_app(2)
    _append_trace(trace_path, "world_ready")

    _append_trace(trace_path, f"robot_begin:{args.articulation_root}")
    robot = _build_isaac_robot(articulation_root=args.articulation_root)
    robot.start()
    _update_app(2)
    robot.process_pending()
    _append_trace(trace_path, "robot_started")

    _append_trace(trace_path, "robot_force_joint_state_begin")
    if hasattr(robot, "_force_arm_positions"):
        robot._force_arm_positions(q_rad)  # type: ignore[attr-defined]
    else:
        robot.command_joint_state({"pos": q_rad})
        robot.process_pending()
    for _ in range(20):
        _update_app(1)
        robot.process_pending()
    if hasattr(robot, "_wait_for_arm_target"):
        _append_trace(trace_path, "robot_wait_for_arm_target_begin")
        robot._wait_for_arm_target(q_rad, timeout_s=5.0)  # type: ignore[attr-defined]
        _append_trace(trace_path, "robot_wait_for_arm_target_done")
        for _ in range(5):
            _update_app(1)
            robot.process_pending()
    settled_q_rad = np.asarray(robot.get_joint_state()["pos"], dtype=np.float64).reshape(-1)[:6]
    settled_q_deg = np.rad2deg(settled_q_rad)
    _append_trace(trace_path, "robot_force_joint_state_done")

    _append_trace(trace_path, "attachment_update_begin")
    attachment.update(settled_q_rad)
    _update_app(2)
    _append_trace(trace_path, "attachment_updated")

    color_camera_path = str(attachment.camera_paths.get("color") or "")
    if not color_camera_path:
        raise RuntimeError("Color camera path unavailable on runtime D405 attachment")
    _append_trace(trace_path, f"camera_path:{color_camera_path}")

    _append_trace(trace_path, f"camera_to_target_begin:{args.target_frame_id}")
    transform = camera_to_target_matrix_from_usd(
        camera_prim_path=color_camera_path,
        target_frame_id=args.target_frame_id,
        joint_pos_rad=q_rad,
    )
    _append_trace(trace_path, "camera_to_target_done")
    report = {
        "source": "isaac_runtime",
        "stage_path": stage_path,
        "target_frame_id": args.target_frame_id,
        "camera_prim_path": color_camera_path,
        "command_joint_pos_deg": [float(v) for v in joint_deg[:6]],
        "actual_joint_pos_deg": [float(v) for v in settled_q_deg.tolist()],
        "joint_settled": bool(np.max(np.abs(settled_q_rad - q_rad)) <= 1e-4),
        "max_joint_err_rad": float(np.max(np.abs(settled_q_rad - q_rad))),
        "transform": _matrix_payload(transform),
    }
    secondary_target = str(args.secondary_target_frame_id or "").strip()
    if secondary_target:
        secondary_transform = camera_to_target_matrix_from_usd(
            camera_prim_path=color_camera_path,
            target_frame_id=secondary_target,
            joint_pos_rad=q_rad,
        )
        report["secondary_target_frame_id"] = secondary_target
        report["secondary_transform"] = _matrix_payload(secondary_transform)
    _append_trace(trace_path, "report_ready")
    try:
        robot.stop()
    except Exception:
        pass

    payload = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
        _append_trace(trace_path, f"output_written:{output_path}")
    print(payload)
    _append_trace(trace_path, "stdout_printed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        SIM_APP.close()
