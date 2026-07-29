#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
OUT_DIR="${1:-$ROOT_DIR/runtime/d405_depth_point_verify_$(date +%Y%m%d_%H%M%S)}"
TARGET_FRAME_ID="${A1Z_BASE_LINK_FRAME:-base_link}"
CONTAINER_OUT_DIR="/workspace/A1Z/${OUT_DIR#$ROOT_DIR/}"
ROS_JSON_PATH="$CONTAINER_OUT_DIR/ros.json"

mkdir -p "$OUT_DIR/capture"
chmod -R 0777 "$OUT_DIR" || true

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

bash "$ROOT_DIR/scripts/run_a1z_ros2_stack_in_container.sh" restart
bash "$ROOT_DIR/scripts/run_a1z_ros2_stack_in_container.sh" wait

docker exec \
  -e A1Z_REPO_ROOT="/workspace/A1Z" \
  "$ROS_CONTAINER_NAME" \
  bash -lc "
    set -euo pipefail
    set +u
    source /opt/ros/humble/setup.bash
    source /workspace/A1Z/ros2_ws/install/setup.bash
    set -u
    python3 /workspace/A1Z/scripts/capture_rgbd.py \
      --target-frame-id '$TARGET_FRAME_ID' \
      --fail-if-tf-unavailable \
      --output-dir '$CONTAINER_OUT_DIR/capture'
    python3 /workspace/A1Z/scripts/query_ros_tf_matrix.py \
      --source-frame-id d405_color_optical_frame \
      --target-frame-id '$TARGET_FRAME_ID' \
      --timeout-s 5.0 \
      --allow-latest \
      --output '$ROS_JSON_PATH'
  "

bash "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" \
  /workspace/A1Z/scripts/compute_d405_extrinsic_from_capture.py \
  --target-frame-id "$TARGET_FRAME_ID" \
  --joint-pos-rad-json "$CONTAINER_OUT_DIR/capture/current_joints_rad.json" \
  --output "$CONTAINER_OUT_DIR/isaac.json"

python3 "$ROOT_DIR/scripts/compare_transform_json.py" \
  --lhs "$OUT_DIR/ros.json" \
  --rhs "$OUT_DIR/isaac.json" \
  --output "$OUT_DIR/extrinsic_compare.json"

docker exec \
  -e A1Z_REPO_ROOT="/workspace/A1Z" \
  "$ROS_CONTAINER_NAME" \
  bash -lc "
    set -euo pipefail
    set +u
    source /opt/ros/humble/setup.bash
    source /workspace/A1Z/ros2_ws/install/setup.bash
    set -u
    python3 /workspace/A1Z/scripts/compare_depth_points_in_base.py \
      --depth '$CONTAINER_OUT_DIR/capture/depth_m.npy' \
      --intrinsics '$CONTAINER_OUT_DIR/capture/intrinsics.json' \
      --ros-extrinsic-json '$CONTAINER_OUT_DIR/ros.json' \
      --isaac-extrinsic-json '$CONTAINER_OUT_DIR/isaac.json' \
      --output '$CONTAINER_OUT_DIR/points_compare.json'
  "

echo "capture:   $OUT_DIR/capture"
echo "ros:       $OUT_DIR/ros.json"
echo "isaac:     $OUT_DIR/isaac.json"
echo "extrinsic: $OUT_DIR/extrinsic_compare.json"
echo "points:    $OUT_DIR/points_compare.json"
