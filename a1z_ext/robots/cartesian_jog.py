"""Frame-explicit Cartesian increments for A1Z end-effector jogging."""

from __future__ import annotations

import math

import numpy as np


_AXIS_VECTORS = {
    "x": np.array([1.0, 0.0, 0.0], dtype=np.float64),
    "y": np.array([0.0, 1.0, 0.0], dtype=np.float64),
    "z": np.array([0.0, 0.0, 1.0], dtype=np.float64),
}


def rotation_matrix(axis: str, angle_rad: float) -> np.ndarray:
    """Return a right-handed active rotation around one Cartesian axis."""
    if axis not in _AXIS_VECTORS:
        raise ValueError(f"Unsupported Cartesian axis: {axis}")
    c = math.cos(float(angle_rad))
    s = math.sin(float(angle_rad))
    if axis == "x":
        return np.array(
            [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]],
            dtype=np.float64,
        )
    if axis == "y":
        return np.array(
            [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]],
            dtype=np.float64,
        )
    return np.array(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )


def apply_translation(
    transform: np.ndarray,
    *,
    axis: str,
    delta_m: float,
    frame: str,
) -> np.ndarray:
    """Translate a base-to-tool pose in either base or current tool axes."""
    if axis not in _AXIS_VECTORS:
        raise ValueError(f"Unsupported Cartesian axis: {axis}")
    if frame not in {"base", "tool"}:
        raise ValueError(f"Unsupported Cartesian frame: {frame}")
    current = np.asarray(transform, dtype=np.float64)
    if current.shape != (4, 4) or not np.all(np.isfinite(current)):
        raise ValueError("transform must be a finite 4x4 homogeneous matrix")
    direction_base = _AXIS_VECTORS[axis]
    if frame == "tool":
        direction_base = current[:3, :3] @ direction_base
    target = current.copy()
    target[:3, 3] += direction_base * float(delta_m)
    return target


def apply_rotation(
    transform: np.ndarray,
    *,
    axis: str,
    delta_deg: float,
    frame: str,
) -> np.ndarray:
    """Rotate a base-to-tool pose around a base or current tool axis."""
    if frame not in {"base", "tool"}:
        raise ValueError(f"Unsupported Cartesian frame: {frame}")
    current = np.asarray(transform, dtype=np.float64)
    if current.shape != (4, 4) or not np.all(np.isfinite(current)):
        raise ValueError("transform must be a finite 4x4 homogeneous matrix")
    delta_rotation = rotation_matrix(axis, math.radians(float(delta_deg)))
    target = current.copy()
    if frame == "tool":
        target[:3, :3] = current[:3, :3] @ delta_rotation
    else:
        target[:3, :3] = delta_rotation @ current[:3, :3]
    return target


def compose_command_space_joint_target(
    measured_q: np.ndarray,
    solved_q: np.ndarray,
    command_q: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply a measured-space IK increment to the SDK command trajectory.

    IK is solved around physical feedback, while the SDK trajectory generator
    starts from its current command position.  Reusing ``solved_q`` as an
    absolute command would therefore rewrite any command/feedback tracking
    offset.  Preserve that offset by transferring only the solved increment.
    """

    measured = np.asarray(measured_q, dtype=np.float64).reshape(-1)
    solved = np.asarray(solved_q, dtype=np.float64).reshape(-1)
    commanded = np.asarray(command_q, dtype=np.float64).reshape(-1)
    if measured.size != 6 or solved.size != 6 or commanded.size != 6:
        raise ValueError(
            "measured_q, solved_q and command_q must each contain 6 joints"
        )
    if not (
        np.all(np.isfinite(measured))
        and np.all(np.isfinite(solved))
        and np.all(np.isfinite(commanded))
    ):
        raise ValueError("joint vectors must contain only finite values")
    joint_delta = solved - measured
    return commanded + joint_delta, joint_delta


def pose_error(target: np.ndarray, actual: np.ndarray) -> tuple[float, float]:
    """Return translation error in metres and orientation error in degrees."""
    expected = np.asarray(target, dtype=np.float64)
    measured = np.asarray(actual, dtype=np.float64)
    if expected.shape != (4, 4) or measured.shape != (4, 4):
        raise ValueError("target and actual must be 4x4 homogeneous matrices")
    translation_error_m = float(np.linalg.norm(expected[:3, 3] - measured[:3, 3]))
    relative_rotation = expected[:3, :3].T @ measured[:3, :3]
    cosine = float(np.clip((np.trace(relative_rotation) - 1.0) * 0.5, -1.0, 1.0))
    orientation_error_deg = math.degrees(math.acos(cosine))
    return translation_error_m, orientation_error_deg
