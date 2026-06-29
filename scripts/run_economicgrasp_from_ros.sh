#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
ECONOMICGRASP_CONTAINER_NAME="${A1Z_ECONOMICGRASP_CONTAINER_NAME:-a1z-economicgrasp-gpu}"
CAPTURE_DIR="${1:-/workspace/A1Z/runtime/economicgrasp_smoke_from_ros_live/capture}"
SMOKE_DIR="${2:-/workspace/A1Z/runtime/economicgrasp_smoke_from_ros_live/economicgrasp}"
CHECKPOINT_PATH="${A1Z_ECONOMICGRASP_REALSENSE_CKPT:-/workspace/A1Z/runtime/models/economicgrasp/economicgrasp_realsense.tar}"
ROS_CAPTURE_TIMEOUT_S="${A1Z_ROS_CAPTURE_TIMEOUT_S:-30}"
ROS_CAPTURE_RETRIES="${A1Z_ROS_CAPTURE_RETRIES:-3}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$ECONOMICGRASP_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ECONOMICGRASP_CONTAINER_NAME" >/dev/null
fi

mkdir -p "$ROOT_DIR/${CAPTURE_DIR#/workspace/A1Z/}" "$ROOT_DIR/${SMOKE_DIR#/workspace/A1Z/}"

if [[ ! -f "$ROOT_DIR/${CHECKPOINT_PATH#/workspace/A1Z/}" ]]; then
  echo "EconomicGrasp checkpoint missing: $CHECKPOINT_PATH" >&2
  echo "Proceeding with structural smoke fallback only." >&2
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

if ! "$ROOT_DIR/scripts/run_economicgrasp_smoke_in_container.sh" \
  --rgb "$CAPTURE_DIR/color.png" \
  --depth "$CAPTURE_DIR/depth_m.npy" \
  --intrinsics "$CAPTURE_DIR/intrinsics.json" \
  --checkpoint-path "$CHECKPOINT_PATH" \
  --output-dir "$SMOKE_DIR" \
  --camera realsense \
  --top-k 20
then
  echo "EconomicGrasp checkpoint path is not usable yet; falling back to structural smoke mode." >&2
  "$ROOT_DIR/scripts/run_economicgrasp_smoke_in_container.sh" \
    --rgb "$CAPTURE_DIR/color.png" \
    --depth "$CAPTURE_DIR/depth_m.npy" \
    --intrinsics "$CAPTURE_DIR/intrinsics.json" \
    --checkpoint-path "$CHECKPOINT_PATH" \
    --output-dir "$SMOKE_DIR" \
    --camera realsense \
    --top-k 20 \
    --allow-random-weights \
    --force-all-graspable
fi
