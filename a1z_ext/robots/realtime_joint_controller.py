"""Real-time joint reference generation and torque shaping for SocketCAN.

The classes in this module contain no CAN access.  They are deliberately
small state machines that are advanced by the hardware owner's control thread;
request threads may only replace the pending final target.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np


def require_ruckig_dependency() -> tuple[Any, Any, Any, Any]:
    try:
        from ruckig import InputParameter, OutputParameter, Result, Ruckig
    except ImportError as exc:
        raise RuntimeError(
            "SocketCAN joint control requires ruckig==0.19.4. Rebuild the "
            "A1Z ROS container or install the hardware extra before starting "
            "the control service."
        ) from exc
    return InputParameter, OutputParameter, Result, Ruckig


def _finite_vector(values: Sequence[float], size: int, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64).reshape(-1)
    if vector.size != size:
        raise ValueError(f"{name} must contain exactly {size} values")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector.copy()


def _positive_vector(
    values: float | Sequence[float],
    size: int,
    name: str,
) -> np.ndarray:
    raw = np.asarray(values, dtype=np.float64)
    if raw.ndim == 0:
        vector = np.full(size, float(raw), dtype=np.float64)
    else:
        vector = raw.reshape(-1)
        if vector.size != size:
            raise ValueError(f"{name} must be a scalar or contain {size} values")
    if not np.all(np.isfinite(vector)) or np.any(vector <= 0.0):
        raise ValueError(f"{name} must contain only positive finite values")
    return vector.copy()


@dataclass(frozen=True)
class JointReference:
    position: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray
    target: np.ndarray
    generation: int
    finished: bool


class RuckigJointReferenceGenerator:
    """Jerk-constrained reference generator owned by one real-time loop.

    ``set_target`` only publishes immutable pending data under a lock.  The
    Ruckig input/output objects are touched exclusively from ``advance`` so the
    250 Hz control loop remains the sole owner of trajectory state.
    """

    def __init__(self, dofs: int, control_period_s: float) -> None:
        self._dofs = int(dofs)
        self._period_s = float(control_period_s)
        if self._dofs <= 0:
            raise ValueError("dofs must be positive")
        if not math.isfinite(self._period_s) or self._period_s <= 0.0:
            raise ValueError("control_period_s must be a positive finite number")
        InputParameter, OutputParameter, Result, Ruckig = (
            require_ruckig_dependency()
        )

        self._result_working = Result.Working
        self._result_finished = Result.Finished
        self._otg = Ruckig(self._dofs, self._period_s)
        self._input = InputParameter(self._dofs)
        self._output = OutputParameter(self._dofs)
        self._target_lock = threading.Lock()
        self._pending: Optional[dict[str, Any]] = None
        self._generation = 0
        self._active_generation = 0
        self._initialized = False
        self._finished = True
        self._target = np.zeros(self._dofs, dtype=np.float64)

    def reset(
        self,
        position: Sequence[float],
        velocity: Optional[Sequence[float]] = None,
    ) -> None:
        pos = _finite_vector(position, self._dofs, "position")
        vel = (
            np.zeros(self._dofs, dtype=np.float64)
            if velocity is None
            else _finite_vector(velocity, self._dofs, "velocity")
        )
        zeros = np.zeros(self._dofs, dtype=np.float64)
        self._input.current_position = pos.tolist()
        self._input.current_velocity = vel.tolist()
        self._input.current_acceleration = zeros.tolist()
        self._input.target_position = pos.tolist()
        self._input.target_velocity = zeros.tolist()
        self._input.target_acceleration = zeros.tolist()
        # Ruckig validates these on update.  Safe non-zero placeholders keep a
        # reset state complete before the first real target is consumed.
        self._input.max_velocity = np.ones(self._dofs).tolist()
        self._input.max_acceleration = np.ones(self._dofs).tolist()
        self._input.max_jerk = np.ones(self._dofs).tolist()
        self._target = pos
        self._initialized = True
        self._finished = True
        with self._target_lock:
            self._pending = None

    def set_target(
        self,
        position: Sequence[float],
        *,
        max_velocity: float | Sequence[float],
        max_acceleration: float | Sequence[float],
        max_jerk: float | Sequence[float],
    ) -> int:
        target = _finite_vector(position, self._dofs, "target position")
        velocity = _positive_vector(max_velocity, self._dofs, "max_velocity")
        acceleration = _positive_vector(
            max_acceleration,
            self._dofs,
            "max_acceleration",
        )
        jerk = _positive_vector(max_jerk, self._dofs, "max_jerk")
        with self._target_lock:
            self._generation += 1
            generation = self._generation
            self._pending = {
                "generation": generation,
                "target": target,
                "max_velocity": velocity,
                "max_acceleration": acceleration,
                "max_jerk": jerk,
            }
        return generation

    def cancel(self) -> None:
        """Stop future advancement at the most recently generated reference."""

        if not self._initialized:
            return
        current = np.asarray(self._input.current_position, dtype=np.float64)
        self.reset(current)

    def _consume_pending(self) -> None:
        with self._target_lock:
            pending = self._pending
            self._pending = None
        if pending is None:
            return
        self._target = pending["target"].copy()
        self._active_generation = int(pending["generation"])
        self._input.target_position = self._target.tolist()
        self._input.target_velocity = np.zeros(self._dofs).tolist()
        self._input.target_acceleration = np.zeros(self._dofs).tolist()
        self._input.max_velocity = pending["max_velocity"].tolist()
        self._input.max_acceleration = pending["max_acceleration"].tolist()
        self._input.max_jerk = pending["max_jerk"].tolist()
        self._finished = False

    def advance(
        self,
        measured_position: Sequence[float],
        measured_velocity: Sequence[float],
    ) -> JointReference:
        measured_pos = _finite_vector(
            measured_position,
            self._dofs,
            "measured_position",
        )
        measured_vel = _finite_vector(
            measured_velocity,
            self._dofs,
            "measured_velocity",
        )
        if not self._initialized:
            self.reset(measured_pos, measured_vel)
        self._consume_pending()

        if not self._finished:
            result = self._otg.update(self._input, self._output)
            if result not in (self._result_working, self._result_finished):
                raise RuntimeError(f"Ruckig trajectory update failed: {result}")
            self._output.pass_to_input(self._input)
            self._finished = result == self._result_finished

        return JointReference(
            position=np.asarray(self._input.current_position, dtype=np.float64).copy(),
            velocity=np.asarray(self._input.current_velocity, dtype=np.float64).copy(),
            acceleration=np.asarray(
                self._input.current_acceleration,
                dtype=np.float64,
            ).copy(),
            target=self._target.copy(),
            generation=self._active_generation,
            finished=self._finished,
        )


class JointTorqueShaper:
    """Bounded residual integral and total torque rate limiter.

    The integral is expressed as an equivalent position correction and then
    multiplied by Kp.  This makes its tuning interpretable against the existing
    MIT impedance gains while applying the correction as a smooth torque bias,
    rather than moving the position reference in visible steps.
    """

    def __init__(
        self,
        dofs: int,
        control_period_s: float,
        torque_slew_rate_nm_s: float | Sequence[float],
    ) -> None:
        self._dofs = int(dofs)
        self._period_s = float(control_period_s)
        self._torque_slew_rate = _positive_vector(
            torque_slew_rate_nm_s,
            self._dofs,
            "torque_slew_rate_nm_s",
        )
        self._equivalent_correction = np.zeros(self._dofs, dtype=np.float64)
        self._last_torque: Optional[np.ndarray] = None

    @property
    def equivalent_correction(self) -> np.ndarray:
        return self._equivalent_correction.copy()

    def reset(self, *, preserve_last_torque: bool = True) -> None:
        self._equivalent_correction.fill(0.0)
        if not preserve_last_torque:
            self._last_torque = None

    def update_integral(
        self,
        *,
        position_error: Sequence[float],
        kp: Sequence[float],
        base_torque: Sequence[float],
        torque_limit: Sequence[float],
        enabled: bool,
        integral_gain_s_inv: float,
        correction_rate_limit_rad_s: float,
        max_correction_rad: float,
    ) -> np.ndarray:
        error = _finite_vector(position_error, self._dofs, "position_error")
        gains = _finite_vector(kp, self._dofs, "kp")
        base = _finite_vector(base_torque, self._dofs, "base_torque")
        limits = _positive_vector(torque_limit, self._dofs, "torque_limit")
        integral_gain = float(integral_gain_s_inv)
        rate_limit = float(correction_rate_limit_rad_s)
        correction_limit = float(max_correction_rad)
        if not all(
            math.isfinite(value) and value > 0.0
            for value in (integral_gain, rate_limit, correction_limit)
        ):
            raise ValueError("Residual integral limits must be positive and finite")

        desired_rate = (
            np.clip(
                integral_gain * error,
                -rate_limit,
                rate_limit,
            )
            if enabled
            else -np.clip(
                self._equivalent_correction / self._period_s,
                -rate_limit,
                rate_limit,
            )
        )
        candidate = np.clip(
            self._equivalent_correction + desired_rate * self._period_s,
            -correction_limit,
            correction_limit,
        )
        candidate_bias = gains * candidate
        candidate_total = base + candidate_bias
        pushes_positive_saturation = (candidate_total > limits) & (desired_rate > 0.0)
        pushes_negative_saturation = (candidate_total < -limits) & (desired_rate < 0.0)
        blocked = pushes_positive_saturation | pushes_negative_saturation
        candidate[blocked] = self._equivalent_correction[blocked]
        self._equivalent_correction = candidate
        return gains * candidate

    def shape_total(
        self,
        torque: Sequence[float],
        torque_limit: Sequence[float],
    ) -> np.ndarray:
        requested = _finite_vector(torque, self._dofs, "torque")
        limits = _positive_vector(torque_limit, self._dofs, "torque_limit")
        clipped = np.clip(requested, -limits, limits)
        if self._last_torque is None:
            self._last_torque = clipped.copy()
            return clipped
        maximum_delta = self._torque_slew_rate * self._period_s
        shaped = self._last_torque + np.clip(
            clipped - self._last_torque,
            -maximum_delta,
            maximum_delta,
        )
        self._last_torque = shaped
        return shaped.copy()
