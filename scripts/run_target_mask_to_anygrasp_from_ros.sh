#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
CONTAINER_ENV_FILE="/workspace/A1Z/config/a1z_vlm.env"
SAM_CKPT="${A1Z_SAM2_DEFAULT_CKPT:-/workspace/A1Z/runtime/models/sam2/sam2.1_hiera_small.pt}"
ANYGRASP_SDK_DIR="${A1Z_ANYGRASP_SDK_DIR:-/workspace/A1Z/vendor/vision/anygrasp_sdk}"
ANYGRASP_CKPT="${A1Z_ANYGRASP_DETECTION_CKPT:-/workspace/A1Z/runtime/models/anygrasp/checkpoint_detection.tar}"
ANYGRASP_LICENSE_DIR="${A1Z_ANYGRASP_LICENSE_DIR:-/workspace/A1Z/runtime/licenses/anygrasp}"
ROS_CAPTURE_TIMEOUT_S="${A1Z_ROS_CAPTURE_TIMEOUT_S:-30}"
ROS_CAPTURE_RETRIES="${A1Z_ROS_CAPTURE_RETRIES:-3}"

INSTRUCTION="${1:-}"
if [[ -z "$INSTRUCTION" ]]; then
  echo "usage: $0 '<instruction>' [output_dir] [provider]" >&2
  exit 2
fi

OUTPUT_DIR="${2:-/workspace/A1Z/runtime/target_mask_to_anygrasp/from_ros_live}"
PROVIDER="${3:-kimi}"
CAPTURE_DIR="$OUTPUT_DIR/capture"
TARGET_MASK_DIR="$OUTPUT_DIR/target_mask"
ANYGRASP_DIR="$OUTPUT_DIR/anygrasp_from_mask"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  "$ROS_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    set +u
    source /opt/ros/humble/setup.bash
    source /workspace/A1Z/ros2_ws/install/setup.bash
    set -u
    for attempt in $(seq 1 "'"$ROS_CAPTURE_RETRIES"'"); do
      if python3 /workspace/A1Z/scripts/capture_ros_rgbd.py \
        --target-frame-id robot_base_frame \
        --timeout-s "'"$ROS_CAPTURE_TIMEOUT_S"'" \
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

docker exec \
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

docker exec \
  -e A1Z_ANYGRASP_RGB="$CAPTURE_DIR/rgb.npy" \
  -e A1Z_ANYGRASP_DEPTH="$CAPTURE_DIR/depth_m.npy" \
  -e A1Z_ANYGRASP_INTRINSICS="$CAPTURE_DIR/intrinsics.json" \
  -e A1Z_ANYGRASP_SELECTION_JSON="$TARGET_MASK_DIR/selection/selection.json" \
  -e A1Z_ANYGRASP_OUTPUT_DIR="$ANYGRASP_DIR" \
  -e A1Z_ANYGRASP_SDK_DIR="$ANYGRASP_SDK_DIR" \
  -e A1Z_ANYGRASP_CKPT="$ANYGRASP_CKPT" \
  -e A1Z_ANYGRASP_LICENSE_DIR="$ANYGRASP_LICENSE_DIR" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source /opt/venvs/a1z-vision/bin/activate
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
