#!/usr/bin/env python3

"""Execute a backend-neutral A1Z joint/grasp plan through the control server."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = REPO_ROOT / "vendor" / "GALAXEA-A1Z"
for path in (REPO_ROOT, SDK_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from a1z_ext.config import (
    get_arm_motion_speed_limits,
    get_socket_path,
    get_tcp_host,
    get_tcp_port,
    validate_arm_motion_speed,
)
from a1z_ext.control_client import send_control_request

ARM_SPEED_LIMITS = get_arm_motion_speed_limits()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="Path to selected_plan.json")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--tcp-host", default=get_tcp_host())
    parser.add_argument("--tcp-port", type=int, default=get_tcp_port())
    parser.add_argument("--output", default="", help="Optional execution result JSON")
    parser.add_argument(
        "--arm-speed",
        type=validate_arm_motion_speed,
        default=ARM_SPEED_LIMITS.default,
        metavar="RAD_S",
        help=(
            "Joint-space speed in rad/s "
            f"({ARM_SPEED_LIMITS.minimum:g}–{ARM_SPEED_LIMITS.maximum:g}, "
            f"default {ARM_SPEED_LIMITS.default:g})"
        ),
    )
    parser.add_argument("--pre-open", action="store_true")
    parser.add_argument("--settle-s", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _request(
    args: argparse.Namespace,
    command: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    return send_control_request(
        command,
        payload,
        socket_path=args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
        timeout_s=timeout_s,
    )


def _wait_for_joint_target(
    args: argparse.Namespace,
    target_rad: list[float],
    *,
    timeout_s: float,
    tolerance_rad: float = 0.10,
) -> dict[str, Any]:
    target = np.asarray(target_rad, dtype=np.float64)
    deadline = time.monotonic() + max(0.1, timeout_s)
    last_status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last_status = _request(args, "status", timeout_s=10.0)
        positions_deg = last_status.get("pos_deg")
        if isinstance(positions_deg, list) and len(positions_deg) >= 6:
            actual = np.deg2rad(np.asarray(positions_deg[:6], dtype=np.float64))
            error = np.abs(actual - target)
            if float(np.max(error)) <= tolerance_rad:
                last_status["max_joint_error_rad"] = float(np.max(error))
                return last_status
        time.sleep(0.1)
    raise TimeoutError(
        f"arm_target_timeout after {timeout_s:.2f}s; last_status={last_status}"
    )


def _validate_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    segments = plan.get("joint_trajectory_segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("plan must contain non-empty joint_trajectory_segments")
    validated: list[dict[str, Any]] = []
    for index, raw in enumerate(segments):
        if not isinstance(raw, dict):
            raise ValueError(f"segment {index} must be an object")
        target = raw.get("target_joint_rad")
        if not isinstance(target, list) or len(target) != 6:
            raise ValueError(f"segment {index} target_joint_rad must contain 6 values")
        validated.append(
            {
                "segment_type": str(raw.get("segment_type", "move")),
                "target_joint_rad": [float(value) for value in target],
                "timeout_s": float(raw.get("timeout_s", 30.0)),
            }
        )
    if not any(segment["segment_type"] == "approach" for segment in validated):
        raise ValueError("plan must contain an approach segment")
    return validated


def main() -> int:
    args = build_parser().parse_args()
    plan_path = Path(args.plan).resolve()
    result: dict[str, Any] = {
        "plan_path": str(plan_path),
        "dry_run": bool(args.dry_run),
        "steps": [],
        "success": False,
    }

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        segments = _validate_plan(plan)
        policy = dict(plan.get("execution_policy", {}) or {})
        close_timeout_s = float(policy.get("grasp_timeout_s", 15.0))
        release_timeout_s = float(policy.get("release_timeout_s", 3.0))

        if args.pre_open:
            step: dict[str, Any] = {"type": "gripper_open"}
            if not args.dry_run:
                step["response"] = _request(
                    args, "gripper", {"value": 1.0}, timeout_s=30.0
                )
            result["steps"].append(step)

        for segment in segments:
            step = {
                "type": segment["segment_type"],
                "target_joint_rad": segment["target_joint_rad"],
                "timeout_s": segment["timeout_s"],
            }
            if not args.dry_run:
                joints_deg = np.rad2deg(
                    np.asarray(segment["target_joint_rad"], dtype=np.float64)
                ).tolist()
                step["response"] = _request(
                    args,
                    "move",
                    {
                        "joints": [float(value) for value in joints_deg],
                        "speed": float(args.arm_speed),
                    },
                    timeout_s=max(30.0, segment["timeout_s"] + 5.0),
                )
                step["status_after"] = _wait_for_joint_target(
                    args,
                    segment["target_joint_rad"],
                    timeout_s=segment["timeout_s"],
                )
                time.sleep(max(0.0, args.settle_s))
            result["steps"].append(step)

            if segment["segment_type"] == "approach":
                close_step: dict[str, Any] = {"type": "grasp_close"}
                if not args.dry_run:
                    close_step["response"] = _request(
                        args,
                        "grasp_close",
                        {"timeout_s": close_timeout_s},
                        timeout_s=max(30.0, close_timeout_s + 5.0),
                    )
                    if not bool(close_step["response"].get("success")):
                        raise RuntimeError(
                            str(
                                close_step["response"].get("failure_reason")
                                or "grasp_close_failed"
                            )
                        )
                result["steps"].append(close_step)

            if segment["segment_type"] in {"lift", "retreat"} and not args.dry_run:
                status_step = {
                    "type": f"{segment['segment_type']}_grasp_status",
                    "response": _request(args, "grasp_status", timeout_s=10.0),
                }
                result["steps"].append(status_step)
                if not bool(status_step["response"].get("object_detected")):
                    raise RuntimeError(f"object_lost_during_{segment['segment_type']}")

        if bool(policy.get("release_after_retreat", False)):
            release_step: dict[str, Any] = {"type": "grasp_release"}
            if not args.dry_run:
                release_step["response"] = _request(
                    args,
                    "grasp_release",
                    {"timeout_s": release_timeout_s},
                    timeout_s=max(30.0, release_timeout_s + 5.0),
                )
                if not bool(release_step["response"].get("success")):
                    raise RuntimeError(
                        str(
                            release_step["response"].get("failure_reason")
                            or "grasp_release_failed"
                        )
                    )
            result["steps"].append(release_step)

        result["final_status"] = (
            {} if args.dry_run else _request(args, "status", timeout_s=10.0)
        )
        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc)
        if not args.dry_run:
            try:
                result["final_status"] = _request(args, "status", timeout_s=10.0)
            except Exception as status_exc:
                result["final_status_error"] = str(status_exc)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
