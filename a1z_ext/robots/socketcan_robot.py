"""SocketCAN hardware adapter for the upstream A1Z arm implementation."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

from a1z.motor_drivers.motor_b_driver import MOTOR_B_ERROR_CODES
from a1z.robots.arm_robot import ArmRobot
from a1z_ext.robots.connection_monitor import (
    ArmFeedbackMonitor,
    SocketCANLinkMonitor,
)


logger = logging.getLogger(__name__)

_SERVICE_MAX_COMMAND_VELOCITY_RAD_S = 4.0
_SERVICE_MAX_COMMAND_ACCELERATION_RAD_S2 = 20.0


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
        can_channel: str = "can0",
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
        self._can_channel = str(can_channel)
        self._can_link_monitor = SocketCANLinkMonitor(self._can_channel)
        self._arm_motor_entries = self._build_arm_motor_entries()
        self._arm_feedback_monitor = ArmFeedbackMonitor(
            [motor_id for _joint_index, motor_id, _motor in self._arm_motor_entries],
            stale_after_s=float(self._stale_estop_s),
        )
        self._last_arm_connection_log_signature: Optional[
            tuple[str, tuple[int, ...]]
        ] = None

    def _build_arm_motor_entries(self) -> tuple[tuple[int, int, Any], ...]:
        entries: list[tuple[int, int, Any]] = []
        for motor, joint_index in zip(
            self._motor_chain._motor_a_list,
            self._motor_chain._motor_a_joint_indices,
        ):
            entries.append((int(joint_index), int(motor.motor_id), motor))
        for motor, joint_index in zip(
            self._motor_chain._motor_b_list,
            self._motor_chain._motor_b_joint_indices,
        ):
            entries.append((int(joint_index), int(motor.motor_id), motor))
        entries.sort(key=lambda entry: entry[0])
        actual_indices = [joint_index for joint_index, _motor_id, _motor in entries]
        expected_indices = list(range(self._num_joints))
        if actual_indices != expected_indices:
            raise ValueError(
                "Arm motor chain must map exactly one CAN motor to every joint; "
                f"expected indices {expected_indices}, got {actual_indices}"
            )
        return tuple(entries)

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
        self._last_arm_connection_log_signature = None
        self._arm_feedback_monitor.reset()
        self._can_link_monitor.start()
        try:
            super().start(initial_kp=initial_kp, initial_kd=initial_kd)
        except Exception:
            self._can_link_monitor.stop()
            raise

    def stop(self) -> None:
        try:
            super().stop()
        finally:
            self._can_link_monitor.stop()

    def _read_state(self) -> None:
        previous_feedback = [
            motor.last_feedback
            for _joint_index, _motor_id, motor in self._arm_motor_entries
        ]
        super()._read_state()
        updated_joints = [
            joint_index
            for (joint_index, _motor_id, motor), previous in zip(
                self._arm_motor_entries,
                previous_feedback,
            )
            if motor.last_feedback is not None and motor.last_feedback is not previous
        ]
        if updated_joints:
            self._arm_feedback_monitor.observe(updated_joints)
        self._log_arm_connection_transition()

    def _check_feedback_stale(self) -> None:
        snapshot = self._arm_feedback_monitor.snapshot()
        maximum_age = float(snapshot["maximum_feedback_age_s"])
        unavailable = [int(value) for value in snapshot["unavailable_joints"]]
        if maximum_age > self._stale_estop_s:
            joints = ", ".join(f"J{index}" for index in unavailable) or "unknown"
            raise RuntimeError(
                "Arm CAN feedback stale or missing for "
                f"{joints} ({maximum_age * 1000.0:.0f}ms, "
                f"limit {self._stale_estop_s * 1000.0:.0f}ms)"
            )
        now = time.monotonic()
        if maximum_age > self._stale_warn_s and now - self._last_stale_warn_t > 1.0:
            lagging = [
                index + 1
                for index, age_ms in enumerate(snapshot["feedback_age_ms"])
                if age_ms is None or float(age_ms) > self._stale_warn_s * 1000.0
            ]
            logger.warning(
                "Arm CAN feedback delayed: joints=%s maximum_age=%.0fms",
                lagging,
                maximum_age * 1000.0,
            )
            self._last_stale_warn_t = now

    def _update(self) -> None:
        try:
            super()._update()
        except Exception as exc:
            self._set_runtime_fault(exc)
            raise

    def get_joint_state(self) -> Dict[str, Any]:
        state = dict(super().get_joint_state())
        monitor = getattr(self, "_arm_feedback_monitor", None)
        if monitor is not None:
            snapshot = monitor.snapshot()
            feedback_time = snapshot["oldest_feedback_monotonic_s"]
            if feedback_time is None:
                feedback_time = (
                    float(snapshot["observed_at_monotonic_s"])
                    - float(snapshot["maximum_feedback_age_s"])
                )
            state["feedback_monotonic_s"] = float(feedback_time)
            state["joint_feedback_age_ms"] = list(snapshot["feedback_age_ms"])
        return state

    def _control_loop(self) -> None:
        super()._control_loop()
        self._log_arm_connection_transition()
        if not self._stop_event.is_set() and not self.runtime_fault:
            self._set_runtime_fault("A1Z SDK control loop stopped unexpectedly.")

    def _log_arm_connection_transition(self) -> None:
        monitor = getattr(self, "_arm_feedback_monitor", None)
        if monitor is None:
            return
        snapshot = monitor.snapshot()
        signature = (
            str(snapshot["status"]),
            tuple(int(value) for value in snapshot["unavailable_joints"]),
        )
        if signature == self._last_arm_connection_log_signature:
            return
        self._last_arm_connection_log_signature = signature
        message = "Arm connection: status=%s online=%s unavailable=%s" % (
            snapshot["status"],
            snapshot["online_joints"],
            snapshot["unavailable_joints"],
        )
        if snapshot["status"] in {"connected", "connecting"}:
            logger.info(message)
        else:
            logger.warning(message)

    def get_connection_status(self) -> Dict[str, Any]:
        """Return backend diagnostics without opening another CAN reader."""

        can_monitor = getattr(self, "_can_link_monitor", None)
        arm_monitor = getattr(self, "_arm_feedback_monitor", None)
        can_status = (
            can_monitor.snapshot()
            if can_monitor is not None
            else {
                "channel": getattr(self, "_can_channel", "unknown"),
                "status": "unknown",
                "connected": False,
                "healthy": False,
                "diagnostic": "monitor_unavailable",
            }
        )
        arm_status = (
            arm_monitor.snapshot()
            if arm_monitor is not None
            else {
                "status": "unknown",
                "connected": False,
                "diagnostic": "monitor_unavailable",
            }
        )
        return {"can": can_status, "arm": arm_status}

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
                "connections": self.get_connection_status(),
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

    def command_motion_frame(
        self,
        position: np.ndarray,
        velocity: np.ndarray,
        acceleration: np.ndarray,
    ) -> None:
        """Atomically accept one server-planned position-mode command frame.

        The latest-target controller is the sole caller.  Keeping position,
        velocity, and acceleration in one command-lock transaction prevents a
        replacement target from exposing a partially updated feedforward state
        to the 250 Hz hardware loop.
        """

        if not self.is_running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self.is_estopped:
            raise RuntimeError("Robot is in estop.")
        if self.zero_gravity_mode:
            raise RuntimeError("Position command requires position-hold mode.")

        pos = np.asarray(position, dtype=np.float64).reshape(-1)
        vel = np.asarray(velocity, dtype=np.float64).reshape(-1)
        acc = np.asarray(acceleration, dtype=np.float64).reshape(-1)
        if pos.size != self._num_joints:
            raise ValueError(f"Expected {self._num_joints} positions, got {pos.size}")
        if vel.size != self._num_joints or acc.size != self._num_joints:
            raise ValueError("Velocity and acceleration must match the arm joint count")
        if not (
            np.all(np.isfinite(pos))
            and np.all(np.isfinite(vel))
            and np.all(np.isfinite(acc))
        ):
            raise ValueError("Motion command frame must contain only finite values")
        safe_pos = self._validate_joint_pos(pos)
        if np.any(np.abs(vel) > _SERVICE_MAX_COMMAND_VELOCITY_RAD_S):
            raise ValueError(
                "Motion command velocity exceeds the service safety limit of "
                f"{_SERVICE_MAX_COMMAND_VELOCITY_RAD_S:g} rad/s"
            )
        if np.any(np.abs(acc) > _SERVICE_MAX_COMMAND_ACCELERATION_RAD_S2):
            raise ValueError(
                "Motion command acceleration exceeds the service safety limit of "
                f"{_SERVICE_MAX_COMMAND_ACCELERATION_RAD_S2:g} rad/s²"
            )

        with self._command_lock:
            self._command.pos = safe_pos.copy()
            self._command.vel = vel.copy()
            self._command.acc = acc.copy()
            self._command.kp = self._default_kp.copy()
            self._command.kd = self._default_kd.copy()
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)

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
