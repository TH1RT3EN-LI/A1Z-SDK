#!/usr/bin/env python3

"""Rank AnyGrasp mapping hypotheses from an observed tool correction delta."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank AnyGrasp mapping hypotheses from observed tool correction.")
    parser.add_argument("--alignment-report", default="", help="Path to anygrasp_alignment_report.json")
    parser.add_argument("--mapping-hypotheses", default="", help="Path to mapping_hypotheses.json; preferred when available.")
    parser.add_argument("--observed-tool-delta-xyz", required=True, help="Observed tool correction delta in base frame, JSON [dx,dy,dz].")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", default="", help="Optional output JSON path")
    return parser


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _parse_vec3(raw: str) -> np.ndarray:
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"expected JSON vec3: {raw}")
    return np.asarray([float(v) for v in value], dtype=np.float64)


def main() -> int:
    args = build_parser().parse_args()
    observed = _parse_vec3(args.observed_tool_delta_xyz)

    rows: list[dict[str, Any]] = []
    source_kind = ""
    source_path = ""
    preferred_binding_label = ""
    if args.mapping_hypotheses:
        mapping = _load_json(args.mapping_hypotheses)
        source_kind = "mapping_hypotheses"
        source_path = str(Path(args.mapping_hypotheses).resolve())
        preferred_binding_label = str(mapping.get("active_binding_label") or "")
        for hyp in mapping.get("all_hypotheses", []):
            predicted = np.asarray(hyp["grasp_gap"]["delta_xyz"], dtype=np.float64).reshape(3)
            residual = observed - predicted
            rows.append(
                {
                    "binding_label": str(hyp["binding_label"]),
                    "camera_correction_label": str(hyp.get("camera_correction_label")),
                    "extrinsic_correction_label": str(hyp.get("extrinsic_correction_label")),
                    "predicted_tool_delta_xyz": predicted.astype(float).tolist(),
                    "observed_tool_delta_xyz": observed.astype(float).tolist(),
                    "residual_xyz": residual.astype(float).tolist(),
                    "residual_norm_m": float(np.linalg.norm(residual)),
                    "predicted_delta_norm_m": float(hyp["grasp_gap"]["delta_norm_m"]),
                    "orientation_gap_deg": float(hyp["grasp_gap"]["orientation_gap_deg"]),
                }
            )
    elif args.alignment_report:
        report = _load_json(args.alignment_report)
        source_kind = "alignment_report"
        source_path = str(Path(args.alignment_report).resolve())
        preferred_binding_label = str(report.get("active_binding_label") or "")
        for binding in report.get("bindings", []):
            predicted = np.asarray(binding["tool_delta_vs_default_xyz"], dtype=np.float64).reshape(3)
            residual = observed - predicted
            rows.append(
                {
                    "binding_label": str(binding["binding_label"]),
                    "predicted_tool_delta_xyz": predicted.astype(float).tolist(),
                    "observed_tool_delta_xyz": observed.astype(float).tolist(),
                    "residual_xyz": residual.astype(float).tolist(),
                    "residual_norm_m": float(np.linalg.norm(residual)),
                    "predicted_delta_norm_m": float(binding["tool_delta_vs_default_norm_m"]),
                    "approach_dot_default": float(binding["approach_dot_default"]),
                }
            )
    else:
        raise ValueError("one of --mapping-hypotheses or --alignment-report is required")

    rows.sort(
        key=lambda row: (
            row["residual_norm_m"],
            0 if preferred_binding_label and row["binding_label"] == preferred_binding_label else 1,
            row["binding_label"],
        )
    )
    payload = {
        "source_kind": source_kind,
        "source_path": source_path,
        "observed_tool_delta_xyz": observed.astype(float).tolist(),
        "ranked_bindings": rows,
        "top_matches": rows[: max(1, int(args.top_k))],
    }

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(json.dumps({
        "observed_tool_delta_xyz": payload["observed_tool_delta_xyz"],
        "top_matches": payload["top_matches"],
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
