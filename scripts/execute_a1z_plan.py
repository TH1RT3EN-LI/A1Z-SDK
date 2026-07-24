#!/usr/bin/env python3

"""Execute a selected A1Z grasp plan through the local socket server."""

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

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from a1z_ext.config import (
    get_arm_motion_speed_limits,
    get_socket_path,
    get_tcp_host,
    get_tcp_port,
    validate_arm_motion_speed,
)
from a1z_ext.control_client import send_control_request

MIN_ARM_TARGET_WAIT_S = 120.0
GRASP_SETTLE_MAX_ERROR_RAD = float(np.deg2rad(2.0))
GRASP_SETTLE_MAX_LEAD_VEL_RAD_S = 0.12
GRASP_SETTLE_MAX_WRIST_VEL_RAD_S = 0.20
GRASP_SETTLE_REQUIRED_SAMPLES = 3
ARM_SPEED_LIMITS = get_arm_motion_speed_limits()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a selected A1Z grasp plan.")
    parser.add_argument("--plan", required=True, help="Path to selected_plan.json")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--tcp-host", default=get_tcp_host())
    parser.add_argument("--tcp-port", type=int, default=get_tcp_port())
    parser.add_argument("--output", default="", help="Optional execution result JSON path")
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


def _send_control(
    args: argparse.Namespace,
    cmd: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    return send_control_request(
        cmd,
        payload,
        socket_path=args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
        timeout_s=float(timeout_s),
    )


def _status(args: argparse.Namespace) -> dict[str, Any]:
    return _send_control(args, "status", timeout_s=20.0)


def _best_effort_status(args: argparse.Namespace) -> dict[str, Any] | None:
    try:
        return _status(args)
    except Exception:
        return None


def _move(args: argparse.Namespace, joints_rad: list[float], *, speed: float) -> dict[str, Any]:
    joints_deg = np.rad2deg(np.asarray(joints_rad, dtype=np.float64)).tolist()
    return _send_control(
        args,
        "move",
        {"joints": [float(v) for v in joints_deg], "speed": float(speed)},
        timeout_s=120.0,
    )


def _gripper(args: argparse.Namespace, value: float) -> dict[str, Any]:
    return _send_control(args, "gripper", {"value": float(value)}, timeout_s=30.0)


def _grasp_attach(
    args: argparse.Namespace,
    *,
    target_prim_path: str,
    timeout_s: float,
    contact_window_s: float,
    require_bilateral_contact: bool,
) -> dict[str, Any]:
    return _send_control(
        args,
        "grasp_attach",
        {
            "target_prim_path": str(target_prim_path or ""),
            "timeout_s": float(timeout_s),
            "contact_window_s": float(contact_window_s),
            "require_bilateral_contact": bool(require_bilateral_contact),
        },
        timeout_s=120.0,
    )


def _grasp_close_physical(
    args: argparse.Namespace,
    *,
    timeout_s: float,
    controller_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    return _send_control(
        args,
        "grasp_close_v2",
        {
            "timeout_s": float(timeout_s),
            "controller_profile": controller_profile,
        },
        timeout_s=max(120.0, float(timeout_s) + 10.0),
    )


def _grasp_contacts(
    args: argparse.Namespace,
    *,
    target_prim_path: str,
    require_bilateral_contact: bool,
) -> dict[str, Any]:
    return _send_control(
        args,
        "grasp_contacts",
        {
            "target_prim_path": str(target_prim_path or ""),
            "require_bilateral_contact": bool(require_bilateral_contact),
        },
        timeout_s=30.0,
    )


def _grasp_release(args: argparse.Namespace, *, open_gripper: bool = True, timeout_s: float = 2.0) -> dict[str, Any]:
    return _send_control(
        args,
        "grasp_release",
        {
            "open_gripper": bool(open_gripper),
            "timeout_s": float(timeout_s),
        },
        timeout_s=60.0,
    )


def _grasp_release_physical(args: argparse.Namespace, *, timeout_s: float = 3.0) -> dict[str, Any]:
    return _send_control(
        args,
        "grasp_release_v2",
        {"timeout_s": float(timeout_s)},
        timeout_s=max(60.0, float(timeout_s) + 10.0),
    )


def _grasp_status_physical(args: argparse.Namespace) -> dict[str, Any]:
    return _send_control(args, "grasp_status_v2", timeout_s=30.0)


def _prim_debug(args: argparse.Namespace, *, prim_path: str) -> dict[str, Any]:
    if not prim_path.startswith("/"):
        raise ValueError("prim_debug requires an absolute prim path")
    return _send_control(
        args,
        "prim_debug",
        {"prim_path": prim_path},
        timeout_s=30.0,
    )


def _sample_physical_status(
    args: argparse.Namespace,
    *,
    duration_s: float,
    period_s: float = 0.1,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + max(0.0, float(duration_s))
    samples: list[dict[str, Any]] = []
    while True:
        sample = _grasp_status_physical(args)
        sample["sample_time_s"] = time.time()
        samples.append(sample)
        if time.monotonic() >= deadline:
            return samples
        time.sleep(max(0.02, float(period_s)))


def _translation(value: object) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    return (float(value[0]), float(value[1]), float(value[2]))


def _debug_translation(debug: dict[str, Any]) -> tuple[float, float, float] | None:
    return _translation(debug.get("physics_world_translation") or debug.get("world_translation"))


def _evaluate_physical_execution(
    *,
    target_before: dict[str, Any],
    close: dict[str, Any],
    lift_samples: list[dict[str, Any]],
    retreat_samples: list[dict[str, Any]],
    release: dict[str, Any],
    release_samples: list[dict[str, Any]],
    minimum_lift_m: float,
    minimum_hold_ratio: float,
) -> dict[str, Any]:
    before_position = (
        _debug_translation(target_before)
        or _translation(close.get("initial_target_world_translation_m"))
    )
    held_samples = [*lift_samples, *retreat_samples]
    held_positions = [
        position
        for sample in lift_samples
        if (position := _translation(sample.get("target_world_translation_m"))) is not None
    ]
    lift_m = (
        None
        if before_position is None or not held_positions
        else max(position[2] - before_position[2] for position in held_positions)
    )
    bilateral_holding = [
        sample
        for sample in held_samples
        if sample.get("phase") == "holding" and bool(sample.get("bilateral_contact"))
    ]
    hold_ratio = len(bilateral_holding) / len(held_samples) if held_samples else 0.0
    all_samples = [close, *held_samples, release, *release_samples]
    maximum_constraint_delta = max(
        (int(sample.get("constraint_count_delta", 0)) for sample in all_samples),
        default=0,
    )
    target_physics_unchanged = not any(
        bool(sample.get("target_physics_state_mutated", False)) for sample in all_samples
    )
    final_release = release_samples[-1] if release_samples else release
    checks = {
        "close_reached_holding": bool(close.get("success")) and close.get("phase") == "holding",
        "constraint_delta_zero": maximum_constraint_delta == 0,
        "target_physics_state_unchanged": target_physics_unchanged,
        "minimum_lift_reached": lift_m is not None and lift_m >= float(minimum_lift_m),
        "bilateral_hold_ratio_reached": hold_ratio >= float(minimum_hold_ratio),
        "release_completed": bool(release.get("success")) and release.get("phase") == "released",
        "released_from_gripper": (
            final_release.get("phase") == "released"
            and not bool(final_release.get("bilateral_contact"))
            and final_release.get("attached_object_path") in {None, ""}
            and final_release.get("attachment_joint_path") in {None, ""}
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": {
            "lift_m": lift_m,
            "bilateral_hold_ratio": hold_ratio,
            "held_sample_count": len(held_samples),
            "maximum_constraint_delta": maximum_constraint_delta,
            "target_physics_state_unchanged": target_physics_unchanged,
        },
    }


def _joint_error_summary(
    actual_deg: list[float] | tuple[float, ...],
    target_rad: list[float],
) -> dict[str, float]:
    actual_rad = np.deg2rad(np.asarray(actual_deg[:6], dtype=np.float64))
    target_arr = np.asarray(target_rad[:6], dtype=np.float64)
    err = np.abs(actual_rad - target_arr)
    lead_max = float(np.max(err[:4])) if err.size >= 4 else float(np.max(err))
    wrist_max = float(np.max(err[4:6])) if err.size >= 6 else lead_max
    return {
        "max_err_rad": float(np.max(err)) if err.size else 0.0,
        "lead_max_err_rad": lead_max,
        "wrist_max_err_rad": wrist_max,
    }


def _joint_velocity_summary(
    velocity_rad_s: list[float] | tuple[float, ...],
) -> dict[str, float]:
    velocity = np.abs(np.asarray(velocity_rad_s[:6], dtype=np.float64))
    lead_max = float(np.max(velocity[:4])) if velocity.size >= 4 else float(np.max(velocity))
    wrist_max = float(np.max(velocity[4:6])) if velocity.size >= 6 else lead_max
    return {
        "max_vel_rad_s": float(np.max(velocity)) if velocity.size else 0.0,
        "lead_max_vel_rad_s": lead_max,
        "wrist_max_vel_rad_s": wrist_max,
    }


def _wait_for_arm_target(
    args: argparse.Namespace,
    target_joint_rad: list[float],
    *,
    timeout_s: float,
    require_grasp_settle: bool = False,
) -> dict[str, Any]:
    deadline = time.time() + max(float(timeout_s), MIN_ARM_TARGET_WAIT_S)
    last_summary: dict[str, float] | None = None
    last_velocity_summary: dict[str, float] | None = None
    stable_samples = 0
    while time.time() < deadline:
        status = _status(args)
        pos_deg = status.get("pos_deg")
        if isinstance(pos_deg, list) and len(pos_deg) >= 6:
            summary = _joint_error_summary(pos_deg, target_joint_rad)
            last_summary = summary
            position_reached = (
                summary["lead_max_err_rad"] <= 0.10
                and summary["wrist_max_err_rad"] <= 0.35
            )
            if not require_grasp_settle and position_reached:
                status["target_error_summary"] = summary
                return status
            velocity_rad_s = status.get("vel_rad_s")
            if (
                require_grasp_settle
                and isinstance(velocity_rad_s, list)
                and len(velocity_rad_s) >= 6
            ):
                velocity_summary = _joint_velocity_summary(velocity_rad_s)
                last_velocity_summary = velocity_summary
                grasp_ready = (
                    summary["max_err_rad"] <= GRASP_SETTLE_MAX_ERROR_RAD
                    and velocity_summary["lead_max_vel_rad_s"]
                    <= GRASP_SETTLE_MAX_LEAD_VEL_RAD_S
                    and velocity_summary["wrist_max_vel_rad_s"]
                    <= GRASP_SETTLE_MAX_WRIST_VEL_RAD_S
                )
                stable_samples = stable_samples + 1 if grasp_ready else 0
                if stable_samples >= GRASP_SETTLE_REQUIRED_SAMPLES:
                    status["target_error_summary"] = summary
                    status["grasp_settle_summary"] = {
                        **velocity_summary,
                        "stable_samples": stable_samples,
                        "required_samples": GRASP_SETTLE_REQUIRED_SAMPLES,
                    }
                    return status
        time.sleep(0.1 if require_grasp_settle else 0.25)
    error_text = "arm_target_timeout"
    if last_summary is not None:
        error_text = (
            f"arm_target_timeout max_err_rad={last_summary['max_err_rad']:.4f} "
            f"lead_max_err_rad={last_summary['lead_max_err_rad']:.4f} "
            f"wrist_max_err_rad={last_summary['wrist_max_err_rad']:.4f}"
        )
    if require_grasp_settle and last_velocity_summary is not None:
        error_text += (
            f" lead_max_vel_rad_s={last_velocity_summary['lead_max_vel_rad_s']:.4f}"
            f" wrist_max_vel_rad_s={last_velocity_summary['wrist_max_vel_rad_s']:.4f}"
            f" stable_samples={stable_samples}/{GRASP_SETTLE_REQUIRED_SAMPLES}"
        )
    raise TimeoutError(error_text)


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
    grasp_mode = str(execution_policy.get("grasp_mode", "raw_gripper") or "raw_gripper")
    backend_execution_details: dict[str, Any] = {}
    target_before_approach: dict[str, Any] = {}
    physical_close: dict[str, Any] = {}
    lift_samples: list[dict[str, Any]] = []
    retreat_samples: list[dict[str, Any]] = []
    physical_release: dict[str, Any] = {}
    release_samples: list[dict[str, Any]] = []

    try:
        if grasp_mode not in {"physical_v2", "sim_contact_attach", "raw_gripper"}:
            raise ValueError(f"unsupported execution_policy.grasp_mode: {grasp_mode}")
        if grasp_mode == "physical_v2":
            target_body_path = ""
            controller_profile = execution_policy.get("controller_profile")
            if not isinstance(controller_profile, dict):
                raise ValueError("execution_policy.controller_profile must be an object")
        else:
            target_body_path = str(
                execution_policy.get("target_body_path")
                or execution_policy.get("target_prim_path")
                or ""
            )
        if bool(args.pre_open):
            open_value = float(plan.get("gripper_commands", {}).get("open_before_grasp", 1.0))
            step = {"type": "gripper_open", "value": open_value}
            if not args.dry_run:
                step["response"] = _gripper(args, open_value)
                time.sleep(max(0.0, float(args.settle_s)))
            result["steps"].append(step)

        for segment in plan.get("joint_trajectory_segments", []):
            step = {
                "type": segment.get("segment_type", "move"),
                "target_joint_rad": list(segment.get("target_joint_rad", [])),
                "timeout_s": float(segment.get("timeout_s", 0.0)),
            }
            if not args.dry_run:
                if (
                    step["type"] == "approach"
                    and grasp_mode == "physical_v2"
                    and target_body_path.startswith("/")
                ):
                    target_before_approach = _prim_debug(args, prim_path=target_body_path)
                    step["target_before_approach"] = target_before_approach
                status_before = _best_effort_status(args)
                if status_before is not None:
                    step["status_before"] = status_before
                else:
                    step["status_before_error"] = "status_unavailable"
                step["response"] = _move(
                    args,
                    step["target_joint_rad"],
                    speed=float(args.arm_speed),
                )
                time.sleep(max(0.0, float(args.settle_s)))
                step["status_after"] = _wait_for_arm_target(
                    args,
                    step["target_joint_rad"],
                    timeout_s=float(step["timeout_s"]),
                    require_grasp_settle=(
                        step["type"] == "approach" and grasp_mode == "physical_v2"
                    ),
                )
            result["steps"].append(step)

            if step["type"] == "approach":
                contact_snapshot_step = {"type": "approach_contact_snapshot"}
                close_value = float(plan.get("gripper_commands", {}).get("close_after_approach", 0.0))
                close_step = {"type": "gripper_close", "value": close_value}
                if not args.dry_run:
                    contact_snapshot_step["response"] = _grasp_contacts(
                        args,
                        target_prim_path=(
                            ""
                            if grasp_mode == "physical_v2"
                            else str(execution_policy.get("target_prim_path", "") or "")
                        ),
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
                    if grasp_mode == "physical_v2":
                        close_step["type"] = "grasp_close_v2"
                        controller_profile = execution_policy.get("controller_profile")
                        close_step["response"] = _grasp_close_physical(
                            args,
                            timeout_s=float(execution_policy.get("timeout_s", 15.0)),
                            controller_profile=controller_profile,
                        )
                        physical_close = dict(close_step["response"])
                        discovered_target = str(
                            close_step["response"].get("target_body_path", "") or ""
                        )
                        if not discovered_target.startswith("/"):
                            raise RuntimeError(
                                "physical_v2 did not discover a bilateral-contact rigid body"
                            )
                        target_body_path = discovered_target
                        backend_execution_details = dict(close_step["response"])
                        if not bool(close_step["response"].get("success", False)):
                            raise RuntimeError(
                                str(close_step["response"].get("failure_reason", "physical_grasp_failed"))
                            )
                        if int(close_step["response"].get("constraint_count_delta", -1)) != 0:
                            raise RuntimeError("physical_grasp_created_constraint")
                    elif grasp_mode == "sim_contact_attach":
                        close_step["type"] = "grasp_attach"
                        close_step["response"] = _grasp_attach(
                            args,
                            target_prim_path=str(execution_policy.get("target_prim_path", "") or ""),
                            timeout_s=float(execution_policy.get("timeout_s", 2.0)),
                            contact_window_s=float(execution_policy.get("contact_window_s", 0.15)),
                            require_bilateral_contact=bool(execution_policy.get("require_bilateral_contact", True)),
                        )
                        backend_execution_details = dict(close_step["response"])
                        if not bool(close_step["response"].get("success", False)):
                            raise RuntimeError(str(close_step["response"].get("failure_reason", "grasp_attach_failed")))
                    else:
                        close_step["response"] = _gripper(args, close_value)
                    time.sleep(max(0.0, float(args.settle_s)))
                result["steps"].append(close_step)

            if not args.dry_run and grasp_mode == "physical_v2" and step["type"] in {"lift", "retreat"}:
                duration_s = (
                    float(execution_policy.get("hold_after_lift_s", 1.0))
                    if step["type"] == "lift"
                    else float(execution_policy.get("hold_after_retreat_s", 0.3))
                )
                samples = _sample_physical_status(args, duration_s=duration_s)
                verification_step = {
                    "type": f"{step['type']}_physical_hold_verification",
                    "duration_s": duration_s,
                    "samples": samples,
                    "target_debug": (
                        _prim_debug(args, prim_path=target_body_path)
                        if target_body_path.startswith("/")
                        else {}
                    ),
                }
                result["steps"].append(verification_step)
                if step["type"] == "lift":
                    lift_samples = samples
                else:
                    retreat_samples = samples

        if not args.dry_run and bool(execution_policy.get("release_after_retreat", False)):
            release_step = {"type": "grasp_release_v2" if grasp_mode == "physical_v2" else "grasp_release"}
            if grasp_mode == "physical_v2":
                release_step["response"] = _grasp_release_physical(
                    args,
                    timeout_s=float(execution_policy.get("release_timeout_s", 3.0)),
                )
                physical_release = dict(release_step["response"])
                release_samples = _sample_physical_status(
                    args,
                    duration_s=float(execution_policy.get("release_observation_s", 0.5)),
                )
                release_step["status_samples"] = release_samples
                release_step["target_debug"] = (
                    _prim_debug(args, prim_path=target_body_path)
                    if target_body_path.startswith("/")
                    else {}
                )
            else:
                release_step["response"] = _grasp_release(
                    args,
                    open_gripper=True,
                    timeout_s=float(execution_policy.get("release_timeout_s", 2.0)),
                )
            result["steps"].append(release_step)
        if not args.dry_run and grasp_mode == "physical_v2":
            evaluation = _evaluate_physical_execution(
                target_before=target_before_approach,
                close=physical_close,
                lift_samples=lift_samples,
                retreat_samples=retreat_samples,
                release=physical_release,
                release_samples=release_samples,
                minimum_lift_m=float(execution_policy.get("minimum_lift_m", 0.03)),
                minimum_hold_ratio=float(execution_policy.get("minimum_hold_ratio", 0.8)),
            )
            result["physical_v2_acceptance"] = evaluation
            if not bool(evaluation["passed"]):
                failed_checks = [name for name, passed in evaluation["checks"].items() if not passed]
                raise RuntimeError(f"physical_v2_acceptance_failed: {','.join(failed_checks)}")
        result["final_status"] = _best_effort_status(args) if not args.dry_run else {}
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
                result["final_status"] = _status(args)
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
