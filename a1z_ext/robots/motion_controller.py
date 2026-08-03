"""Single-owner, latest-target-wins arm motion controller.

Every arm target source submits into this controller.  One worker owns the
feedback -> FK -> arrival decision -> command-frame cycle, so SDK writes can
never race and a replacement target never waits behind a command queue.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

import numpy as np


ForwardKinematics = Callable[[np.ndarray], np.ndarray]


def _rotation_error_deg(target: np.ndarray, measured: np.ndarray) -> float:
    relative = target[:3, :3].T @ measured[:3, :3]
    cosine = float(np.clip((np.trace(relative) - 1.0) * 0.5, -1.0, 1.0))
    return float(math.degrees(math.acos(cosine)))


@dataclass
class MotionGoal:
    goal_id: int
    target_rad: np.ndarray
    target_pose: np.ndarray
    speed_rad_s: float
    source: str
    timeout_s: float
    metadata: dict[str, Any] = field(default_factory=dict)
    submitted_at: float = field(default_factory=time.monotonic)
    state: str = "pending"
    result: Optional[dict[str, Any]] = None
    completion_event: threading.Event = field(default_factory=threading.Event)
    motion_performed: bool = False


class LatestTargetMotionController:
    """Own the only arm command writer and maintain the newest valid target."""

    def __init__(
        self,
        robot: Any,
        *,
        forward_kinematics: Optional[ForwardKinematics] = None,
        endpoint_frame: str = "grasp_tcp",
        endpoint_position_tolerance_mm: float = 0.5,
        endpoint_orientation_tolerance_deg: float = 0.5,
        endpoint_stable_samples: int = 5,
        settle_velocity_rad_s: float = 0.02,
        feedback_timeout_s: float = 2.0,
        feedback_stale_timeout_s: float = 0.25,
        control_period_s: float = 0.02,
        acceleration_limit_rad_s2: float = 2.0,
        jerk_limit_rad_s3: float = 12.0,
        correction_gain: float = 0.2,
        correction_period_s: float = 0.1,
        max_correction_deg: float = 3.0,
    ) -> None:
        self._robot = robot
        self._forward_kinematics = forward_kinematics
        self._endpoint_frame = str(endpoint_frame)
        self._position_tolerance_mm = self._positive(
            endpoint_position_tolerance_mm,
            "endpoint_position_tolerance_mm",
        )
        self._orientation_tolerance_deg = self._positive(
            endpoint_orientation_tolerance_deg,
            "endpoint_orientation_tolerance_deg",
        )
        self._stable_samples_required = max(1, int(endpoint_stable_samples))
        self._settle_velocity_rad_s = self._positive(
            settle_velocity_rad_s,
            "settle_velocity_rad_s",
        )
        self._feedback_timeout_s = self._nonnegative(
            feedback_timeout_s,
            "feedback_timeout_s",
        )
        self._feedback_stale_timeout_s = self._positive(
            feedback_stale_timeout_s,
            "feedback_stale_timeout_s",
        )
        self._period_s = self._positive(control_period_s, "control_period_s")
        self._acceleration_limit = self._positive(
            acceleration_limit_rad_s2,
            "acceleration_limit_rad_s2",
        )
        self._jerk_limit = self._positive(jerk_limit_rad_s3, "jerk_limit_rad_s3")
        self._correction_gain = self._positive(correction_gain, "correction_gain")
        self._correction_period_s = self._positive(
            correction_period_s,
            "correction_period_s",
        )
        self._max_correction_rad = math.radians(
            self._positive(max_correction_deg, "max_correction_deg")
        )

        self._condition = threading.Condition()
        self._sdk_write_lock = threading.Lock()
        self._fk_lock = threading.Lock()
        self._shutdown = False
        self._accepting_targets = True
        self._next_goal_id = 1
        self._latest_goal: Optional[MotionGoal] = None
        self._reference_target_rad: Optional[np.ndarray] = None
        self._status: dict[str, Any] = {
            "state": "idle",
            "endpoint_position_tolerance_mm": self._position_tolerance_mm,
            "endpoint_orientation_tolerance_deg": self._orientation_tolerance_deg,
        }
        self._planner_state_lock = threading.Lock()
        self._last_command_position: Optional[np.ndarray] = None
        self._last_command_velocity: Optional[np.ndarray] = None
        self._last_command_acceleration: Optional[np.ndarray] = None
        self._worker = threading.Thread(
            target=self._run,
            name="a1z-latest-target-controller",
            daemon=True,
        )
        self._worker.start()

    @staticmethod
    def _positive(value: float, name: str) -> float:
        result = float(value)
        if not math.isfinite(result) or result <= 0.0:
            raise ValueError(f"{name} must be a positive finite number")
        return result

    @staticmethod
    def _nonnegative(value: float, name: str) -> float:
        result = float(value)
        if not math.isfinite(result) or result < 0.0:
            raise ValueError(f"{name} must be a non-negative finite number")
        return result

    def _fk(self, joints_rad: np.ndarray) -> np.ndarray:
        with self._fk_lock:
            if self._forward_kinematics is None:
                from a1z.robots.kinematics import Kinematics
                from a1z_ext.config import get_default_control_urdf_path

                kinematics = Kinematics(
                    get_default_control_urdf_path(),
                    end_effector_frame=self._endpoint_frame,
                )
                self._forward_kinematics = lambda q: kinematics.fk(
                    q,
                    frame_name=self._endpoint_frame,
                )
            transform = np.asarray(
                self._forward_kinematics(joints_rad),
                dtype=np.float64,
            )
        if transform.shape != (4, 4) or not np.all(np.isfinite(transform)):
            raise ValueError("Forward kinematics returned an invalid 4x4 transform")
        return transform.copy()

    def _robot_info(self) -> dict[str, Any]:
        reader = getattr(self._robot, "get_robot_info", None)
        return dict(reader()) if callable(reader) else {}

    def _joint_limits(self) -> Optional[np.ndarray]:
        raw = self._robot_info().get("joint_limits")
        if raw is None:
            return None
        try:
            limits = np.asarray(raw, dtype=np.float64).reshape(-1, 2)[:6]
        except (TypeError, ValueError):
            return None
        if limits.shape != (6, 2) or not np.all(np.isfinite(limits)):
            return None
        return limits.copy()

    def _validate_target(self, target_rad: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
        target = np.asarray(target_rad, dtype=np.float64).reshape(-1)
        if target.size != 6 or not np.all(np.isfinite(target)):
            raise ValueError("Arm target must contain exactly 6 finite joint values")
        limits = self._joint_limits()
        if limits is not None:
            invalid = (target < limits[:, 0]) | (target > limits[:, 1])
            if np.any(invalid):
                index = int(np.flatnonzero(invalid)[0])
                raise ValueError(
                    f"Joint target violates soft limit at J{index + 1}: "
                    f"{math.degrees(float(target[index])):.3f}° is outside "
                    f"[{math.degrees(float(limits[index, 0])):.3f}°, "
                    f"{math.degrees(float(limits[index, 1])):.3f}°]"
                )
        return target.copy(), self._fk(target)

    def _initial_reference(self) -> np.ndarray:
        info = self._robot_info()
        raw = info.get("command_pos")
        if raw is None:
            reader = getattr(self._robot, "get_joint_pos", None)
            if not callable(reader):
                raise RuntimeError("Robot backend exposes no arm position reference")
            raw = reader()
        reference = np.asarray(raw, dtype=np.float64).reshape(-1)[:6]
        if reference.size != 6 or not np.all(np.isfinite(reference)):
            raise RuntimeError("Robot backend returned an invalid arm position reference")
        return reference.copy()

    def _new_goal_locked(
        self,
        target: np.ndarray,
        target_pose: np.ndarray,
        *,
        speed_rad_s: float,
        source: str,
        timeout_s: float,
        metadata: Optional[Mapping[str, Any]],
    ) -> MotionGoal:
        goal = MotionGoal(
            goal_id=self._next_goal_id,
            target_rad=target.copy(),
            target_pose=target_pose.copy(),
            speed_rad_s=self._positive(speed_rad_s, "speed_rad_s"),
            source=str(source or "unknown"),
            timeout_s=self._positive(timeout_s, "timeout_s"),
            metadata=dict(metadata or {}),
        )
        self._next_goal_id += 1
        previous = self._latest_goal
        if previous is not None and not previous.completion_event.is_set():
            self._complete_superseded_locked(previous, replacement_goal_id=goal.goal_id)
        self._latest_goal = goal
        self._reference_target_rad = target.copy()
        self._status = self._goal_status(goal, state="pending")
        self._condition.notify_all()
        return goal

    def submit(
        self,
        target_rad: Sequence[float],
        *,
        speed_rad_s: float,
        source: str,
        timeout_s: float = 120.0,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> MotionGoal:
        """Validate completely, then atomically replace the current goal."""

        speed = self._positive(speed_rad_s, "speed_rad_s")
        timeout = self._positive(timeout_s, "timeout_s")
        target, pose = self._validate_target(target_rad)
        with self._condition:
            if self._shutdown:
                raise RuntimeError("Arm motion controller is stopped")
            if not self._accepting_targets:
                raise RuntimeError("Arm motion target submission is temporarily gated")
            return self._new_goal_locked(
                target,
                pose,
                speed_rad_s=speed,
                source=source,
                timeout_s=timeout,
                metadata=metadata,
            )

    def submit_delta(
        self,
        delta_rad: Sequence[float],
        *,
        speed_rad_s: float,
        source: str,
        timeout_s: float = 120.0,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> MotionGoal:
        delta = np.asarray(delta_rad, dtype=np.float64).reshape(-1)
        if delta.size != 6 or not np.all(np.isfinite(delta)):
            raise ValueError("Arm delta must contain exactly 6 finite joint values")
        with self._condition:
            if self._shutdown:
                raise RuntimeError("Arm motion controller is stopped")
            if not self._accepting_targets:
                raise RuntimeError("Arm motion target submission is temporarily gated")
            base = (
                self._reference_target_rad.copy()
                if self._reference_target_rad is not None
                else self._initial_reference()
            )
            target, pose = self._validate_target(base + delta)
            return self._new_goal_locked(
                target,
                pose,
                speed_rad_s=speed_rad_s,
                source=source,
                timeout_s=timeout_s,
                metadata=metadata,
            )

    def submit_replacement(
        self,
        expected_goal: MotionGoal,
        target_rad: Sequence[float],
        *,
        speed_rad_s: float,
        source: str,
        timeout_s: float = 120.0,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> MotionGoal:
        """Advance a server-side program only if no external target took over."""

        speed = self._positive(speed_rad_s, "speed_rad_s")
        timeout = self._positive(timeout_s, "timeout_s")
        target, pose = self._validate_target(target_rad)
        with self._condition:
            if self._shutdown:
                raise RuntimeError("Arm motion controller is stopped")
            if not self._accepting_targets:
                raise RuntimeError("Arm motion target submission is temporarily gated")
            if self._latest_goal is not expected_goal:
                raise RuntimeError(
                    "Motion program was superseded by a newer external target"
                )
            return self._new_goal_locked(
                target,
                pose,
                speed_rad_s=speed,
                source=source,
                timeout_s=timeout,
                metadata=metadata,
            )

    def accepted_response(self, goal: MotionGoal) -> dict[str, Any]:
        return {
            "ok": True,
            "data": {
                "accepted": True,
                "goal_id": goal.goal_id,
                "target_deg": self._degrees(goal.target_rad),
                "speed_rad_s": goal.speed_rad_s,
                "completion": "accepted",
            },
        }

    def wait(self, goal: MotionGoal, *, timeout_s: Optional[float] = None) -> dict[str, Any]:
        # The controller and the waiting request must not race on the exact
        # same deadline. Give the worker a short scheduling margin so callers
        # receive the authoritative reached/failed result instead of a
        # misleading local wait timeout at the boundary.
        timeout = (
            goal.timeout_s + max(0.25, self._period_s * 2.0)
            if timeout_s is None
            else self._positive(timeout_s, "timeout_s")
        )
        if goal.completion_event.wait(timeout=timeout):
            assert goal.result is not None
            return goal.result
        snapshot = self.status_snapshot()
        return {
            "ok": False,
            "execution_state": "submitted_unverified",
            "error": (
                f"Motion goal {goal.goal_id} is still active after waiting "
                f"{timeout:.3f} s; the service continues to own and maintain it."
            ),
            "data": {
                "goal_id": goal.goal_id,
                "completion": "wait_timeout",
                "motion": snapshot,
            },
        }

    def cancel(self, reason: str, *, execution_state: str = "cancelled") -> None:
        with self._condition:
            goal = self._latest_goal
            self._latest_goal = None
            self._reference_target_rad = None
            if goal is not None and not goal.completion_event.is_set():
                goal.state = execution_state
                goal.result = {
                    "ok": False,
                    "execution_state": execution_state,
                    "error": str(reason),
                    "data": {
                        "goal_id": goal.goal_id,
                        "completion": execution_state,
                    },
                }
                goal.completion_event.set()
            self._status = {
                "state": execution_state,
                "reason": str(reason),
                "endpoint_position_tolerance_mm": self._position_tolerance_mm,
                "endpoint_orientation_tolerance_deg": self._orientation_tolerance_deg,
            }
            self._condition.notify_all()
        self._reset_planner_state()

    def run_exclusive(self, callback: Callable[[], Any], *, reason: str) -> Any:
        """Cancel motion, finish one command-frame write, then run an SDK transition."""

        with self._condition:
            self._accepting_targets = False
        self.cancel(reason)
        try:
            with self._sdk_write_lock:
                result = callback()
                self._reset_planner_state()
                return result
        finally:
            with self._condition:
                self._accepting_targets = True
                self._condition.notify_all()

    def owns_goal(self, goal: MotionGoal) -> bool:
        """Return whether ``goal`` is still the service's newest target."""

        return self._is_current(goal)

    def shutdown(self) -> None:
        self.cancel("Arm motion controller is stopping.", execution_state="cancelled")
        with self._condition:
            self._shutdown = True
            self._condition.notify_all()
        if self._worker.is_alive() and threading.current_thread() is not self._worker:
            self._worker.join(timeout=1.0)

    def status_snapshot(self) -> dict[str, Any]:
        with self._condition:
            return dict(self._status)

    def config_snapshot(self) -> dict[str, Any]:
        return {
            "owner": "server_latest_target_controller",
            "policy": "latest_target_wins",
            "endpoint_frame": self._endpoint_frame,
            "endpoint_position_tolerance_mm": self._position_tolerance_mm,
            "endpoint_orientation_tolerance_deg": self._orientation_tolerance_deg,
            "stable_samples_required": self._stable_samples_required,
            "settle_velocity_rad_s": self._settle_velocity_rad_s,
            "feedback_stale_timeout_s": self._feedback_stale_timeout_s,
            "control_period_s": self._period_s,
            "acceleration_limit_rad_s2": self._acceleration_limit,
            "jerk_limit_rad_s3": self._jerk_limit,
            "max_correction_deg": math.degrees(self._max_correction_rad),
        }

    @staticmethod
    def _degrees(values: np.ndarray, digits: int = 3) -> list[float]:
        return [round(float(value), digits) for value in np.rad2deg(values)]

    def _goal_status(self, goal: MotionGoal, *, state: str, **extra: Any) -> dict[str, Any]:
        return {
            "goal_id": goal.goal_id,
            "state": state,
            "source": goal.source,
            "target_deg": self._degrees(goal.target_rad),
            "speed_rad_s": goal.speed_rad_s,
            "endpoint_position_tolerance_mm": self._position_tolerance_mm,
            "endpoint_orientation_tolerance_deg": self._orientation_tolerance_deg,
            **extra,
        }

    def _set_status(self, goal: MotionGoal, *, state: str, **extra: Any) -> None:
        with self._condition:
            if self._latest_goal is goal:
                goal.state = state
                self._status = self._goal_status(goal, state=state, **extra)

    def _is_current(self, goal: MotionGoal) -> bool:
        with self._condition:
            return not self._shutdown and self._latest_goal is goal

    def _pause_while_current(self, goal: MotionGoal, seconds: float) -> bool:
        with self._condition:
            if self._latest_goal is not goal or self._shutdown:
                return False
            self._condition.wait(timeout=max(0.0, seconds))
            return self._latest_goal is goal and not self._shutdown

    def _complete_superseded_locked(
        self,
        goal: MotionGoal,
        *,
        replacement_goal_id: int,
    ) -> None:
        goal.state = "superseded"
        goal.result = {
            "ok": False,
            "execution_state": "superseded",
            "error": (
                f"Motion goal {goal.goal_id} was replaced by newer goal "
                f"{replacement_goal_id}."
            ),
            "data": {
                "goal_id": goal.goal_id,
                "replacement_goal_id": replacement_goal_id,
                "completion": "superseded",
            },
        }
        goal.completion_event.set()

    def _read_feedback(
        self,
        previous_position: Optional[np.ndarray],
        previous_time: Optional[float],
    ) -> tuple[np.ndarray, np.ndarray, float]:
        now = time.monotonic()
        state_reader = getattr(self._robot, "get_joint_state", None)
        if callable(state_reader):
            state = dict(state_reader())
            raw_feedback_time = state.get("feedback_monotonic_s")
            if raw_feedback_time is not None:
                feedback_age = now - float(raw_feedback_time)
                if not math.isfinite(feedback_age) or feedback_age < -0.001:
                    raise RuntimeError("Robot returned an invalid feedback timestamp")
                if feedback_age > self._feedback_stale_timeout_s:
                    raise RuntimeError(
                        "Robot joint feedback is stale by "
                        f"{feedback_age:.3f} s (limit "
                        f"{self._feedback_stale_timeout_s:.3f} s)"
                    )
            position = np.asarray(state.get("pos"), dtype=np.float64).reshape(-1)[:6]
            raw_velocity = state.get("vel")
            velocity = (
                np.asarray(raw_velocity, dtype=np.float64).reshape(-1)[:6]
                if raw_velocity is not None
                else np.empty(0, dtype=np.float64)
            )
        else:
            position = np.asarray(
                self._robot.get_joint_pos(),
                dtype=np.float64,
            ).reshape(-1)[:6]
            velocity = np.empty(0, dtype=np.float64)
        if position.size != 6 or not np.all(np.isfinite(position)):
            raise RuntimeError("Robot returned invalid six-axis joint feedback")
        if velocity.size != 6 or not np.all(np.isfinite(velocity)):
            if previous_position is None or previous_time is None or now <= previous_time:
                velocity = np.zeros(6, dtype=np.float64)
            else:
                velocity = (position - previous_position) / (now - previous_time)
        return position.copy(), velocity.copy(), now

    def _write_motion_frame(
        self,
        position: np.ndarray,
        velocity: np.ndarray,
        acceleration: np.ndarray,
        *,
        fallback_speed: float,
    ) -> None:
        with self._sdk_write_lock:
            writer = getattr(self._robot, "command_motion_frame", None)
            if callable(writer):
                writer(position, velocity, acceleration)
            else:
                state_writer = getattr(self._robot, "command_joint_state", None)
                if callable(state_writer):
                    state_writer(
                        {
                            "pos": position,
                            "vel": velocity,
                            "acc": acceleration,
                        }
                    )
                else:
                    position_writer = getattr(self._robot, "command_joint_pos", None)
                    if callable(position_writer):
                        position_writer(position)
                    else:
                        self._robot.move_joints(position, speed=fallback_speed)
            with self._planner_state_lock:
                self._last_command_position = position.copy()
                self._last_command_velocity = velocity.copy()
                self._last_command_acceleration = acceleration.copy()

    def _reset_planner_state(self) -> None:
        with self._planner_state_lock:
            self._last_command_position = None
            self._last_command_velocity = None
            self._last_command_acceleration = None

    def _initial_planner_state(
        self,
        measured_position: np.ndarray,
        measured_velocity: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        with self._planner_state_lock:
            if self._last_command_position is not None:
                return (
                    self._last_command_position.copy(),
                    self._last_command_velocity.copy(),
                    self._last_command_acceleration.copy(),
                )
        raw = self._robot_info().get("command_pos")
        if raw is None:
            command_position = measured_position.copy()
        else:
            command_position = np.asarray(raw, dtype=np.float64).reshape(-1)[:6]
            if command_position.size != 6 or not np.all(np.isfinite(command_position)):
                command_position = measured_position.copy()
        command_velocity = np.clip(
            measured_velocity,
            -self._acceleration_limit,
            self._acceleration_limit,
        )
        return (
            command_position.copy(),
            command_velocity.copy(),
            np.zeros(6, dtype=np.float64),
        )

    def _planner_step(
        self,
        position: np.ndarray,
        velocity: np.ndarray,
        acceleration: np.ndarray,
        destination: np.ndarray,
        speed_limit: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        dt = self._period_s
        error = destination - position
        braking_speed = np.sqrt(2.0 * self._acceleration_limit * np.abs(error))
        desired_velocity = np.sign(error) * np.minimum(speed_limit, braking_speed)
        moving_toward_target = velocity * error > 0.0
        conservative_stop_distance = (
            velocity**2 / (2.0 * self._acceleration_limit)
            + np.abs(velocity) * self._acceleration_limit / self._jerk_limit
            + np.abs(acceleration) * self._acceleration_limit
            / (self._jerk_limit**2)
        )
        should_brake = moving_toward_target & (
            np.abs(error) <= conservative_stop_distance
        )
        desired_velocity[should_brake] = 0.0
        desired_acceleration = np.clip(
            (desired_velocity - velocity) / dt,
            -self._acceleration_limit,
            self._acceleration_limit,
        )
        acceleration_delta = np.clip(
            desired_acceleration - acceleration,
            -self._jerk_limit * dt,
            self._jerk_limit * dt,
        )
        next_acceleration = np.clip(
            acceleration + acceleration_delta,
            -self._acceleration_limit,
            self._acceleration_limit,
        )
        next_velocity = np.clip(
            velocity + next_acceleration * dt,
            -speed_limit,
            speed_limit,
        )
        next_position = position + next_velocity * dt
        crossed = (error != 0.0) & ((destination - next_position) * error <= 0.0)
        next_position[crossed] = destination[crossed]
        next_velocity[crossed] = 0.0
        next_acceleration[crossed] = 0.0
        close = np.abs(destination - next_position) <= 1e-7
        slow = np.abs(next_velocity) <= self._jerk_limit * dt * dt
        stopped = close & slow
        next_position[stopped] = destination[stopped]
        next_velocity[stopped] = 0.0
        next_acceleration[stopped] = 0.0
        return next_position, next_velocity, next_acceleration

    def _verification(
        self,
        goal: MotionGoal,
        measured: np.ndarray,
        velocity: np.ndarray,
        measured_pose: np.ndarray,
        *,
        position_error_mm: float,
        orientation_error_deg: float,
        stable_samples: int,
        reached: bool,
        destination_commanded: bool,
    ) -> dict[str, Any]:
        return {
            "reached": reached,
            "goal_id": goal.goal_id,
            "target_deg": self._degrees(goal.target_rad),
            "measured_deg": self._degrees(measured),
            "joint_error_deg": self._degrees(np.abs(goal.target_rad - measured), digits=4),
            "target_tcp_m": [round(float(value), 6) for value in goal.target_pose[:3, 3]],
            "measured_tcp_m": [round(float(value), 6) for value in measured_pose[:3, 3]],
            "position_error_mm": round(position_error_mm, 4),
            "position_tolerance_mm": self._position_tolerance_mm,
            "orientation_error_deg": round(orientation_error_deg, 4),
            "orientation_tolerance_deg": self._orientation_tolerance_deg,
            "max_velocity_rad_s": round(float(np.max(np.abs(velocity))), 5),
            "settle_velocity_rad_s": self._settle_velocity_rad_s,
            "stable_samples": stable_samples,
            "stable_samples_required": self._stable_samples_required,
            "target_frame_commanded": destination_commanded,
            **goal.metadata,
        }

    def _complete_reached(
        self,
        goal: MotionGoal,
        verification: dict[str, Any],
    ) -> None:
        with self._condition:
            if self._latest_goal is not goal or goal.completion_event.is_set():
                return
            completion = (
                "feedback_verified" if goal.motion_performed else "already_at_target"
            )
            goal.state = "holding"
            goal.result = {
                "ok": True,
                "data": {
                    "goal_id": goal.goal_id,
                    "pos_deg": list(verification["measured_deg"]),
                    "verification": verification,
                    "motion_performed": goal.motion_performed,
                    "completion": completion,
                },
            }
            goal.completion_event.set()
            self._condition.notify_all()

    def _complete_failed(
        self,
        goal: MotionGoal,
        message: str,
        *,
        verification: Optional[dict[str, Any]] = None,
    ) -> None:
        with self._condition:
            if self._latest_goal is goal:
                self._latest_goal = None
                self._reference_target_rad = None
                self._status = self._goal_status(
                    goal,
                    state="failed",
                    error=str(message),
                    verification=dict(verification or {}),
                )
            if not goal.completion_event.is_set():
                goal.state = "failed"
                goal.result = {
                    "ok": False,
                    "execution_state": "submitted_unverified",
                    "error": str(message),
                    "data": {
                        "goal_id": goal.goal_id,
                        "completion": "failed",
                        "verification": dict(verification or {}),
                    },
                }
                goal.completion_event.set()
            self._condition.notify_all()

    def _runtime_failure(self) -> Optional[str]:
        fault = str(getattr(self._robot, "runtime_fault", "") or "").strip()
        if bool(getattr(self._robot, "is_faulted", False)) or fault:
            return f"Robot control loop faulted: {fault or 'unknown fault'}"
        if not bool(getattr(self._robot, "is_running", False)):
            return "Robot control loop is not running."
        if bool(getattr(self._robot, "is_estopped", False)):
            return "Robot is in estop."
        info = self._robot_info()
        mode = str(info.get("control_mode", ""))
        if mode and mode != "position_hold":
            return f"Position target lost position-hold mode; current mode is {mode}."
        return None

    def _maintain_goal(self, goal: MotionGoal) -> None:
        previous_measured: Optional[np.ndarray] = None
        previous_feedback_time: Optional[float] = None
        try:
            measured, measured_velocity, feedback_time = self._read_feedback(None, None)
            command_pos, command_vel, command_acc = self._initial_planner_state(
                measured,
                measured_velocity,
            )
        except Exception as exc:
            self._complete_failed(goal, f"Failed to initialize arm feedback: {exc}")
            return
        correction = np.zeros(6, dtype=np.float64)
        next_correction_time = feedback_time
        stable_samples = 0
        reached_once = False
        outside_tolerance_since: Optional[float] = None
        destination_was_commanded = False

        while self._is_current(goal):
            cycle_started = time.monotonic()
            try:
                runtime_failure = self._runtime_failure()
            except Exception as exc:
                self._complete_failed(goal, f"Failed to inspect arm runtime state: {exc}")
                return
            if runtime_failure is not None:
                self._complete_failed(goal, runtime_failure)
                return

            try:
                measured, measured_velocity, feedback_time = self._read_feedback(
                    previous_measured,
                    previous_feedback_time,
                )
                measured_pose = self._fk(measured)
            except Exception as exc:
                self._complete_failed(goal, f"Failed to read arm feedback: {exc}")
                return
            previous_measured = measured.copy()
            previous_feedback_time = feedback_time

            position_error_mm = float(
                np.linalg.norm(goal.target_pose[:3, 3] - measured_pose[:3, 3])
                * 1000.0
            )
            orientation_error_deg = _rotation_error_deg(goal.target_pose, measured_pose)
            max_velocity = float(np.max(np.abs(measured_velocity)))
            within_pose = (
                position_error_mm <= self._position_tolerance_mm
                and orientation_error_deg <= self._orientation_tolerance_deg
            )
            settled = max_velocity <= self._settle_velocity_rad_s

            limits = self._joint_limits()
            destination = goal.target_rad + correction
            if limits is not None:
                destination = np.clip(destination, limits[:, 0], limits[:, 1])
            destination_commanded = (
                float(np.max(np.abs(command_pos - destination))) <= 1e-5
                and float(np.max(np.abs(command_vel))) <= self._settle_velocity_rad_s
            )
            stable_samples = (
                stable_samples + 1
                if within_pose and settled and destination_commanded
                else 0
            )
            reached = stable_samples >= self._stable_samples_required

            verification = self._verification(
                goal,
                measured,
                measured_velocity,
                measured_pose,
                position_error_mm=position_error_mm,
                orientation_error_deg=orientation_error_deg,
                stable_samples=stable_samples,
                reached=reached,
                destination_commanded=destination_commanded,
            )
            if reached:
                if not reached_once:
                    self._complete_reached(goal, verification)
                    reached_once = True
                self._set_status(
                    goal,
                    state="holding",
                    position_error_mm=verification["position_error_mm"],
                    orientation_error_deg=verification["orientation_error_deg"],
                    max_velocity_rad_s=verification["max_velocity_rad_s"],
                    stable_samples=stable_samples,
                )
            else:
                self._set_status(
                    goal,
                    state="correcting" if reached_once else "running",
                    position_error_mm=verification["position_error_mm"],
                    orientation_error_deg=verification["orientation_error_deg"],
                    max_velocity_rad_s=verification["max_velocity_rad_s"],
                    stable_samples=stable_samples,
                )

            if (
                destination_commanded
                and feedback_time >= next_correction_time
                and not within_pose
            ):
                correction = np.clip(
                    correction
                    + self._correction_gain * (goal.target_rad - measured),
                    -self._max_correction_rad,
                    self._max_correction_rad,
                )
                next_correction_time = feedback_time + self._correction_period_s
                destination = goal.target_rad + correction
                if limits is not None:
                    destination = np.clip(destination, limits[:, 0], limits[:, 1])
                destination_commanded = (
                    float(np.max(np.abs(command_pos - destination))) <= 1e-5
                    and float(np.max(np.abs(command_vel)))
                    <= self._settle_velocity_rad_s
                )

            if within_pose:
                outside_tolerance_since = None
            elif destination_commanded:
                if not destination_was_commanded or outside_tolerance_since is None:
                    outside_tolerance_since = feedback_time
            else:
                outside_tolerance_since = None
            destination_was_commanded = destination_commanded

            if (
                destination_commanded
                and outside_tolerance_since is not None
                and self._feedback_timeout_s >= 0.0
                and feedback_time - outside_tolerance_since >= self._feedback_timeout_s
                and settled
            ):
                self._complete_failed(
                    goal,
                    (
                        "End-effector stalled outside the arrival tolerance: "
                        f"position error {position_error_mm:.3f} mm "
                        f"(limit {self._position_tolerance_mm:.3f} mm), "
                        f"orientation error {orientation_error_deg:.3f}° "
                        f"(limit {self._orientation_tolerance_deg:.3f}°)."
                    ),
                    verification=verification,
                )
                return
            if not reached_once and feedback_time - goal.submitted_at >= goal.timeout_s:
                self._complete_failed(
                    goal,
                    (
                        f"End-effector goal {goal.goal_id} timed out after "
                        f"{goal.timeout_s:.3f} s."
                    ),
                    verification=verification,
                )
                return

            # If feedback is already settled at the requested endpoint, keep
            # observing it without emitting a redundant command frame.  This
            # makes an already-satisfied goal a truly no-motion operation and
            # avoids microscopic twitches while the stability dwell completes.
            if within_pose and settled and destination_commanded:
                elapsed = time.monotonic() - cycle_started
                if not self._pause_while_current(goal, self._period_s - elapsed):
                    return
                continue

            command_pos, command_vel, command_acc = self._planner_step(
                command_pos,
                command_vel,
                command_acc,
                destination,
                goal.speed_rad_s,
            )
            if not self._is_current(goal):
                return
            try:
                self._write_motion_frame(
                    command_pos,
                    command_vel,
                    command_acc,
                    fallback_speed=goal.speed_rad_s,
                )
                goal.motion_performed = goal.motion_performed or bool(
                    np.max(np.abs(command_pos - measured)) > 1e-7
                )
            except Exception as exc:
                self._complete_failed(goal, f"Failed to send arm command frame: {exc}")
                return

            elapsed = time.monotonic() - cycle_started
            if not self._pause_while_current(goal, self._period_s - elapsed):
                return

    def _run(self) -> None:
        while True:
            with self._condition:
                while self._latest_goal is None and not self._shutdown:
                    self._condition.wait()
                if self._shutdown:
                    return
                goal = self._latest_goal
            assert goal is not None
            try:
                self._maintain_goal(goal)
            except Exception as exc:  # Defensive: never lose the sole writer thread.
                self._complete_failed(
                    goal,
                    f"Arm motion controller internal failure: {exc}",
                )
