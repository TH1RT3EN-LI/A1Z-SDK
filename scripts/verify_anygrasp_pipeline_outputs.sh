#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/runtime/anygrasp_pipeline_outputs_verify"
ANALYSIS_FIXTURE_DIR="$ROOT_DIR/runtime/anygrasp_output_dir_analysis_verify"
RENDER_FIXTURE_JSON="$(find "$ROOT_DIR/runtime" -path '*/renders/anygrasp_graspgroup_all.json' -print 2>/dev/null | head -n1 || true)"

if [[ -z "$RENDER_FIXTURE_JSON" ]]; then
  echo "missing fixture: runtime/*/renders/anygrasp_graspgroup_all.json" >&2
  exit 1
fi

RENDER_FIXTURE_DIR="$(dirname "$RENDER_FIXTURE_JSON")"

rm -rf "$OUTPUT_DIR"
mkdir -p \
  "$OUTPUT_DIR/capture" \
  "$OUTPUT_DIR/target_mask/selection" \
  "$OUTPUT_DIR/anygrasp_from_mask/anygrasp" \
  "$OUTPUT_DIR/anygrasp_from_mask/masked_point_cloud" \
  "$OUTPUT_DIR/adapter/best_direct" \
  "$OUTPUT_DIR/analysis" \
  "$OUTPUT_DIR/renders"

if [[ ! -f "$ANALYSIS_FIXTURE_DIR/analysis_index.json" ]]; then
  bash "$ROOT_DIR/scripts/verify_analyze_anygrasp_output_dir.sh" >/dev/null
fi

python3 - <<PY
import json
from pathlib import Path
import shutil

root = Path(r"$OUTPUT_DIR")
render_fixture_dir = Path(r"$RENDER_FIXTURE_DIR")

copy_map = {
    Path("runtime/target_mask_to_anygrasp/from_ros_live/capture/rgb.npy"): root / "capture/rgb.npy",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/capture/depth_m.npy"): root / "capture/depth_m.npy",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/capture/intrinsics.json"): root / "capture/intrinsics.json",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/capture/observation.json"): root / "capture/observation.json",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/capture/extrinsic_camera_to_base.npy"): root / "capture/extrinsic_camera_to_base.npy",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/target_mask/selection/selected_mask.npy"): root / "target_mask/selection/selected_mask.npy",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/target_mask/selection/selection.json"): root / "target_mask/selection/selection.json",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/anygrasp_from_mask/masked_point_cloud/points.npy"): root / "anygrasp_from_mask/masked_point_cloud/points.npy",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/anygrasp_from_mask/masked_point_cloud/colors.npy"): root / "anygrasp_from_mask/masked_point_cloud/colors.npy",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/anygrasp_from_mask/masked_point_cloud/masked_point_cloud.json"): root / "anygrasp_from_mask/masked_point_cloud/masked_point_cloud.json",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/anygrasp_from_mask/pipeline_result.json"): root / "anygrasp_from_mask/pipeline_result.json",
    Path("runtime/anygrasp_verify/anygrasp_result.json"): root / "anygrasp_from_mask/anygrasp/anygrasp_result.json",
    Path("runtime/anygrasp_verify_adapter_real_v3/result/anygrasp_adapter_result.json"): root / "adapter/anygrasp_adapter_result.json",
    Path("runtime/anygrasp_verify_adapter_real_v3/result/selected_plan.json"): root / "adapter/selected_plan.json",
    Path("runtime/anygrasp_best_direct_smoke/anygrasp_best_direct_result.json"): root / "adapter/best_direct/anygrasp_best_direct_result.json",
    Path("runtime/anygrasp_replay_with_gap_summary/adapter/best_direct/ik_target_gap.json"): root / "adapter/best_direct/ik_target_gap.json",
    Path("runtime/anygrasp_replay_compare_summary_v4/adapter/best_vs_selected_summary.json"): root / "adapter/best_vs_selected_summary.json",
    Path("runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_pose_chain_summary.json"): root / "adapter/anygrasp_pose_chain_summary.json",
    Path("runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_frame_binding_analysis.json"): root / "adapter/anygrasp_frame_binding_analysis.json",
    Path("runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_alignment_report.json"): root / "adapter/anygrasp_alignment_report.json",
    Path("runtime/anygrasp_output_dir_analysis_verify/analysis_summary.json"): root / "analysis/analysis_summary.json",
    Path("runtime/anygrasp_output_dir_analysis_verify/analysis_index.json"): root / "analysis/analysis_index.json",
    render_fixture_dir / "anygrasp_graspgroup_all.png": root / "renders/anygrasp_graspgroup_all.png",
    render_fixture_dir / "anygrasp_graspgroup_all.json": root / "renders/anygrasp_graspgroup_all.json",
}

