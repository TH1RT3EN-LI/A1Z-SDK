#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="/workspace/A1Z/runtime/grconvnet_adapter_verify_${RUN_ID}"
INFER_DIR="$OUTPUT_DIR/grconvnet"
CAPTURE_DIR="/workspace/A1Z/runtime/target_mask_to_anygrasp/from_ros_live/capture"
TARGET_MASK_DIR="/workspace/A1Z/runtime/target_mask_to_anygrasp/from_ros_live/target_mask/selection"
EXTRINSIC_BASE_PATH="$CAPTURE_DIR/extrinsic_camera_to_base.npy"
OBSERVATION_JSON="$CAPTURE_DIR/observation.json"
ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
CURRENT_JOINTS_RAD_JSON="${A1Z_GRCONVNET_CURRENT_JOINTS_RAD:-}"

mkdir -p "$ROOT_DIR/runtime/grconvnet_adapter_verify_${RUN_ID}/grconvnet"
mkdir -p "$ROOT_DIR/runtime/grconvnet_adapter_verify_${RUN_ID}/adapter"

"$ROOT_DIR/scripts/setup_a1z_vision_in_container.sh"

if [[ ! -f "$ROOT_DIR/${EXTRINSIC_BASE_PATH#/workspace/A1Z/}" ]]; then
  if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
    docker start "$ROS_CONTAINER_NAME" >/dev/null
  fi
  docker exec \
    "$ROS_CONTAINER_NAME" \
    bash -lc '
      set -euo pipefail
      set +u
      source /opt/ros/humble/setup.bash
      source /workspace/A1Z/ros2_ws/install/setup.bash
      set -u
      python3 /workspace/A1Z/scripts/resolve_ros_tf.py \
        --observation-json "'"$OBSERVATION_JSON"'" \
        --target-frame-id robot_base_frame \
        --output-path "'"$EXTRINSIC_BASE_PATH"'" \
        --timeout-s 2.0 \
        --allow-latest
    '
fi

"$ROOT_DIR/scripts/run_grconvnet_inference_in_container.sh" \
  --rgb "$CAPTURE_DIR/color.png" \
  --depth "$CAPTURE_DIR/depth_m.npy" \
  --mask "$TARGET_MASK_DIR/selected_mask.npy" \
  --output-dir "$INFER_DIR" \
  --top-k 5 \
  --min-quality 0.05

readarray -t CROP_VALUES < <(
  cd "$ROOT_DIR" && RUN_ID="$RUN_ID" python3 - <<'PY'
import os
import json
from pathlib import Path

run_id = os.environ["RUN_ID"]
payload = json.loads(
    Path(f"runtime/grconvnet_adapter_verify_{run_id}/grconvnet/grconvnet_result.json").read_text(encoding="utf-8")
)
top, left = payload["input_crop_top_left_rc"]
bottom, right = payload["input_crop_bottom_right_rc"]
print(top)
print(left)
print(bottom)
print(right)
PY
)

CURRENT_JOINTS_ARGS=()
if [[ -n "$CURRENT_JOINTS_RAD_JSON" ]]; then
  CURRENT_JOINTS_ARGS=(--current-joints-rad "$CURRENT_JOINTS_RAD_JSON")
fi

"$ROOT_DIR/scripts/run_grconvnet_adapter_in_container.sh" \
  --quality-map "/workspace/A1Z/runtime/grconvnet_adapter_verify_${RUN_ID}/grconvnet/quality_map.npy" \
  --angle-map-rad "/workspace/A1Z/runtime/grconvnet_adapter_verify_${RUN_ID}/grconvnet/angle_map_rad.npy" \
  --width-map-px "/workspace/A1Z/runtime/grconvnet_adapter_verify_${RUN_ID}/grconvnet/width_map_px.npy" \
  --crop-top "${CROP_VALUES[0]}" \
  --crop-left "${CROP_VALUES[1]}" \
  --crop-bottom "${CROP_VALUES[2]}" \
  --crop-right "${CROP_VALUES[3]}" \
  --depth "$CAPTURE_DIR/depth_m.npy" \
  --intrinsics "$CAPTURE_DIR/intrinsics.json" \
  --extrinsic-camera-to-base "$EXTRINSIC_BASE_PATH" \
  --mask "$TARGET_MASK_DIR/selected_mask.npy" \
  --output-dir "$OUTPUT_DIR/adapter" \
  --backend verify \
  --pregrasp-offset-m 0.0 \
  --lift-offset-m 0.0 \
  --retreat-offset-m 0.0 \
  --top-k 5 \
  --min-quality 0.05 \
  "${CURRENT_JOINTS_ARGS[@]}"

echo "verify output: $OUTPUT_DIR"
