#!/usr/bin/env python3

"""Summarize AnyGrasp alignment diagnostics from pose-chain and binding analyses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize AnyGrasp alignment diagnostics.")
    parser.add_argument("--pose-chain", required=True, help="Path to anygrasp_pose_chain_summary.json")
    parser.add_argument("--frame-binding-analysis", required=True, help="Path to anygrasp_frame_binding_analysis.json")
    parser.add_argument("--best-direct-result", required=True, help="Path to anygrasp_best_direct_result.json")
    parser.add_argument("--output", required=True, help="Output JSON path")
    return parser


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _vec3(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).reshape(3)


def _tool_xyz_from_matrix(matrix: Any) -> np.ndarray:
    arr = np.asarray(matrix, dtype=np.float64).reshape(4, 4)
    return arr[:3, 3].copy()


def _axes_from_summary(summary: dict[str, Any]) -> dict[str, np.ndarray]:
    return {
        "opening": _vec3(summary["opening_xyz"]),
        "height": _vec3(summary["height_xyz"]),
        "approach": _vec3(summary["approach_xyz"]),
    }


def main() -> int:
    args = build_parser().parse_args()
    pose_chain = _load_json(args.pose_chain)
    frame_binding = _load_json(args.frame_binding_analysis)
    best_direct = _load_json(args.best_direct_result)

    if not pose_chain.get("grasps"):
        raise ValueError("pose_chain has no grasps")
    default_grasp = dict(pose_chain["grasps"][0])
    default_tool = _vec3(default_grasp["tool_grasp_pose_xyz"])
    default_axes = _axes_from_summary(default_grasp["grasp_base_axes"])
    best_tool = _tool_xyz_from_matrix(best_direct["tool_grasp_pose_matrix"])

    rows: list[dict[str, Any]] = []
    for binding in frame_binding.get("bindings", []):
        if binding.get("error"):
            continue
        if "tool_grasp_pose_xyz" not in binding or "grasp_base_axes" not in binding:
            continue
        tool = _vec3(binding["tool_grasp_pose_xyz"])
        axes = _axes_from_summary(binding["grasp_base_axes"])
        delta_tool = tool - default_tool
        rows.append(
            {
                "binding_label": str(binding["binding_label"]),
                "tool_grasp_pose_xyz": tool.astype(float).tolist(),
                "tool_delta_vs_default_xyz": delta_tool.astype(float).tolist(),
                "tool_delta_vs_default_norm_m": float(np.linalg.norm(delta_tool)),
                "approach_axis_xyz": axes["approach"].astype(float).tolist(),
                "opening_axis_xyz": axes["opening"].astype(float).tolist(),
                "height_axis_xyz": axes["height"].astype(float).tolist(),
                "approach_dot_default": float(np.dot(axes["approach"], default_axes["approach"])),
                "opening_dot_default": float(np.dot(axes["opening"], default_axes["opening"])),
                "height_dot_default": float(np.dot(axes["height"], default_axes["height"])),
            }
        )

    payload = {
        "pose_chain_path": str(Path(args.pose_chain).resolve()),
        "frame_binding_analysis_path": str(Path(args.frame_binding_analysis).resolve()),
        "best_direct_result_path": str(Path(args.best_direct_result).resolve()),
        "active_binding_label": str(frame_binding.get("active_binding_label", "unknown")),
        "active_camera_correction_label": str(
            frame_binding.get(
                "active_camera_correction_label",
                pose_chain.get(
                    "active_camera_correction_label",
                    best_direct.get("active_camera_correction_label", "unknown"),
                ),
            )
        ),
        "active_extrinsic_correction_label": str(
            frame_binding.get(
                "active_extrinsic_correction_label",
                pose_chain.get(
                    "active_extrinsic_correction_label",
                    best_direct.get("active_extrinsic_correction_label", "unknown"),
                ),
            )
        ),
        "default_rank0_grasp_pose_base_xyz": list(default_grasp["grasp_pose_base_xyz"]),
        "default_rank0_tool_grasp_pose_xyz": default_tool.astype(float).tolist(),
        "best_direct_tool_grasp_pose_xyz": best_tool.astype(float).tolist(),
        "best_direct_vs_default_tool_delta_xyz": (best_tool - default_tool).astype(float).tolist(),
        "bindings": rows,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "binding_count": len(rows)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
