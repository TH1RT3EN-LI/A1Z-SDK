#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
DOCKER_USER="${A1Z_CONTAINER_DOCKER_USER:-$(id -u):$(id -g)}"
ANYGRASP_SDK_DIR="${A1Z_ANYGRASP_SDK_DIR:-/workspace/A1Z/vendor/vision/anygrasp_sdk}"
ANYGRASP_CKPT="${A1Z_ANYGRASP_DETECTION_CKPT:-/workspace/A1Z/runtime/models/anygrasp/checkpoint_detection.tar}"
ANYGRASP_LICENSE_DIR="${A1Z_ANYGRASP_LICENSE_DIR:-/workspace/A1Z/runtime/licenses/anygrasp}"
ANYGRASP_IFCONFIG_SNAPSHOT="${A1Z_ANYGRASP_IFCONFIG_SNAPSHOT:-/workspace/A1Z/runtime/anygrasp/ifconfig.snapshot}"
ANYGRASP_BINDING_LABEL="${A1Z_ANYGRASP_BINDING_LABEL:-opening=c1,height=c2,approach=c0}"
ANYGRASP_CAMERA_CORRECTION_LABEL="${A1Z_ANYGRASP_CAMERA_CORRECTION_LABEL:-identity}"
ANYGRASP_EXTRINSIC_CORRECTION_LABEL="${A1Z_ANYGRASP_EXTRINSIC_CORRECTION_LABEL:-identity}"
ANYGRASP_EE_GRASP_ORIGIN="${A1Z_ANYGRASP_EE_GRASP_ORIGIN:-[0.0, 0.0, 0.0]}"
ANYGRASP_EE_OPENING_AXIS="${A1Z_ANYGRASP_EE_OPENING_AXIS:-[0.0, 0.0, 1.0]}"
ANYGRASP_EE_APPROACH_AXIS="${A1Z_ANYGRASP_EE_APPROACH_AXIS:-[1.0, 0.0, 0.0]}"
REQUIRE_CURRENT_JOINTS=0

POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --binding-label)
      ANYGRASP_BINDING_LABEL="${2:?missing value for --binding-label}"
      shift 2
      ;;
    --camera-correction-label)
      ANYGRASP_CAMERA_CORRECTION_LABEL="${2:?missing value for --camera-correction-label}"
      shift 2
      ;;
    --extrinsic-correction-label)
      ANYGRASP_EXTRINSIC_CORRECTION_LABEL="${2:?missing value for --extrinsic-correction-label}"
      shift 2
      ;;
    --ee-grasp-origin-xyz-m)
      ANYGRASP_EE_GRASP_ORIGIN="${2:?missing value for --ee-grasp-origin-xyz-m}"
      shift 2
      ;;
    --ee-opening-axis-xyz)
      ANYGRASP_EE_OPENING_AXIS="${2:?missing value for --ee-opening-axis-xyz}"
      shift 2
      ;;
    --ee-approach-axis-xyz)
      ANYGRASP_EE_APPROACH_AXIS="${2:?missing value for --ee-approach-axis-xyz}"
      shift 2
      ;;
    --require-current-joints)
      REQUIRE_CURRENT_JOINTS=1
      shift
      ;;
    -h|--help)
  cat <<'EOF'
usage: replay_anygrasp_from_capture.sh [--binding-label <label>] [--camera-correction-label <label>] [--extrinsic-correction-label <label>] [--ee-grasp-origin-xyz-m <json>] [--ee-opening-axis-xyz <json>] [--ee-approach-axis-xyz <json>] [--require-current-joints] <source_pipeline_dir> [output_dir]

Replay one existing capture/target-mask directory through AnyGrasp + adapter + best_direct + analysis outputs.
EOF
      exit 0
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}"

SOURCE_DIR="${1:-}"
if [[ -z "$SOURCE_DIR" ]]; then
  echo "usage: $0 [--binding-label <label>] [--camera-correction-label <label>] [--extrinsic-correction-label <label>] [--ee-grasp-origin-xyz-m <json>] [--ee-opening-axis-xyz <json>] [--ee-approach-axis-xyz <json>] [--require-current-joints] <source_pipeline_dir> [output_dir]" >&2
  exit 2
fi

