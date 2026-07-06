#!/usr/bin/env python3

"""Execute a selected A1Z grasp plan through the local socket server."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a selected A1Z grasp plan.")
    parser.add_argument("--plan", required=True, help="Path to selected_plan.json")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--output", default="", help="Optional execution result JSON path")
    parser.add_argument("--arm-speed", type=float, default=0.2)
    parser.add_argument("--pre-open", action="store_true")
    parser.add_argument("--settle-s", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _send_socket_request(socket_path: str, cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    request = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(120.0)
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


def _status(socket_path: str) -> dict[str, Any]:
    return _send_socket_request(socket_path, "status")


def _move(socket_path: str, joints_rad: list[float], *, speed: float) -> dict[str, Any]:
    joints_deg = np.rad2deg(np.asarray(joints_rad, dtype=np.float64)).tolist()
    return _send_socket_request(socket_path, "move", {"joints": [float(v) for v in joints_deg], "speed": float(speed)})


def _gripper(socket_path: str, value: float) -> dict[str, Any]:
    return _send_socket_request(socket_path, "gripper", {"value": float(value)})


def _grasp_attach(
    socket_path: str,
    *,
    target_prim_path: str,
    timeout_s: float,
    contact_window_s: float,
    require_bilateral_contact: bool,
) -> dict[str, Any]:
    return _send_socket_request(
        socket_path,
        "grasp_attach",
        {
            "target_prim_path": str(target_prim_path or ""),
            "timeout_s": float(timeout_s),
            "contact_window_s": float(contact_window_s),
            "require_bilateral_contact": bool(require_bilateral_contact),
        },
    )


def _grasp_contacts(
    socket_path: str,
    *,
    target_prim_path: str,
    require_bilateral_contact: bool,
) -> dict[str, Any]:
    return _send_socket_request(
        socket_path,
        "grasp_contacts",
        {
            "target_prim_path": str(target_prim_path or ""),
            "require_bilateral_contact": bool(require_bilateral_contact),
        },
    )


def _grasp_release(socket_path: str, *, open_gripper: bool = True, timeout_s: float = 2.0) -> dict[str, Any]:
    return _send_socket_request(
        socket_path,
        "grasp_release",
        {
            "open_gripper": bool(open_gripper),
            "timeout_s": float(timeout_s),
        },
    )


def main() -> int:
    args = build_parser().parse_args()
    plan_path = Path(args.plan).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    result: dict[str, Any] = {
        "plan_path": str(plan_path),
        "dry_run": bool(args.dry_run),
        "steps": [],
        "success": False,
    }
    execution_policy = dict(plan.get("execution_policy", {}) or {})
    backend_execution_details: dict[str, Any] = {}

    try:
        if bool(args.pre_open):
            open_value = float(plan.get("gripper_commands", {}).get("open_before_grasp", 1.0))
            step = {"type": "gripper_open", "value": open_value}
            if not args.dry_run:
                step["response"] = _gripper(args.socket_path, open_value)
                time.sleep(max(0.0, float(args.settle_s)))
            result["steps"].append(step)

        for segment in plan.get("joint_trajectory_segments", []):
            step = {
                "type": segment.get("segment_type", "move"),
                "target_joint_rad": list(segment.get("target_joint_rad", [])),
                "timeout_s": float(segment.get("timeout_s", 0.0)),
            }
            if not args.dry_run:
                step["status_before"] = _status(args.socket_path)
                step["response"] = _move(
                    args.socket_path,
                    step["target_joint_rad"],
                    speed=float(args.arm_speed),
                )
                time.sleep(max(0.0, float(args.settle_s)))
                step["status_after"] = _status(args.socket_path)
            result["steps"].append(step)

            if step["type"] == "approach":
                contact_snapshot_step = {"type": "approach_contact_snapshot"}
                close_value = float(plan.get("gripper_commands", {}).get("close_after_approach", 0.0))
                close_step = {"type": "gripper_close", "value": close_value}
                if not args.dry_run:
                    contact_snapshot_step["response"] = _grasp_contacts(
                        args.socket_path,
                        target_prim_path=str(execution_policy.get("target_prim_path", "") or ""),
                        require_bilateral_contact=bool(execution_policy.get("require_bilateral_contact", True)),
                    )
                    snapshot = dict(contact_snapshot_step["response"])
                    left_details = list(snapshot.get("left_contact_details", []) or [])
                    right_details = list(snapshot.get("right_contact_details", []) or [])
                    snapshot_summary = {
                        "target_prim_path": snapshot.get("target_prim_path"),
                        "target_body_path": snapshot.get("target_body_path"),
                        "snapshot_body_path": snapshot.get("snapshot_body_path"),
                        "snapshot_ok": snapshot.get("snapshot_ok"),
                        "ground_contact_present": snapshot.get("ground_contact_present"),
                        "left_contacts": [
                            {
                                "body1": detail.get("body1"),
                                "collider1": detail.get("collider1"),
                                "separation": detail.get("separation"),
                            }
                            for detail in left_details
                        ],
                        "right_contacts": [
                            {
                                "body1": detail.get("body1"),
                                "collider1": detail.get("collider1"),
                                "separation": detail.get("separation"),
                            }
                            for detail in right_details
                        ],
                    }
                    contact_snapshot_step["summary"] = snapshot_summary
                    print(
                        json.dumps(
                            {
                                "approach_contact_snapshot": snapshot_summary,
                            },
                            ensure_ascii=False,
                        )
                    )
                result["steps"].append(contact_snapshot_step)
                if not args.dry_run:
                    if str(execution_policy.get("grasp_mode", "")) == "sim_contact_attach":
                        close_step["type"] = "grasp_attach"
                        close_step["response"] = _grasp_attach(
                            args.socket_path,
                            target_prim_path=str(execution_policy.get("target_prim_path", "") or ""),
                            timeout_s=float(execution_policy.get("timeout_s", 2.0)),
                            contact_window_s=float(execution_policy.get("contact_window_s", 0.15)),
                            require_bilateral_contact=bool(execution_policy.get("require_bilateral_contact", True)),
                        )
                        backend_execution_details = dict(close_step["response"])
                        if not bool(close_step["response"].get("success", False)):
                            raise RuntimeError(str(close_step["response"].get("failure_reason", "grasp_attach_failed")))
                    else:
                        close_step["response"] = _gripper(args.socket_path, close_value)
                    time.sleep(max(0.0, float(args.settle_s)))
                result["steps"].append(close_step)

        if not args.dry_run and bool(execution_policy.get("release_after_retreat", False)):
            release_step = {"type": "grasp_release"}
            release_step["response"] = _grasp_release(
                args.socket_path,
                open_gripper=True,
                timeout_s=float(execution_policy.get("release_timeout_s", 2.0)),
            )
            result["steps"].append(release_step)
        result["final_status"] = _status(args.socket_path) if not args.dry_run else {}
        if backend_execution_details:
            result["backend_execution_details"] = backend_execution_details
        result["success"] = True
    except Exception as exc:
        result["success"] = False
        result["error"] = str(exc)
        if backend_execution_details:
            result["backend_execution_details"] = backend_execution_details
        if not args.dry_run:
            try:
                result["final_status"] = _status(args.socket_path)
            except Exception as status_exc:
                result["final_status_error"] = str(status_exc)

    output_path = Path(args.output).resolve() if args.output else None
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
