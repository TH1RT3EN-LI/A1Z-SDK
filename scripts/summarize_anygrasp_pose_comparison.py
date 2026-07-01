#!/usr/bin/env python3

"""Summarize AnyGrasp rank-0 vs adapter-selected pose differences."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize AnyGrasp best-vs-selected pose differences.")
    parser.add_argument("--adapter-result", required=True, help="Path to anygrasp_adapter_result.json")
    parser.add_argument("--best-direct-result", required=True, help="Path to anygrasp_best_direct_result.json")
    parser.add_argument("--output", required=True, help="Output JSON path")
    return parser


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _vec3_from_matrix(matrix: Any) -> np.ndarray:
    arr = np.asarray(matrix, dtype=np.float64).reshape(4, 4)
    return arr[:3, 3].copy()


def _selected_candidate(adapter_payload: dict[str, Any]) -> dict[str, Any] | None:
    selected_id = adapter_payload.get("summary", {}).get("selected_candidate_id")
    if not selected_id:
        return None
    for candidate in adapter_payload.get("candidates", []):
        if candidate.get("candidate_id") == selected_id:
            return dict(candidate)
    return None


def main() -> int:
    args = build_parser().parse_args()
    adapter_payload = _load_json(args.adapter_result)
    best_direct_payload = _load_json(args.best_direct_result)

    selected = _selected_candidate(adapter_payload)
    best_grasp = _vec3_from_matrix(best_direct_payload["grasp_pose_base"])
    best_tool = _vec3_from_matrix(best_direct_payload["tool_grasp_pose_matrix"])
    selected_grasp = None if selected is None else _vec3_from_matrix(selected["source_grasp_pose_matrix"])
    selected_tool = None if selected is None else _vec3_from_matrix(selected["tool_grasp_pose_matrix"])

    grasp_delta = None if selected_grasp is None else (selected_grasp - best_grasp)
    tool_delta = None if selected_tool is None else (selected_tool - best_tool)

    summary = {
        "adapter_active_binding_label": adapter_payload.get("summary", {}).get("active_binding_label"),
        "adapter_active_camera_correction_label": adapter_payload.get("summary", {}).get("active_camera_correction_label"),
        "adapter_active_extrinsic_correction_label": adapter_payload.get("summary", {}).get("active_extrinsic_correction_label"),
        "best_direct_active_binding_label": best_direct_payload.get("active_binding_label"),
        "best_direct_active_camera_correction_label": best_direct_payload.get("active_camera_correction_label"),
        "best_direct_active_extrinsic_correction_label": best_direct_payload.get("active_extrinsic_correction_label"),
        "best_direct_rank": int(best_direct_payload.get("selected_rank", 0)),
        "selected_rank": -1 if selected is None else int(selected.get("rank", -1)),
        "adapter_selected_candidate_present": selected is not None,
        "best_direct_failure_reasons": list(best_direct_payload.get("failure_reasons", [])),
        "selected_failure_reasons": [] if selected is None else list(selected.get("failure_reasons", [])),
        "best_direct_has_plan": Path(args.best_direct_result).with_name("selected_plan.json").is_file(),
        "selected_has_plan": Path(args.adapter_result).with_name("selected_plan.json").is_file(),
        "best_direct_grasp_pose_base_xyz": best_grasp.astype(float).tolist(),
        "selected_grasp_pose_base_xyz": None if selected_grasp is None else selected_grasp.astype(float).tolist(),
        "grasp_pose_base_delta_xyz": None if grasp_delta is None else grasp_delta.astype(float).tolist(),
        "best_direct_tool_grasp_pose_xyz": best_tool.astype(float).tolist(),
        "selected_tool_grasp_pose_xyz": None if selected_tool is None else selected_tool.astype(float).tolist(),
        "tool_grasp_pose_delta_xyz": None if tool_delta is None else tool_delta.astype(float).tolist(),
        "delta_norms_m": {
            "grasp": None if grasp_delta is None else float(np.linalg.norm(grasp_delta)),
            "tool": None if tool_delta is None else float(np.linalg.norm(tool_delta)),
        },
        "axis_deltas_m": {
            "grasp_dx": None if grasp_delta is None else float(grasp_delta[0]),
            "grasp_dy": None if grasp_delta is None else float(grasp_delta[1]),
            "grasp_dz": None if grasp_delta is None else float(grasp_delta[2]),
            "tool_dx": None if tool_delta is None else float(tool_delta[0]),
            "tool_dy": None if tool_delta is None else float(tool_delta[1]),
            "tool_dz": None if tool_delta is None else float(tool_delta[2]),
        },
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "summary": summary}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
