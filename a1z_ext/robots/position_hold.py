"""Numerically safe helpers for torque-assisted joint position holding."""

from __future__ import annotations

import numpy as np


def bounded_position_hold_feedforward(
    gravity_torque_nm: np.ndarray,
    command_torque_nm: np.ndarray,
    limit_nm: np.ndarray,
) -> np.ndarray:
    """Combine gravity and caller feedforward without exceeding rated limits."""

    gravity = np.asarray(gravity_torque_nm, dtype=np.float64).reshape(-1)
    command = np.asarray(command_torque_nm, dtype=np.float64).reshape(-1)
    limit = np.asarray(limit_nm, dtype=np.float64).reshape(-1)
    if gravity.shape != command.shape or gravity.shape != limit.shape:
        raise ValueError(
            "position-hold feedforward arrays must have identical shapes: "
            f"gravity={gravity.shape} command={command.shape} limit={limit.shape}"
        )
    if not np.all(np.isfinite(gravity)) or not np.all(np.isfinite(command)):
        raise ValueError("position-hold feedforward torques must be finite")
    if not np.all(np.isfinite(limit)) or np.any(limit <= 0.0):
        raise ValueError("position-hold feedforward limits must be finite and positive")
    return np.clip(gravity + command, -limit, limit)
