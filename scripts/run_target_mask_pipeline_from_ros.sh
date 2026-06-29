#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
HOST_ENV_FILE="${A1Z_VLM_ENV_FILE:-$ROOT_DIR/config/a1z_vlm.env}"
CONTAINER_ENV_FILE="/workspace/A1Z/config/a1z_vlm.env"
SAM_CKPT="${A1Z_SAM2_DEFAULT_CKPT:-/workspace/A1Z/runtime/models/sam2/sam2.1_hiera_small.pt}"

INSTRUCTION="${1:-}"
if [[ -z "$INSTRUCTION" ]]; then
  echo "usage: $0 '<instruction>' [ros_topic] [output_dir] [provider]" >&2
  exit 2
fi

ROS_TOPIC="${2:-/a1z/d405/color/image_raw}"
OUTPUT_DIR="${3:-/workspace/A1Z/runtime/target_mask_pipeline/from_ros_live}"
PROVIDER="${4:-kimi}"
CAPTURE_PATH="$OUTPUT_DIR/current_ros_capture.png"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_CAPTURE_TOPIC="$ROS_TOPIC" \
  -e A1Z_CAPTURE_OUTPUT="$CAPTURE_PATH" \
  "$ROS_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    set +u
    source /opt/ros/humble/setup.bash
    source /workspace/A1Z/ros2_ws/install/setup.bash
    set -u
    python3 /workspace/A1Z/scripts/capture_ros_image.py \
      --ros-topic "$A1Z_CAPTURE_TOPIC" \
      --output "$A1Z_CAPTURE_OUTPUT"
  '

docker exec \
  -e A1Z_TARGET_INSTRUCTION="$INSTRUCTION" \
  -e A1Z_TARGET_IMAGE="$CAPTURE_PATH" \
  -e A1Z_TARGET_OUTPUT_DIR="$OUTPUT_DIR" \
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
