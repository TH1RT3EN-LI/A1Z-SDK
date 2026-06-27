#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ROS_CONTAINER_NAME" >/dev/null
fi

DOCKER_TTY_ARGS=()
if [[ -t 0 && -t 1 ]]; then
  DOCKER_TTY_ARGS=(-it)
fi

docker exec \
  -e A1Z_CONTROL_URDF="${A1Z_CONTROL_URDF:-/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf}" \
  -e A1Z_SDK_DIR="${A1Z_SDK_DIR:-/workspace/A1Z/vendor/GALAXEA-A1Z}" \
  -e A1Z_REPO_ROOT="${A1Z_REPO_ROOT:-/workspace/A1Z}" \
  -e A1Z_TCP_HOST="${A1Z_TCP_HOST:-127.0.0.1}" \
  -e A1Z_TCP_PORT="${A1Z_TCP_PORT:-18080}" \
  -e A1Z_D405_LINK_FRAME="${A1Z_D405_LINK_FRAME:-d405_link}" \
  -e A1Z_D405_COLOR_FRAME_ID="${A1Z_D405_COLOR_FRAME_ID:-d405_color_optical_frame}" \
  -e A1Z_D405_DEPTH_FRAME_ID="${A1Z_D405_DEPTH_FRAME_ID:-d405_depth_optical_frame}" \
  "${DOCKER_TTY_ARGS[@]}" "$ROS_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    cleanup_a1z_motion() {
      local pattern
      local line
      local pid
      for pattern in \
        "/opt/ros/humble/bin/ros2 launch a1z_motion a1z_motion.launch.py" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor"
      do
        while IFS= read -r line; do
          pid="${line%% *}"
          if [[ -n "$pid" && "$pid" != "$$" ]]; then
            kill "$pid" >/dev/null 2>&1 || true
          fi
        done < <(ps -eo pid=,args= | grep -F "$pattern" | grep -v -F "grep -F")
      done
    }
    set +u
    source /opt/ros/humble/setup.bash
    set -u
    cd /workspace/A1Z/ros2_ws
    colcon build
    set +u
    source install/setup.bash
    set -u
    cleanup_a1z_motion
    sleep 1
    ros2 launch a1z_motion a1z_motion.launch.py
  '
