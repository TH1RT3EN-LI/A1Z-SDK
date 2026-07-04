#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_DIR="$ROOT_DIR/runtime/anygrasp_replay_compare_summary_v4"
OUTPUT_DIR="$ROOT_DIR/runtime/anygrasp_output_dir_analysis_verify"
INPUT_DIR="$ROOT_DIR/runtime/anygrasp_output_dir_analysis_input"

rm -rf "$OUTPUT_DIR"
rm -rf "$INPUT_DIR"
mkdir -p "$INPUT_DIR"

bash "$ROOT_DIR/scripts/analyze_anygrasp_frame_bindings_in_container.sh" \
  --result-json /workspace/A1Z/runtime/anygrasp_replay_compare_summary_v4/anygrasp_from_mask/anygrasp/anygrasp_result.json \
  --extrinsic-camera-to-base /workspace/A1Z/runtime/target_mask_to_anygrasp/from_ros_live/capture/extrinsic_camera_to_base.npy \
  --output /workspace/A1Z/runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_frame_binding_analysis.json \
  --grasp-rank 0 \
  --binding-label 'opening=c1,height=c2,approach=c0' \
  --camera-correction-label 'identity' \
  --extrinsic-correction-label 'identity' \
  --ee-grasp-origin-xyz-m '[0.0, 0.0, 0.0]' \
  --ee-opening-axis-xyz '[0.0, 0.0, 1.0]' \
  --ee-approach-axis-xyz '[1.0, 0.0, 0.0]' >/dev/null

bash "$ROOT_DIR/scripts/summarize_anygrasp_alignment_report_in_container.sh" \
  --pose-chain /workspace/A1Z/runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_pose_chain_summary.json \
  --frame-binding-analysis /workspace/A1Z/runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_frame_binding_analysis.json \
  --best-direct-result /workspace/A1Z/runtime/anygrasp_replay_compare_summary_v4/adapter/best_direct/anygrasp_best_direct_result.json \
  --output /workspace/A1Z/runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_alignment_report.json >/dev/null

python3 - <<PY
import json
import shutil
from pathlib import Path

root = Path(r"$ROOT_DIR")
src_dir = Path(r"$PIPELINE_DIR")
dst_dir = Path(r"$INPUT_DIR")

