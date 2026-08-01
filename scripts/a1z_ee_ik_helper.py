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
from a1z_ext.robots.cartesian_jog import (
    apply_rotation,
    apply_translation,
    compose_command_space_joint_target,
    pose_error,
)

_MOTION_REQUEST_ATTEMPTED = False
_MOTION_OUTCOME_VERIFIED = False


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
        "rotation_matrix": [
            [float(value) for value in row]
            for row in transform[:3, :3].tolist()
        ],
    }


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
    payload = {
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
        "gripper_target": status.get("gripper_target"),
        "gripper_measured": status.get("gripper_measured"),
        "pose": _pose_dict(transform),
    }
    for key in ("running", "faulted", "fault_message", "estopped"):
        if key in status:
            payload[key] = status[key]
        elif key in info:
            payload[key] = info[key]
    return payload


def _execute_motion(
    *,
    joint_target_deg: list[float],
    joint_delta_deg: list[float] | None = None,
    speed: float,
    motion_mode: str,
) -> dict[str, Any]:
    global _MOTION_OUTCOME_VERIFIED, _MOTION_REQUEST_ATTEMPTED
    _MOTION_REQUEST_ATTEMPTED = True
    if motion_mode == "move":
        result = _ok_or_raise(
            _send(
                "move",
                {
                    "joints": joint_target_deg,
                    "speed": speed,
                },
            )
        )
        verification = dict(result.get("verification", {}) or {})
        _MOTION_OUTCOME_VERIFIED = bool(verification.get("reached"))
        return result
    if motion_mode == "cartesian_jog":
        if joint_delta_deg is None:
            raise ValueError("cartesian_jog requires a six-axis joint increment")
        result = _ok_or_raise(
            _send(
                "cartesian_jog",
                {
                    "joint_delta_deg": joint_delta_deg,
                    "speed": speed,
                },
            )
        )
        verification = dict(result.get("verification", {}) or {})
        _MOTION_OUTCOME_VERIFIED = bool(verification.get("settled"))
        return result
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
    info = _verified_info(args.expected_backend)
    current_transform = kinematics.fk(current_q, frame_name=args.end_effector_frame)

    if args.kind == "translation":
        target_transform = apply_translation(
            current_transform,
            axis=args.axis,
            delta_m=args.delta,
            frame=args.frame,
        )
    else:
        target_transform = apply_rotation(
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

    solved_q = _validate_joint_limits(
        kinematics,
        target_q,
        margin_deg=args.joint_margin_deg,
    )
    max_joint_step_deg = float(
        np.max(np.abs(np.rad2deg(solved_q - current_q)))
    )
    if max_joint_step_deg > args.max_joint_step_deg:
        raise RuntimeError(
            "IK solution exceeds one-step joint jump limit: "
            f"{max_joint_step_deg:.2f} > {args.max_joint_step_deg:.2f} deg"
        )
    raw_command_pos_deg = info.get("command_pos_deg")
    if not isinstance(raw_command_pos_deg, list) or len(raw_command_pos_deg) < 6:
        raise RuntimeError(
            "A1Z server did not expose the SDK six-axis command trajectory."
        )
    command_q = np.deg2rad(
        np.asarray(raw_command_pos_deg[:6], dtype=np.float64)
    )
    command_target_q, joint_delta_q = compose_command_space_joint_target(
        current_q,
        solved_q,
        command_q,
    )
    command_target_q = _validate_joint_limits(
        kinematics,
        command_target_q,
        margin_deg=args.joint_margin_deg,
    )
    solved_target_deg = [float(v) for v in np.rad2deg(solved_q).tolist()]
    command_start_deg = [float(v) for v in np.rad2deg(command_q).tolist()]
    command_target_deg = [
        float(v) for v in np.rad2deg(command_target_q).tolist()
    ]
    joint_delta_deg = [float(v) for v in np.rad2deg(joint_delta_q).tolist()]
    motion_result = _execute_motion(
        joint_target_deg=command_target_deg,
        joint_delta_deg=joint_delta_deg,
        speed=args.speed,
        motion_mode=args.motion_mode,
    )

    payload = _snapshot_payload(
        kinematics=kinematics,
        end_effector_frame=args.end_effector_frame,
        expected_backend=args.expected_backend,
    )
    actual_pose = kinematics.fk(
        np.deg2rad(np.asarray(payload["joint_pos_deg"][:6], dtype=np.float64)),
        frame_name=args.end_effector_frame,
    )
    translation_error_m, orientation_error_deg = pose_error(
        target_transform,
        actual_pose,
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
            "ik_solution_from_measured_deg": solved_target_deg,
            "ik_joint_delta_deg": joint_delta_deg,
            "command_start_deg": command_start_deg,
            "command_target_deg": command_target_deg,
            "target_pose": _pose_dict(target_transform),
            "verification": {
                "translation_error_mm": translation_error_m * 1000.0,
                "orientation_error_deg": orientation_error_deg,
                "diagnostic_only": True,
                "completion_basis": "joint_feedback_settled",
            },
            "joint_verification": motion_result.get("verification"),
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
    motion_result = _execute_motion(
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
            "joint_verification": motion_result.get("verification"),
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
    step.add_argument(
        "--motion-mode",
        choices=["move", "cartesian_jog", "command"],
        default="cartesian_jog",
    )
    step.add_argument("--ik-dt", type=float, default=0.1)
    step.add_argument("--ik-damping", type=float, default=1e-6)
    step.add_argument("--max-iters", type=int, default=300)
    # Numerical IK convergence only; neither value determines physical arrival.
    step.add_argument("--pos-threshold-m", type=float, default=5e-5)
    step.add_argument("--ori-threshold-deg", type=float, default=0.05)
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
                "motion_outcome_verified": _MOTION_OUTCOME_VERIFIED,
            },
            exit_code=1,
        )


if __name__ == "__main__":
    main()
