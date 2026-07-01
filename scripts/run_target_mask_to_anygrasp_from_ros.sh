#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
DOCKER_USER="${A1Z_CONTAINER_DOCKER_USER:-$(id -u):$(id -g)}"
CONTAINER_ENV_FILE="/workspace/A1Z/config/a1z_vlm.env"
SAM_CKPT="${A1Z_SAM2_DEFAULT_CKPT:-/workspace/A1Z/runtime/models/sam2/sam2.1_hiera_small.pt}"
ANYGRASP_SDK_DIR="${A1Z_ANYGRASP_SDK_DIR:-/workspace/A1Z/vendor/vision/anygrasp_sdk}"
ANYGRASP_CKPT="${A1Z_ANYGRASP_DETECTION_CKPT:-/workspace/A1Z/runtime/models/anygrasp/checkpoint_detection.tar}"
ANYGRASP_LICENSE_DIR="${A1Z_ANYGRASP_LICENSE_DIR:-/workspace/A1Z/runtime/licenses/anygrasp}"
ANYGRASP_IFCONFIG_SNAPSHOT="${A1Z_ANYGRASP_IFCONFIG_SNAPSHOT:-/workspace/A1Z/runtime/anygrasp/ifconfig.snapshot}"
ANYGRASP_BINDING_LABEL="${A1Z_ANYGRASP_BINDING_LABEL:-opening=c1,height=c2,approach=mc0}"
ANYGRASP_CAMERA_CORRECTION_LABEL="${A1Z_ANYGRASP_CAMERA_CORRECTION_LABEL:-identity}"
ANYGRASP_EXTRINSIC_CORRECTION_LABEL="${A1Z_ANYGRASP_EXTRINSIC_CORRECTION_LABEL:-identity}"
ANYGRASP_EE_GRASP_ORIGIN="${A1Z_ANYGRASP_EE_GRASP_ORIGIN:-[0.04, 0.0, 0.0]}"
ANYGRASP_EE_OPENING_AXIS="${A1Z_ANYGRASP_EE_OPENING_AXIS:-[0.0, 0.0, 1.0]}"
ANYGRASP_EE_APPROACH_AXIS="${A1Z_ANYGRASP_EE_APPROACH_AXIS:-[0.0, -1.0, 0.0]}"
ROS_CAPTURE_TIMEOUT_S="${A1Z_ROS_CAPTURE_TIMEOUT_S:-30}"
ROS_CAPTURE_RETRIES="${A1Z_ROS_CAPTURE_RETRIES:-3}"
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
usage: run_target_mask_to_anygrasp_from_ros.sh [--binding-label <label>] [--camera-correction-label <label>] [--extrinsic-correction-label <label>] [--ee-grasp-origin-xyz-m <json>] [--ee-opening-axis-xyz <json>] [--ee-approach-axis-xyz <json>] [--require-current-joints] '<instruction>' [output_dir] [provider]

Pipeline:
  natural-language target -> ROS RGB-D capture -> target mask -> AnyGrasp -> adapter + best_direct + analysis + renders
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

INSTRUCTION="${1:-}"
if [[ -z "$INSTRUCTION" ]]; then
  echo "usage: $0 [--binding-label <label>] [--camera-correction-label <label>] [--extrinsic-correction-label <label>] [--ee-grasp-origin-xyz-m <json>] [--ee-opening-axis-xyz <json>] [--ee-approach-axis-xyz <json>] [--require-current-joints] '<instruction>' [output_dir] [provider]" >&2
  exit 2
fi

OUTPUT_DIR="${2:-/workspace/A1Z/runtime/target_mask_to_anygrasp/from_ros_live}"
PROVIDER="${3:-kimi}"
CAPTURE_DIR="$OUTPUT_DIR/capture"
TARGET_MASK_DIR="$OUTPUT_DIR/target_mask"
ANYGRASP_DIR="$OUTPUT_DIR/anygrasp_from_mask"
ADAPTER_DIR="$OUTPUT_DIR/adapter"
RENDERS_DIR="$OUTPUT_DIR/renders"
HOST_OUTPUT_DIR="$ROOT_DIR/${OUTPUT_DIR#/workspace/A1Z/}"
CAPTURE_STATUS=-1
TARGET_MASK_STATUS=-1
ANYGRASP_STATUS=-1
EXTRINSIC_STATUS=-1
ADAPTER_STATUS=-1
SELECTED_RANK=-1
BEST_DIRECT_STATUS=-1
BEST_DIRECT_PLAN_PRESENT=0
CURRENT_JOINTS_ARG=()

