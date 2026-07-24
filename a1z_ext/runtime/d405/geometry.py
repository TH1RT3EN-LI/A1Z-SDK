from __future__ import annotations

import math

import numpy as np

from .settings import D405ComputeSettings


def rpy_deg_to_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cr = math.cos(roll)
    sr = math.sin(roll)
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=np.float64,
    )


def xyz_rpy_deg_to_matrix(
    xyz: tuple[float, float, float] | list[float],
    rpy_deg: tuple[float, float, float] | list[float],
) -> np.ndarray:
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = rpy_deg_to_matrix(float(rpy_deg[0]), float(rpy_deg[1]), float(rpy_deg[2]))
    out[:3, 3] = np.asarray(xyz, dtype=np.float64)
    return out


def d405_install_rotation_matrix(rpy_deg: tuple[float, float, float] | list[float] | None = None) -> np.ndarray:
    # User-confirmed semantics:
    # D405 z+ is counterclockwise from link6 z+ around Y, but the concrete
    # compute-side installation angles must come from the dedicated compute entry.
    if rpy_deg is None:
        rpy_deg = D405ComputeSettings.from_env().install_rpy_deg
    return rpy_deg_to_matrix(float(rpy_deg[0]), float(rpy_deg[1]), float(rpy_deg[2]))


def d405_rectified_to_optical_axis_rotation_matrix() -> np.ndarray:
    # User-confirmed axis convention for the compute chain:
    # x_cof = -y_rectified
    # y_cof = -z_rectified
    # z_cof = +x_rectified
    # This is the fixed axis remap only. Any mechanical install rotation is
    # handled separately by the compute install/rectify entries.
    return np.array(
        [
            [0.0, 0.0, 1.0],
            [-1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
        ],
        dtype=np.float64,
    )


def d405_rectified_to_optical_transform(
    *,
    offset_xyz_m: tuple[float, float, float] | list[float],
) -> np.ndarray:
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = d405_rectified_to_optical_axis_rotation_matrix()
    out[:3, 3] = np.asarray(offset_xyz_m, dtype=np.float64)
    return out
