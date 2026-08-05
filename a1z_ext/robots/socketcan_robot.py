"""SocketCAN hardware adapter for the upstream A1Z arm implementation."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Sequence

import numpy as np

from a1z.motor_drivers.motor_b_driver import MOTOR_B_ERROR_CODES
from a1z.robots.arm_robot import ArmRobot, JointCommand
from a1z_ext.robots.connection_monitor import (
    ArmFeedbackMonitor,
    ArmFeedbackStartupGate,
    SocketCANLinkMonitor,
)
from a1z_ext.robots.realtime_joint_controller import (
    JointTorqueShaper,
    RuckigJointReferenceGenerator,
)


logger = logging.getLogger(__name__)

_SERVICE_MAX_COMMAND_VELOCITY_RAD_S = 4.0
_SERVICE_MAX_COMMAND_ACCELERATION_RAD_S2 = 20.0
_DEFAULT_TORQUE_SLEW_RATE_NM_S = np.array(
    [250.0, 250.0, 250.0, 100.0, 40.0, 40.0],
    dtype=np.float64,
)


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
        feedback_startup_timeout_s: float = 2.0,
        torque_slew_rate_nm_s: Optional[Sequence[float]] = None,
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
        self._arm_feedback_startup_gate = ArmFeedbackStartupGate(
            timeout_s=feedback_startup_timeout_s,
        )
        # ArmRobot.start() creates the control thread before returning. Hold
        # this lock across that hand-off so the first adapter update cannot
        # evaluate a pre-reset snapshot against the post-reset startup gate.
        self._arm_feedback_startup_lock = threading.Lock()
        self._feedback_probe_zero = np.zeros(self._num_joints, dtype=np.float64)
        self._feedback_probe_kd = np.full(self._num_joints, 0.05, dtype=np.float64)
        self._last_arm_connection_log_signature: Optional[
            tuple[str, tuple[int, ...]]
        ] = None
        self._native_reference_lock = threading.Lock()
        self._native_trajectory_lock = threading.Lock()
        self._torque_shaper_lock = threading.Lock()
        self._native_trajectory_mode = "inactive"
        self._native_integral_gain_s_inv = 0.6
        self._native_correction_rate_limit_rad_s = np.deg2rad(0.5)
        self._native_max_correction_rad = np.deg2rad(3.0)
        self._joint_reference_generator = RuckigJointReferenceGenerator(
            self._num_joints,
            self._control_period_s,
        )
        torque_slew_rate = (
            _DEFAULT_TORQUE_SLEW_RATE_NM_S
            if torque_slew_rate_nm_s is None
            else torque_slew_rate_nm_s
        )
        self._joint_torque_shaper = JointTorqueShaper(
            self._num_joints,
            self._control_period_s,
            torque_slew_rate,
        )
        self._joint_trajectory_status: Dict[str, Any] = {
            "mode": "inactive",
            "generation": 0,
            "finished": True,
            "target_rad": None,
            "reference_position_rad": None,
            "reference_velocity_rad_s": None,
            "reference_acceleration_rad_s2": None,
            "integral_torque_bias_nm": [0.0] * self._num_joints,
            "equivalent_position_correction_rad": [0.0] * self._num_joints,
            "correction_saturated": False,
        }

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
        self._can_link_monitor.start()
        try:
            with self._arm_feedback_startup_lock:
                self._arm_feedback_startup_gate.begin_initialization()
                self._arm_feedback_monitor.reset()
                super().start(initial_kp=initial_kp, initial_kd=initial_kd)
                startup_started_at = time.monotonic()
                self._arm_feedback_monitor.reset(now=startup_started_at)
                self._arm_feedback_startup_gate.begin_waiting(now=startup_started_at)
        except Exception:
            self._arm_feedback_startup_gate.stop()
            self._can_link_monitor.stop()
            raise

    def stop(self) -> None:
        try:
            super().stop()
        finally:
            self._arm_feedback_startup_gate.stop()
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
        startup_gate = getattr(self, "_arm_feedback_startup_gate", None)
        if startup_gate is not None and startup_gate.phase != "monitoring":
            return
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

    def _run_feedback_startup_step(self) -> None:
        """Acquire all arm feedback using probes that cannot chase a position."""

        self._read_state()
        # Keep every runtime safety check except feedback freshness active while
        # acquiring the initial replies. _check_feedback_stale() is gated until
        # all joints have answered, but motor faults, temperatures, limits, and
        # measured velocity retain their normal protection.
        self._check_runtime_safety()
        snapshot = self._arm_feedback_monitor.snapshot()
        action = self._arm_feedback_startup_gate.evaluate(snapshot)
        if action == "ready":
            with self._state_lock:
                measured = self._state.pos.copy()
            with self._command_lock:
                self._command.pos = measured
                self._command.vel.fill(0.0)
                self._command.acc.fill(0.0)
                self._command.torque_ff.fill(0.0)
            reference_generator = getattr(self, "_joint_reference_generator", None)
            if reference_generator is not None:
                with self._native_reference_lock:
                    reference_generator.reset(measured)
            torque_shaper = getattr(self, "_joint_torque_shaper", None)
            if torque_shaper is not None:
                with self._torque_shaper_lock:
                    torque_shaper.reset(preserve_last_torque=False)
            logger.info(
                "Arm feedback startup complete: online=%s",
                snapshot["online_joints"],
            )
            return
        if action == "timeout":
            unavailable = [int(value) for value in snapshot["unavailable_joints"]]
            joints = ", ".join(f"J{index}" for index in unavailable) or "unknown"
            gate = self._arm_feedback_startup_gate.snapshot()
            raise RuntimeError(
                "Arm CAN feedback startup timed out for "
                f"{joints} after {float(gate['timeout_ms']) / 1000.0:.1f}s"
            )
        self._motor_chain.send_commands(
            pos=self._feedback_probe_zero,
            vel=self._feedback_probe_zero,
            kp=self._feedback_probe_zero,
            kd=self._feedback_probe_kd,
            torque=self._feedback_probe_zero,
        )

    def _trajectory_mode(self) -> str:
        with self._native_trajectory_lock:
            return self._native_trajectory_mode

    def set_joint_trajectory_target(
        self,
        position: Sequence[float],
        *,
        max_velocity_rad_s: float,
        max_acceleration_rad_s2: float,
        max_jerk_rad_s3: float,
        integral_gain_s_inv: float,
        correction_rate_limit_rad_s: float,
        max_correction_rad: float,
    ) -> int:
        """Atomically publish a final target to the 250 Hz control owner."""

        if not self.is_running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self.is_estopped:
            raise RuntimeError("Robot is in estop.")
        if self.zero_gravity_mode:
            raise RuntimeError("Joint trajectory requires position-hold mode.")
        target = np.asarray(position, dtype=np.float64).reshape(-1)
        if target.size != self._num_joints or not np.all(np.isfinite(target)):
            raise ValueError(
                f"Joint trajectory target must contain {self._num_joints} finite values"
            )
        safe_target = self._validate_joint_pos(target)
        integral_gain = float(integral_gain_s_inv)
        correction_rate = float(correction_rate_limit_rad_s)
        correction_limit = float(max_correction_rad)
        if not all(
            np.isfinite(value) and value > 0.0
            for value in (integral_gain, correction_rate, correction_limit)
        ):
            raise ValueError("Joint residual correction limits must be positive")
        generation = self._joint_reference_generator.set_target(
            safe_target,
            max_velocity=max_velocity_rad_s,
            max_acceleration=max_acceleration_rad_s2,
            max_jerk=max_jerk_rad_s3,
        )
        with self._native_trajectory_lock:
            self._native_integral_gain_s_inv = integral_gain
            self._native_correction_rate_limit_rad_s = correction_rate
            self._native_max_correction_rad = correction_limit
            self._native_trajectory_mode = "active"
        return generation

    def cancel_joint_trajectory(self) -> None:
        """Freeze the current generated reference and leave native trajectory mode."""

        generator = getattr(self, "_joint_reference_generator", None)
        if generator is None:
            return
        with self._native_reference_lock:
            generator.cancel()
        with self._command_lock:
            held = self._command.pos.copy()
            self._command.vel.fill(0.0)
            self._command.acc.fill(0.0)
        with self._torque_shaper_lock:
            self._joint_torque_shaper.reset()
        with self._native_trajectory_lock:
            self._native_trajectory_mode = "inactive"
            self._joint_trajectory_status = {
                **self._joint_trajectory_status,
                "mode": "inactive",
                "finished": True,
                "target_rad": held.tolist(),
                "reference_position_rad": held.tolist(),
                "reference_velocity_rad_s": [0.0] * self._num_joints,
                "reference_acceleration_rad_s2": [0.0] * self._num_joints,
                "integral_torque_bias_nm": [0.0] * self._num_joints,
                "equivalent_position_correction_rad": [0.0] * self._num_joints,
                "correction_saturated": False,
            }

    def _reset_native_reference(self, position: Sequence[float]) -> None:
        generator = getattr(self, "_joint_reference_generator", None)
        if generator is None:
            return
        with self._native_reference_lock:
            generator.reset(position)

    def estop(self) -> None:
        self.cancel_joint_trajectory()
        super().estop()
        with self._command_lock:
            held = self._command.pos.copy()
        self._reset_native_reference(held)

    def release(self) -> None:
        super().release()
        with self._command_lock:
            held = self._command.pos.copy()
        self._reset_native_reference(held)

    def get_joint_trajectory_status(self) -> Dict[str, Any]:
        lock = getattr(self, "_native_trajectory_lock", None)
        if lock is None:
            return {
                "mode": "inactive",
                "generation": 0,
                "finished": True,
            }
        with lock:
            return dict(self._joint_trajectory_status)

    def _advance_native_joint_reference(
        self,
        measured_position: np.ndarray,
        measured_velocity: np.ndarray,
    ) -> tuple[bool, bool, int, np.ndarray]:
        mode = self._trajectory_mode()
        if mode != "active":
            return False, True, 0, np.zeros(self._num_joints, dtype=np.float64)
        with self._native_reference_lock:
            reference = self._joint_reference_generator.advance(
                measured_position,
                measured_velocity,
            )
        with self._command_lock:
            self._command.pos = reference.position.copy()
            self._command.vel = reference.velocity.copy()
            self._command.acc = reference.acceleration.copy()
            self._command.kp = self._default_kp.copy()
            self._command.kd = self._default_kd.copy()
            self._command.torque_ff.fill(0.0)
        return (
            True,
            reference.finished,
            reference.generation,
            reference.target.copy(),
        )

    def _update_trajectory_status(
        self,
        *,
        active: bool,
        finished: bool,
        generation: int,
        target: np.ndarray,
        command: JointCommand,
        integral_torque_bias: np.ndarray,
        equivalent_correction: np.ndarray,
    ) -> None:
        with self._native_trajectory_lock:
            previous = self._joint_trajectory_status
            self._joint_trajectory_status = {
                "mode": "active" if active else "inactive",
                "generation": int(generation) if active else int(
                    previous.get("generation", 0)
                ),
                "finished": bool(finished),
                "target_rad": target.tolist() if active else previous.get("target_rad"),
                "reference_position_rad": command.pos.tolist(),
                "reference_velocity_rad_s": command.vel.tolist(),
                "reference_acceleration_rad_s2": command.acc.tolist(),
                "integral_torque_bias_nm": integral_torque_bias.tolist(),
                "equivalent_position_correction_rad": equivalent_correction.tolist(),
                "correction_saturated": bool(
                    np.any(
                        np.abs(equivalent_correction)
                        >= self._native_max_correction_rad - 1e-12
                    )
                ),
            }

    def _update(self) -> None:
        """One 250 Hz impedance step with an in-thread Ruckig reference."""

        try:
            with self._arm_feedback_startup_lock:
                if self._arm_feedback_startup_gate.active:
                    self._run_feedback_startup_step()
                    return

            if self.zero_gravity_mode:
                # Apart from the project-selected control URDF, floating mode
                # must follow the upstream SDK exactly: live measured q for
                # RNEA, upstream torque scaling/clipping, and the upstream MIT
                # command frame. Position-mode additions stay below this gate.
                super()._update()
                return

            t_now = time.time()
            self._read_state()
            self._check_runtime_safety()

            if self._recording and t_now - self._record_last_t >= self._record_period:
                with self._state_lock:
                    pos_snap = self._state.pos.copy()
                if self.gripper is not None:
                    pos_snap = np.append(pos_snap, self.gripper.get_feedback_norm())
                with self._record_lock:
                    if self._recording:
                        self._record_buffer.append((t_now, pos_snap))
                self._record_last_t = t_now

            with self._state_lock:
                measured_position = self._state.pos.copy()
                measured_velocity = self._state.vel.copy()
            (
                native_active,
                trajectory_finished,
                trajectory_generation,
                trajectory_target,
            ) = (
                self._advance_native_joint_reference(
                    measured_position,
                    measured_velocity,
                )
            )

            with self._command_lock:
                cmd = JointCommand(
                    pos=self._command.pos.copy(),
                    vel=self._command.vel.copy(),
                    acc=self._command.acc.copy(),
                    kp=self._command.kp.copy(),
                    kd=self._command.kd.copy(),
                    torque_ff=self._command.torque_ff.copy(),
                )
            if np.any(np.abs(cmd.vel) > _SERVICE_MAX_COMMAND_VELOCITY_RAD_S):
                raise RuntimeError(
                    "Ruckig reference velocity exceeds the service safety limit: "
                    f"{np.round(cmd.vel, 3).tolist()}"
                )
            if np.any(
                np.abs(cmd.acc) > _SERVICE_MAX_COMMAND_ACCELERATION_RAD_S2
            ):
                raise RuntimeError(
                    "Ruckig reference acceleration exceeds the service safety limit: "
                    f"{np.round(cmd.acc, 3).tolist()}"
                )

            # Position-hold uses one internally consistent Ruckig desired state
            # for inverse-dynamics feedforward. Floating mode returned through
            # the official SDK path above.
            tau_id = self._gravity_model.compute_inverse_dynamics(
                cmd.pos,
                cmd.vel,
                cmd.acc,
            )
            if np.any(np.abs(tau_id) > self._max_gravity_torque):
                raise RuntimeError(
                    "Inverse dynamics torques too large! "
                    f"tau={np.round(tau_id, 2)} Nm. "
                    f"Max allowed: {self._max_gravity_torque} Nm."
                )
            tau_id_scaled = tau_id * self._gravity_torque_scale
            base_torque = (
                cmd.torque_ff
                + tau_id_scaled * self.gravity_comp_factor
            )

            with self._native_trajectory_lock:
                integral_gain = self._native_integral_gain_s_inv
                correction_rate = self._native_correction_rate_limit_rad_s
                correction_limit = self._native_max_correction_rad
            integral_enabled = bool(
                native_active
                and trajectory_finished
                and np.max(np.abs(measured_velocity)) <= 0.05
                and not self.zero_gravity_mode
            )
            with self._torque_shaper_lock:
                integral_torque_bias = self._joint_torque_shaper.update_integral(
                    position_error=trajectory_target - measured_position,
                    kp=cmd.kp,
                    base_torque=base_torque,
                    torque_limit=self._torque_clip,
                    enabled=integral_enabled,
                    integral_gain_s_inv=integral_gain,
                    correction_rate_limit_rad_s=correction_rate,
                    max_correction_rad=correction_limit,
                )
                torques_urdf = self._joint_torque_shaper.shape_total(
                    base_torque + integral_torque_bias,
                    self._torque_clip,
                )
                equivalent_correction = (
                    self._joint_torque_shaper.equivalent_correction
                )
            motor_torques = torques_urdf * self._joint_sign

            self._motor_chain.send_commands(
                pos=cmd.pos * self._joint_sign,
                vel=cmd.vel * self._joint_sign,
                kp=cmd.kp,
                kd=cmd.kd,
                torque=motor_torques,
            )
            self._update_trajectory_status(
                active=native_active,
                finished=trajectory_finished,
                generation=trajectory_generation,
                target=trajectory_target,
                command=cmd,
                integral_torque_bias=integral_torque_bias,
                equivalent_correction=equivalent_correction,
            )

            if self.gripper is not None:
                if self._gripper_free_drive:
                    self.gripper.free_drive_step()
                else:
                    self.gripper.step()
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
        startup_gate = getattr(self, "_arm_feedback_startup_gate", None)
        if startup_gate is not None:
            arm_status = {
                **arm_status,
                "startup": startup_gate.snapshot(),
            }
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
                "joint_control_architecture": (
                    "ruckig_250hz_inverse_dynamics_mit_impedance"
                ),
                "joint_trajectory": self.get_joint_trajectory_status(),
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
        self.cancel_joint_trajectory()
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
        torque_shaper = getattr(self, "_joint_torque_shaper", None)
        torque_shaper_lock = getattr(self, "_torque_shaper_lock", None)
        if torque_shaper is not None and torque_shaper_lock is not None:
            with torque_shaper_lock:
                # Floating mode bypasses the position controller's torque
                # shaper. Do not carry a stale pre-switch torque into the next
                # hold step.
                torque_shaper.reset(preserve_last_torque=False)
        self._reset_native_reference(measured)
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

        # This is the compatibility path for non-native callers.  It must never
        # race the in-thread Ruckig owner.
        self.cancel_joint_trajectory()
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
