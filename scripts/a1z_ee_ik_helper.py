#!/usr/bin/env python3

"""Incremental end-effector and joint teleop helper for operator GUIs."""

from __future__ import annotations

import argparse
import json
import math
import os
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
from a1z_ext.config import (
    get_default_backend,
    get_default_control_urdf_path,
    get_socket_path,
    get_tcp_host,
    get_tcp_port,
)
from a1z_ext.control_client import send_control_request

_MOTION_REQUEST_ATTEMPTED = False


def _emit(payload: dict[str, Any], *, exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=True))
    raise SystemExit(exit_code)


def _send(cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        data = send_control_request(
            cmd,
            args,
            socket_path=get_socket_path(),
            tcp_host=get_tcp_host(),
            tcp_port=get_tcp_port(),
            timeout_s=120.0,
        )
    except Exception as exc:
        raise RuntimeError(f"{cmd} request failed: {exc}") from exc
    return {"ok": True, "data": data}


def _ok_or_raise(resp: dict[str, Any]) -> dict[str, Any]:
    if not resp.get("ok"):
        raise RuntimeError(str(resp.get("error", "unknown error")))
    return dict(resp.get("data", {}))


def _current_joint_pos_rad() -> np.ndarray:
    status = _ok_or_raise(_send("status"))
    pos_deg = status.get("pos_deg")
    if not isinstance(pos_deg, list) or len(pos_deg) < 6:
        raise RuntimeError(f"Unexpected status payload: {status}")
    return np.deg2rad(np.asarray(pos_deg[:6], dtype=np.float64))


def _verified_info(expected_backend: str) -> dict[str, Any]:
    info = _ok_or_raise(_send("info"))
    actual_backend = str(info.get("backend", ""))
    if actual_backend != expected_backend:
        raise RuntimeError(
            "Backend identity mismatch: "
            f"expected={expected_backend}, actual={actual_backend or 'unknown'}"
        )
    return info


def _joint_limits_deg_from_info(info: dict[str, Any]) -> list[list[float]] | None:
    raw_limits = info.get("joint_limits_deg")
    if not isinstance(raw_limits, dict):
        return None

    limits_deg: list[list[float]] = []
    for idx in range(6):
        pair = raw_limits.get(f"J{idx + 1}")
        if not isinstance(pair, list) or len(pair) != 2:
            return None
        limits_deg.append([float(pair[0]), float(pair[1])])
    return limits_deg


def _rotation_matrix(axis: str, angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    if axis == "x":
        return np.array(
            [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]],
            dtype=np.float64,
        )
    if axis == "y":
        return np.array(
            [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]],
            dtype=np.float64,
        )
    if axis == "z":
        return np.array(
            [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
    raise ValueError(f"Unsupported axis: {axis}")


def _rpy_deg_from_matrix(rotation: np.ndarray) -> list[float]:
    sy = math.hypot(float(rotation[0, 0]), float(rotation[1, 0]))
    singular = sy < 1e-9
    if not singular:
        roll = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        pitch = math.atan2(float(-rotation[2, 0]), sy)
        yaw = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    else:
        roll = math.atan2(float(-rotation[1, 2]), float(rotation[1, 1]))
        pitch = math.atan2(float(-rotation[2, 0]), sy)
        yaw = 0.0
    return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]


def _pose_dict(transform: np.ndarray) -> dict[str, Any]:
    xyz_m = transform[:3, 3]
    rpy_deg = _rpy_deg_from_matrix(transform[:3, :3])
    return {
        "xyz_m": [float(v) for v in xyz_m.tolist()],
        "xyz_mm": [float(v * 1000.0) for v in xyz_m.tolist()],
        "rpy_deg": [float(v) for v in rpy_deg],
    }


def _apply_translation(
    transform: np.ndarray,
    *,
    axis: str,
    delta_m: float,
    frame: str,
) -> np.ndarray:
    axis_vectors = {
        "x": np.array([1.0, 0.0, 0.0], dtype=np.float64),
        "y": np.array([0.0, 1.0, 0.0], dtype=np.float64),
        "z": np.array([0.0, 0.0, 1.0], dtype=np.float64),
    }
    direction = axis_vectors[axis]
    world_delta = direction * delta_m
    if frame == "tool":
        world_delta = transform[:3, :3] @ world_delta
    target = transform.copy()
    target[:3, 3] = target[:3, 3] + world_delta
    return target


def _apply_rotation(
    transform: np.ndarray,
    *,
    axis: str,
    delta_deg: float,
    frame: str,
) -> np.ndarray:
    target = transform.copy()
    delta_rot = _rotation_matrix(axis, math.radians(delta_deg))
    if frame == "tool":
        target[:3, :3] = target[:3, :3] @ delta_rot
    else:
        target[:3, :3] = delta_rot @ target[:3, :3]
    return target


def _validate_joint_limits(
    kinematics: Kinematics,
    q: np.ndarray,
    *,
    margin_deg: float = 0.0,
) -> np.ndarray:
    lower = np.asarray(kinematics._model.lowerPositionLimit, dtype=np.float64).reshape(-1)
    upper = np.asarray(kinematics._model.upperPositionLimit, dtype=np.float64).reshape(-1)
    margin_rad = math.radians(max(0.0, float(margin_deg)))
    lower = lower + margin_rad
    upper = upper - margin_rad
    if np.any(lower >= upper):
        raise RuntimeError(f"Joint margin is too large: {margin_deg} deg")
    tol = 1e-6
    if np.any(q < lower - tol) or np.any(q > upper + tol):
        joint_index = int(np.argmax((q < lower - tol) | (q > upper + tol))) + 1
        raise RuntimeError(
            "IK solution violates joint limits/margin "
            f"(joint J{joint_index}, deg={np.rad2deg(q).round(2).tolist()})"
        )
    return np.clip(q, lower, upper)


def _snapshot_payload(
    *,
    kinematics: Kinematics,
    end_effector_frame: str,
    expected_backend: str,
) -> dict[str, Any]:
    q = _current_joint_pos_rad()
    transform = kinematics.fk(q, frame_name=end_effector_frame)
    status = _ok_or_raise(_send("status"))
    info = _verified_info(expected_backend)
    return {
        "ok": True,
        "backend": info.get("backend"),
        "control_mode": info.get("control_mode"),
        "endpoint": (
            get_socket_path()
            or f"tcp://{get_tcp_host()}:{get_tcp_port()}"
        ),
        "end_effector_frame": end_effector_frame,
        "joint_pos_deg": [float(v) for v in status.get("pos_deg", [])[:6]],
        "joint_limits_deg": _joint_limits_deg_from_info(info),
        "gripper": status.get("gripper"),
        "pose": _pose_dict(transform),
    }


def _execute_motion(
    *,
    joint_target_deg: list[float],
    speed: float,
    motion_mode: str,
) -> dict[str, Any]:
    global _MOTION_REQUEST_ATTEMPTED
    _MOTION_REQUEST_ATTEMPTED = True
    if motion_mode == "move":
        return _ok_or_raise(
            _send(
                "move",
                {
                    "joints": joint_target_deg,
                    "speed": speed,
                },
            )
        )
    if motion_mode == "command":
        return _ok_or_raise(_send("command", {"joints": joint_target_deg}))
    raise ValueError(f"Unsupported motion mode: {motion_mode}")


def _handle_snapshot(args: argparse.Namespace) -> None:
    kinematics = Kinematics(args.urdf, end_effector_frame=args.end_effector_frame)
    _emit(
        _snapshot_payload(
            kinematics=kinematics,
            end_effector_frame=args.end_effector_frame,
            expected_backend=args.expected_backend,
        )
    )


def _handle_step(args: argparse.Namespace) -> None:
    kinematics = Kinematics(args.urdf, end_effector_frame=args.end_effector_frame)
    current_q = _current_joint_pos_rad()
    current_transform = kinematics.fk(current_q, frame_name=args.end_effector_frame)

    if args.kind == "translation":
        target_transform = _apply_translation(
            current_transform,
            axis=args.axis,
            delta_m=args.delta,
            frame=args.frame,
        )
    else:
        target_transform = _apply_rotation(
            current_transform,
            axis=args.axis,
            delta_deg=args.delta,
            frame=args.frame,
        )

    converged, target_q = kinematics.ik(
        target_transform,
        init_q=current_q,
        frame_name=args.end_effector_frame,
        dt=args.ik_dt,
        pos_threshold=args.pos_threshold_m,
        ori_threshold=math.radians(args.ori_threshold_deg),
        damping=args.ik_damping,
        max_iters=args.max_iters,
    )
    if not converged:
        raise RuntimeError("IK did not converge for the requested end-effector step.")

    target_q = _validate_joint_limits(
        kinematics,
        target_q,
        margin_deg=args.joint_margin_deg,
    )
    max_joint_step_deg = float(
        np.max(np.abs(np.rad2deg(target_q - current_q)))
    )
    if max_joint_step_deg > args.max_joint_step_deg:
        raise RuntimeError(
            "IK solution exceeds one-step joint jump limit: "
            f"{max_joint_step_deg:.2f} > {args.max_joint_step_deg:.2f} deg"
        )
    joint_target_deg = [float(v) for v in np.rad2deg(target_q).tolist()]
    _execute_motion(
        joint_target_deg=joint_target_deg,
        speed=args.speed,
        motion_mode=args.motion_mode,
    )

    payload = _snapshot_payload(
        kinematics=kinematics,
        end_effector_frame=args.end_effector_frame,
        expected_backend=args.expected_backend,
    )
    payload.update(
        {
            "requested_step": {
                "kind": args.kind,
                "axis": args.axis,
                "delta": float(args.delta),
                "frame": args.frame,
                "motion_mode": args.motion_mode,
            },
            "ik_joint_target_deg": joint_target_deg,
            "target_pose": _pose_dict(target_transform),
        }
    )
    _emit(payload)


def _handle_joint_step(args: argparse.Namespace) -> None:
    joint_index = args.joint_index - 1
    if joint_index < 0 or joint_index >= 6:
        raise RuntimeError(f"Joint index out of range: {args.joint_index}")

    status = _ok_or_raise(_send("status"))
    current_deg = status.get("pos_deg")
    if not isinstance(current_deg, list) or len(current_deg) < 6:
        raise RuntimeError(f"Unexpected status payload: {status}")

    info = _verified_info(args.expected_backend)
    limits_deg = _joint_limits_deg_from_info(info)
    if limits_deg is None:
        raise RuntimeError("Joint soft limits are unavailable from the A1Z server.")

    lo_deg, hi_deg = limits_deg[joint_index]
    requested_deg = float(current_deg[joint_index]) + float(args.delta)
    applied_deg = min(max(requested_deg, lo_deg), hi_deg)

    target_deg = [float(v) for v in current_deg[:6]]
    target_deg[joint_index] = applied_deg
    _execute_motion(
        joint_target_deg=target_deg,
        speed=args.speed,
        motion_mode=args.motion_mode,
    )

    kinematics = Kinematics(args.urdf, end_effector_frame=args.end_effector_frame)
    payload = _snapshot_payload(
        kinematics=kinematics,
        end_effector_frame=args.end_effector_frame,
        expected_backend=args.expected_backend,
    )
    status_message = f"J{args.joint_index} -> {applied_deg:.1f} deg"
    if abs(applied_deg - requested_deg) > 1e-6:
        status_message = (
            f"J{args.joint_index} hit soft limit [{lo_deg:.1f}, {hi_deg:.1f}] deg"
        )
    payload.update(
        {
            "requested_joint_step": {
                "joint_index": int(args.joint_index),
                "delta_deg": float(args.delta),
                "requested_target_deg": requested_deg,
                "applied_target_deg": applied_deg,
                "soft_limit_deg": [lo_deg, hi_deg],
                "motion_mode": args.motion_mode,
            },
            "status_message": status_message,
        }
    )
    _emit(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Incremental A1Z teleop helper for Cartesian IK and per-joint trim."
    )
    parser.add_argument(
        "--urdf",
        default=os.environ.get("A1Z_CONTROL_URDF", get_default_control_urdf_path()),
        help="Control URDF for IK/FK.",
    )
    parser.add_argument(
        "--end-effector-frame",
        default=os.environ.get("A1Z_EE_FRAME", "grasp_tcp"),
        help="URDF frame name used as the controlled end effector.",
    )
    parser.add_argument(
        "--expected-backend",
        choices=["socketcan", "mock", "isaacsim"],
        default=get_default_backend(),
        help="Fail closed unless the connected server reports this backend.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot", help="Read the current pose and joint state.")

    step = sub.add_parser("step", help="Apply one Cartesian step and solve IK.")
    step.add_argument("--kind", choices=["translation", "rotation"], required=True)
    step.add_argument("--axis", choices=["x", "y", "z"], required=True)
    step.add_argument("--delta", type=float, required=True)
    step.add_argument("--frame", choices=["base", "tool"], default="base")
    step.add_argument("--speed", type=float, default=0.5)
    step.add_argument("--motion-mode", choices=["move", "command"], default="move")
    step.add_argument("--ik-dt", type=float, default=0.1)
    step.add_argument("--ik-damping", type=float, default=1e-6)
    step.add_argument("--max-iters", type=int, default=300)
    step.add_argument("--pos-threshold-m", type=float, default=5e-4)
    step.add_argument("--ori-threshold-deg", type=float, default=1.0)
    step.add_argument("--joint-margin-deg", type=float, default=2.0)
    step.add_argument("--max-joint-step-deg", type=float, default=15.0)

    joint_step = sub.add_parser("joint-step", help="Apply one incremental step to a single joint.")
    joint_step.add_argument("--joint-index", type=int, required=True, help="1-based joint index (J1..J6).")
    joint_step.add_argument("--delta", type=float, required=True, help="Increment in degrees.")
    joint_step.add_argument("--speed", type=float, default=0.5)
    joint_step.add_argument("--motion-mode", choices=["move", "command"], default="move")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        _verified_info(args.expected_backend)
        if args.command == "snapshot":
            _handle_snapshot(args)
        if args.command == "step":
            _handle_step(args)
        if args.command == "joint-step":
            _handle_joint_step(args)
        raise RuntimeError(f"Unsupported command: {args.command}")
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": str(exc),
                "motion_request_attempted": _MOTION_REQUEST_ATTEMPTED,
            },
            exit_code=1,
        )


if __name__ == "__main__":
    main()