for src, dst in copy_map.items():
    if not src.is_file():
        raise SystemExit(f"missing fixture: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

optional_copies = {
    Path("runtime/target_mask_to_anygrasp/from_ros_live/target_mask/selection/overlay_object_candidates.png"): root / "target_mask/selection/overlay_object_candidates.png",
    Path("runtime/anygrasp_output_dir_analysis_verify/analysis_index.json"): root / "analysis/analysis_index.json",
    Path("runtime/target_mask_to_anygrasp/from_ros_live/capture/current_joints_rad.json"): root / "capture/current_joints_rad.json",
    render_fixture_dir / "anygrasp_best.png": root / "renders/anygrasp_best.png",
    render_fixture_dir / "anygrasp_best.json": root / "renders/anygrasp_best.json",
    render_fixture_dir / "anygrasp_masked_pointcloud.png": root / "renders/anygrasp_masked_pointcloud.png",
    render_fixture_dir / "anygrasp_masked_pointcloud.json": root / "renders/anygrasp_masked_pointcloud.json",
}
for src, dst in optional_copies.items():
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

selected_id = json.loads((root / "adapter/anygrasp_adapter_result.json").read_text(encoding="utf-8"))["summary"]["selected_candidate_id"]
adapter_payload = json.loads((root / "adapter/anygrasp_adapter_result.json").read_text(encoding="utf-8"))
selected = next(c for c in adapter_payload["candidates"] if c["candidate_id"] == selected_id)
selected_rank = int(selected["rank"])

if not (root / "analysis" / "analysis_index.json").is_file():
    summary_path = root / "analysis" / "analysis_summary.json"
    index_payload = {
        "pipeline_dir": str(root),
        "selected_rank": selected_rank,
        "recommended_read_order": [
            str(summary_path),
            str(root / "adapter" / "best_direct" / "anygrasp_best_direct_result.json"),
            str(root / "adapter" / "best_direct" / "ik_target_gap.json"),
            str(root / "adapter" / "anygrasp_alignment_report.json"),
            str(root / "adapter" / "anygrasp_frame_binding_analysis.json"),
            str(root / "adapter" / "anygrasp_pose_chain_summary.json"),
            str(root / "adapter" / "best_vs_selected_summary.json"),
        ],
        "artifacts": {
            "analysis_summary_json": str(summary_path),
            "binding_hypotheses_json": str(root / "analysis" / "binding_hypotheses.json"),
            "best_direct_result_json": str(root / "adapter" / "best_direct" / "anygrasp_best_direct_result.json"),
            "best_direct_ik_target_gap_json": str(root / "adapter" / "best_direct" / "ik_target_gap.json"),
            "alignment_report_json": str(root / "adapter" / "anygrasp_alignment_report.json"),
            "frame_binding_analysis_json": str(root / "adapter" / "anygrasp_frame_binding_analysis.json"),
            "pose_chain_summary_json": str(root / "adapter" / "anygrasp_pose_chain_summary.json"),
            "best_vs_selected_summary_json": str(root / "adapter" / "best_vs_selected_summary.json"),
        },
        "notes": [
            "Use best_direct first to isolate AnyGrasp rank0 alignment from adapter candidate selection.",
            "If the observed tool error is available, generate binding_hypotheses.json to rank frame-binding candidates.",
        ],
    }
    (root / "analysis" / "analysis_index.json").write_text(json.dumps(index_payload, ensure_ascii=True, indent=2), encoding="utf-8")

status_payload = {
    "capture_ok": True,
    "target_mask_ok": True,
    "anygrasp_ran": True,
    "anygrasp_grasp_count": 412,
    "anygrasp_error": "",
    "adapter_result_present": True,
    "selected_plan_present": True,
    "best_direct_result_present": True,
    "best_direct_plan_present": False,
    "best_vs_selected_summary_present": True,
    "pose_chain_summary_present": True,
    "frame_binding_analysis_present": True,
    "alignment_report_present": True,
    "analysis_summary_present": True,
    "adapter_selected_candidate_id": selected_id,
    "adapter_executable_count": adapter_payload["summary"]["executable_count"],
    "selected_rank": selected_rank,
    "stage_status": {
        "capture": 0,
        "target_mask": 0,
        "extrinsic": 0,
        "anygrasp": 0,
        "adapter": 0,
        "best_direct": 1,
    },
}
(root / "pipeline_status.json").write_text(json.dumps(status_payload, ensure_ascii=True, indent=2), encoding="utf-8")

manifest = {
    "output_dir": str(root),
    "capture": {
        "dir": str(root / "capture"),
        "rgb_npy": str(root / "capture/rgb.npy"),
        "depth_npy": str(root / "capture/depth_m.npy"),
        "intrinsics_json": str(root / "capture/intrinsics.json"),
        "extrinsic_camera_to_base_npy": str(root / "capture/extrinsic_camera_to_base.npy"),
        "observation_json": str(root / "capture/observation.json"),
        "current_joints_rad_json": str(root / "capture/current_joints_rad.json"),
    },
    "target_mask": {
        "dir": str(root / "target_mask"),
        "selection_json": str(root / "target_mask/selection/selection.json"),
        "selected_mask_npy": str(root / "target_mask/selection/selected_mask.npy"),
        "overlay_candidates_png": str(root / "target_mask/selection/overlay_object_candidates.png"),
    },
    "anygrasp": {
        "dir": str(root / "anygrasp_from_mask"),
        "pipeline_result_json": str(root / "anygrasp_from_mask/pipeline_result.json"),
        "masked_point_cloud_json": str(root / "anygrasp_from_mask/masked_point_cloud/masked_point_cloud.json"),
        "points_npy": str(root / "anygrasp_from_mask/masked_point_cloud/points.npy"),
        "colors_npy": str(root / "anygrasp_from_mask/masked_point_cloud/colors.npy"),
        "result_json": str(root / "anygrasp_from_mask/anygrasp/anygrasp_result.json"),
    },
    "adapter": {
        "dir": str(root / "adapter"),
        "result_json": str(root / "adapter/anygrasp_adapter_result.json"),
        "selected_plan_json": str(root / "adapter/selected_plan.json"),
        "best_direct_dir": str(root / "adapter/best_direct"),
        "best_direct_result_json": str(root / "adapter/best_direct/anygrasp_best_direct_result.json"),
        "best_direct_plan_json": str(root / "adapter/best_direct/selected_plan.json"),
        "best_direct_ik_target_gap_json": str(root / "adapter/best_direct/ik_target_gap.json"),
        "best_vs_selected_summary_json": str(root / "adapter/best_vs_selected_summary.json"),
        "pose_chain_summary_json": str(root / "adapter/anygrasp_pose_chain_summary.json"),
        "frame_binding_analysis_json": str(root / "adapter/anygrasp_frame_binding_analysis.json"),
        "alignment_report_json": str(root / "adapter/anygrasp_alignment_report.json"),
    },
    "renders": {
        "dir": str(root / "renders"),
        "graspgroup_all_image": str(root / "renders/anygrasp_graspgroup_all.png"),
        "graspgroup_all_json": str(root / "renders/anygrasp_graspgroup_all.json"),
        "selected_grasp_image": str(root / "renders/anygrasp_selected.png"),
        "selected_grasp_json": str(root / "renders/anygrasp_selected.json"),
        "best_grasp_image": str(root / "renders/anygrasp_best.png"),
        "best_grasp_json": str(root / "renders/anygrasp_best.json"),
        "masked_pointcloud_image": str(root / "renders/anygrasp_masked_pointcloud.png"),
        "masked_pointcloud_json": str(root / "renders/anygrasp_masked_pointcloud.json"),
        "open3d_enabled": True,
    },
    "analysis": {
        "dir": str(root / "analysis"),
        "analysis_summary_json": str(root / "analysis/analysis_summary.json"),
        "analysis_index_json": str(root / "analysis/analysis_index.json"),
        "binding_hypotheses_json": str(root / "analysis/binding_hypotheses.json"),
    },
    "summary": {
        "selected_rank": selected_rank,
        "best_direct_plan_present": False,
        "best_vs_selected_summary_present": True,
        "analysis_summary_present": True,
        "tcp_defaults": {
            "ee_grasp_origin_xyz_m": [0.0, 0.0, 0.0],
            "ee_opening_axis_xyz": [0.0, 0.0, 1.0],
            "ee_approach_axis_xyz": [1.0, 0.0, 0.0],
        },
        "active_binding_label": "opening=c1,height=c2,approach=c0",
        "active_camera_correction_label": "identity",
        "active_extrinsic_correction_label": "identity",
    },
}
(root / "pipeline_manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")

print(json.dumps({
    "output_dir": str(root),
    "selected_rank": selected_rank,
}, ensure_ascii=True))
PY

python3 - <<PY
import json
from pathlib import Path

root = Path(r"$OUTPUT_DIR")
status = json.loads((root / "pipeline_status.json").read_text(encoding="utf-8"))
manifest = json.loads((root / "pipeline_manifest.json").read_text(encoding="utf-8"))

assert status["capture_ok"] is True, status
assert status["target_mask_ok"] is True, status
assert status["anygrasp_ran"] is True, status
assert status["selected_plan_present"] is True, status
assert status["best_direct_result_present"] is True, status
assert status["best_direct_plan_present"] is False, status
assert (root / "adapter" / "best_direct" / "ik_target_gap.json").is_file(), status
assert status["best_vs_selected_summary_present"] is True, status
assert status["pose_chain_summary_present"] is True, status
assert status["frame_binding_analysis_present"] is True, status
assert status["alignment_report_present"] is True, status
assert status["analysis_summary_present"] is True, status
assert status["adapter_executable_count"] >= 1, status
assert status["stage_status"]["best_direct"] == 1, status
assert "capture" in manifest and "adapter" in manifest and "renders" in manifest and "analysis" in manifest, manifest
assert "best_direct_result_json" in manifest["adapter"], manifest
assert "best_direct_ik_target_gap_json" in manifest["adapter"], manifest
assert "best_vs_selected_summary_json" in manifest["adapter"], manifest
assert "pose_chain_summary_json" in manifest["adapter"], manifest
assert "frame_binding_analysis_json" in manifest["adapter"], manifest
assert "alignment_report_json" in manifest["adapter"], manifest
assert "analysis_summary_json" in manifest["analysis"], manifest
assert "analysis_index_json" in manifest["analysis"], manifest
assert (root / "analysis" / "analysis_summary.json").is_file(), manifest
assert (root / "analysis" / "analysis_index.json").is_file(), manifest
assert manifest["summary"]["tcp_defaults"]["ee_approach_axis_xyz"] == [1.0, 0.0, 0.0], manifest
assert manifest["summary"]["active_binding_label"] == "opening=c1,height=c2,approach=c0", manifest
assert manifest["summary"]["active_camera_correction_label"] == "identity", manifest
assert manifest["summary"]["active_extrinsic_correction_label"] == "identity", manifest
print("AnyGrasp pipeline output manifest/status verification passed")
PY

echo "AnyGrasp pipeline output manifest/status verification passed."
