"""USD pose helpers for the Isaac-hosted D405 camera."""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

from .geometry import (
    d405_install_rotation_matrix,
    d405_rectified_to_optical_transform,
    xyz_rpy_deg_to_matrix,
)
from .settings import D405ComputeSettings

_ROBOT_BASE_SEMANTIC_PRIM_CANDIDATES = (
    "/World/A1Z_G1Z/Geometry",
    "/World/A1Z_G1Z",
)

_ROBOT_BASE_LINK_BODY_PRIM_CANDIDATES = (
    "/World/A1Z_G1Z/Geometry/base_link",
    "/World/A1Z_G1Z/base_link",
    "/World/base_link",
)

# UsdGeom.Camera looks along local -Z with +Y up, while RGB-D arrays and ROS
# optical frames use +Z forward with +Y down. The ColorOpticalFrame parent
# describes the mechanical optical-frame pose, but the Camera child still has
# USD camera-axis semantics; pixels therefore require this final axis mapping.
_USD_CAMERA_FROM_ROS_OPTICAL = np.diag([1.0, -1.0, -1.0, 1.0]).astype(np.float64)


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _semantic_kinematics():
    from a1z.robots.kinematics import Kinematics
    from a1z_ext.config import get_default_control_urdf_path

    tool_link_frame = str(os.environ.get("A1Z_TOOL_LINK_FRAME", "grasp_tcp") or "grasp_tcp").strip()
    return Kinematics(get_default_control_urdf_path(), end_effector_frame=tool_link_frame)


def _semantic_tool_link_frame() -> str:
    return str(os.environ.get("A1Z_TOOL_LINK_FRAME", "grasp_tcp") or "grasp_tcp").strip()


def _semantic_tool_frame_aliases() -> tuple[str, ...]:
    aliases = {
        _semantic_tool_link_frame(),
        str(os.environ.get("A1Z_TOOL_FRAME", _semantic_tool_link_frame()) or _semantic_tool_link_frame()).strip(),
        "grasp_tcp",
    }
    return tuple(sorted(alias for alias in aliases if alias))


def _gf_matrix_to_np(matrix) -> np.ndarray:
    # USD/Gf matrices use row-vector semantics; the perception stack uses the
    # conventional column-vector homogeneous transform layout.
    return np.array([[float(matrix[row][col]) for col in range(4)] for row in range(4)], dtype=np.float64).T


def _rigidize_transform(transform: np.ndarray) -> np.ndarray:
    rigid = np.asarray(transform, dtype=np.float64).copy()
    rotation_scale = rigid[:3, :3]
    u, _, vh = np.linalg.svd(rotation_scale)
    rotation = u @ vh
    if np.linalg.det(rotation) < 0.0:
        u[:, -1] *= -1.0
        rotation = u @ vh
    rigid[:3, :3] = rotation
    rigid[3, :] = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return rigid


def _world_transform(stage, prim_path: str) -> np.ndarray:
    from pxr import Usd, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"Invalid USD prim path: {prim_path}")
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    return _rigidize_transform(_gf_matrix_to_np(cache.GetLocalToWorldTransform(prim)))


def _find_descendant_prim_path(stage, *, root_path: str, prim_name: str) -> str | None:
    from pxr import Usd

    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        return None
    for prim in Usd.PrimRange(root):
        if prim.GetName() == prim_name:
            return prim.GetPath().pathString
    return None


