"""Shared AnyGrasp frame-convention helpers."""

from __future__ import annotations

from typing import Any

import numpy as np

from .contact_graspnet_adapter import _rigidize_transform


ANYGRASP_ACTIVE_BINDING_LABEL = "opening=c1,height=c2,approach=c0"
ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL = "identity"
ANYGRASP_RAW_FRAME_CONVENTION = {
    "column_0": "approach_depth_axis",
    "column_1": "gripper_opening_axis",
    "column_2": "gripper_height_axis",
}
ANYGRASP_PLANNER_FRAME_CONVENTION = {
    "column_0": "gripper_opening_axis",
    "column_1": "gripper_height_axis",
    "column_2": "approach_depth_axis",
}
ANYGRASP_SUPPORTED_BINDINGS = {
    "opening=c1,height=mc2,approach=c0": (1, 2, 0, (1.0, -1.0, 1.0)),
    "opening=mc1,height=mc2,approach=c0": (1, 2, 0, (-1.0, -1.0, 1.0)),
    "opening=c1,height=c2,approach=c0": (1, 2, 0, (1.0, 1.0, 1.0)),
    "opening=mc1,height=c2,approach=c0": (1, 2, 0, (-1.0, 1.0, 1.0)),
    "opening=c1,height=c2,approach=mc0": (1, 2, 0, (1.0, 1.0, -1.0)),
    "opening=c2,height=mc1,approach=c0": (2, 1, 0, (1.0, -1.0, 1.0)),
    "opening=mc2,height=c1,approach=c0": (2, 1, 0, (-1.0, 1.0, 1.0)),
}
ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL = "identity"

_AXES = {
    "+x": np.array([1.0, 0.0, 0.0], dtype=np.float64),
    "-x": np.array([-1.0, 0.0, 0.0], dtype=np.float64),
    "+y": np.array([0.0, 1.0, 0.0], dtype=np.float64),
    "-y": np.array([0.0, -1.0, 0.0], dtype=np.float64),
    "+z": np.array([0.0, 0.0, 1.0], dtype=np.float64),
    "-z": np.array([0.0, 0.0, -1.0], dtype=np.float64),
}


def _build_supported_camera_corrections() -> dict[str, np.ndarray]:
    rows: dict[str, np.ndarray] = {"identity": np.eye(3, dtype=np.float64)}
    labels = list(_AXES.keys())
    for x_label in labels:
        x_axis = _AXES[x_label]
        for y_label in labels:
            y_axis = _AXES[y_label]
            if abs(float(np.dot(x_axis, y_axis))) > 1e-9:
                continue
            z_axis = np.cross(x_axis, y_axis)
            for z_label, axis in _AXES.items():
                if np.allclose(z_axis, axis):
                    label = f"x={x_label},y={y_label},z={z_label}"
                    rows[label] = np.column_stack([x_axis, y_axis, axis])
                    break
    return rows


ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS = _build_supported_camera_corrections()


def anygrasp_rotation_to_planner_rotation(rotation_anygrasp: np.ndarray) -> np.ndarray:
    rotation_anygrasp = np.asarray(rotation_anygrasp, dtype=np.float64).reshape(3, 3)
    approach = rotation_anygrasp[:, 0]
    opening = rotation_anygrasp[:, 1]
    height = rotation_anygrasp[:, 2]
    return np.column_stack([opening, height, approach])


def anygrasp_rotation_to_planner_rotation_with_binding_label(
    rotation_anygrasp: np.ndarray,
    *,
    binding_label: str = ANYGRASP_ACTIVE_BINDING_LABEL,
) -> np.ndarray:
    rotation_anygrasp = np.asarray(rotation_anygrasp, dtype=np.float64).reshape(3, 3)
    if binding_label not in ANYGRASP_SUPPORTED_BINDINGS:
        supported = ", ".join(sorted(ANYGRASP_SUPPORTED_BINDINGS))
        raise ValueError(f"unsupported AnyGrasp binding_label {binding_label!r}; supported: {supported}")
    opening_idx, height_idx, approach_idx, signs = ANYGRASP_SUPPORTED_BINDINGS[binding_label]
    columns = [rotation_anygrasp[:, idx].copy() for idx in range(3)]
    opening = columns[opening_idx] * float(signs[0])
    height = columns[height_idx] * float(signs[1])
    approach = columns[approach_idx] * float(signs[2])
    planner_rotation = np.column_stack([opening, height, approach])
    det = float(np.linalg.det(planner_rotation))
    if det <= 0.0:
        raise ValueError(
            f"binding_label {binding_label!r} produces a non-right-handed planner rotation (det={det:.6f})"
        )
    return planner_rotation


def anygrasp_camera_correction_transform(
    *,
    correction_label: str = ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL,
) -> np.ndarray:
    if correction_label not in ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS:
        supported = ", ".join(sorted(ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS))
        raise ValueError(f"unsupported AnyGrasp camera correction {correction_label!r}; supported: {supported}")
    correction = np.eye(4, dtype=np.float64)
    correction[:3, :3] = ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS[correction_label]
    return correction


def anygrasp_extrinsic_correction_transform(
    *,
    correction_label: str = ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL,
) -> np.ndarray:
    if correction_label not in ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS:
        supported = ", ".join(sorted(ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS))
        raise ValueError(f"unsupported AnyGrasp extrinsic correction {correction_label!r}; supported: {supported}")
    correction = np.eye(4, dtype=np.float64)
    correction[:3, :3] = ANYGRASP_SUPPORTED_CAMERA_CORRECTIONS[correction_label]
    return correction


def anygrasp_item_to_grasp_pose(item: dict[str, Any]) -> np.ndarray:
    translation = np.asarray(item["translation_xyz_m"], dtype=np.float64).reshape(3)
    rotation = anygrasp_rotation_to_planner_rotation(item["rotation_matrix"])
    grasp = np.eye(4, dtype=np.float64)
    grasp[:3, :3] = rotation
    grasp[:3, 3] = translation
    return _rigidize_transform(grasp)


def anygrasp_item_to_grasp_pose_with_binding_label(
    item: dict[str, Any],
    *,
    binding_label: str = ANYGRASP_ACTIVE_BINDING_LABEL,
    camera_correction_label: str = ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL,
) -> np.ndarray:
    translation = np.asarray(item["translation_xyz_m"], dtype=np.float64).reshape(3)
    rotation = anygrasp_rotation_to_planner_rotation_with_binding_label(
        item["rotation_matrix"],
        binding_label=binding_label,
    )
    grasp = np.eye(4, dtype=np.float64)
    grasp[:3, :3] = rotation
    grasp[:3, 3] = translation
    correction = anygrasp_camera_correction_transform(correction_label=camera_correction_label)
    return _rigidize_transform(correction @ grasp)
