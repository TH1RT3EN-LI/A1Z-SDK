"""A1Z robot arm control server.

Binds the configured TCP listener and, when enabled, an optional Unix socket,
then dispatches JSON commands to a live ArmRobot instance. Start via
``tools/a1zctl`` and communicate through the same script.

Protocol
--------
Each connection sends one newline-terminated JSON request and receives one
newline-terminated JSON response:

  Request:  {"cmd": "<name>", "args": {...}}
  Response: {"ok": true,  "data": {...}}
         or {"ok": false, "execution_state": "rejected", "error": "<message>"}
         or {"ok": false, "execution_state": "submitted_unverified", ...}

Commands include status, movement, camera capture, and a backend-neutral
grasp close/status/release contract.
"""

import json
import math
import os
import select
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from a1z_ext.config import (
    get_arm_motion_speed_limits,
    get_default_backend,
    get_default_can_channel,
    get_socket_path,
    get_tcp_host,
    validate_arm_motion_speed,
)
from a1z_ext.robots.get_robot import create_a1z_robot
from a1z_ext.robots.motion_controller import LatestTargetMotionController, MotionGoal
from a1z_ext.robots.trajectory import load_trajectory, save_trajectory


def _deg(*angles: float) -> np.ndarray:
    return np.deg2rad(np.array(angles, dtype=np.float64))


PRESETS: dict[str, np.ndarray] = {
    "home":    _deg(  0,  60,  -60,   0,   0,   0),
    "ready":   _deg(  0,  30,  -30,   0,  45,   0),
    "salute":  _deg( 30,  35,  -80,   0,  80,  90),
    "wave_l":  _deg(-80,  60,  -60,   0,  60,  90),
    "wave_r":  _deg( 80,  60,  -60,   0, -60, -90),
    "nod_a":   _deg(  0,  70,  -60,  50,   0,   0),
    "nod_b":   _deg(  0,  70,  -60,   0,   0,   0),
    "shake_a": _deg(  0,  70,  -60,   0,  40,   0),
    "shake_b": _deg(  0,  70,  -60,   0, -40,   0),
    "reach":   _deg(  0,  20,  -30,   0,  60,   0),
    "bow":     _deg(  0, 110, -130,   0,   0,   0),
}

# Each move: list of (pose_key, speed_multiplier, pause_s)
DANCE_MOVES: dict[str, list] = {
    "salute": [
        ("salute", 1.0, 0.8), ("home", 0.8, 0.0),
    ],
    "wave": [
        ("ready",  1.0, 0.0), ("wave_l", 1.5, 0.1),
        ("wave_r", 1.5, 0.1), ("wave_l", 1.5, 0.1),
        ("wave_r", 1.5, 0.1), ("home",   1.0, 0.0),
    ],
    "nod": [
        ("nod_a", 1.2, 0.0), ("nod_b", 1.2, 0.0), ("home", 1.0, 0.0),
    ],
    "shake": [
        ("shake_a", 1.2, 0.0), ("shake_b", 1.2, 0.0),
        ("shake_a", 1.2, 0.0), ("shake_b", 1.2, 0.0),
        ("home",    1.0, 0.0),
    ],
    "reach": [("reach", 0.9, 0.5), ("home", 0.9, 0.0)],
    "bow":   [("home", 0.7, 0.0), ("bow", 0.5, 0.8), ("home", 0.5, 0.0)],
}

DEFAULT_DANCE_ORDER = ["salute", "wave", "nod", "reach", "bow"]


