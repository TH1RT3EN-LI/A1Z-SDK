#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
OUT_DIR="${1:-$ROOT_DIR/runtime/d405_alignment_verify_$(date +%Y%m%d_%H%M%S)}"
TARGET_FRAME_ID="${A1Z_BASE_LINK_FRAME:-base_link}"
CONTAINER_OUT_DIR="/workspace/A1Z/${OUT_DIR#$ROOT_DIR/}"

mkdir -p "$OUT_DIR"
chmod 0777 "$OUT_DIR" || true

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

bash "$ROOT_DIR/scripts/run_a1z_ros2_motion_in_container.sh" restart
bash "$ROOT_DIR/scripts/run_a1z_ros2_motion_in_container.sh" wait

docker exec \
  -e A1Z_REPO_ROOT="/workspace/A1Z" \
  "$ROS_CONTAINER_NAME" \
  bash -lc "
    set -euo pipefail
    set +u
    source /opt/ros/humble/setup.bash
    source /workspace/A1Z/ros2_ws/install/setup.bash
    set -u
    python3 /workspace/A1Z/scripts/query_ros_tf_matrix.py \
      --source-frame-id d405_color_optical_frame \
      --target-frame-id '$TARGET_FRAME_ID' \
      --timeout-s 5.0 \
      --allow-latest \
      --retry-count 10 \
      --retry-sleep-s 0.5 \
      --output $CONTAINER_OUT_DIR/ros.json
  "

bash "$ROOT_DIR/scripts/a1z_isaac_python_in_container.sh" \
  /workspace/A1Z/scripts/query_isaac_d405_extrinsic.py \
  --target-frame-id "$TARGET_FRAME_ID" \
  --output "$CONTAINER_OUT_DIR/isaac.json"

python3 "$ROOT_DIR/scripts/compare_transform_json.py" \
  --lhs "$OUT_DIR/ros.json" \
  --rhs "$OUT_DIR/isaac.json" \
  --output "$OUT_DIR/compare.json"

echo "isaac:   $OUT_DIR/isaac.json"
echo "ros:     $OUT_DIR/ros.json"
echo "compare: $OUT_DIR/compare.json"
