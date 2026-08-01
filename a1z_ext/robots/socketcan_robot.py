"""SocketCAN hardware adapter for the upstream A1Z arm implementation."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

from a1z.motor_drivers.motor_b_driver import MOTOR_B_ERROR_CODES
from a1z.robots.arm_robot import ArmRobot


logger = logging.getLogger(__name__)


class SocketCANArmRobot(ArmRobot):
    """Safety adapter around the official SocketCAN hardware SDK.

    The adapter deliberately leaves the official 250 Hz control loop in charge.
    It only fixes state transitions and fault interpretation at the SDK
    boundary, and adds the backend-neutral grasp contract.
    """

    def __init__(
        self,
        *args: Any,
        gripper_max_torque_nm: float,
        empty_close_threshold: float = 0.04,
        feedback_tolerance: float = 0.01,
        stable_samples: int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._gripper_max_torque_nm = float(gripper_max_torque_nm)
        self._empty_close_threshold = float(empty_close_threshold)
        self._grasp_feedback_tolerance = float(feedback_tolerance)
        self._grasp_stable_samples = int(stable_samples)
        self._grasp_lock = threading.Lock()
        self._grasp_status: Dict[str, Any] = self._idle_grasp_status()
        self._runtime_fault_lock = threading.Lock()
        self._runtime_fault = ""
        self._motor_a_status_codes = [0, 0, 0]

    @property
    def runtime_fault(self) -> str:
        with self._runtime_fault_lock:
            return self._runtime_fault

    @property
    def is_faulted(self) -> bool:
        return bool(self.runtime_fault)

    def _set_runtime_fault(self, message: object) -> None:
        text = str(message).strip() or "A1Z SDK control loop stopped unexpectedly."
        with self._runtime_fault_lock:
            if not self._runtime_fault:
                self._runtime_fault = text

    def start(
        self,
        initial_kp: Optional[np.ndarray] = None,
        initial_kd: Optional[np.ndarray] = None,
    ) -> None:
        with self._runtime_fault_lock:
            self._runtime_fault = ""
        super().start(initial_kp=initial_kp, initial_kd=initial_kd)

    def _update(self) -> None:
        try:
            super()._update()
        except Exception as exc:
            self._set_runtime_fault(exc)
            raise

    def _control_loop(self) -> None:
        super()._control_loop()
        if not self._stop_event.is_set() and not self.runtime_fault:
            self._set_runtime_fault("A1Z SDK control loop stopped unexpectedly.")

    def _check_motor_errors(self) -> None:
        """Apply MotorB fault semantics only to the MotorB joints.

        The official diagnostic tool intentionally excludes MotorA from its
        MotorB error-code table.  MotorA values are therefore exposed as raw
        status telemetry instead of being misclassified as fatal faults.
        """

        with self._state_lock:
            errors = np.asarray(self._state.error_codes, dtype=np.int64).copy()
        motor_a_count = min(3, errors.size)
        self._motor_a_status_codes = [
            int(value) for value in errors[:motor_a_count].tolist()
        ]
        for joint_index in range(motor_a_count, errors.size):
            code = int(errors[joint_index])
            if code in (0x0, 0x1):
                continue
            message = MOTOR_B_ERROR_CODES.get(code, f"unknown({code})")
            raise RuntimeError(
                f"MotorB fault on joint{joint_index + 1}: "
                f"error_code=0x{code:X} ({message})"
            )

    def _idle_grasp_status(self) -> Dict[str, Any]:
        return {
            "backend": "socketcan",
            "phase": "idle",
            "success": False,
            "object_detected": False,
            "gripper_position": None,
            "force_limited": True,
            "torque_limit_nm": self._gripper_max_torque_nm,
            "failure_reason": None,
        }

    def get_robot_info(self) -> Dict[str, Any]:
        info = dict(super().get_robot_info())
        with self._command_lock:
            command_pos = self._command.pos.copy()
        info.update(
            {
                "backend": "socketcan",
                "with_gripper": self.gripper is not None,
                "zero_gravity_mode": self.zero_gravity_mode,
                "control_mode": (
                    "gravity_comp_effort" if self.zero_gravity_mode else "position_hold"
                ),
                "gripper_torque_limit_nm": (
                    self._gripper_max_torque_nm if self.gripper is not None else None
                ),
                "gripper_free_drive": bool(self._gripper_free_drive),
                "running": bool(self.is_running),
                "faulted": self.is_faulted,
                "fault_message": self.runtime_fault,
                "motor_a_status_codes": list(self._motor_a_status_codes),
                # A relative joint jog must preserve the controller's existing
                # six-axis reference.  Reconstructing it from measured
                # feedback discards the position error that is currently
                # producing load-holding PD torque on the untouched joints.
                "command_pos": command_pos,
            }
        )
        return info

    def set_gravity_mode(self, enabled: bool) -> None:
        """Switch modes atomically while holding the current measured pose.

        The official implementation only changes Kp/Kd.  If the arm was moved
        in zero-gravity mode, restoring Kp would then chase the stale command
        position.  This adapter pins the command to measured feedback and clears
        all dynamic/feedforward terms before changing the gains.
        """

        if not self.is_running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self.is_estopped:
            raise RuntimeError("Robot is in estop.")
        measured = np.asarray(
            self.get_joint_pos()[: self._num_joints], dtype=np.float64
        ).copy()
        with self._command_lock:
            self._command.pos = measured
            self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)
            if enabled:
                self._command.kp = np.zeros(self._num_joints, dtype=np.float64)
                self._command.kd = self._default_kd.copy() * 0.5
            else:
                self._command.kp = self._default_kp.copy()
                self._command.kd = self._default_kd.copy()
            self.zero_gravity_mode = bool(enabled)
        logger.info(
            "Control mode switched to %s at measured pose %s rad",
            "zero-gravity" if enabled else "position-hold",
            np.round(measured, 3).tolist(),
        )

    def get_gripper_target_pos(self) -> Optional[float]:
        """Return the normalized target last accepted by the official SDK."""
        return super().get_gripper_pos()

    def get_gripper_measured_pos(self) -> Optional[float]:
        """Return normalized CAN feedback without substituting the target."""
        if self.gripper is None or self.gripper._motor.last_feedback is None:
            return None
        return float(self.gripper.get_feedback_norm())

    def command_gripper(self, value: float) -> None:
        """Reject states where the upstream setter would only change a draft."""
        if not self.is_running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self.is_estopped:
            raise RuntimeError("Robot is in estop.")
        if self._gripper_free_drive:
            raise RuntimeError("Gripper is in free-drive mode.")
        super().command_gripper(value)

    def _require_live_gripper_feedback(self) -> float:
        if not self.is_running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self.gripper is None:
            raise RuntimeError("No gripper attached. Start with --with-gripper.")
        if self.is_estopped:
            raise RuntimeError("Robot is in estop.")
        if self.gripper._motor.last_feedback is None:
            raise RuntimeError("No live gripper CAN feedback is available.")
        return float(self.gripper.get_feedback_norm())

    def grasp_close(self, *, timeout_s: float = 5.0) -> Dict[str, Any]:
        """Close with the configured hardware torque limit and detect an object."""

        timeout = float(timeout_s)
        if timeout <= 0.0:
            raise ValueError("timeout_s must be positive")
        initial_position = self._require_live_gripper_feedback()
        self.command_gripper(0.0)
        deadline = time.monotonic() + timeout
        last_position = initial_position
        stable_count = 0
        movement_seen = False

        while time.monotonic() < deadline:
            time.sleep(0.02)
            position = self._require_live_gripper_feedback()
            if position < initial_position - self._grasp_feedback_tolerance:
                movement_seen = True
            if movement_seen and abs(position - last_position) <= self._grasp_feedback_tolerance:
                stable_count += 1
            else:
                stable_count = 0
            last_position = position
            if stable_count < self._grasp_stable_samples:
                continue

            object_detected = position > self._empty_close_threshold
            status = {
                "backend": "socketcan",
                "phase": "holding" if object_detected else "empty",
                "success": object_detected,
                "object_detected": object_detected,
                "gripper_position": position,
                "initial_gripper_position": initial_position,
                "force_limited": True,
                "torque_limit_nm": self._gripper_max_torque_nm,
                "stable_samples": stable_count,
                "failure_reason": None if object_detected else "no_object_detected",
            }
            with self._grasp_lock:
                self._grasp_status = status
            return dict(status)

        status = {
            "backend": "socketcan",
            "phase": "failed",
            "success": False,
            "object_detected": False,
            "gripper_position": last_position,
            "initial_gripper_position": initial_position,
            "force_limited": True,
            "torque_limit_nm": self._gripper_max_torque_nm,
            "stable_samples": stable_count,
            "failure_reason": "gripper_close_timeout",
        }
        with self._grasp_lock:
            self._grasp_status = status
        return dict(status)

    def grasp_release(self, *, timeout_s: float = 3.0) -> Dict[str, Any]:
        """Open the jaws and wait for live position feedback."""

        timeout = float(timeout_s)
        if timeout <= 0.0:
            raise ValueError("timeout_s must be positive")
        self._require_live_gripper_feedback()
        self.command_gripper(1.0)
        deadline = time.monotonic() + timeout
        last_position = 0.0
        while time.monotonic() < deadline:
            time.sleep(0.02)
            last_position = self._require_live_gripper_feedback()
            if last_position >= 0.95:
                status = {
                    "backend": "socketcan",
                    "phase": "released",
                    "success": True,
                    "object_detected": False,
                    "gripper_position": last_position,
                    "force_limited": True,
                    "torque_limit_nm": self._gripper_max_torque_nm,
                    "failure_reason": None,
                }
                with self._grasp_lock:
                    self._grasp_status = status
                return dict(status)

        status = {
            "backend": "socketcan",
            "phase": "failed",
            "success": False,
            "object_detected": False,
            "gripper_position": last_position,
            "force_limited": True,
            "torque_limit_nm": self._gripper_max_torque_nm,
            "failure_reason": "gripper_release_timeout",
        }
        with self._grasp_lock:
            self._grasp_status = status
        return dict(status)

    def get_grasp_status(self) -> Dict[str, Any]:
        with self._grasp_lock:
            status = dict(self._grasp_status)
        if self.gripper is not None and self.gripper._motor.last_feedback is not None:
            current_position = float(self.gripper.get_feedback_norm())
            held_position = status.get("gripper_position")
            status["gripper_position"] = current_position
            if (
                status.get("phase") == "holding"
                and isinstance(held_position, (int, float))
                and current_position
                < max(self._empty_close_threshold, float(held_position) - 0.08)
            ):
                status.update(
                    {
                        "phase": "lost",
                        "success": False,
                        "object_detected": False,
                        "failure_reason": "object_lost",
                    }
                )
                with self._grasp_lock:
                    self._grasp_status = dict(status)
        status["estopped"] = self.is_estopped
        return status

    def play_trajectory(
        self,
        trajectory,
        speed_factor: float = 1.0,
    ) -> None:
        """Play recorded positions while making the official estop interruptible."""
        if not trajectory:
            raise ValueError("Empty trajectory")
        if not self.is_running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self.is_estopped:
            raise RuntimeError("Robot is in estop.")
        if speed_factor <= 0:
            raise ValueError("speed_factor must be > 0")

        started = time.monotonic()
        for recorded_s, position in trajectory:
            if self.is_estopped:
                raise RuntimeError("Trajectory playback interrupted by estop.")
            target_time = started + float(recorded_s) / float(speed_factor)
            self.command_joint_pos(np.asarray(position, dtype=np.float64))
            remaining = target_time - time.monotonic()
            if remaining > 0.0 and self._estop_latch.wait(timeout=remaining):
                raise RuntimeError("Trajectory playback interrupted by estop.")