class RobotServer:
    def __init__(
        self,
        robot,
        with_gripper: bool,
        camera_session=None,
        *,
        forward_kinematics: Optional[Callable[[np.ndarray], np.ndarray]] = None,
        endpoint_position_tolerance_mm: float = 0.5,
        endpoint_orientation_tolerance_deg: float = 0.5,
        endpoint_feedback_timeout_s: float = 2.0,
        endpoint_stable_samples: int = 5,
        settle_velocity_rad_s: float = 0.02,
        gripper_feedback_tolerance: float = 0.025,
        gripper_feedback_timeout_s: float = 3.0,
    ) -> None:
        self._robot = robot
        self._with_gripper = with_gripper
        self._camera_session = camera_session
        self._lock = threading.Lock()
        self._camera_lock = threading.Lock()
        self._shutdown = threading.Event()
        self._listener_ready = threading.Event()
        self._listener_startup_error: Optional[BaseException] = None
        self._recording_active = False
        self._recording_sample_hz = 0
        self._recording_trajectory = []
        self._recording_name = ""
        self._motion = LatestTargetMotionController(
            robot,
            forward_kinematics=forward_kinematics,
            endpoint_position_tolerance_mm=endpoint_position_tolerance_mm,
            endpoint_orientation_tolerance_deg=endpoint_orientation_tolerance_deg,
            endpoint_stable_samples=endpoint_stable_samples,
            settle_velocity_rad_s=settle_velocity_rad_s,
            feedback_timeout_s=endpoint_feedback_timeout_s,
        )
        self._gripper_feedback_tolerance = float(gripper_feedback_tolerance)
        self._gripper_feedback_timeout_s = float(gripper_feedback_timeout_s)

    def _is_estopped(self) -> bool:
        return bool(getattr(self._robot, "is_estopped", False))

    def _is_running(self) -> bool:
        return bool(getattr(self._robot, "is_running", False))

    def _fault_message(self) -> str:
        return str(getattr(self._robot, "runtime_fault", "") or "").strip()

    def _is_faulted(self) -> bool:
        return bool(getattr(self._robot, "is_faulted", False) or self._fault_message())

    def _control_mode(self) -> str:
        info = self._robot.get_robot_info()
        mode = info.get("control_mode")
        if mode:
            return str(mode)
        return (
            "gravity_comp_effort"
            if bool(info.get("zero_gravity_mode", False))
            else "position_hold"
        )

    def _runtime_health(self) -> dict:
        return {
            "running": self._is_running(),
            "faulted": self._is_faulted(),
            "fault_message": self._fault_message(),
        }

    def _reject_if_estopped(self) -> Optional[dict]:
        if self._is_estopped():
            return {"ok": False, "error": "Robot is in estop."}
        return None

    def _reject_if_not_operational(self) -> Optional[dict]:
        if self._is_faulted():
            return {
                "ok": False,
                "error": f"Robot control loop faulted: {self._fault_message() or 'unknown fault'}",
            }
        if not self._is_running():
            return {
                "ok": False,
                "error": "Robot control loop is not running. Restart the control service.",
            }
        return self._reject_if_estopped()

    def _reject_if_not_position_hold(self) -> Optional[dict]:
        mode = self._control_mode()
        if mode != "position_hold":
            return {
                "ok": False,
                "error": (
                    "Position motion requires position-hold mode; "
                    f"current mode is {mode or 'unknown'}."
                ),
            }
        return None

    def _get_gripper_positions(self) -> tuple[Optional[float], Optional[float]]:
        legacy_reader = getattr(self._robot, "get_gripper_pos", None)
        legacy = legacy_reader() if callable(legacy_reader) else None
        target_reader = getattr(self._robot, "get_gripper_target_pos", None)
        measured_reader = getattr(self._robot, "get_gripper_measured_pos", None)
        target = target_reader() if callable(target_reader) else legacy
        measured = measured_reader() if callable(measured_reader) else legacy
        return (
            None if target is None else float(target),
            None if measured is None else float(measured),
        )

    def _verify_gripper_feedback(
        self,
        target: float,
        *,
        measured_before: Optional[float],
    ) -> dict:
        tolerance = self._gripper_feedback_tolerance
        deadline = time.monotonic() + max(0.0, self._gripper_feedback_timeout_s)
        stable_samples = 0
        measured: Optional[float] = None
        while True:
            if self._is_faulted() or not self._is_running() or self._is_estopped():
                break
            _commanded, measured = self._get_gripper_positions()
            if measured is not None and abs(float(target) - measured) <= tolerance:
                stable_samples += 1
                if stable_samples >= 2:
                    break
            else:
                stable_samples = 0
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)

        error = (
            abs(float(target) - float(measured))
            if measured is not None
            else float("inf")
        )
        reached = (
            measured is not None
            and self._is_running()
            and not self._is_faulted()
            and not self._is_estopped()
            and stable_samples >= 2
            and error <= tolerance
        )
        motion_performed = (
            measured_before is None
            or abs(float(target) - float(measured_before)) > tolerance
        )
        return {
            "reached": reached,
            "target": round(float(target), 4),
            "measured": (
                round(float(measured), 4) if measured is not None else None
            ),
            "error": round(float(error), 4) if np.isfinite(error) else None,
            "tolerance": tolerance,
            "feedback_available": measured is not None,
            "motion_performed": motion_performed,
            **self._runtime_health(),
            "estopped": self._is_estopped(),
        }

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_status(self, _args: dict) -> dict:
        state = self._robot.get_joint_state()
        info = self._robot.get_robot_info()
        pos_deg = np.rad2deg(state["pos"]).tolist()
        control_mode = info.get("control_mode")
        if not control_mode:
            control_mode = (
                "gravity_comp_effort"
                if bool(info.get("zero_gravity_mode", False))
                else "position_hold"
            )
        try:
            gravity_comp_factor = float(info.get("gravity_comp_factor", 1.0))
        except (TypeError, ValueError):
            gravity_comp_factor = None
        data: dict = {
            "pos_deg":    [round(v, 2) for v in pos_deg],
            "vel_rad_s":  [round(v, 3) for v in state["vel"].tolist()],
            "torque_nm":  [round(v, 3) for v in state["eff"].tolist()],
            "control_mode": str(control_mode),
            "gravity_comp_factor": gravity_comp_factor,
            **self._runtime_health(),
            "motion": self._motion.status_snapshot(),
        }
        raw_joint_limits = info.get("joint_limits")
        if raw_joint_limits is not None:
            try:
                joint_limits = np.asarray(
                    raw_joint_limits, dtype=np.float64
                ).reshape(-1, 2)[:6]
            except (TypeError, ValueError):
                joint_limits = np.empty((0, 2), dtype=np.float64)
            if joint_limits.shape == (6, 2) and np.all(
                np.isfinite(joint_limits)
            ):
                data["joint_limits_deg"] = [
                    [round(float(value), 3) for value in np.rad2deg(pair)]
                    for pair in joint_limits
                ]
        speed_limits = get_arm_motion_speed_limits()
        data["arm_motion_speed_rad_s"] = {
            "minimum": speed_limits.minimum,
            "default": speed_limits.default,
            "maximum": speed_limits.maximum,
        }
        if self._with_gripper:
            target, measured = self._get_gripper_positions()
            data["gripper_target"] = (
                round(target, 3) if target is not None else None
            )
            data["gripper_measured"] = (
                round(measured, 3) if measured is not None else None
            )
            # Compatibility for older clients: "gripper" now prefers physical
            # feedback and falls back to the commanded target only when no
            # measured value exists.
            compatibility_value = measured if measured is not None else target
            data["gripper"] = (
                round(compatibility_value, 3)
                if compatibility_value is not None
                else None
            )
        if hasattr(self._robot, "is_estopped"):
            data["estopped"] = bool(self._robot.is_estopped)
        diagnostic_fields = {
            "error_codes": "error_codes",
            "temp_mos_c": "temp_mos",
            "temp_rotor_c": "temp_rotor",
        }
        for response_key, state_key in diagnostic_fields.items():
            raw = state.get(state_key)
            if raw is None:
                continue
            values = np.asarray(raw).reshape(-1)[:6]
            if response_key == "error_codes":
                data[response_key] = [int(value) for value in values]
            else:
                data[response_key] = [round(float(value), 1) for value in values]
        return {"ok": True, "data": data}

    def _cmd_move(self, args: dict) -> dict:
        rejected = self._reject_if_not_position_hold()
        if rejected is not None:
            return rejected
        speed_limits = get_arm_motion_speed_limits()
        speed = validate_arm_motion_speed(args.get("speed", speed_limits.default))
        if "preset" in args:
            name = args["preset"]
            if name not in PRESETS:
                avail = ", ".join(sorted(PRESETS))
                return {"ok": False, "error": f"Unknown preset '{name}'. Available: {avail}"}
            target = PRESETS[name]
        elif "joints" in args:
            joints = args["joints"]
            if not isinstance(joints, (list, tuple)) or len(joints) != 6:
                return {"ok": False, "error": "joints must be a list of 6 values (degrees)"}
            try:
                target = np.deg2rad(np.array(joints, dtype=np.float64))
            except (TypeError, ValueError):
                return {"ok": False, "error": "joints must contain 6 finite values (degrees)"}
            if not np.all(np.isfinite(target)):
                return {"ok": False, "error": "joints must contain 6 finite values (degrees)"}
        else:
            return {"ok": False, "error": "move requires 'preset' or 'joints'"}
        try:
            goal = self._motion.submit(
                target,
                speed_rad_s=speed,
                source="move",
                timeout_s=float(args.get("timeout_s", 120.0)),
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return self._motion.wait(goal)

    def _cmd_cartesian_jog(self, args: dict) -> dict:
        """Apply one IK-derived increment to the service's newest target."""

        rejected = self._reject_if_not_position_hold()
        if rejected is not None:
            return rejected

        raw_delta = args.get("joint_delta_deg")
        try:
            joint_delta_deg = np.asarray(raw_delta, dtype=np.float64).reshape(-1)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "error": "joint_delta_deg must be a list of 6 finite values (degrees)",
            }
        if joint_delta_deg.size != 6 or not np.all(np.isfinite(joint_delta_deg)):
            return {
                "ok": False,
                "error": "joint_delta_deg must be a list of 6 finite values (degrees)",
            }
        if float(np.max(np.abs(joint_delta_deg))) <= 1e-12:
            return {
                "ok": False,
                "error": "joint_delta_deg must contain a non-zero increment",
            }

        speed_limits = get_arm_motion_speed_limits()
        speed = validate_arm_motion_speed(args.get("speed", speed_limits.default))
        try:
            goal = self._motion.submit_delta(
                np.deg2rad(joint_delta_deg),
                speed_rad_s=speed,
                source="cartesian_jog",
                timeout_s=float(args.get("timeout_s", 30.0)),
                metadata={
                    "joint_delta_deg": [
                        round(float(value), 4) for value in joint_delta_deg
                    ]
                },
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return self._motion.wait(goal)

    def _cmd_joint_jog(self, args: dict) -> dict:
        """Increment one command-space joint without rewriting the other five."""

        rejected = self._reject_if_not_position_hold()
        if rejected is not None:
            return rejected

        raw_joint_index = args.get("joint_index")
        try:
            joint_number = float(raw_joint_index)
        except (TypeError, ValueError):
            return {"ok": False, "error": "joint_index must be an integer from 1 to 6"}
        if not np.isfinite(joint_number) or not joint_number.is_integer():
            return {"ok": False, "error": "joint_index must be an integer from 1 to 6"}
        joint_index = int(joint_number) - 1
        if not 0 <= joint_index < 6:
            return {"ok": False, "error": "joint_index must be an integer from 1 to 6"}

        try:
            requested_delta_deg = float(args.get("delta_deg"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "delta_deg must be a finite non-zero number"}
        if not np.isfinite(requested_delta_deg) or abs(requested_delta_deg) <= 1e-12:
            return {"ok": False, "error": "delta_deg must be a finite non-zero number"}

        speed_limits = get_arm_motion_speed_limits()
        speed = validate_arm_motion_speed(args.get("speed", speed_limits.default))
        delta = np.zeros(6, dtype=np.float64)
        delta[joint_index] = math.radians(requested_delta_deg)
        try:
            goal = self._motion.submit_delta(
                delta,
                speed_rad_s=speed,
                source="joint_jog",
                timeout_s=float(args.get("timeout_s", 30.0)),
                metadata={
                    "joint_index": joint_index + 1,
                    "requested_delta_deg": requested_delta_deg,
                },
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return self._motion.wait(goal)

    def _cmd_command(self, args: dict) -> dict:
        rejected = self._reject_if_not_position_hold()
        if rejected is not None:
            return rejected
        joints = args.get("joints")
        if joints is None:
            return {"ok": False, "error": "command requires 'joints' (6 joint values in degrees)"}
        if len(joints) != 6:
            return {"ok": False, "error": "joints must be a list of 6 values (degrees)"}

        try:
            target = np.deg2rad(np.array(joints, dtype=np.float64))
        except (TypeError, ValueError):
            return {"ok": False, "error": "joints must contain 6 finite values (degrees)"}
        if not np.all(np.isfinite(target)):
            return {"ok": False, "error": "joints must contain 6 finite values (degrees)"}

        if self._with_gripper and "gripper" in args:
            value = float(args["gripper"])
            if not 0.0 <= value <= 1.0:
                return {"ok": False, "error": "gripper must be in [0.0, 1.0]"}
        speed_limits = get_arm_motion_speed_limits()
        speed = validate_arm_motion_speed(args.get("speed", speed_limits.default))
        try:
            goal = self._motion.submit(
                target,
                speed_rad_s=speed,
                source="command",
                timeout_s=float(args.get("timeout_s", 120.0)),
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        if self._with_gripper and "gripper" in args:
            self._robot.command_gripper(value)
        response = self._motion.accepted_response(goal)
        if self._with_gripper and "gripper" in args:
            response["data"].update(
                {"gripper": round(value, 3), "gripper_target": round(value, 3)}
            )
        return response

    def _cmd_gripper(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if bool(self._robot.get_robot_info().get("gripper_free_drive", False)):
            return {
                "ok": False,
                "error": "Gripper is in free-drive mode. Restore gripper control first.",
            }
        value = float(args.get("value", 1.0))
        if not 0.0 <= value <= 1.0:
            return {"ok": False, "error": "value must be in [0.0, 1.0]"}
        _target_before, measured_before = self._get_gripper_positions()
        self._robot.command_gripper(value)
        verification = self._verify_gripper_feedback(
            value,
            measured_before=measured_before,
        )
        if not verification["reached"]:
            measured_text = (
                f"{verification['measured']:.3f}"
                if verification["measured"] is not None
                else "unavailable"
            )
            return {
                "ok": False,
                "execution_state": "submitted_unverified",
                "error": (
                    "Gripper target was not reached from SDK feedback: "
                    f"target {value:.3f}, measured {measured_text}, "
                    f"tolerance {verification['tolerance']:.3f}."
                ),
                "data": {"verification": verification},
            }
        return {
            "ok": True,
            "data": {
                "gripper": value,
                "gripper_target": value,
                "gripper_measured": verification["measured"],
                "verification": verification,
                "motion_performed": verification["motion_performed"],
                "completion": (
                    "feedback_verified"
                    if verification["motion_performed"]
                    else "already_at_target"
                ),
            },
        }

    def _cmd_grasp_close(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "grasp_close"):
            return {"ok": False, "error": "Active backend does not support grasp_close"}
        data = self._robot.grasp_close(
            timeout_s=float(args.get("timeout_s", 15.0)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_release(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "grasp_release"):
            return {"ok": False, "error": "Active backend does not support grasp_release"}
        data = self._robot.grasp_release(
            timeout_s=float(args.get("timeout_s", 3.0)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_status(self, _args: dict) -> dict:
        if not hasattr(self._robot, "get_grasp_status"):
            return {"ok": False, "error": "Active backend does not support grasp_status"}
        return {"ok": True, "data": dict(self._robot.get_grasp_status())}

    def _cmd_estop(self, _args: dict) -> dict:
        if not hasattr(self._robot, "estop"):
            return {"ok": False, "error": "Active backend does not support estop"}
        self._motion.cancel(
            "Motion goal cancelled by estop (emergency stop).",
            execution_state="estopped",
        )
        self._robot.estop()
        return {"ok": True, "data": {"estopped": True}}

    def _cmd_estop_release(self, _args: dict) -> dict:
        if not hasattr(self._robot, "release"):
            return {"ok": False, "error": "Active backend does not support estop release"}
        self._motion.run_exclusive(
            self._robot.release,
            reason="Estop release resets the arm motion reference.",
        )
        return {"ok": True, "data": {"estopped": False}}

    def _cmd_gravity_mode(self, args: dict) -> dict:
        if not hasattr(self._robot, "set_gravity_mode"):
            return {"ok": False, "error": "Active backend does not support gravity mode"}
        if "factor" in args:
            return {
                "ok": False,
                "error": (
                    "Gravity factor is a startup parameter. Restart the control "
                    "service with --gravity-factor instead of changing it live."
                ),
        }
        enabled = bool(args.get("enabled", True))
        info = self._robot.get_robot_info()
        try:
            current_factor = float(info.get("gravity_comp_factor", 1.0))
        except (TypeError, ValueError):
            current_factor = float("nan")
        if enabled and (
            not np.isfinite(current_factor)
            or not 0.0 < current_factor <= 1.0
        ):
            return {
                "ok": False,
                "error": (
                    "Zero-force mode requires a finite startup gravity "
                    "compensation factor in (0.0, 1.0]."
                ),
            }
        self._motion.run_exclusive(
            lambda: self._robot.set_gravity_mode(enabled),
            reason="Motion goal cancelled by arm control-mode transition.",
        )
        return {
            "ok": True,
            "data": {
                "gravity_mode": enabled,
                "control_mode": "gravity_comp_effort" if enabled else "position_hold",
                "gravity_comp_factor": current_factor,
            },
        }

    def _cmd_gripper_free_drive(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "set_gripper_free_drive"):
            return {
                "ok": False,
                "error": "Active backend does not support gripper free-drive",
            }
        enabled = bool(args.get("enabled", True))
        self._robot.set_gripper_free_drive(enabled)
        return {"ok": True, "data": {"gripper_free_drive": enabled}}

    def _recording_path(self, name: object) -> Path:
        safe_name = Path(str(name or "teach.json")).name
        if not safe_name.endswith(".json"):
            safe_name += ".json"
        backend = str(
            self._robot.get_robot_info().get("backend", "unknown")
        ).strip()
        safe_backend = "".join(
            character
            for character in backend
            if character.isalnum() or character in {"-", "_"}
        ) or "unknown"
        root = (
            Path(__file__).resolve().parents[2]
            / "runtime"
            / "recordings"
            / safe_backend
        )
        root.mkdir(parents=True, exist_ok=True)
        return root / safe_name

    @staticmethod
    def _trajectory_summary(trajectory, *, path: Optional[Path] = None) -> dict:
        frames = len(trajectory)
        duration_s = float(trajectory[-1][0]) if frames else 0.0
        data = {
            "frames": frames,
            "duration_s": round(duration_s, 3),
        }
        if path is not None:
            data["path"] = str(path)
        return data

    def _cmd_record_start(self, args: dict) -> dict:
        if not hasattr(self._robot, "start_recording"):
            return {"ok": False, "error": "Active backend does not support recording"}
        if self._recording_active:
            return {"ok": False, "error": "A recording is already active"}
        sample_hz = int(args.get("sample_hz", 50))
        if not 1 <= sample_hz <= 250:
            return {"ok": False, "error": "sample_hz must be in [1, 250]"}
        before = dict(self._robot.get_robot_info())
        previous_gravity_mode = (
            str(before.get("control_mode", "")) == "gravity_comp_effort"
        )
        previous_gripper_free_drive = bool(
            before.get("gripper_free_drive", False)
        )

        def start_recording_transition() -> None:
            if hasattr(self._robot, "set_gravity_mode"):
                self._robot.set_gravity_mode(True)
            if self._with_gripper and hasattr(
                self._robot,
                "set_gripper_free_drive",
            ):
                self._robot.set_gripper_free_drive(True)
            self._robot.start_recording(sample_hz)

        try:
            self._motion.run_exclusive(
                start_recording_transition,
                reason="Motion goal cancelled because teaching recording started.",
            )
        except Exception as exc:
            rollback_errors: list[str] = []
            if self._with_gripper and hasattr(
                self._robot,
                "set_gripper_free_drive",
            ):
                try:
                    self._robot.set_gripper_free_drive(
                        previous_gripper_free_drive
                    )
                except Exception as rollback_exc:
                    rollback_errors.append(f"gripper: {rollback_exc}")
            if hasattr(self._robot, "set_gravity_mode"):
                try:
                    self._robot.set_gravity_mode(previous_gravity_mode)
                except Exception as rollback_exc:
                    rollback_errors.append(f"arm: {rollback_exc}")
            detail = (
                f"; rollback failed ({'; '.join(rollback_errors)})"
                if rollback_errors
                else ""
            )
            return {
                "ok": False,
                "execution_state": "submitted_unverified",
                "error": f"Failed to start recording: {exc}{detail}",
            }
        self._recording_active = True
        self._recording_sample_hz = sample_hz
        self._recording_trajectory = []
        return {
            "ok": True,
            "data": {
                "recording": True,
                "sample_hz": sample_hz,
                "control_mode": "gravity_comp_effort",
                "gripper_free_drive": self._with_gripper,
            },
        }

    def _cmd_record_stop(self, args: dict) -> dict:
        if not self._recording_active:
            return {"ok": False, "error": "No recording is active"}
        trajectory = self._robot.stop_recording()
        self._recording_active = False
        restore_errors: list[str] = []
        if self._with_gripper and hasattr(self._robot, "set_gripper_free_drive"):
            try:
                self._robot.set_gripper_free_drive(False)
            except Exception as exc:
                restore_errors.append(f"gripper: {exc}")
        if hasattr(self._robot, "set_gravity_mode"):
            try:
                self._robot.set_gravity_mode(False)
            except Exception as exc:
                restore_errors.append(f"arm: {exc}")
        self._recording_trajectory = list(trajectory)
        path = self._recording_path(args.get("name", "teach.json"))
        robot_info = dict(self._robot.get_robot_info())
        backend = str(robot_info.get("backend", "unknown"))
        save_trajectory(
            self._recording_trajectory,
            str(path),
            metadata={
                "backend": backend,
                "sample_hz": self._recording_sample_hz,
            },
        )
        self._recording_name = path.name
        data = self._trajectory_summary(self._recording_trajectory, path=path)
        data["recording"] = False
        after = dict(self._robot.get_robot_info())
        data["control_mode"] = str(after.get("control_mode", ""))
        data["gripper_free_drive"] = bool(
            after.get("gripper_free_drive", False)
        )
        data["backend"] = backend
        data["safe_state_restored"] = not restore_errors
        if restore_errors:
            data["restore_warning"] = "; ".join(restore_errors)
        return {"ok": True, "data": data}

    def _cmd_record_play(self, args: dict) -> dict:
        if self._recording_active:
            return {"ok": False, "error": "Stop the active recording before playback"}
        name = args.get("name", self._recording_name or "teach.json")
        path = self._recording_path(name)
        robot_info = dict(self._robot.get_robot_info())
        backend = str(robot_info.get("backend", "unknown"))
        try:
            trajectory = load_trajectory(
                str(path),
                expected_backend=backend,
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}
        if not trajectory:
            return {"ok": False, "error": "Recording is empty; playback is unavailable"}
        has_gripper_commands = any(
            np.asarray(frame[1], dtype=np.float64).size >= 7
            for frame in trajectory
        )
        if has_gripper_commands and bool(
            robot_info.get("gripper_free_drive", False)
        ):
            return {
                "ok": False,
                "error": (
                    "Trajectory contains gripper commands, but the gripper is "
                    "in free-drive mode. Restore gripper control first."
                ),
            }
        speed_factor = float(args.get("speed_factor", 1.0))
        if not 0.1 <= speed_factor <= 3.0:
            return {"ok": False, "error": "speed_factor must be in [0.1, 3.0]"}
        if hasattr(self._robot, "set_gravity_mode"):
            self._motion.run_exclusive(
                lambda: self._robot.set_gravity_mode(False),
                reason="Motion goal cancelled because trajectory playback started.",
            )

        speed_limits = get_arm_motion_speed_limits()
        playback_speed = speed_limits.minimum
        for (previous_t, previous_q), (next_t, next_q) in zip(
            trajectory,
            trajectory[1:],
        ):
            dt = (float(next_t) - float(previous_t)) / speed_factor
            if dt <= 0.0:
                continue
            delta = np.asarray(next_q, dtype=np.float64)[:6] - np.asarray(
                previous_q,
                dtype=np.float64,
            )[:6]
            playback_speed = max(
                playback_speed,
                float(np.max(np.abs(delta))) / dt,
            )
        playback_speed = min(speed_limits.maximum, playback_speed * 1.15)

        playback_started = time.monotonic()
        previous_goal: Optional[MotionGoal] = None
        try:
            for frame_index, (recorded_time, raw_target) in enumerate(trajectory):
                due = playback_started + float(recorded_time) / speed_factor
                while True:
                    remaining = due - time.monotonic()
                    if remaining <= 0.0:
                        break
                    if previous_goal is not None and not self._motion.owns_goal(
                        previous_goal
                    ):
                        return {
                            "ok": False,
                            "execution_state": "superseded",
                            "error": "Trajectory playback was replaced by a newer target.",
                            "data": {"completion": "superseded"},
                        }
                    time.sleep(min(0.02, remaining))

                frame = np.asarray(raw_target, dtype=np.float64).reshape(-1)
                metadata = {
                    "trajectory_name": path.name,
                    "trajectory_frame": frame_index,
                    "trajectory_frames": len(trajectory),
                }
                if previous_goal is None:
                    goal = self._motion.submit(
                        frame[:6],
                        speed_rad_s=playback_speed,
                        source="record_play",
                        timeout_s=120.0,
                        metadata=metadata,
                    )
                else:
                    goal = self._motion.submit_replacement(
                        previous_goal,
                        frame[:6],
                        speed_rad_s=playback_speed,
                        source="record_play",
                        timeout_s=120.0,
                        metadata=metadata,
                    )
                previous_goal = goal
                if frame.size >= 7 and self._with_gripper:
                    self._robot.command_gripper(float(frame[6]))
        except (RuntimeError, ValueError) as exc:
            return {
                "ok": False,
                "execution_state": "superseded",
                "error": str(exc),
                "data": {"completion": "superseded"},
            }

        assert previous_goal is not None
        result = self._motion.wait(previous_goal)
        self._recording_trajectory = list(trajectory)
        self._recording_name = path.name
        data = self._trajectory_summary(trajectory, path=path)
        data["speed_factor"] = speed_factor
        if result.get("ok") is not True:
            result_data = dict(result.get("data", {}))
            result_data.update(data)
            return {**result, "data": result_data}
        result_data = dict(result["data"])
        result_data.update(data)
        return {"ok": True, "data": result_data}

    def _cmd_record_info(self, _args: dict) -> dict:
        data = self._trajectory_summary(self._recording_trajectory)
        data.update(
            {
                "recording": self._recording_active,
                "sample_hz": self._recording_sample_hz,
                "name": self._recording_name,
            }
        )
        return {"ok": True, "data": data}

    def _cmd_dance(self, args: dict) -> dict:
        moves_list = args.get("moves", DEFAULT_DANCE_ORDER)
        speed = float(args.get("speed", 0.6))
        unknown = [m for m in moves_list if m not in DANCE_MOVES]
        if unknown:
            avail = ", ".join(DANCE_MOVES)
            return {"ok": False, "error": f"Unknown moves: {unknown}. Available: {avail}"}

        previous_goal: Optional[MotionGoal] = None

        def advance(target: np.ndarray, target_speed: float, label: str) -> dict:
            nonlocal previous_goal
            checked_speed = validate_arm_motion_speed(target_speed)
            try:
                if previous_goal is None:
                    goal = self._motion.submit(
                        target,
                        speed_rad_s=checked_speed,
                        source="dance",
                        metadata={"dance_pose": label},
                    )
                else:
                    goal = self._motion.submit_replacement(
                        previous_goal,
                        target,
                        speed_rad_s=checked_speed,
                        source="dance",
                        metadata={"dance_pose": label},
                    )
            except (RuntimeError, ValueError) as exc:
                return {
                    "ok": False,
                    "execution_state": "superseded",
                    "error": str(exc),
                }
            previous_goal = goal
            return self._motion.wait(goal)

        def pause_while_owned(seconds: float) -> bool:
            assert previous_goal is not None
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if not self._motion.owns_goal(previous_goal):
                    return False
                time.sleep(min(0.02, deadline - time.monotonic()))
            return True

        result = advance(PRESETS["home"], speed * 0.7, "home")
        if not result["ok"]:
            return result
        if not pause_while_owned(0.4):
            return {
                "ok": False,
                "execution_state": "superseded",
                "error": "Dance was replaced by a newer target.",
            }
        for move_name in moves_list:
            print(f"[a1z] dance: {move_name}")
            for pose_key, spd_mul, pause in DANCE_MOVES[move_name]:
                result = advance(PRESETS[pose_key], speed * spd_mul, pose_key)
                if not result["ok"]:
                    return result
                if pause > 0 and not pause_while_owned(pause):
                    return {
                        "ok": False,
                        "execution_state": "superseded",
                        "error": "Dance was replaced by a newer target.",
                    }
            if not pause_while_owned(0.2):
                return {
                    "ok": False,
                    "execution_state": "superseded",
                    "error": "Dance was replaced by a newer target.",
                }
        result = advance(PRESETS["home"], speed * 0.6, "home")
        if not result["ok"]:
            return result
        return {
            "ok": True,
            "data": {
                "moves": moves_list,
                "verification": result["data"]["verification"],
            },
        }

    def _cmd_stop(self, _args: dict) -> dict:
        self._motion.shutdown()
        self._shutdown.set()
        return {"ok": True, "data": {"message": "Stopping server"}}

    def _cmd_info(self, _args: dict) -> dict:
        info = self._robot.get_robot_info()
        raw_joint_limits = info.get("joint_limits")
        joint_limits = []
        if raw_joint_limits is not None:
            joint_limits = np.asarray(raw_joint_limits, dtype=np.float64).reshape(-1, 2)
        arm_joint_limits = joint_limits[:6]
        joint_limits_deg = {
            f"J{i + 1}": [round(np.rad2deg(lo), 1), round(np.rad2deg(hi), 1)]
            for i, (lo, hi) in enumerate(arm_joint_limits)
        }
        data = {
            "backend": info.get("backend", "socketcan"),
            "presets": sorted(PRESETS),
            "dance_moves": list(DANCE_MOVES),
            "joint_limits_deg": joint_limits_deg,
            "control_mode": info.get("control_mode"),
            "commands": sorted(self._HANDLERS),
            "recording": self._recording_active,
            "recording_name": self._recording_name,
            "estopped": self._is_estopped(),
            "gravity_comp_factor": float(info.get("gravity_comp_factor", 1.0)),
            "gravity_comp_factor_range": [0.0, 1.0],
            "motion_controller": self._motion.config_snapshot(),
            "motion": self._motion.status_snapshot(),
            **self._runtime_health(),
        }
        if info.get("motor_a_status_codes") is not None:
            data["motor_a_status_codes"] = [
                int(value) for value in info["motor_a_status_codes"]
            ]
        if info.get("control_freq_hz") is not None:
            data["control_freq_hz"] = int(info["control_freq_hz"])
        for source_key in ("default_kp", "default_kd"):
            if info.get(source_key) is not None:
                values = np.asarray(info[source_key], dtype=np.float64).reshape(-1)[:6]
                data[source_key] = [round(float(value), 3) for value in values]
        if info.get("gripper_torque_limit_nm") is not None:
            data["gripper_torque_limit_nm"] = round(
                float(info["gripper_torque_limit_nm"]), 3
            )
        if info.get("hard_joint_limits") is not None:
            hard_joint_limits = np.asarray(info["hard_joint_limits"], dtype=np.float64).reshape(-1, 2)[:6]
            data["hard_joint_limits_deg"] = {
                f"J{i + 1}": [round(np.rad2deg(lo), 1), round(np.rad2deg(hi), 1)]
                for i, (lo, hi) in enumerate(hard_joint_limits)
            }
        if info.get("arm_max_velocity") is not None:
            arm_max_velocity = np.asarray(info["arm_max_velocity"], dtype=np.float64).reshape(-1)[:6]
            data["arm_max_velocity_rad_s"] = [round(float(v), 3) for v in arm_max_velocity]
        speed_limits = get_arm_motion_speed_limits()
        data["arm_motion_speed_rad_s"] = {
            "minimum": speed_limits.minimum,
            "default": speed_limits.default,
            "maximum": speed_limits.maximum,
        }
        if info.get("with_gripper"):
            data["gripper_range"] = [0.0, 1.0]
        if info.get("gripper_free_drive") is not None:
            data["gripper_free_drive"] = bool(info["gripper_free_drive"])
        if info.get("articulation_root_prim"):
            data["articulation_root_prim"] = info["articulation_root_prim"]
        if info.get("dof_names"):
            data["dof_names"] = list(info["dof_names"])
        arm_joint_indices = None
        if info.get("arm_joint_indices") is not None:
            arm_joint_indices = np.asarray(info["arm_joint_indices"], dtype=np.int64).reshape(-1)
            data["arm_joint_indices"] = arm_joint_indices.tolist()
        gripper_joint_indices = None
        if info.get("gripper_joint_indices") is not None:
            gripper_joint_indices = np.asarray(
                info["gripper_joint_indices"], dtype=np.int64
            ).reshape(-1)
            data["gripper_joint_indices"] = gripper_joint_indices.tolist()
        if info.get("gripper_target_value") is not None:
            data["gripper_target_value"] = round(float(info["gripper_target_value"]), 4)
        if info.get("gripper_target_dofs") is not None:
            gripper_target_dofs = np.asarray(info["gripper_target_dofs"], dtype=np.float64).reshape(-1)
            data["gripper_target_dofs"] = [round(float(v), 6) for v in gripper_target_dofs]
        if info.get("gripper_command_dofs") is not None:
            gripper_command_dofs = np.asarray(
                info["gripper_command_dofs"], dtype=np.float64
            ).reshape(-1)
            data["gripper_command_dofs"] = [
                round(float(v), 6) for v in gripper_command_dofs
            ]
        if info.get("gripper_current_dofs") is not None:
            gripper_current_dofs = np.asarray(info["gripper_current_dofs"], dtype=np.float64).reshape(-1)
            data["gripper_current_dofs"] = [round(float(v), 6) for v in gripper_current_dofs]
        if info.get("actual_kp") is not None:
            actual_kp_all = np.asarray(info["actual_kp"], dtype=np.float64).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_kp"] = [
                    round(float(v), 3) for v in actual_kp_all[gripper_joint_indices]
                ]
            actual_kp = actual_kp_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_kp = actual_kp[arm_joint_indices]
            data["actual_kp"] = [round(float(v), 3) for v in actual_kp[:6]]
        if info.get("actual_kd") is not None:
            actual_kd_all = np.asarray(info["actual_kd"], dtype=np.float64).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_kd"] = [
                    round(float(v), 3) for v in actual_kd_all[gripper_joint_indices]
                ]
            actual_kd = actual_kd_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_kd = actual_kd[arm_joint_indices]
            data["actual_kd"] = [round(float(v), 3) for v in actual_kd[:6]]
        if info.get("actual_max_effort") is not None:
            actual_max_effort_all = np.asarray(
                info["actual_max_effort"], dtype=np.float64
            ).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_max_effort"] = [
                    round(float(v), 3)
                    for v in actual_max_effort_all[gripper_joint_indices]
                ]
            actual_max_effort = actual_max_effort_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_max_effort = actual_max_effort[arm_joint_indices]
            data["actual_max_effort_nm"] = [
                round(float(v), 3) for v in actual_max_effort[:6]
            ]
        if info.get("actual_position_targets") is not None:
            actual_position_targets_all = np.asarray(
                info["actual_position_targets"], dtype=np.float64
            ).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_position_targets_m"] = [
                    round(float(v), 6)
                    for v in actual_position_targets_all[gripper_joint_indices]
                ]
            actual_position_targets = actual_position_targets_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_position_targets = actual_position_targets[arm_joint_indices]
            data["actual_position_targets_deg"] = [
                round(float(v), 2)
                for v in np.rad2deg(actual_position_targets[:6])
            ]
        if info.get("active_physics_engine"):
            data["active_physics_engine"] = str(info["active_physics_engine"])
        if info.get("configured_arm_drive_type"):
            data["configured_arm_drive_type"] = str(info["configured_arm_drive_type"])
        if info.get("gravity_model_available") is not None:
            data["gravity_model_available"] = bool(info["gravity_model_available"])
        if info.get("position_hold_gravity_compensation_enabled") is not None:
            data["position_hold_gravity_compensation_enabled"] = bool(
                info["position_hold_gravity_compensation_enabled"]
            )
        if info.get("position_hold_gravity_compensation_active") is not None:
            data["position_hold_gravity_compensation_active"] = bool(
                info["position_hold_gravity_compensation_active"]
            )
        if info.get("position_hold_feedforward_limit_nm") is not None:
            position_hold_feedforward_limit = np.asarray(
                info["position_hold_feedforward_limit_nm"], dtype=np.float64
            ).reshape(-1)
            data["position_hold_feedforward_limit_nm"] = [
                round(float(v), 3) for v in position_hold_feedforward_limit[:6]
            ]
        if info.get("controller_kp") is not None:
            controller_kp = np.asarray(info["controller_kp"], dtype=np.float64).reshape(-1)
            data["controller_kp"] = [round(float(v), 3) for v in controller_kp[:6]]
        if info.get("controller_kd") is not None:
            controller_kd = np.asarray(info["controller_kd"], dtype=np.float64).reshape(-1)
            data["controller_kd"] = [round(float(v), 3) for v in controller_kd[:6]]
        if info.get("gravity_debug_q") is not None:
            gravity_q = np.asarray(info["gravity_debug_q"], dtype=np.float64).reshape(-1)
            data["gravity_debug_q_deg"] = [round(float(v), 3) for v in np.rad2deg(gravity_q[:6])]
        if info.get("gravity_debug_qd") is not None:
            gravity_qd = np.asarray(info["gravity_debug_qd"], dtype=np.float64).reshape(-1)
            data["gravity_debug_qd"] = [round(float(v), 3) for v in gravity_qd[:6]]
        if info.get("gravity_debug_pos_err") is not None:
            gravity_pos_err = np.asarray(info["gravity_debug_pos_err"], dtype=np.float64).reshape(-1)
            data["gravity_debug_pos_err_deg"] = [round(float(v), 3) for v in np.rad2deg(gravity_pos_err[:6])]
        if info.get("gravity_debug_vel_err") is not None:
            gravity_vel_err = np.asarray(info["gravity_debug_vel_err"], dtype=np.float64).reshape(-1)
            data["gravity_debug_vel_err"] = [round(float(v), 3) for v in gravity_vel_err[:6]]
        if info.get("gravity_debug_tau_id") is not None:
            gravity_tau_id = np.asarray(info["gravity_debug_tau_id"], dtype=np.float64).reshape(-1)
            data["gravity_debug_tau_id"] = [round(float(v), 3) for v in gravity_tau_id[:6]]
        if info.get("gravity_debug_effort") is not None:
            gravity_effort = np.asarray(info["gravity_debug_effort"], dtype=np.float64).reshape(-1)
            data["gravity_debug_effort"] = [round(float(v), 3) for v in gravity_effort[:6]]
        if info.get("effort_modes") is not None:
            data["effort_modes"] = list(info["effort_modes"])
        if info.get("command_pos") is not None:
            cmd = np.asarray(info["command_pos"], dtype=np.float64).reshape(-1)
            data["command_pos_deg"] = [round(float(v), 2) for v in np.rad2deg(cmd[:6])]
        return {
            "ok": True,
            "data": data,
        }

    def _cmd_camera_status(self, _args: dict) -> dict:
        if self._camera_session is None:
            return {"ok": False, "error": "D405 camera session is not available."}
        return {"ok": True, "data": self._camera_session.health()}

    def _cmd_camera_capture(self, args: dict) -> dict:
        if self._camera_session is None:
            return {"ok": False, "error": "D405 camera session is not available."}
        fresh = bool(args.get("fresh", True))
        return {"ok": True, "data": self._camera_session.latest_payload(fresh=fresh)}

    def _cmd_camera_extrinsic(self, _args: dict) -> dict:
        if self._camera_session is None:
            return {"ok": False, "error": "D405 camera session is not available."}
        return {"ok": True, "data": self._camera_session.latest_extrinsic_payload()}

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    _HANDLERS = {
        "status":  _cmd_status,
        "move":    _cmd_move,
        "cartesian_jog": _cmd_cartesian_jog,
        "joint_jog": _cmd_joint_jog,
        "command": _cmd_command,
        "gripper": _cmd_gripper,
        "grasp_close": _cmd_grasp_close,
        "grasp_release": _cmd_grasp_release,
        "grasp_status": _cmd_grasp_status,
        "estop": _cmd_estop,
        "estop_release": _cmd_estop_release,
        "gravity_mode": _cmd_gravity_mode,
        "gripper_free_drive": _cmd_gripper_free_drive,
        "record_start": _cmd_record_start,
        "record_stop": _cmd_record_stop,
        "record_play": _cmd_record_play,
        "record_info": _cmd_record_info,
        "dance":   _cmd_dance,
        "stop":    _cmd_stop,
        "info":    _cmd_info,
        "camera_status": _cmd_camera_status,
        "camera_capture": _cmd_camera_capture,
        "camera_extrinsic": _cmd_camera_extrinsic,
    }
    _CAMERA_READ_COMMANDS = frozenset(
        {"camera_status", "camera_capture", "camera_extrinsic"}
    )
    _READ_COMMANDS = frozenset(
        {"status", "info", "grasp_status", "record_info"}
    )
    _EMERGENCY_COMMANDS = frozenset({"estop"})
    _LATEST_TARGET_COMMANDS = frozenset(
        {"move", "cartesian_jog", "joint_jog", "command"}
    )
    _MOTION_COMMANDS = frozenset(
        {
            "move",
            "cartesian_jog",
            "joint_jog",
            "command",
            "gripper",
            "grasp_close",
            "grasp_release",
            "gravity_mode",
            "gripper_free_drive",
            "record_start",
            "record_play",
            "dance",
        }
    )

    def _dispatch_request(self, cmd: str, args: dict) -> dict:
        handler = self._HANDLERS.get(cmd)
        if handler is None:
            return self._normalize_handler_result(
                {"ok": False, "error": f"Unknown command '{cmd}'"}
            )
        if cmd in self._MOTION_COMMANDS:
            rejected = self._reject_if_not_operational()
            if rejected is not None:
                return self._normalize_handler_result(rejected)

        def invoke_handler() -> dict:
            return self._normalize_handler_result(handler(self, args))

        if cmd in self._EMERGENCY_COMMANDS:
            # E-stop must never queue behind a long blocking move/playback.
            return invoke_handler()
        if cmd in self._CAMERA_READ_COMMANDS:
            # A fresh frame can wait for Kit and then spend tens of milliseconds
            # encoding. Keep camera requests serialized without holding the arm
            # command lock for that entire interval.
            with self._camera_lock:
                return invoke_handler()
        if cmd in self._READ_COMMANDS:
            # Backends protect snapshots internally. Keep telemetry responsive
            # while a blocking move owns the serialized command path.
            return invoke_handler()
        if cmd in self._LATEST_TARGET_COMMANDS:
            # These handlers only validate and atomically replace one latest
            # target slot. They must never queue behind an older blocking
            # caller, otherwise preemption would be impossible.
            if self._recording_active:
                return self._normalize_handler_result(
                    {
                        "ok": False,
                        "error": "Recording is active. Stop recording before submitting motion.",
                    }
                )
            return invoke_handler()
        with self._lock:
            if self._recording_active and cmd != "record_stop":
                return self._normalize_handler_result(
                    {
                        "ok": False,
                        "error": (
                            "Recording is active. Only record_stop, telemetry, "
                            "camera reads, and estop are allowed."
                        ),
                    }
                )
            return invoke_handler()

    @staticmethod
    def _normalize_handler_result(result: dict) -> dict:
        if result.get("ok") is not False or "execution_state" in result:
            return result
        return {**result, "execution_state": "rejected"}

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk
            req = json.loads(data.split(b"\n", 1)[0].decode())
            cmd = req.get("cmd", "")
            args = req.get("args", {})
            result = self._dispatch_request(cmd, args)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        try:
            conn.sendall((json.dumps(result) + "\n").encode())
        except Exception:
            pass
        finally:
            conn.close()

    def wait_until_ready(self, timeout_s: float = 5.0) -> None:
        if not self._listener_ready.wait(timeout=max(0.0, float(timeout_s))):
            raise TimeoutError("Timed out waiting for A1Z robot server listeners.")
        if self._listener_startup_error is not None:
            raise RuntimeError("A1Z robot server listeners failed to start") from self._listener_startup_error

    def run(
        self,
        socket_path: Optional[str] = None,
        tcp_host: Optional[str] = None,
        tcp_port: Optional[int] = None,
    ) -> None:
        try:
            self._run_listeners(
                socket_path=socket_path,
                tcp_host=tcp_host,
                tcp_port=tcp_port,
            )
        except BaseException as exc:
            if not self._listener_ready.is_set():
                self._listener_startup_error = exc
                self._listener_ready.set()
            raise

    def _run_listeners(
        self,
        socket_path: Optional[str] = None,
        tcp_host: Optional[str] = None,
        tcp_port: Optional[int] = None,
    ) -> None:
        listeners: list[socket.socket] = []
        unix_socket_path = get_socket_path() if socket_path is None else str(socket_path).strip()
        if unix_socket_path:
            if os.path.exists(unix_socket_path):
                os.unlink(unix_socket_path)

            unix_srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            unix_srv.bind(unix_socket_path)
            unix_srv.listen(8)
            unix_srv.setblocking(False)
            listeners.append(unix_srv)
            print(f"[a1z] Listening on unix://{unix_socket_path}")

        if tcp_port is not None and int(tcp_port) > 0:
            resolved_host = tcp_host or get_tcp_host()
            resolved_port = int(tcp_port)
            tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_srv.bind((resolved_host, resolved_port))
            tcp_srv.listen(8)
            tcp_srv.setblocking(False)
            listeners.append(tcp_srv)
            print(f"[a1z] Listening on tcp://{resolved_host}:{resolved_port}")

        if not listeners:
            raise RuntimeError("No A1Z control listener is configured.")
        self._listener_ready.set()
        try:
            while not self._shutdown.is_set():
                try:
                    ready_listeners, _, _ = select.select(listeners, [], [], 0.25)
                except (OSError, ValueError):
                    if self._shutdown.is_set():
                        break
                    raise
                for srv in ready_listeners:
                    try:
                        conn, _ = srv.accept()
                    except BlockingIOError:
                        continue
                    conn.setblocking(True)
                    conn.settimeout(120.0)
                    t = threading.Thread(
                        target=self._handle_connection, args=(conn,), daemon=True
                    )
                    t.start()
        finally:
            for srv in listeners:
                try:
                    srv.close()
                except OSError:
                    pass
            if unix_socket_path and os.path.exists(unix_socket_path):
                os.unlink(unix_socket_path)


# ------------------------------------------------------------------
# Entry point (called from tools/a1zctl)
# ------------------------------------------------------------------

def serve(
    can_channel: str = get_default_can_channel(),
    with_gripper: bool = False,
    gravity_mode: bool = False,
    gravity_comp_factor: float = 1.0,
    backend: Optional[str] = None,
    socket_path: Optional[str] = None,
    tcp_host: Optional[str] = None,
    tcp_port: Optional[int] = None,
    control_freq_hz: int = 60,
    min_freq_hz: float = 80.0,
    gripper_max_torque: float = 0.5,
    gripper_empty_close_threshold: float = 0.04,
    articulation_root_prim: Optional[str] = None,
) -> None:
    """Start the robot server in the foreground."""
    gravity_comp_factor = float(gravity_comp_factor)
    if not np.isfinite(gravity_comp_factor) or not 0.0 <= gravity_comp_factor <= 1.0:
        raise ValueError("gravity_comp_factor must be finite and in [0.0, 1.0]")
    backend_name = backend or get_default_backend()
    print(
        f"[a1z] Initialising arm  backend={backend_name}  can={can_channel}  "
        f"gripper={'yes' if with_gripper else 'no'}"
    )
    robot = create_a1z_robot(
        backend=backend_name,
        can_channel=can_channel,
        zero_gravity_mode=gravity_mode,
        with_gripper=with_gripper,
        gravity_comp_factor=gravity_comp_factor,
        control_freq_hz=control_freq_hz,
        min_freq_hz=min_freq_hz,
        gripper_max_torque=gripper_max_torque,
        gripper_empty_close_threshold=gripper_empty_close_threshold,
        articulation_root_prim=articulation_root_prim,
    )

    server = RobotServer(robot, with_gripper=with_gripper)

    def _sigint(sig, frame):
        print("\n[a1z] Interrupted — stopping...")
        server._shutdown.set()

    signal.signal(signal.SIGINT, _sigint)

    robot.start()
    connection_reader = getattr(robot, "get_connection_status", None)
    if callable(connection_reader):
        connections = connection_reader()
        can_status = connections.get("can", {})
        arm_status = connections.get("arm", {})
        print(
            "[a1z] Connectivity  "
            f"CAN={can_status.get('status', 'unknown')}  "
            f"arm={arm_status.get('status', 'unknown')}",
            flush=True,
        )
        unavailable = arm_status.get("unavailable_joints", [])
        if arm_status.get("status") in {"partial", "disconnected"} and unavailable:
            print(f"[a1z] Arm feedback unavailable: {unavailable}", flush=True)
    print("[a1z] Arm ready.  Press Ctrl+C to stop.")

    try:
        server.run(
            socket_path=socket_path,
            tcp_host=tcp_host,
            tcp_port=tcp_port,
        )
    finally:
        server._motion.shutdown()
        robot.stop()
        print("[a1z] Arm stopped.")
