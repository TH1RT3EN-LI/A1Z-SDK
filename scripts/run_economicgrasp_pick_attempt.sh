#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
BASE_DIR="/workspace/A1Z/runtime/economicgrasp_pick_attempt_${RUN_ID}"
CAPTURE_DIR="$BASE_DIR/capture"
SMOKE_DIR="$BASE_DIR/economicgrasp"
ADAPTER_DIR="$BASE_DIR/adapter"
EXEC_DIR="$BASE_DIR/execute"
ROS_CAPTURE_TIMEOUT_S="${A1Z_ROS_CAPTURE_TIMEOUT_S:-30}"
ROS_CAPTURE_RETRIES="${A1Z_ROS_CAPTURE_RETRIES:-3}"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

mkdir -p "$ROOT_DIR/${BASE_DIR#/workspace/A1Z/}"

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
    for attempt in $(seq 1 "'"$ROS_CAPTURE_RETRIES"'"); do
      if python3 /workspace/A1Z/scripts/capture_ros_rgbd.py \
        --target-frame-id robot_base_frame \
        --timeout-s "'"$ROS_CAPTURE_TIMEOUT_S"'" \
        --tf-lookup-timeout-s 2.0 \
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

"$ROOT_DIR/scripts/run_economicgrasp_smoke_in_container.sh" \
  --rgb "$CAPTURE_DIR/color.png" \
  --depth "$CAPTURE_DIR/depth_m.npy" \
  --intrinsics "$CAPTURE_DIR/intrinsics.json" \
  --checkpoint-path "${A1Z_ECONOMICGRASP_REALSENSE_CKPT:-/workspace/A1Z/runtime/models/economicgrasp/economicgrasp_realsense.tar}" \
  --output-dir "$SMOKE_DIR" \
  --camera realsense \
  --top-k 64

if [[ ! -f "$ROOT_DIR/${CAPTURE_DIR#/workspace/A1Z/}/extrinsic_camera_to_base.npy" ]]; then
  docker exec \
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
fi

"$ROOT_DIR/scripts/run_economicgrasp_adapter_in_container.sh" \
  --predictions "$SMOKE_DIR/raw_predictions.npy" \
  --extrinsic-camera-to-base "$CAPTURE_DIR/extrinsic_camera_to_base.npy" \
  --output-dir "$ADAPTER_DIR" \
  --backend economicgrasp_live \
  --top-k 64 \
  --grasp-center-is-contact-center

EXEC_ARGS=(
  --plan "$ADAPTER_DIR/selected_plan.json"
  --output "$EXEC_DIR/execution_result.json"
  --pre-open
  --arm-speed 0.12
  --settle-s 0.75
)
if [[ "$DRY_RUN" == "1" ]]; then
  EXEC_ARGS+=(--dry-run)
fi

"$ROOT_DIR/scripts/execute_a1z_plan_in_container.sh" "${EXEC_ARGS[@]}"

echo "attempt output: $BASE_DIR"