def _resolve_target_world_transform(stage, *, target_frame_id: str, target_prim_path: str | None) -> np.ndarray:
    if target_prim_path:
        return _world_transform(stage, target_prim_path)

    normalized = target_frame_id.strip()
    if normalized in {"", "world", "world_frame", "/World"}:
        return np.eye(4, dtype=np.float64)

    if normalized.startswith("/"):
        return _world_transform(stage, normalized)

    if normalized in {"robot_base_frame", "base_link"}:
        for candidate in _ROBOT_BASE_LINK_BODY_PRIM_CANDIDATES:
            if stage.GetPrimAtPath(candidate).IsValid():
                return _world_transform(stage, candidate)
        for root_path in ("/World/A1Z_G1Z/Geometry", "/World/A1Z_G1Z", "/World"):
            found = _find_descendant_prim_path(stage, root_path=root_path, prim_name="base_link")
            if found:
                return _world_transform(stage, found)
        articulation_root = str(os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", "") or "").strip()
        if articulation_root and stage.GetPrimAtPath(articulation_root).IsValid():
            return _world_transform(stage, articulation_root)
        for candidate in _ROBOT_BASE_SEMANTIC_PRIM_CANDIDATES:
            if stage.GetPrimAtPath(candidate).IsValid():
                return _world_transform(stage, candidate)

    for root_path in ("/World/A1Z_G1Z/Geometry", "/World/A1Z_G1Z", "/World"):
        found = _find_descendant_prim_path(stage, root_path=root_path, prim_name=normalized)
        if found:
            return _world_transform(stage, found)

    raise RuntimeError(f"Could not resolve target frame '{target_frame_id}' to a USD prim")


def _resolve_semantic_target_from_fk(
    stage,
    *,
    camera_prim_path: str,
    target_frame_id: str,
    joint_pos_rad: np.ndarray | None,
) -> np.ndarray | None:
    if joint_pos_rad is None:
        return None

    normalized = target_frame_id.strip()
    tool_aliases = set(_semantic_tool_frame_aliases())
    semantic_frames = {
        "base_link",
        "robot_base_frame",
        "d405_link",
        "d405_rectified_link",
        "arm_link6",
        *_semantic_tool_frame_aliases(),
    }
    if normalized not in semantic_frames:
        return None

    q = np.asarray(joint_pos_rad, dtype=np.float64).reshape(-1)
    if q.shape[0] < 6:
        raise ValueError(f"joint_pos_rad must contain at least 6 arm joints, got {q.shape[0]}")
    q = q[:6]
    d405_compute = D405ComputeSettings.from_env()
    kin = _semantic_kinematics()
    t_zero_tool = np.asarray(
        kin.fk(np.zeros(6, dtype=np.float64), frame_name=_semantic_tool_link_frame()),
        dtype=np.float64,
    ).reshape(4, 4)
    t_tool_d405 = np.asarray(
        kin.fk(np.zeros(6, dtype=np.float64), frame_name="d405_link"),
        dtype=np.float64,
    ).reshape(4, 4)
    t_tool_d405 = np.linalg.inv(t_zero_tool) @ t_tool_d405
    t_tool_d405[:3, :3] = t_tool_d405[:3, :3] @ d405_install_rotation_matrix(d405_compute.install_rpy_deg)
    t_d405_rectified = xyz_rpy_deg_to_matrix((0.0, 0.0, 0.0), d405_compute.rectify_rpy_deg)
    t_d405_camera = d405_rectified_to_optical_transform(
        offset_xyz_m=d405_compute.rectified_to_optical_offset_xyz_m
    )
    t_tool_camera = t_tool_d405 @ t_d405_rectified @ t_d405_camera

    t_base_tool = np.asarray(kin.fk(q, frame_name=_semantic_tool_link_frame()), dtype=np.float64).reshape(4, 4)
    t_base_camera = t_base_tool @ t_tool_camera

    if normalized in {"base_link", "robot_base_frame"}:
        return t_base_camera
    if normalized in tool_aliases:
        return t_tool_camera

    t_base_target = np.asarray(kin.fk(q, frame_name=normalized), dtype=np.float64).reshape(4, 4)
    return np.linalg.inv(t_base_target) @ t_base_camera


def camera_to_target_matrix_from_usd(
    *,
    camera_prim_path: str,
    target_frame_id: str,
    target_prim_path: str | None = None,
    joint_pos_rad: np.ndarray | None = None,
) -> np.ndarray:
    """Return a column-vector transform from ROS optical camera frame to target frame."""

    import omni.usd

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No active USD stage")

    normalized_target = str(target_frame_id or "").strip()

    # For the robot base, the live imported stage already carries the authoritative
    # D405 chain. Bypass semantic FK here so capture/extrinsic generation follows
    # the current USD geometry directly and avoids runtime stalls in FK setup.
    if normalized_target in {"base_link", "robot_base_frame"} and target_prim_path is None:
        t_world_camera = _world_transform(stage, camera_prim_path) @ _USD_CAMERA_FROM_ROS_OPTICAL
        t_world_target = _resolve_target_world_transform(
            stage,
            target_frame_id=normalized_target,
            target_prim_path=None,
        )
        return np.linalg.inv(t_world_target) @ t_world_camera

    semantic_transform = _resolve_semantic_target_from_fk(
        stage,
        camera_prim_path=camera_prim_path,
        target_frame_id=normalized_target,
        joint_pos_rad=joint_pos_rad,
    )
    if semantic_transform is not None:
        return semantic_transform

    t_world_camera = _world_transform(stage, camera_prim_path) @ _USD_CAMERA_FROM_ROS_OPTICAL

    t_world_target = _resolve_target_world_transform(
        stage,
        target_frame_id=normalized_target,
        target_prim_path=target_prim_path,
    )
    return np.linalg.inv(t_world_target) @ t_world_camera