wait_for_ros_tf() {
  docker exec \
    -e HOME="/tmp/a1z-home-$(id -u)" \
    -e ROS_LOG_DIR="/tmp/a1z-home-$(id -u)/.ros/log" \
    "$ROS_CONTAINER_NAME" \
    bash -lc '
      set -euo pipefail
      mkdir -p "$HOME/.ros/log"
      set +u
      source /opt/ros/humble/setup.bash
      source /workspace/A1Z/ros2_ws/install/setup.bash
      set -u
      python3 /workspace/A1Z/scripts/resolve_ros_tf.py \
        --source-frame-id d405_color_optical_frame \
        --target-frame-id robot_base_frame \
        --output-path /tmp/a1z_ros_tf_ready.npy \
        --timeout-s 8.0 \
        --cache-time-s 10.0 \
        --allow-latest >/dev/null
    '
}

mkdir -p \
  "$HOST_OUTPUT_DIR/capture" \
  "$HOST_OUTPUT_DIR/target_mask" \
  "$HOST_OUTPUT_DIR/anygrasp_from_mask" \
  "$HOST_OUTPUT_DIR/adapter" \
  "$HOST_OUTPUT_DIR/analysis" \
  "$HOST_OUTPUT_DIR/renders"

write_pipeline_artifacts() {
  set +e
  python3 - <<PY
import json
from pathlib import Path

output_dir = Path(r"$HOST_OUTPUT_DIR")
anygrasp_result_path = output_dir / "anygrasp_from_mask" / "anygrasp" / "anygrasp_result.json"
adapter_result_path = output_dir / "adapter" / "anygrasp_adapter_result.json"

anygrasp_result = {}
if anygrasp_result_path.is_file():
    anygrasp_result = json.loads(anygrasp_result_path.read_text(encoding="utf-8"))
adapter_result = {}
if adapter_result_path.is_file():
    adapter_result = json.loads(adapter_result_path.read_text(encoding="utf-8"))

status_payload = {
    "capture_ok": (output_dir / "capture" / "rgb.npy").is_file() and (output_dir / "capture" / "depth_m.npy").is_file(),
    "target_mask_ok": (output_dir / "target_mask" / "selection" / "selected_mask.npy").is_file(),
    "anygrasp_ran": bool(anygrasp_result.get("ran", False)),
    "anygrasp_grasp_count": int(anygrasp_result.get("grasp_count", 0) or 0),
    "anygrasp_error": str(anygrasp_result.get("error", "")),
    "adapter_result_present": adapter_result_path.is_file(),
    "selected_plan_present": (output_dir / "adapter" / "selected_plan.json").is_file(),
    "adapter_selected_candidate_id": adapter_result.get("summary", {}).get("selected_candidate_id"),
    "adapter_executable_count": adapter_result.get("summary", {}).get("executable_count"),
    "selected_rank": int(r"$SELECTED_RANK"),
    "best_direct_result_present": (output_dir / "adapter" / "best_direct" / "anygrasp_best_direct_result.json").is_file(),
    "best_direct_plan_present": bool(int(r"$BEST_DIRECT_PLAN_PRESENT")),
    "best_vs_selected_summary_present": (output_dir / "adapter" / "best_vs_selected_summary.json").is_file(),
    "pose_chain_summary_present": (output_dir / "adapter" / "anygrasp_pose_chain_summary.json").is_file(),
    "frame_binding_analysis_present": (output_dir / "adapter" / "anygrasp_frame_binding_analysis.json").is_file(),
    "alignment_report_present": (output_dir / "adapter" / "anygrasp_alignment_report.json").is_file(),
    "analysis_summary_present": (output_dir / "analysis" / "analysis_summary.json").is_file(),
    "current_joints_required": bool(int(r"$REQUIRE_CURRENT_JOINTS")),
    "current_joints_present": (output_dir / "capture" / "current_joints_rad.json").is_file(),
    "stage_status": {
        "capture": int(r"$CAPTURE_STATUS"),
        "target_mask": int(r"$TARGET_MASK_STATUS"),
        "anygrasp": int(r"$ANYGRASP_STATUS"),
        "extrinsic": int(r"$EXTRINSIC_STATUS"),
        "adapter": int(r"$ADAPTER_STATUS"),
        "best_direct": int(r"$BEST_DIRECT_STATUS"),
    },
}
(output_dir / "pipeline_status.json").write_text(json.dumps(status_payload, ensure_ascii=True, indent=2), encoding="utf-8")

manifest = {
    "output_dir": str(output_dir),
    "capture": {
        "dir": str(output_dir / "capture"),
        "rgb_npy": str(output_dir / "capture" / "rgb.npy"),
        "depth_npy": str(output_dir / "capture" / "depth_m.npy"),
        "intrinsics_json": str(output_dir / "capture" / "intrinsics.json"),
        "extrinsic_camera_to_base_npy": str(output_dir / "capture" / "extrinsic_camera_to_base.npy"),
        "observation_json": str(output_dir / "capture" / "observation.json"),
        "current_joints_rad_json": str(output_dir / "capture" / "current_joints_rad.json"),
        "current_joints_required": bool(int(r"$REQUIRE_CURRENT_JOINTS")),
    },
    "target_mask": {
        "dir": str(output_dir / "target_mask"),
        "selection_json": str(output_dir / "target_mask" / "selection" / "selection.json"),
        "selected_mask_npy": str(output_dir / "target_mask" / "selection" / "selected_mask.npy"),
        "overlay_candidates_png": str(output_dir / "target_mask" / "selection" / "overlay_object_candidates.png"),
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
        "open3d_enabled": True,
    },
    "analysis": {
        "dir": str(output_dir / "analysis"),
        "analysis_summary_json": str(output_dir / "analysis" / "analysis_summary.json"),
        "analysis_index_json": str(output_dir / "analysis" / "analysis_index.json"),
        "binding_hypotheses_json": str(output_dir / "analysis" / "binding_hypotheses.json"),
    },
    "summary": {
        "selected_rank": int(r"$SELECTED_RANK"),
        "best_direct_plan_present": bool(int(r"$BEST_DIRECT_PLAN_PRESENT")),
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
        "capture_current_joints_required": bool(int(r"$REQUIRE_CURRENT_JOINTS")),
    },
}
(output_dir / "pipeline_manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
print(json.dumps({
    "pipeline_status": str(output_dir / "pipeline_status.json"),
    "pipeline_manifest": str(output_dir / "pipeline_manifest.json"),
}, ensure_ascii=True))
PY
}

on_exit() {
  write_pipeline_artifacts
}

trap on_exit EXIT

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

"$ROOT_DIR/scripts/freeze_anygrasp_machine_fingerprint.sh" "${ANYGRASP_IFCONFIG_SNAPSHOT/#\/workspace\/A1Z/$ROOT_DIR}"

if ! wait_for_ros_tf; then
  echo "error: robot_base_frame <- d405_color_optical_frame TF did not become available before capture" >&2
  exit 3
fi

if docker exec \
  -e HOME="/tmp/a1z-home-$(id -u)" \
  -e ROS_LOG_DIR="/tmp/a1z-home-$(id -u)/.ros/log" \
  "$ROS_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    mkdir -p "$HOME/.ros/log"
    set +u
    source /opt/ros/humble/setup.bash
    source /workspace/A1Z/ros2_ws/install/setup.bash
    set -u
    for attempt in $(seq 1 "'"$ROS_CAPTURE_RETRIES"'"); do
      if python3 /workspace/A1Z/scripts/capture_ros_rgbd.py \
        --target-frame-id robot_base_frame \
        --timeout-s "'"$ROS_CAPTURE_TIMEOUT_S"'" \
        --tf-lookup-timeout-s 5.0 \
        --fail-if-tf-unavailable \
        --output-dir "'"$CAPTURE_DIR"'"
      then
        exit 0
      fi
      if [[ "$attempt" -lt "'"$ROS_CAPTURE_RETRIES"'" ]]; then
        echo "capture_ros_rgbd retry $attempt/'"$ROS_CAPTURE_RETRIES"'" >&2
        sleep 1
      fi
    done
    exit 1
  '
then
  CAPTURE_STATUS=0
else
  CAPTURE_STATUS=$?
  exit "$CAPTURE_STATUS"
fi

if [[ -f "$HOST_OUTPUT_DIR/capture/current_joints_rad.json" ]]; then
  :
elif python3 "$ROOT_DIR/scripts/capture_a1z_current_joints.py" \
  --output-path "$HOST_OUTPUT_DIR/capture/current_joints_rad.json" >/dev/null 2>&1
then
  :
else
  if [[ "$REQUIRE_CURRENT_JOINTS" == "1" ]]; then
    echo "error: failed to capture required current_joints_rad.json from control server" >&2
    exit 4
  fi
  echo "warning: failed to capture current_joints_rad.json from control server" >&2
fi

if docker exec \
  -u "$DOCKER_USER" \
  -e HOME="/tmp/a1z-home-$(id -u)" \
  -e MPLCONFIGDIR="/tmp/a1z-mpl-$(id -u)" \
  -e A1Z_TARGET_INSTRUCTION="$INSTRUCTION" \
  -e A1Z_TARGET_IMAGE="$CAPTURE_DIR/color.png" \
  -e A1Z_TARGET_OUTPUT_DIR="$TARGET_MASK_DIR" \
  -e A1Z_TARGET_PROVIDER="$PROVIDER" \
  -e A1Z_TARGET_ENV_FILE="$CONTAINER_ENV_FILE" \
  -e A1Z_TARGET_SAM_CKPT="$SAM_CKPT" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source /opt/venvs/a1z-vision/bin/activate
    cd /workspace/A1Z
    python3 /workspace/A1Z/scripts/run_target_mask_pipeline.py \
      --instruction "$A1Z_TARGET_INSTRUCTION" \
      --image "$A1Z_TARGET_IMAGE" \
      --output-dir "$A1Z_TARGET_OUTPUT_DIR" \
      --env-file "$A1Z_TARGET_ENV_FILE" \
      --provider "$A1Z_TARGET_PROVIDER" \
      --sam-checkpoint "$A1Z_TARGET_SAM_CKPT"
  '
then
  TARGET_MASK_STATUS=0
else
  TARGET_MASK_STATUS=$?
  exit "$TARGET_MASK_STATUS"
fi

if docker exec \
  -u "$DOCKER_USER" \
  -e HOME="/tmp/a1z-home-$(id -u)" \
  -e MPLCONFIGDIR="/tmp/a1z-mpl-$(id -u)" \
  -e A1Z_ANYGRASP_RGB="$CAPTURE_DIR/rgb.npy" \
  -e A1Z_ANYGRASP_DEPTH="$CAPTURE_DIR/depth_m.npy" \
  -e A1Z_ANYGRASP_INTRINSICS="$CAPTURE_DIR/intrinsics.json" \
  -e A1Z_ANYGRASP_SELECTION_JSON="$TARGET_MASK_DIR/selection/selection.json" \
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

if [[ ! -f "$ROOT_DIR/${CAPTURE_DIR#/workspace/A1Z/}/extrinsic_camera_to_base.npy" ]]; then
  if ! docker exec \
    "$ROS_CONTAINER_NAME" \
    bash -lc '
      set -euo pipefail
      set +u
      source /opt/ros/humble/setup.bash
      source /workspace/A1Z/ros2_ws/install/setup.bash
      set -u
      python3 /workspace/A1Z/scripts/resolve_ros_tf.py \
        --observation-json "'"$CAPTURE_DIR/observation.json"'" \
        --target-frame-id robot_base_frame \
        --output-path "'"$CAPTURE_DIR/extrinsic_camera_to_base.npy"'" \
        --timeout-s 2.0 \
        --allow-latest
    '
  then
    EXTRINSIC_STATUS=$?
    echo "warning: failed to resolve extrinsic_camera_to_base.npy; adapter stage will be skipped if base-frame extrinsic remains unavailable" >&2
  else
    EXTRINSIC_STATUS=0
  fi
else
  EXTRINSIC_STATUS=0
fi
if [[ -f "$ROOT_DIR/${CAPTURE_DIR#/workspace/A1Z/}/current_joints_rad.json" ]]; then
  CURRENT_JOINTS_ARG=(--current-joints-rad "$CAPTURE_DIR/current_joints_rad.json")
fi

if [[ -f "$ROOT_DIR/${CAPTURE_DIR#/workspace/A1Z/}/extrinsic_camera_to_base.npy" ]]; then
  if "$ROOT_DIR/scripts/run_anygrasp_adapter_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$CAPTURE_DIR/extrinsic_camera_to_base.npy" \
    "${CURRENT_JOINTS_ARG[@]}" \
    --output-dir "$ADAPTER_DIR" \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS" \
      --backend anygrasp_ros_live
  then
    ADAPTER_STATUS=0
  else
    ADAPTER_STATUS=$?
  fi
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

  if "$ROOT_DIR/scripts/run_anygrasp_best_plan_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$CAPTURE_DIR/extrinsic_camera_to_base.npy" \
    "${CURRENT_JOINTS_ARG[@]}" \
    --output-dir "$ADAPTER_DIR/best_direct" \
    --grasp-rank 0 \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS" \
    --backend anygrasp_best_direct_ros_live
  then
    BEST_DIRECT_STATUS=0
  else
    BEST_DIRECT_STATUS=$?
  fi
  if ! "$ROOT_DIR/scripts/summarize_anygrasp_pose_chain_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$CAPTURE_DIR/extrinsic_camera_to_base.npy" \
    --output "$ADAPTER_DIR/anygrasp_pose_chain_summary.json" \
    --top-k 5 \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS"
  then
    echo "warning: failed to summarize anygrasp pose chain" >&2
  fi
  if ! "$ROOT_DIR/scripts/analyze_anygrasp_frame_bindings_in_container.sh" \
    --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
    --extrinsic-camera-to-base "$CAPTURE_DIR/extrinsic_camera_to_base.npy" \
    --output "$ADAPTER_DIR/anygrasp_frame_binding_analysis.json" \
    --grasp-rank 0 \
    --binding-label "$ANYGRASP_BINDING_LABEL" \
    --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
    --extrinsic-correction-label "$ANYGRASP_EXTRINSIC_CORRECTION_LABEL" \
    --ee-grasp-origin-xyz-m "$ANYGRASP_EE_GRASP_ORIGIN" \
    --ee-opening-axis-xyz "$ANYGRASP_EE_OPENING_AXIS" \
    --ee-approach-axis-xyz "$ANYGRASP_EE_APPROACH_AXIS"
  then
    echo "warning: failed to analyze anygrasp frame bindings" >&2
  fi
  if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/best_direct/selected_plan.json" ]]; then
    BEST_DIRECT_PLAN_PRESENT=1
  fi
  if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_adapter_result.json" && -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/best_direct/anygrasp_best_direct_result.json" ]]; then
    if ! "$ROOT_DIR/scripts/summarize_anygrasp_pose_comparison_in_container.sh" \
      --adapter-result "$ADAPTER_DIR/anygrasp_adapter_result.json" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/best_vs_selected_summary.json"
    then
      echo "warning: failed to summarize anygrasp best-vs-selected pose comparison" >&2
    fi
  fi
  if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_pose_chain_summary.json" && -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/anygrasp_frame_binding_analysis.json" && -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/best_direct/anygrasp_best_direct_result.json" ]]; then
    if ! "$ROOT_DIR/scripts/summarize_anygrasp_alignment_report_in_container.sh" \
      --pose-chain "$ADAPTER_DIR/anygrasp_pose_chain_summary.json" \
      --frame-binding-analysis "$ADAPTER_DIR/anygrasp_frame_binding_analysis.json" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/anygrasp_alignment_report.json"
    then
      echo "warning: failed to summarize anygrasp alignment report" >&2
    fi
  fi
  if [[ -f "$ROOT_DIR/${ADAPTER_DIR#/workspace/A1Z/}/best_direct/anygrasp_best_direct_result.json" ]]; then
    if ! "$ROOT_DIR/scripts/summarize_anygrasp_ik_target_gap_in_container.sh" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/best_direct/ik_target_gap.json"
    then
      echo "warning: failed to summarize anygrasp ik target gap" >&2
    fi
    if ! "$ROOT_DIR/scripts/scan_anygrasp_mapping_hypotheses_in_container.sh" \
      --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
      --extrinsic-camera-to-base "$CAPTURE_DIR/extrinsic_camera_to_base.npy" \
      --best-direct-result "$ADAPTER_DIR/best_direct/anygrasp_best_direct_result.json" \
      --output "$ADAPTER_DIR/mapping_hypotheses.json"
    then
      echo "warning: failed to scan anygrasp mapping hypotheses" >&2
    fi
  fi
