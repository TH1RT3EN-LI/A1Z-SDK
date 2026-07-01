#!/usr/bin/env python3

"""Analyze alternative AnyGrasp frame bindings for a fixed top grasp."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from a1z_ext.grasping import (
    ANYGRASP_ACTIVE_BINDING_LABEL,
    ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL,
    ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL,
    ANYGRASP_SUPPORTED_BINDINGS,
    anygrasp_extrinsic_correction_transform,
    anygrasp_item_to_grasp_pose_with_binding_label,
)
from a1z_ext.grasping.contact_graspnet_adapter import _invert_transform, _normalize, _rigidize_transform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze AnyGrasp frame-binding alternatives.")
    parser.add_argument("--result-json", required=True, help="Path to anygrasp_result.json")
    parser.add_argument("--extrinsic-camera-to-base", required=True, help="Path to 4x4 extrinsic_camera_to_base.npy")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--grasp-rank", type=int, default=0)
    parser.add_argument("--binding-label", default=ANYGRASP_ACTIVE_BINDING_LABEL, help="Binding label used by the active execution path.")
    parser.add_argument("--camera-correction-label", default=ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL, help="Camera-frame correction used by the active execution path.")
    parser.add_argument("--extrinsic-correction-label", default=ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL, help="Extrinsic correction used by the active execution path.")
    parser.add_argument("--ee-grasp-origin-xyz-m", default="[0.04, 0.0, 0.0]")
    parser.add_argument("--ee-opening-axis-xyz", default="[0.0, 0.0, 1.0]")
    parser.add_argument("--ee-approach-axis-xyz", default="[0.0, -1.0, 0.0]")
    return parser


def _parse_json_vector(raw: str, *, expected_len: int) -> np.ndarray:
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) != expected_len:
        raise ValueError(f"expected JSON list of length {expected_len}: {raw}")
    return np.asarray([float(item) for item in value], dtype=np.float64)


def _matrix_to_list(matrix: np.ndarray) -> list[list[float]]:
    return np.asarray(matrix, dtype=np.float64).reshape(4, 4).astype(float).tolist()


def _load_top_grasp(path: str | Path, rank: int) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not payload.get("ran", False):
        raise ValueError(f"AnyGrasp result did not run successfully: {payload.get('error', '')}")
    top_grasps = payload.get("top_grasps")
    if not isinstance(top_grasps, list) or not top_grasps:
        raise ValueError(f"AnyGrasp result missing top_grasps: {path}")
    if rank < 0 or rank >= len(top_grasps):
        raise ValueError(f"grasp-rank out of range: {rank}")
    return dict(top_grasps[rank])


def _ee_to_grasp_transform(
    *,
    ee_grasp_origin_xyz_m: np.ndarray,
    ee_opening_axis_xyz: np.ndarray,
    ee_approach_axis_xyz: np.ndarray,
) -> np.ndarray:
    opening = _normalize(ee_opening_axis_xyz)
    approach = ee_approach_axis_xyz - float(np.dot(ee_approach_axis_xyz, opening)) * opening
    approach = _normalize(approach)
    binormal = _normalize(np.cross(approach, opening))
    approach = _normalize(np.cross(opening, binormal))
    transform = np.eye(4, dtype=np.float64)
    transform[:3, 0] = opening
    transform[:3, 1] = binormal
    transform[:3, 2] = approach
    transform[:3, 3] = ee_grasp_origin_xyz_m
    return transform


def _vec3(matrix: np.ndarray) -> list[float]:
    return matrix[:3, 3].astype(float).tolist()


def _axes(matrix: np.ndarray) -> dict[str, list[float]]:
    return {
        "opening_xyz": matrix[:3, 0].astype(float).tolist(),
        "height_xyz": matrix[:3, 1].astype(float).tolist(),
        "approach_xyz": matrix[:3, 2].astype(float).tolist(),
    }


def main() -> int:
    args = build_parser().parse_args()
    item = _load_top_grasp(args.result_json, int(args.grasp_rank))
    rotation_anygrasp = np.asarray(item["rotation_matrix"], dtype=np.float64).reshape(3, 3)
    translation = np.asarray(item["translation_xyz_m"], dtype=np.float64).reshape(3)
    extrinsic_camera_to_base = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError(f"extrinsic_camera_to_base must be 4x4, got {extrinsic_camera_to_base.shape}")
    extrinsic_camera_to_base = (
        np.asarray(extrinsic_camera_to_base, dtype=np.float64).reshape(4, 4)
        @ anygrasp_extrinsic_correction_transform(correction_label=str(args.extrinsic_correction_label))
    )

    ee_to_grasp = _ee_to_grasp_transform(
        ee_grasp_origin_xyz_m=_parse_json_vector(args.ee_grasp_origin_xyz_m, expected_len=3),
        ee_opening_axis_xyz=_parse_json_vector(args.ee_opening_axis_xyz, expected_len=3),
        ee_approach_axis_xyz=_parse_json_vector(args.ee_approach_axis_xyz, expected_len=3),
    )
    grasp_to_ee = _invert_transform(ee_to_grasp)

    rows: list[dict[str, Any]] = []
    columns = [rotation_anygrasp[:, idx].copy() for idx in range(3)]
    for label, (opening_idx, height_idx, approach_idx, signs) in ANYGRASP_SUPPORTED_BINDINGS.items():
        grasp_cam = anygrasp_item_to_grasp_pose_with_binding_label(
            item,
            binding_label=label,
            camera_correction_label=str(args.camera_correction_label),
        )
        grasp_base = _rigidize_transform(extrinsic_camera_to_base @ grasp_cam)
        tool_grasp = _rigidize_transform(grasp_base @ grasp_to_ee)
        rows.append(
            {
                "binding_label": label,
                "grasp_pose_cam_xyz": _vec3(grasp_cam),
                "grasp_pose_base_xyz": _vec3(grasp_base),
                "tool_grasp_pose_xyz": _vec3(tool_grasp),
                "grasp_pose_cam_matrix": _matrix_to_list(grasp_cam),
                "grasp_pose_base_matrix": _matrix_to_list(grasp_base),
                "tool_grasp_pose_matrix": _matrix_to_list(tool_grasp),
                "grasp_cam_axes": _axes(grasp_cam),
                "grasp_base_axes": _axes(grasp_base),
                "tool_axes": {
                    "x_xyz": tool_grasp[:3, 0].astype(float).tolist(),
                    "y_xyz": tool_grasp[:3, 1].astype(float).tolist(),
                    "z_xyz": tool_grasp[:3, 2].astype(float).tolist(),
                },
            }
        )

    payload = {
        "result_json": str(Path(args.result_json).resolve()),
        "extrinsic_camera_to_base": str(Path(args.extrinsic_camera_to_base).resolve()),
        "grasp_rank": int(args.grasp_rank),
        "active_binding_label": str(args.binding_label),
        "active_camera_correction_label": str(args.camera_correction_label),
        "active_extrinsic_correction_label": str(args.extrinsic_correction_label),
        "raw_rotation_matrix": rotation_anygrasp.astype(float).tolist(),
        "raw_translation_xyz_m": translation.astype(float).tolist(),
        "ee_to_grasp_transform": _matrix_to_list(ee_to_grasp),
        "bindings": rows,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "binding_count": len(rows)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
