"""Transform helpers for the ROS 2 A1Z motion stack."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from geometry_msgs.msg import Pose, PoseStamped, TransformStamped


def quaternion_xyzw_to_matrix(quaternion_xyzw: Iterable[float]) -> np.ndarray:
    x, y, z, w = [float(v) for v in quaternion_xyzw]
    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def matrix_to_quaternion_xyzw(rotation: np.ndarray) -> np.ndarray:
    m = np.asarray(rotation, dtype=np.float64)
    trace = float(np.trace(m))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    quat = np.array([x, y, z, w], dtype=np.float64)
    norm = np.linalg.norm(quat)
    if norm > 0.0:
        quat /= norm
    return quat


def rpy_rad_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
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


def xyz_rpy_deg_to_matrix(pose: Iterable[float]) -> np.ndarray:
    x, y, z, roll_deg, pitch_deg, yaw_deg = [float(v) for v in pose]
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rpy_rad_to_matrix(math.radians(roll_deg), math.radians(pitch_deg), math.radians(yaw_deg))
    matrix[:3, 3] = np.array([x, y, z], dtype=np.float64)
    return matrix


def pose_to_matrix(pose: Pose | PoseStamped) -> np.ndarray:
    pose_msg = pose.pose if isinstance(pose, PoseStamped) else pose
    transform = np.eye(4, dtype=np.float64)
    quat = np.array(
        [
            pose_msg.orientation.x,
            pose_msg.orientation.y,
            pose_msg.orientation.z,
            pose_msg.orientation.w,
        ],
        dtype=np.float64,
    )
    if np.linalg.norm(quat) < 1e-8:
        quat = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    transform[:3, :3] = quaternion_xyzw_to_matrix(quat)
    transform[:3, 3] = np.array(
        [pose_msg.position.x, pose_msg.position.y, pose_msg.position.z],
        dtype=np.float64,
    )
    return transform


def matrix_to_pose_stamped(matrix: np.ndarray, *, frame_id: str, stamp) -> PoseStamped:
    pose = PoseStamped()
    pose.header.frame_id = frame_id
    pose.header.stamp = stamp
    pose.pose.position.x = float(matrix[0, 3])
    pose.pose.position.y = float(matrix[1, 3])
    pose.pose.position.z = float(matrix[2, 3])
    quat = matrix_to_quaternion_xyzw(matrix[:3, :3])
    pose.pose.orientation.x = float(quat[0])
    pose.pose.orientation.y = float(quat[1])
    pose.pose.orientation.z = float(quat[2])
    pose.pose.orientation.w = float(quat[3])
    return pose


def matrix_to_transform_stamped(
    matrix: np.ndarray,
    *,
    parent_frame: str,
    child_frame: str,
    stamp,
) -> TransformStamped:
    msg = TransformStamped()
    msg.header.frame_id = parent_frame
    msg.header.stamp = stamp
    msg.child_frame_id = child_frame
    msg.transform.translation.x = float(matrix[0, 3])
    msg.transform.translation.y = float(matrix[1, 3])
    msg.transform.translation.z = float(matrix[2, 3])
    quat = matrix_to_quaternion_xyzw(matrix[:3, :3])
    msg.transform.rotation.x = float(quat[0])
    msg.transform.rotation.y = float(quat[1])
    msg.transform.rotation.z = float(quat[2])
    msg.transform.rotation.w = float(quat[3])
    return msg


def transform_stamped_to_matrix(transform: TransformStamped) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = quaternion_xyzw_to_matrix(
        [
            transform.transform.rotation.x,
            transform.transform.rotation.y,
            transform.transform.rotation.z,
            transform.transform.rotation.w,
        ]
    )
    matrix[:3, 3] = np.array(
        [
            transform.transform.translation.x,
            transform.transform.translation.y,
            transform.transform.translation.z,
        ],
        dtype=np.float64,
    )
    return matrix


def orientation_error_rad(a_rot: np.ndarray, b_rot: np.ndarray) -> float:
    delta = a_rot.T @ b_rot
    cos_theta = np.clip((np.trace(delta) - 1.0) * 0.5, -1.0, 1.0)
    return float(math.acos(cos_theta))