normalize_workspace_path() {
  local raw="$1"
  raw="${raw%/}"
  if [[ "$raw" == /workspace/A1Z/* ]]; then
    printf '%s\n' "$ROOT_DIR/${raw#/workspace/A1Z/}"
  else
    printf '%s\n' "$raw"
  fi
}

SOURCE_DIR="$(normalize_workspace_path "$SOURCE_DIR")"
OUTPUT_DIR_RAW="${2:-${SOURCE_DIR}_replay_anygrasp}"
OUTPUT_DIR="$(normalize_workspace_path "$OUTPUT_DIR_RAW")"
SOURCE_WS="/workspace/A1Z/${SOURCE_DIR#$ROOT_DIR/}"
OUTPUT_WS="/workspace/A1Z/${OUTPUT_DIR#$ROOT_DIR/}"
CAPTURE_DIR="$SOURCE_DIR/capture"
TARGET_MASK_DIR="$SOURCE_DIR/target_mask"
ANYGRASP_DIR="$OUTPUT_WS/anygrasp_from_mask"
ADAPTER_DIR="$OUTPUT_WS/adapter"
RENDERS_DIR="$OUTPUT_WS/renders"
HOST_OUTPUT_DIR="$OUTPUT_DIR"
BEST_DIRECT_PLAN_PRESENT=0
CAPTURE_STATUS=-1
TARGET_MASK_STATUS=-1
EXTRINSIC_STATUS=-1
ANYGRASP_STATUS=-1
ADAPTER_STATUS=-1
BEST_DIRECT_STATUS=-1
CURRENT_JOINTS_ARG=()

if [[ -f "$CAPTURE_DIR/rgb.npy" && -f "$CAPTURE_DIR/depth_m.npy" ]]; then
  CAPTURE_STATUS=0
else
  CAPTURE_STATUS=2
fi
if [[ -f "$TARGET_MASK_DIR/selection/selected_mask.npy" && -f "$TARGET_MASK_DIR/selection/selection.json" ]]; then
  TARGET_MASK_STATUS=0
else
  TARGET_MASK_STATUS=2
fi
if [[ -f "$CAPTURE_DIR/extrinsic_camera_to_base.npy" ]]; then
  EXTRINSIC_STATUS=0
else
  EXTRINSIC_STATUS=2
fi
if [[ -f "$CAPTURE_DIR/current_joints_rad.json" ]]; then
  CURRENT_JOINTS_ARG=(--current-joints-rad "$SOURCE_WS/capture/current_joints_rad.json")
elif [[ "$REQUIRE_CURRENT_JOINTS" == "1" ]]; then
  echo "error: source capture is missing required current_joints_rad.json: $CAPTURE_DIR/current_joints_rad.json" >&2
  exit 4
fi

mkdir -p \
  "$HOST_OUTPUT_DIR/anygrasp_from_mask" \
  "$HOST_OUTPUT_DIR/adapter" \
  "$HOST_OUTPUT_DIR/analysis" \
  "$HOST_OUTPUT_DIR/renders"

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

"$ROOT_DIR/scripts/freeze_anygrasp_machine_fingerprint.sh" "${ANYGRASP_IFCONFIG_SNAPSHOT/#\/workspace\/A1Z/$ROOT_DIR}"

if docker exec \
  -u "$DOCKER_USER" \
  -e HOME="/tmp/a1z-home-$(id -u)" \
  -e MPLCONFIGDIR="/tmp/a1z-mpl-$(id -u)" \
  -e A1Z_ANYGRASP_RGB="$SOURCE_WS/capture/rgb.npy" \
  -e A1Z_ANYGRASP_DEPTH="$SOURCE_WS/capture/depth_m.npy" \
  -e A1Z_ANYGRASP_INTRINSICS="$SOURCE_WS/capture/intrinsics.json" \
  -e A1Z_ANYGRASP_SELECTION_JSON="$SOURCE_WS/target_mask/selection/selection.json" \
  -e A1Z_ANYGRASP_OUTPUT_DIR="$ANYGRASP_DIR" \
  -e A1Z_ANYGRASP_SDK_DIR="$ANYGRASP_SDK_DIR" \
  -e A1Z_ANYGRASP_CKPT="$ANYGRASP_CKPT" \
  -e A1Z_ANYGRASP_LICENSE_DIR="$ANYGRASP_LICENSE_DIR" \
  -e A1Z_ANYGRASP_IFCONFIG_SNAPSHOT="$ANYGRASP_IFCONFIG_SNAPSHOT" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source /opt/venvs/a1z-vision/bin/activate
    if [[ -f "$A1Z_ANYGRASP_IFCONFIG_SNAPSHOT" ]]; then
      tmp_anygrasp_bin="/tmp/a1z-anygrasp-bin-$(id -u)"
      mkdir -p "$tmp_anygrasp_bin"
      cat >"$tmp_anygrasp_bin/ifconfig" <<EOF
#!/usr/bin/env bash
cat "$A1Z_ANYGRASP_IFCONFIG_SNAPSHOT"
EOF
      chmod +x "$tmp_anygrasp_bin/ifconfig"
      export PATH="$tmp_anygrasp_bin:$PATH"
    fi
    cd /workspace/A1Z
    python3 /workspace/A1Z/scripts/run_anygrasp_from_selected_mask.py \
      --rgb "$A1Z_ANYGRASP_RGB" \
      --depth "$A1Z_ANYGRASP_DEPTH" \
      --intrinsics "$A1Z_ANYGRASP_INTRINSICS" \
      --selection-json "$A1Z_ANYGRASP_SELECTION_JSON" \
      --output-dir "$A1Z_ANYGRASP_OUTPUT_DIR" \
      --sdk-dir "$A1Z_ANYGRASP_SDK_DIR" \
      --checkpoint-path "$A1Z_ANYGRASP_CKPT" \
      --license-dir "$A1Z_ANYGRASP_LICENSE_DIR"
  '
then
  ANYGRASP_STATUS=0
else
  ANYGRASP_STATUS=$?
fi

if [[ -f "$CAPTURE_DIR/extrinsic_camera_to_base.npy" ]]; then
  if "$ROOT_DIR/scripts/run_anygrasp_adapter_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$SOURCE_WS/capture/extrinsic_camera_to_base.npy" \
    "${CURRENT_JOINTS_ARG[@]}" \
    --output-dir "$ADAPTER_DIR" \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS" \
    --backend anygrasp_replay
  then
    ADAPTER_STATUS=0
  else
    ADAPTER_STATUS=$?
  fi

  if "$ROOT_DIR/scripts/run_anygrasp_best_plan_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$SOURCE_WS/capture/extrinsic_camera_to_base.npy" \
    "${CURRENT_JOINTS_ARG[@]}" \
    --output-dir "$ADAPTER_DIR/best_direct" \
    --grasp-rank 0 \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS" \
    --backend anygrasp_best_direct_replay
  then
    BEST_DIRECT_STATUS=0
  else
    BEST_DIRECT_STATUS=$?
  fi
  "$ROOT_DIR/scripts/summarize_anygrasp_pose_chain_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$SOURCE_WS/capture/extrinsic_camera_to_base.npy" \
    --output "$ADAPTER_DIR/anygrasp_pose_chain_summary.json" \
    --top-k 5 \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS" || true
  "$ROOT_DIR/scripts/analyze_anygrasp_frame_bindings_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$SOURCE_WS/capture/extrinsic_camera_to_base.npy" \
    --output "$ADAPTER_DIR/anygrasp_frame_binding_analysis.json" \
    --grasp-rank 0 \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS" || true
  if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_adapter_result.json" && -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/best_direct/anygrasp_best_direct_result.json" ]]; then
    "$ROOT_DIR/scripts/summarize_anygrasp_pose_comparison_in_container.sh" \
      --adapter-result "$ADAPTER_DIR/anygrasp_adapter_result.json" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/best_vs_selected_summary.json" || true
  fi
  if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_pose_chain_summary.json" && -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_frame_binding_analysis.json" && -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/best_direct/anygrasp_best_direct_result.json" ]]; then
    "$ROOT_DIR/scripts/summarize_anygrasp_alignment_report_in_container.sh" \
      --pose-chain "$ADAPTER_DIR/anygrasp_pose_chain_summary.json" \
      --frame-binding-analysis "$ADAPTER_DIR/anygrasp_frame_binding_analysis.json" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/anygrasp_alignment_report.json" || true
  fi
  if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/best_direct/anygrasp_best_direct_result.json" ]]; then
    "$ROOT_DIR/scripts/summarize_anygrasp_ik_target_gap_in_container.sh" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/best_direct/ik_target_gap.json" || true
    "$ROOT_DIR/scripts/scan_anygrasp_mapping_hypotheses_in_container.sh" \
      --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
      --extrinsic-camera-to-base "$SOURCE_WS/capture/extrinsic_camera_to_base.npy" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/mapping_hypotheses.json" || true
  fi
else
  ADAPTER_STATUS=2
  BEST_DIRECT_STATUS=2
fi

SELECTED_RANK=-1
if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_adapter_result.json" ]]; then
  SELECTED_RANK="$(python3 - <<PY
import json
from pathlib import Path
result_path = Path(r"$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_adapter_result.json")
payload = json.loads(result_path.read_text(encoding="utf-8"))
selected_id = payload.get("summary", {}).get("selected_candidate_id")
selected = None if not selected_id else next((c for c in payload.get("candidates", []) if c.get("candidate_id") == selected_id), None)
print(-1 if selected is None else int(selected.get("rank", -1)))
PY
)"
fi

if "$ROOT_DIR/scripts/a1z_vision_python_in_container.sh" -c "import json; from pathlib import Path; p=Path('$ANYGRASP_DIR/anygrasp/anygrasp_result.json'); d=json.loads(p.read_text(encoding='utf-8')); raise SystemExit(0 if d.get('ran') and d.get('top_grasps') else 1)" >/dev/null 2>&1; then
  if ! "$ROOT_DIR/scripts/render_anygrasp_open3d_in_container.sh" \
    --points "$ANYGRASP_DIR/masked_point_cloud/points.npy" \
    --colors "$ANYGRASP_DIR/masked_point_cloud/colors.npy" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --output-image "$RENDERS_DIR/anygrasp_graspgroup_all.png" \
    --output-json "$RENDERS_DIR/anygrasp_graspgroup_all.json" \
    --top-k 0 \
    --crop-radius-m -1 \
    --selected-gripper-color "[0.0, 0.2, 1.0]"
  then
    echo "warning: failed to render anygrasp_graspgroup_all" >&2
  fi

  if ! "$ROOT_DIR/scripts/render_anygrasp_open3d_in_container.sh" \
    --points "$ANYGRASP_DIR/masked_point_cloud/points.npy" \
    --colors "$ANYGRASP_DIR/masked_point_cloud/colors.npy" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --output-image "$RENDERS_DIR/anygrasp_masked_pointcloud.png" \
    --output-json "$RENDERS_DIR/anygrasp_masked_pointcloud.json" \
    --camera-view \
    --intrinsics "$SOURCE_WS/capture/intrinsics.json" \
    --crop-radius-m -1 \
    --disable-offscreen-renderer
  then
    echo "warning: failed to render anygrasp_masked_pointcloud" >&2
  fi

  if ! "$ROOT_DIR/scripts/render_anygrasp_open3d_in_container.sh" \
    --points "$ANYGRASP_DIR/masked_point_cloud/points.npy" \
    --colors "$ANYGRASP_DIR/masked_point_cloud/colors.npy" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --output-image "$RENDERS_DIR/anygrasp_best.png" \
    --output-json "$RENDERS_DIR/anygrasp_best.json" \
    --best-only \
    --camera-view \
    --intrinsics "$SOURCE_WS/capture/intrinsics.json" \
    --crop-radius-m -1 \
    --disable-offscreen-renderer
  then
    echo "warning: failed to render anygrasp_best" >&2
  fi

  if [[ "$SELECTED_RANK" != "-1" ]]; then
    if ! "$ROOT_DIR/scripts/render_anygrasp_open3d_in_container.sh" \
      --points "$ANYGRASP_DIR/masked_point_cloud/points.npy" \
      --colors "$ANYGRASP_DIR/masked_point_cloud/colors.npy" \
      --depth "$SOURCE_WS/capture/depth_m.npy" \
      --mask "$SOURCE_WS/target_mask/selection/selected_mask.npy" \
      --highlight-mask \
      --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
      --binding-label "$ANYGRASP_BINDING_LABEL" \
      --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
      --output-image "$RENDERS_DIR/anygrasp_selected.png" \
      --output-json "$RENDERS_DIR/anygrasp_selected.json" \
      --selected-rank "$SELECTED_RANK" \
      --selected-only \
      --camera-view \
      --intrinsics "$SOURCE_WS/capture/intrinsics.json" \
      --crop-radius-m -1 \
      --disable-offscreen-renderer \
      --selected-gripper-color "[0.0, 0.2, 1.0]" \
      --mask-highlight-color "[0.0, 1.0, 0.2]"
    then
      echo "warning: failed to render anygrasp_selected" >&2
    fi
  fi
fi

python3 - <<PY
import json
from pathlib import Path

output_dir = Path(r"$HOST_OUTPUT_DIR")
source_dir = Path(r"$SOURCE_DIR")
anygrasp_result_path = output_dir / "anygrasp_from_mask" / "anygrasp" / "anygrasp_result.json"
adapter_result_path = output_dir / "adapter" / "anygrasp_adapter_result.json"

anygrasp_result = {}
if anygrasp_result_path.is_file():
    anygrasp_result = json.loads(anygrasp_result_path.read_text(encoding="utf-8"))
adapter_result = {}
if adapter_result_path.is_file():
    adapter_result = json.loads(adapter_result_path.read_text(encoding="utf-8"))

status_payload = {
    "source_dir": str(source_dir),
    "replay_mode": True,
    "anygrasp_ran": bool(anygrasp_result.get("ran", False)),
    "anygrasp_grasp_count": int(anygrasp_result.get("grasp_count", 0) or 0),
    "anygrasp_error": str(anygrasp_result.get("error", "")),
    "adapter_result_present": adapter_result_path.is_file(),
    "selected_plan_present": (output_dir / "adapter" / "selected_plan.json").is_file(),
    "best_direct_result_present": (output_dir / "adapter" / "best_direct" / "anygrasp_best_direct_result.json").is_file(),
    "best_direct_plan_present": (output_dir / "adapter" / "best_direct" / "selected_plan.json").is_file(),
    "best_vs_selected_summary_present": (output_dir / "adapter" / "best_vs_selected_summary.json").is_file(),
    "pose_chain_summary_present": (output_dir / "adapter" / "anygrasp_pose_chain_summary.json").is_file(),
    "frame_binding_analysis_present": (output_dir / "adapter" / "anygrasp_frame_binding_analysis.json").is_file(),
    "alignment_report_present": (output_dir / "adapter" / "anygrasp_alignment_report.json").is_file(),
    "analysis_summary_present": (output_dir / "analysis" / "analysis_summary.json").is_file(),
    "selected_rank": int(r"$SELECTED_RANK"),
    "stage_status": {
        "capture": int(r"$CAPTURE_STATUS"),
        "target_mask": int(r"$TARGET_MASK_STATUS"),
        "extrinsic": int(r"$EXTRINSIC_STATUS"),
        "anygrasp": int(r"$ANYGRASP_STATUS"),
        "adapter": int(r"$ADAPTER_STATUS"),
        "best_direct": int(r"$BEST_DIRECT_STATUS"),
    },
}
(output_dir / "pipeline_status.json").write_text(json.dumps(status_payload, ensure_ascii=True, indent=2), encoding="utf-8")

manifest = {
    "source_dir": str(source_dir),
    "replay_mode": True,
    "capture": {
        "dir": str(source_dir / "capture"),
        "rgb_npy": str(source_dir / "capture" / "rgb.npy"),
        "depth_npy": str(source_dir / "capture" / "depth_m.npy"),
        "intrinsics_json": str(source_dir / "capture" / "intrinsics.json"),
        "extrinsic_camera_to_base_npy": str(source_dir / "capture" / "extrinsic_camera_to_base.npy"),
        "observation_json": str(source_dir / "capture" / "observation.json"),
        "current_joints_rad_json": str(source_dir / "capture" / "current_joints_rad.json"),
    },
    "target_mask": {
        "dir": str(source_dir / "target_mask"),
        "selection_json": str(source_dir / "target_mask" / "selection" / "selection.json"),
        "selected_mask_npy": str(source_dir / "target_mask" / "selection" / "selected_mask.npy"),
        "overlay_candidates_png": str(source_dir / "target_mask" / "selection" / "overlay_object_candidates.png"),
    },
    "anygrasp": {
        "dir": str(output_dir / "anygrasp_from_mask"),
        "pipeline_result_json": str(output_dir / "anygrasp_from_mask" / "pipeline_result.json"),
        "masked_point_cloud_json": str(output_dir / "anygrasp_from_mask" / "masked_point_cloud" / "masked_point_cloud.json"),
        "points_npy": str(output_dir / "anygrasp_from_mask" / "masked_point_cloud" / "points.npy"),
        "colors_npy": str(output_dir / "anygrasp_from_mask" / "masked_point_cloud" / "colors.npy"),
        "result_json": str(output_dir / "anygrasp_from_mask" / "anygrasp" / "anygrasp_result.json"),
    },
    "adapter": {
        "dir": str(output_dir / "adapter"),
        "result_json": str(output_dir / "adapter" / "anygrasp_adapter_result.json"),
        "selected_plan_json": str(output_dir / "adapter" / "selected_plan.json"),
        "best_direct_dir": str(output_dir / "adapter" / "best_direct"),
        "best_direct_result_json": str(output_dir / "adapter" / "best_direct" / "anygrasp_best_direct_result.json"),
        "best_direct_plan_json": str(output_dir / "adapter" / "best_direct" / "selected_plan.json"),
        "best_direct_ik_target_gap_json": str(output_dir / "adapter" / "best_direct" / "ik_target_gap.json"),
        "best_vs_selected_summary_json": str(output_dir / "adapter" / "best_vs_selected_summary.json"),
        "pose_chain_summary_json": str(output_dir / "adapter" / "anygrasp_pose_chain_summary.json"),
        "frame_binding_analysis_json": str(output_dir / "adapter" / "anygrasp_frame_binding_analysis.json"),
        "alignment_report_json": str(output_dir / "adapter" / "anygrasp_alignment_report.json"),
        "mapping_hypotheses_json": str(output_dir / "adapter" / "mapping_hypotheses.json"),
    },
    "renders": {
        "dir": str(output_dir / "renders"),
        "graspgroup_all_image": str(output_dir / "renders" / "anygrasp_graspgroup_all.png"),
        "graspgroup_all_json": str(output_dir / "renders" / "anygrasp_graspgroup_all.json"),
        "selected_grasp_image": str(output_dir / "renders" / "anygrasp_selected.png"),
        "selected_grasp_json": str(output_dir / "renders" / "anygrasp_selected.json"),
        "best_grasp_image": str(output_dir / "renders" / "anygrasp_best.png"),
        "best_grasp_json": str(output_dir / "renders" / "anygrasp_best.json"),
        "masked_pointcloud_image": str(output_dir / "renders" / "anygrasp_masked_pointcloud.png"),
        "masked_pointcloud_json": str(output_dir / "renders" / "anygrasp_masked_pointcloud.json"),
    },
    "analysis": {
        "dir": str(output_dir / "analysis"),
        "analysis_summary_json": str(output_dir / "analysis" / "analysis_summary.json"),
        "analysis_index_json": str(output_dir / "analysis" / "analysis_index.json"),
        "binding_hypotheses_json": str(output_dir / "analysis" / "binding_hypotheses.json"),
    },
    "summary": {
        "selected_rank": int(r"$SELECTED_RANK"),
        "best_direct_plan_present": (output_dir / "adapter" / "best_direct" / "selected_plan.json").is_file(),
        "best_vs_selected_summary_present": (output_dir / "adapter" / "best_vs_selected_summary.json").is_file(),
        "analysis_summary_present": (output_dir / "analysis" / "analysis_summary.json").is_file(),
        "tcp_defaults": {
            "ee_grasp_origin_xyz_m": json.loads(r'''$ANYGRASP_EE_GRASP_ORIGIN'''),
            "ee_opening_axis_xyz": json.loads(r'''$ANYGRASP_EE_OPENING_AXIS'''),
            "ee_approach_axis_xyz": json.loads(r'''$ANYGRASP_EE_APPROACH_AXIS'''),
        },
        "active_binding_label": r"$ANYGRASP_BINDING_LABEL",
        "active_camera_correction_label": r"$ANYGRASP_CAMERA_CORRECTION_LABEL",
        "active_extrinsic_correction_label": r"$ANYGRASP_EXTRINSIC_CORRECTION_LABEL",
    },
}
(output_dir / "pipeline_manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
print(json.dumps({"output_dir": str(output_dir)}, ensure_ascii=True))
PY

if ! "$ROOT_DIR/scripts/analyze_anygrasp_output_dir.sh" "$OUTPUT_DIR" >/dev/null; then
  echo "warning: failed to generate anygrasp analysis summary" >&2
fi

python3 - <<PY
import json
from pathlib import Path

output_dir = Path(r"$HOST_OUTPUT_DIR")
status_path = output_dir / "pipeline_status.json"
manifest_path = output_dir / "pipeline_manifest.json"

if status_path.is_file():
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["analysis_summary_present"] = (output_dir / "analysis" / "analysis_summary.json").is_file()
    status_path.write_text(json.dumps(status, ensure_ascii=True, indent=2), encoding="utf-8")

if manifest_path.is_file():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("summary", {})
    manifest["summary"]["analysis_summary_present"] = (output_dir / "analysis" / "analysis_summary.json").is_file()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
PY

echo "anygrasp replay output: $OUTPUT_DIR"