shutil.copy2(src_dir / "pipeline_status.json", dst_dir / "pipeline_status.json")
manifest = json.loads((src_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))
manifest["output_dir"] = str(dst_dir)
summary = manifest.setdefault("summary", {})
summary["tcp_defaults"] = {
    "ee_grasp_origin_xyz_m": [0.0, 0.0, 0.0],
    "ee_opening_axis_xyz": [0.0, 0.0, 1.0],
    "ee_approach_axis_xyz": [1.0, 0.0, 0.0],
}
summary["active_binding_label"] = "opening=c1,height=c2,approach=c0"
summary["active_camera_correction_label"] = "identity"
summary["active_extrinsic_correction_label"] = "identity"
(dst_dir / "pipeline_manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
PY

bash "$ROOT_DIR/scripts/analyze_anygrasp_output_dir.sh" \
  "$INPUT_DIR" \
  --observed-tool-delta-xyz '[0.07, 0.10, -0.08]' \
  --top-k 2 \
  --output-dir "$OUTPUT_DIR" >/dev/null

python3 - <<PY
import json
from pathlib import Path

root = Path(r"$OUTPUT_DIR")
summary = json.loads((root / "analysis_summary.json").read_text(encoding="utf-8"))
hindex = json.loads((root / "analysis_index.json").read_text(encoding="utf-8"))
hyp = json.loads((root / "binding_hypotheses.json").read_text(encoding="utf-8"))

assert summary["selected_rank"] == 0, summary
assert summary["active_binding_label"] == "opening=c1,height=c2,approach=c0", summary
assert summary["active_camera_correction_label"] == "identity", summary
assert summary["active_extrinsic_correction_label"] == "identity", summary
assert summary["manifest_active_binding_label"] == "opening=c1,height=c2,approach=c0", summary
assert summary["manifest_active_camera_correction_label"] == "identity", summary
assert summary["manifest_active_extrinsic_correction_label"] == "identity", summary
assert summary["frame_analysis_active_binding_label"] == "opening=c1,height=c2,approach=c0", summary
assert summary["frame_analysis_active_camera_correction_label"] == "identity", summary
assert summary["frame_analysis_active_extrinsic_correction_label"] == "identity", summary
assert summary["binding_label_sources_present"] == ["frame_analysis", "manifest"], summary
assert summary["binding_label_sources_missing"] == ["best_direct"], summary
assert summary["binding_label_consistent"] is True, summary
assert summary["camera_correction_sources_present"] == ["frame_analysis", "manifest"], summary
assert summary["camera_correction_sources_missing"] == ["best_direct"], summary
assert summary["camera_correction_consistent"] is True, summary
assert summary["extrinsic_correction_sources_present"] == ["frame_analysis", "manifest"], summary
assert summary["extrinsic_correction_sources_missing"] == ["best_direct"], summary
assert summary["extrinsic_correction_consistent"] is True, summary
assert summary["alignment_report_json"].endswith("/adapter/anygrasp_alignment_report.json"), summary
assert (
    summary["best_direct_ik_target_gap_json"] is None
    or summary["best_direct_ik_target_gap_json"].endswith("/adapter/best_direct/ik_target_gap.json")
), summary
assert summary["binding_hypotheses_json"].endswith("/binding_hypotheses.json"), summary
assert summary["tcp_defaults"]["ee_approach_axis_xyz"] == [1.0, 0.0, 0.0], summary
assert (
    summary["capture_current_joints_rad_json"] is None
    or summary["capture_current_joints_rad_json"].endswith("/capture/current_joints_rad.json")
), summary
assert summary["capture_current_joints_rad_present"] is False, summary
assert summary["capture_current_joints_status"] == "missing", summary
assert summary["capture_current_joints_required_for_alignment"] is True, summary
assert summary["capture_current_joints_rad"] is None, summary
assert isinstance(summary["best_direct_current_q_rad"], list) and len(summary["best_direct_current_q_rad"]) == 6, summary
assert summary["best_direct_used_capture_joints"] is False, summary
assert summary["best_direct_reference_state_reliable"] is False, summary
assert isinstance(summary["best_direct_ik_target_gap_present"], bool), summary
assert len(summary["best_direct_grasp_pose_base_xyz"]) == 3, summary
assert len(summary["best_direct_tool_grasp_pose_xyz"]) == 3, summary
assert summary["diagnostic_summary"]["evidence_quality"]["capture_current_joints_status"] == "missing", summary
assert summary["diagnostic_summary"]["evidence_quality"]["best_direct_reference_state_reliable"] is False, summary
assert summary["diagnostic_summary"]["evidence_quality"]["alignment_fit_for_decision"] is False, summary
assert hindex["artifacts"]["analysis_summary_json"].endswith("/analysis_summary.json"), hindex
assert hindex["artifacts"]["best_direct_result_json"].endswith("/adapter/best_direct/anygrasp_best_direct_result.json"), hindex
assert (
    hindex["artifacts"]["best_direct_ik_target_gap_json"] is None
    or hindex["artifacts"]["best_direct_ik_target_gap_json"].endswith("/adapter/best_direct/ik_target_gap.json")
), hindex
assert isinstance(hyp.get("top_matches"), list) and len(hyp["top_matches"]) == 2, hyp
assert hyp["top_matches"][0]["binding_label"] in {
    "opening=c1,height=c2,approach=c0",
    "opening=c2,height=mc1,approach=c0",
    "opening=mc2,height=c1,approach=c0",
    "opening=c1,height=c2,approach=c0",
    "opening=c1,height=c2,approach=c0",
}, hyp
assert hyp["top_matches"][0]["residual_norm_m"] >= 0.0, hyp
print("AnyGrasp output-dir analysis verification passed")
PY

echo "AnyGrasp output-dir analysis verification passed."