else
  ADAPTER_STATUS=2
  BEST_DIRECT_STATUS=2
  echo "warning: skipping adapter stage because extrinsic_camera_to_base.npy is unavailable" >&2
fi

if [[ -f "$ROOT_DIR/${ANYGRASP_DIR#/workspace/A1Z/}/masked_point_cloud/points.npy" && -f "$ROOT_DIR/${ANYGRASP_DIR#/workspace/A1Z/}/anygrasp/anygrasp_result.json" ]]; then
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
      --intrinsics "$CAPTURE_DIR/intrinsics.json" \
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
      --intrinsics "$CAPTURE_DIR/intrinsics.json" \
      --crop-radius-m -1 \
      --disable-offscreen-renderer
    then
      echo "warning: failed to render anygrasp_best" >&2
    fi

    if [[ "$SELECTED_RANK" != "-1" ]]; then
      if ! "$ROOT_DIR/scripts/render_anygrasp_open3d_in_container.sh" \
        --points "$ANYGRASP_DIR/masked_point_cloud/points.npy" \
        --colors "$ANYGRASP_DIR/masked_point_cloud/colors.npy" \
        --depth "$CAPTURE_DIR/depth_m.npy" \
        --mask "$TARGET_MASK_DIR/selection/selected_mask.npy" \
        --highlight-mask \
        --result-json "$ANYGRASP_DIR/anygrasp/anygrasp_result.json" \
        --binding-label "$ANYGRASP_BINDING_LABEL" \
        --camera-correction-label "$ANYGRASP_CAMERA_CORRECTION_LABEL" \
        --output-image "$RENDERS_DIR/anygrasp_selected.png" \
        --output-json "$RENDERS_DIR/anygrasp_selected.json" \
        --selected-rank "$SELECTED_RANK" \
        --selected-only \
        --camera-view \
        --intrinsics "$CAPTURE_DIR/intrinsics.json" \
        --crop-radius-m -1 \
        --disable-offscreen-renderer \
        --selected-gripper-color "[0.0, 0.2, 1.0]" \
        --mask-highlight-color "[0.0, 1.0, 0.2]"
      then
        echo "warning: failed to render anygrasp_selected" >&2
      fi
    fi
  fi
fi

write_pipeline_artifacts

if ! "$ROOT_DIR/scripts/analyze_anygrasp_output_dir.sh" "$OUTPUT_DIR" >/dev/null; then
  echo "warning: failed to generate anygrasp analysis summary" >&2
fi

write_pipeline_artifacts

echo "target-mask anygrasp pipeline output: $OUTPUT_DIR"
echo "anygrasp renders output: $RENDERS_DIR"
exit "$ADAPTER_STATUS"
