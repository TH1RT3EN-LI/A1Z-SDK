#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
CONTAINER_ENV_FILE="/workspace/A1Z/config/a1z_vlm.env"
SAM_CKPT="${A1Z_SAM2_DEFAULT_CKPT:-/workspace/A1Z/runtime/models/sam2/sam2.1_hiera_small.pt}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

INSTRUCTION="${1:-}"
if [[ -z "$INSTRUCTION" ]]; then
  echo "usage: $0 '<instruction>' [output_dir] [provider]" >&2
  exit 2
fi

OUTPUT_DIR="${2:-/workspace/A1Z/runtime/grconvnet_ros_live}"
PROVIDER="${3:-kimi}"
CAPTURE_DIR="$OUTPUT_DIR/capture"
TARGET_MASK_DIR="$OUTPUT_DIR/target_mask"
GRCONVNET_DIR="$OUTPUT_DIR/grconvnet"
ADAPTER_DIR="$OUTPUT_DIR/adapter"
HOST_OUTPUT_DIR="$ROOT_DIR/${OUTPUT_DIR#/workspace/A1Z/}"

mkdir -p "$HOST_OUTPUT_DIR/capture" "$HOST_OUTPUT_DIR/target_mask" "$HOST_OUTPUT_DIR/grconvnet" "$HOST_OUTPUT_DIR/adapter"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -u "${HOST_UID}:${HOST_GID}" \
  -e HOME=/tmp \
  -e ROS_LOG_DIR=/tmp/a1z_ros_logs \
  "$ROS_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    mkdir -p "$HOME" "$ROS_LOG_DIR"
    set +u
    source /opt/ros/humble/setup.bash
    source /workspace/A1Z/ros2_ws/install/setup.bash
    set -u
    python3 /workspace/A1Z/scripts/capture_ros_rgbd.py \
      --target-frame-id robot_base_frame \
      --fail-if-tf-unavailable \
      --output-dir "'"$CAPTURE_DIR"'"
  '

docker exec \
  -u "${HOST_UID}:${HOST_GID}" \
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

"$ROOT_DIR/scripts/setup_a1z_vision_in_container.sh"

"$ROOT_DIR/scripts/run_grconvnet_inference_in_container.sh" \
  --rgb "$CAPTURE_DIR/color.png" \
  --depth "$CAPTURE_DIR/depth_m.npy" \
  --mask "$TARGET_MASK_DIR/selection/selected_mask.npy" \
  --output-dir "$GRCONVNET_DIR" \
  --top-k 5 \
  --min-quality 0.05

readarray -t CROP_VALUES < <(
  cd "$ROOT_DIR" && OUTPUT_DIR_HOST="${OUTPUT_DIR#/workspace/A1Z/}" python3 - <<'PY'
import json
import os
from pathlib import Path

output_dir_host = os.environ["OUTPUT_DIR_HOST"]
payload = json.loads(
    Path(output_dir_host, "grconvnet", "grconvnet_result.json").read_text(encoding="utf-8")
)
top, left = payload["input_crop_top_left_rc"]
bottom, right = payload["input_crop_bottom_right_rc"]
print(top)
print(left)
print(bottom)
print(right)
PY
)

"$ROOT_DIR/scripts/run_grconvnet_adapter_in_container.sh" \
  --quality-map "$GRCONVNET_DIR/quality_map.npy" \
  --angle-map-rad "$GRCONVNET_DIR/angle_map_rad.npy" \
  --width-map-px "$GRCONVNET_DIR/width_map_px.npy" \
  --crop-top "${CROP_VALUES[0]}" \
  --crop-left "${CROP_VALUES[1]}" \
  --crop-bottom "${CROP_VALUES[2]}" \
  --crop-right "${CROP_VALUES[3]}" \
  --depth "$CAPTURE_DIR/depth_m.npy" \
  --intrinsics "$CAPTURE_DIR/intrinsics.json" \
  --extrinsic-camera-to-base "$CAPTURE_DIR/extrinsic_camera_to_base.npy" \
  --mask "$TARGET_MASK_DIR/selection/selected_mask.npy" \
  --output-dir "$ADAPTER_DIR" \
  --backend ros_live \
  --pregrasp-offset-m 0.0 \
  --lift-offset-m 0.0 \
  --retreat-offset-m 0.0 \
  --top-k 5 \
  --min-quality 0.05

echo "grconvnet ros pipeline output: $OUTPUT_DIR"
