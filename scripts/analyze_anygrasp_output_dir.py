#!/usr/bin/env python3

"""Analyze one AnyGrasp pipeline output directory and emit a compact diagnostics bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze one AnyGrasp pipeline output directory.")
    parser.add_argument("--pipeline-dir", required=True, help="Path to AnyGrasp pipeline output directory")
    parser.add_argument("--observed-tool-delta-xyz", default="", help="Optional observed tool correction delta JSON [dx,dy,dz]")
    parser.add_argument("--top-k", type=int, default=3, help="Top binding hypotheses to keep when observed delta is provided")
    parser.add_argument("--output-dir", default="", help="Optional output directory; defaults to <pipeline-dir>/analysis")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _matrix_xyz(matrix: Any) -> list[float] | None:
    try:
        rows = matrix
        if not isinstance(rows, list) or len(rows) != 4:
            return None
        return [float(rows[0][3]), float(rows[1][3]), float(rows[2][3])]
    except Exception:
        return None


def _load_optional_json(path_value: Any) -> Any | None:
    if not path_value:
        return None
    try:
        path = Path(str(path_value))
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _severity_from_gap(*, norm_m: Any, orientation_deg: Any) -> str:
    try:
        norm = float(norm_m)
        orientation = float(orientation_deg)
    except Exception:
        return "unknown"
    if norm >= 0.25 or orientation >= 120.0:
        return "high"
    if norm >= 0.10 or orientation >= 45.0:
        return "medium"
    return "low"


def main() -> int:
    args = build_parser().parse_args()
    pipeline_dir = Path(args.pipeline_dir).resolve()
    manifest = _load_json(pipeline_dir / "pipeline_manifest.json")
    status = _load_json(pipeline_dir / "pipeline_status.json")
    adapter = manifest["adapter"]
    manifest_summary = manifest.get("summary", {})

    output_dir = Path(args.output_dir).resolve() if args.output_dir else (pipeline_dir / "analysis").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_binding_path = Path(str(adapter.get("frame_binding_analysis_json", "")))
    frame_binding = _load_json(frame_binding_path) if frame_binding_path.is_file() else {}
    mapping_hypotheses_path = Path(str(adapter.get("mapping_hypotheses_json", "")))
    mapping_hypotheses = _load_json(mapping_hypotheses_path) if mapping_hypotheses_path.is_file() else {}
    best_direct_path = Path(str(adapter.get("best_direct_result_json", "")))
    best_direct = _load_json(best_direct_path) if best_direct_path.is_file() else {}
    best_direct_gap_path = Path(str(adapter.get("best_direct_ik_target_gap_json", "")))
    best_direct_gap = _load_json(best_direct_gap_path) if best_direct_gap_path.is_file() else {}
    adapter_result_path = Path(str(adapter.get("result_json", "")))
    adapter_result = _load_json(adapter_result_path) if adapter_result_path.is_file() else {}
    capture_manifest = manifest.get("capture", {})
    capture_joints = _load_optional_json(capture_manifest.get("current_joints_rad_json"))

    manifest_binding_label = manifest_summary.get("active_binding_label")
    manifest_camera_correction_label = manifest_summary.get("active_camera_correction_label")
    manifest_extrinsic_correction_label = manifest_summary.get("active_extrinsic_correction_label")
    frame_binding_label = frame_binding.get("active_binding_label")
    frame_camera_correction_label = frame_binding.get("active_camera_correction_label")
    frame_extrinsic_correction_label = frame_binding.get("active_extrinsic_correction_label")
    best_direct_binding_label = best_direct.get("active_binding_label")
    best_direct_camera_correction_label = best_direct.get("active_camera_correction_label")
    best_direct_extrinsic_correction_label = best_direct.get("active_extrinsic_correction_label")

    present_binding_labels = {
        key: value
        for key, value in {
            "manifest": manifest_binding_label,
            "frame_analysis": frame_binding_label,
            "best_direct": best_direct_binding_label,
        }.items()
        if value
    }
    binding_label_values = sorted(set(str(value) for value in present_binding_labels.values()))
    present_camera_correction_labels = {
        key: value
        for key, value in {
            "manifest": manifest_camera_correction_label,
            "frame_analysis": frame_camera_correction_label,
            "best_direct": best_direct_camera_correction_label,
        }.items()
        if value
    }
    camera_correction_values = sorted(set(str(value) for value in present_camera_correction_labels.values()))
    present_extrinsic_correction_labels = {
        key: value
        for key, value in {
            "manifest": manifest_extrinsic_correction_label,
            "frame_analysis": frame_extrinsic_correction_label,
            "best_direct": best_direct_extrinsic_correction_label,
        }.items()
        if value
    }
    extrinsic_correction_values = sorted(set(str(value) for value in present_extrinsic_correction_labels.values()))

    summary = {
        "pipeline_dir": str(pipeline_dir),
        "pipeline_manifest_path": str((pipeline_dir / "pipeline_manifest.json").resolve()),
        "pipeline_status_path": str((pipeline_dir / "pipeline_status.json").resolve()),
        "selected_rank": status.get("selected_rank"),
        "tcp_defaults": manifest_summary.get("tcp_defaults"),
        "adapter_result_json": adapter.get("result_json"),
        "best_direct_result_json": adapter.get("best_direct_result_json"),
        "best_vs_selected_summary_json": adapter.get("best_vs_selected_summary_json"),
        "pose_chain_summary_json": adapter.get("pose_chain_summary_json"),
        "frame_binding_analysis_json": adapter.get("frame_binding_analysis_json"),
        "alignment_report_json": adapter.get("alignment_report_json"),
        "mapping_hypotheses_json": adapter.get("mapping_hypotheses_json"),
        "best_direct_ik_target_gap_json": adapter.get("best_direct_ik_target_gap_json"),
        "active_binding_label": frame_binding_label or manifest_binding_label,
        "active_camera_correction_label": frame_camera_correction_label or manifest_camera_correction_label,
        "active_extrinsic_correction_label": frame_extrinsic_correction_label or manifest_extrinsic_correction_label,
        "manifest_active_binding_label": manifest_binding_label,
        "manifest_active_camera_correction_label": manifest_camera_correction_label,
        "manifest_active_extrinsic_correction_label": manifest_extrinsic_correction_label,
        "frame_analysis_active_binding_label": frame_binding_label,
        "frame_analysis_active_camera_correction_label": frame_camera_correction_label,
        "frame_analysis_active_extrinsic_correction_label": frame_extrinsic_correction_label,
        "best_direct_active_binding_label": best_direct_binding_label,
        "best_direct_active_camera_correction_label": best_direct_camera_correction_label,
        "best_direct_active_extrinsic_correction_label": best_direct_extrinsic_correction_label,
        "binding_label_sources_present": sorted(present_binding_labels.keys()),
        "binding_label_sources_missing": sorted(
            {"manifest", "frame_analysis", "best_direct"} - set(present_binding_labels.keys())
        ),
        "binding_label_consistent": len(binding_label_values) <= 1 and bool(present_binding_labels),
        "camera_correction_sources_present": sorted(present_camera_correction_labels.keys()),
        "camera_correction_sources_missing": sorted(
            {"manifest", "frame_analysis", "best_direct"} - set(present_camera_correction_labels.keys())
        ),
        "camera_correction_consistent": len(camera_correction_values) <= 1 and bool(present_camera_correction_labels),
        "extrinsic_correction_sources_present": sorted(present_extrinsic_correction_labels.keys()),
        "extrinsic_correction_sources_missing": sorted(
            {"manifest", "frame_analysis", "best_direct"} - set(present_extrinsic_correction_labels.keys())
        ),
        "extrinsic_correction_consistent": len(extrinsic_correction_values) <= 1 and bool(present_extrinsic_correction_labels),
        "adapter_selected_candidate_id": adapter_result.get("summary", {}).get("selected_candidate_id"),
        "adapter_executable_count": adapter_result.get("summary", {}).get("executable_count"),
        "best_direct_selected_rank": best_direct.get("selected_rank"),
        "best_direct_failure_reasons": list(best_direct.get("failure_reasons", [])),
        "best_direct_grasp_pose_base_xyz": _matrix_xyz(best_direct.get("grasp_pose_base")),
        "best_direct_tool_grasp_pose_xyz": _matrix_xyz(best_direct.get("tool_grasp_pose_matrix")),
        "capture_current_joints_rad_json": capture_manifest.get("current_joints_rad_json"),
        "capture_current_joints_rad_present": isinstance(capture_joints, list) and len(capture_joints) == 6,
        "capture_current_joints_rad": capture_joints if isinstance(capture_joints, list) else None,
        "capture_current_joints_status": (
            "present"
            if isinstance(capture_joints, list) and len(capture_joints) == 6
            else "missing"
        ),
        "capture_current_joints_required_for_alignment": True,
        "best_direct_current_q_rad": best_direct.get("current_q_rad"),
        "best_direct_used_capture_joints": (
            isinstance(capture_joints, list)
            and isinstance(best_direct.get("current_q_rad"), list)
            and len(capture_joints) == len(best_direct.get("current_q_rad"))
            and all(abs(float(a) - float(b)) <= 1e-9 for a, b in zip(capture_joints, best_direct.get("current_q_rad")))
        ),
        "best_direct_reference_state_reliable": (
            isinstance(capture_joints, list)
            and isinstance(best_direct.get("current_q_rad"), list)
            and len(capture_joints) == len(best_direct.get("current_q_rad"))
            and all(abs(float(a) - float(b)) <= 1e-9 for a, b in zip(capture_joints, best_direct.get("current_q_rad")))
        ),
        "best_direct_ik_target_gap_present": bool(best_direct_gap),
        "best_direct_current_ee_xyz": best_direct_gap.get("current_ee_xyz"),
        "best_direct_pregrasp_gap_xyz": best_direct_gap.get("pregrasp_gap", {}).get("delta_xyz"),
        "best_direct_pregrasp_gap_norm_m": best_direct_gap.get("pregrasp_gap", {}).get("delta_norm_m"),
        "best_direct_pregrasp_orientation_gap_deg": best_direct_gap.get("pregrasp_gap", {}).get("orientation_gap_deg"),
        "best_direct_grasp_gap_xyz": best_direct_gap.get("grasp_gap", {}).get("delta_xyz"),
        "best_direct_grasp_gap_norm_m": best_direct_gap.get("grasp_gap", {}).get("delta_norm_m"),
        "best_direct_grasp_orientation_gap_deg": best_direct_gap.get("grasp_gap", {}).get("orientation_gap_deg"),
        "mapping_hypotheses_present": bool(mapping_hypotheses),
        "mapping_best_binding_label": (
            None if not mapping_hypotheses.get("top_hypotheses") else mapping_hypotheses["top_hypotheses"][0].get("binding_label")
        ),
        "mapping_best_camera_correction_label": (
            None
            if not mapping_hypotheses.get("top_hypotheses")
            else mapping_hypotheses["top_hypotheses"][0].get("camera_correction_label")
        ),
        "mapping_best_extrinsic_correction_label": (
            None
            if not mapping_hypotheses.get("top_hypotheses")
            else mapping_hypotheses["top_hypotheses"][0].get("extrinsic_correction_label")
        ),
        "mapping_best_grasp_gap_norm_m": (
            None
            if not mapping_hypotheses.get("top_hypotheses")
            else mapping_hypotheses["top_hypotheses"][0].get("grasp_gap", {}).get("delta_norm_m")
        ),
        "mapping_best_grasp_orientation_gap_deg": (
            None
            if not mapping_hypotheses.get("top_hypotheses")
            else mapping_hypotheses["top_hypotheses"][0].get("grasp_gap", {}).get("orientation_gap_deg")
        ),
        "observed_tool_delta_xyz": None,
        "binding_hypotheses_json": None,
    }

    if args.observed_tool_delta_xyz:
        summary["observed_tool_delta_xyz"] = json.loads(args.observed_tool_delta_xyz)
        summary["binding_hypotheses_json"] = str(output_dir / "binding_hypotheses.json")

    summary["diagnostic_summary"] = {
        "active_mapping": {
            "binding_label": summary["active_binding_label"],
            "camera_correction_label": summary["active_camera_correction_label"],
            "extrinsic_correction_label": summary["active_extrinsic_correction_label"],
        },
        "evidence_quality": {
            "capture_current_joints_status": summary["capture_current_joints_status"],
            "best_direct_reference_state_reliable": summary["best_direct_reference_state_reliable"],
            "alignment_fit_for_decision": bool(summary["best_direct_reference_state_reliable"]),
        },
        "active_best_direct_gap": {
            "translation_norm_m": summary["best_direct_grasp_gap_norm_m"],
            "orientation_gap_deg": summary["best_direct_grasp_orientation_gap_deg"],
            "severity": _severity_from_gap(
                norm_m=summary["best_direct_grasp_gap_norm_m"],
                orientation_deg=summary["best_direct_grasp_orientation_gap_deg"],
            ),
        },
        "best_scanned_mapping": {
            "binding_label": summary["mapping_best_binding_label"],
            "camera_correction_label": summary["mapping_best_camera_correction_label"],
            "extrinsic_correction_label": summary["mapping_best_extrinsic_correction_label"],
            "translation_norm_m": summary["mapping_best_grasp_gap_norm_m"],
            "orientation_gap_deg": summary["mapping_best_grasp_orientation_gap_deg"],
            "severity": _severity_from_gap(
                norm_m=summary["mapping_best_grasp_gap_norm_m"],
                orientation_deg=summary["mapping_best_grasp_orientation_gap_deg"],
            ),
        },
        "mapping_disagreement": {
            "binding_differs": (
                summary["active_binding_label"] != summary["mapping_best_binding_label"]
                if summary["mapping_best_binding_label"] is not None
                else None
            ),
            "camera_correction_differs": (
                summary["active_camera_correction_label"] != summary["mapping_best_camera_correction_label"]
                if summary["mapping_best_camera_correction_label"] is not None
                else None
            ),
            "extrinsic_correction_differs": (
                summary["active_extrinsic_correction_label"] != summary["mapping_best_extrinsic_correction_label"]
                if summary["mapping_best_extrinsic_correction_label"] is not None
                else None
            ),
        },
    }

    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    index_payload = {
        "pipeline_dir": str(pipeline_dir),
        "selected_rank": status.get("selected_rank"),
        "recommended_read_order": [
            str(output_dir / "analysis_summary.json"),
            adapter.get("best_direct_result_json"),
            adapter.get("best_direct_ik_target_gap_json"),
            adapter.get("mapping_hypotheses_json"),
            adapter.get("alignment_report_json"),
            adapter.get("frame_binding_analysis_json"),
            adapter.get("pose_chain_summary_json"),
            adapter.get("best_vs_selected_summary_json"),
        ],
        "artifacts": {
            "analysis_summary_json": str(output_dir / "analysis_summary.json"),
            "binding_hypotheses_json": None if not args.observed_tool_delta_xyz else str(output_dir / "binding_hypotheses.json"),
            "best_direct_result_json": adapter.get("best_direct_result_json"),
            "best_direct_ik_target_gap_json": adapter.get("best_direct_ik_target_gap_json"),
            "mapping_hypotheses_json": adapter.get("mapping_hypotheses_json"),
            "alignment_report_json": adapter.get("alignment_report_json"),
            "frame_binding_analysis_json": adapter.get("frame_binding_analysis_json"),
            "pose_chain_summary_json": adapter.get("pose_chain_summary_json"),
            "best_vs_selected_summary_json": adapter.get("best_vs_selected_summary_json"),
        },
        "notes": [
            "Use best_direct first to isolate AnyGrasp rank0 alignment from adapter candidate selection.",
            "If best_direct_ik_target_gap_json shows large position or orientation gaps, fix frame/extrinsic mapping before TCP micro-tuning.",
            "Use mapping_hypotheses_json to compare joint-frame gap under alternative AnyGrasp binding and camera-frame correction assumptions.",
            "Read active_binding_label together with tcp_defaults before interpreting tool deltas.",
            "If the observed tool error is available, generate binding_hypotheses.json to rank frame-binding candidates.",
            "Treat best_direct gap metrics as alignment evidence only when capture/current_joints_rad.json is present and matches best_direct_current_q_rad.",
        ],
    }
    (output_dir / "analysis_index.json").write_text(
        json.dumps(index_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "summary": summary}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
