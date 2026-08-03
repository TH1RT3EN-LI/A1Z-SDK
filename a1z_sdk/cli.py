"""Command-line access to the same public API used by applications."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from .client import A1ZClient
from .errors import A1ZCommandError, A1ZError
from .models import Endpoint


def _joint_values(text: str) -> list[float]:
    values = [float(value.strip()) for value in text.split(",")]
    if len(values) != 6 or not all(math.isfinite(value) for value in values):
        raise argparse.ArgumentTypeError(
            "expected 6 comma-separated finite joint angles in degrees"
        )
    return values


def _emit(payload: dict[str, Any], *, compact: bool) -> None:
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        )
    )


def _endpoint(args: argparse.Namespace) -> Endpoint:
    return Endpoint(
        socket_path=args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
        timeout_s=args.timeout,
    )


def _client_result(args: argparse.Namespace) -> dict[str, Any]:
    client = A1ZClient(_endpoint(args))
    command = args.command
    if command == "status":
        state = client.status()
        return {"ok": True, "data": dict(state.raw)}
    if command == "info":
        return {"ok": True, "data": client.info()}
    if command == "move":
        return client.move_joints(
            args.joints, speed_rad_s=args.speed, timeout_s=args.motion_timeout
        ).as_dict()
    if command == "target":
        return client.set_joint_target(
            args.joints,
            speed_rad_s=args.speed,
            timeout_s=args.motion_timeout,
        ).as_dict()
    if command == "jog":
        return client.jog_joint(
            args.joint,
            args.delta_deg,
            speed_rad_s=args.speed,
            timeout_s=args.motion_timeout,
        ).as_dict()
    if command == "mode":
        return client.set_control_mode(args.mode).as_dict()
    if command == "gripper":
        return client.set_gripper_opening(
            args.opening, timeout_s=args.motion_timeout
        ).as_dict()
    if command == "grasp":
        if args.grasp_command == "close":
            return client.close_grasp(timeout_s=args.motion_timeout).as_dict()
        if args.grasp_command == "release":
            return client.release_grasp(timeout_s=args.motion_timeout).as_dict()
        return client.grasp_status().as_dict()
    if command == "estop":
        return client.emergency_stop().as_dict()
    if command == "estop-release":
        return client.release_emergency_stop().as_dict()
    if command == "stop":
        return client.stop_service().as_dict()
    raise AssertionError(f"unhandled command: {command}")


def _add_source_vendor_to_path() -> None:
    """Make a source checkout runnable before the upstream is pip-installed."""

    repository_root = Path(__file__).resolve().parents[1]
    upstream = repository_root / "vendor" / "GALAXEA-A1Z"
    if (upstream / "a1z" / "__init__.py").is_file():
        path = str(upstream)
        if path not in sys.path:
            sys.path.insert(0, path)


def _serve(args: argparse.Namespace) -> None:
    _add_source_vendor_to_path()
    try:
        from a1z_ext.robots.server import serve
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "hardware dependencies are missing; initialize the upstream submodule "
            "and install with `python -m pip install -e '.[hardware]'`"
        ) from exc

    serve(
        backend="socketcan",
        can_channel=args.can,
        with_gripper=args.with_gripper,
        gravity_mode=args.start_mode == "zero-force",
        gravity_comp_factor=args.gravity_factor,
        socket_path=args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
        control_freq_hz=args.control_frequency,
        min_freq_hz=args.minimum_control_frequency,
        gripper_max_torque=args.gripper_max_torque,
        gripper_empty_close_threshold=args.gripper_empty_close_threshold,
    )


def build_parser() -> argparse.ArgumentParser:
    defaults = Endpoint.from_env()
    parser = argparse.ArgumentParser(
        prog="a1z",
        description="Control a real A1Z through the feedback-aware SDK service.",
    )
    parser.add_argument("--json", action="store_true", help="Emit compact JSON")
    parser.add_argument("--socket-path", default=defaults.socket_path)
    parser.add_argument("--tcp-host", default=defaults.tcp_host)
    parser.add_argument("--tcp-port", type=int, default=defaults.tcp_port)
    parser.add_argument("--timeout", type=float, default=defaults.timeout_s)
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser(
        "serve", help="Start the only process allowed to own the real hardware"
    )
    serve_parser.add_argument("--can", default="can0")
    serve_parser.add_argument(
        "--with-gripper", action=argparse.BooleanOptionalAction, default=False
    )
    serve_parser.add_argument(
        "--start-mode", choices=("hold", "zero-force"), default="hold"
    )
    serve_parser.add_argument("--gravity-factor", type=float, default=1.0)
    serve_parser.add_argument("--control-frequency", type=int, default=250)
    serve_parser.add_argument("--minimum-control-frequency", type=float, default=80.0)
    serve_parser.add_argument("--gripper-max-torque", type=float, default=0.5)
    serve_parser.add_argument(
        "--gripper-empty-close-threshold", type=float, default=0.04
    )

    subparsers.add_parser("status", help="Read measured robot state")
    subparsers.add_parser("info", help="Read capabilities and current control mode")

    move_parser = subparsers.add_parser(
        "move", help="Move and wait for measured feedback verification"
    )
    move_parser.add_argument("joints", type=_joint_values)
    move_parser.add_argument("--speed", type=float, default=0.5)
    move_parser.add_argument("--motion-timeout", type=float, default=120.0)

    target_parser = subparsers.add_parser(
        "target", help="Asynchronously replace the service's latest joint target"
    )
    target_parser.add_argument("joints", type=_joint_values)
    target_parser.add_argument("--speed", type=float, default=0.5)
    target_parser.add_argument("--motion-timeout", type=float, default=120.0)

    jog_parser = subparsers.add_parser(
        "jog", help="Jog one joint and wait for feedback to settle"
    )
    jog_parser.add_argument("joint", type=int, choices=range(1, 7))
    jog_parser.add_argument("delta_deg", type=float)
    jog_parser.add_argument("--speed", type=float, default=0.5)
    jog_parser.add_argument("--motion-timeout", type=float, default=30.0)

    mode_parser = subparsers.add_parser(
        "mode", help="Select exactly one arm control mode"
    )
    mode_parser.add_argument("mode", choices=("hold", "zero-force"))

    gripper_parser = subparsers.add_parser(
        "gripper", help="Set normalized G1Z opening and verify measured feedback"
    )
    gripper_parser.add_argument("opening", type=float)
    gripper_parser.add_argument("--motion-timeout", type=float, default=10.0)

    grasp_parser = subparsers.add_parser("grasp", help="Closed-loop grasp operations")
    grasp_subparsers = grasp_parser.add_subparsers(
        dest="grasp_command", required=True
    )
    close_parser = grasp_subparsers.add_parser("close")
    close_parser.add_argument("--motion-timeout", type=float, default=15.0)
    grasp_subparsers.add_parser("status")
    release_parser = grasp_subparsers.add_parser("release")
    release_parser.add_argument("--motion-timeout", type=float, default=3.0)

    subparsers.add_parser("estop", help="Latch the SDK emergency stop")
    subparsers.add_parser("estop-release", help="Release the SDK emergency stop")
    subparsers.add_parser("stop", help="Stop the control service")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            _serve(args)
            return 0
        _emit(_client_result(args), compact=args.json)
        return 0
    except A1ZCommandError as exc:
        payload = {
            "ok": False,
            "command": exc.command,
            "execution_state": exc.execution_state,
            "error": str(exc),
            "data": exc.data,
        }
    except (A1ZError, RuntimeError, ValueError) as exc:
        payload = {"ok": False, "error": str(exc)}
    _emit(payload, compact=args.json)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
