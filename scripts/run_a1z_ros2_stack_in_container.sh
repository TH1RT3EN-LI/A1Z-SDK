#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
ACTION="${1:-run}"
if [[ $# -gt 0 ]]; then
  shift
fi

RUN_LOG_PATH="${A1Z_ROS2_MOTION_LOG_PATH:-/tmp/a1z_ros2_motion.log}"
RUN_PID_PATH="${A1Z_ROS2_MOTION_PID_PATH:-/tmp/a1z_ros2_motion.pid}"

case "$ACTION" in
  run|start|stop|restart|status|wait) ;;
  *)
    echo "usage: $0 [run|start|stop|restart|status|wait]" >&2
    exit 2
    ;;
esac

if ! docker inspect "$ROS_CONTAINER_NAME" >/dev/null 2>&1; then
  case "$ACTION" in
    stop)
      exit 0
      ;;
    status)
      echo "ROS 2 container does not exist: $ROS_CONTAINER_NAME" >&2
      exit 1
      ;;
    *)
      "$ROOT_DIR/scripts/create_a1z_ros2_container.sh"
      ;;
  esac
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$ROS_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  case "$ACTION" in
    stop)
      exit 0
      ;;
    status)
      echo "ROS 2 container is stopped: $ROS_CONTAINER_NAME" >&2
      exit 1
      ;;
    *)
      docker start "$ROS_CONTAINER_NAME" >/dev/null
      ;;
  esac
fi

if [[ "$ACTION" == "wait" ]]; then
  WAIT_SOURCE_FRAME="${A1Z_D405_COLOR_FRAME_ID:-d405_color_optical_frame}"
  WAIT_TARGET_FRAME="${A1Z_BASE_LINK_FRAME:-base_link}"
  WAIT_UID="$(id -u)"
  WAIT_GID="$(id -g)"
  WAIT_HOME="/tmp/a1z-home-$WAIT_UID"
  deadline=$(( $(date +%s) + 30 ))
  while [[ $(date +%s) -lt $deadline ]]; do
    if docker exec \
      -u "$WAIT_UID:$WAIT_GID" \
      -e HOME="$WAIT_HOME" \
      -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-62}" \
      "$ROS_CONTAINER_NAME" bash -lc "
      set +u
      source /opt/ros/humble/setup.bash
      set -u
      cd /workspace/A1Z/ros2_ws
      set +u
      source install/setup.bash
      set -u
      export ROS_LOG_DIR=/tmp/a1z-ros-log-\$(id -u)
      mkdir -p \"\$ROS_LOG_DIR\"
      export PYTHONPATH=\"/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z\${PYTHONPATH:+:\$PYTHONPATH}\"
      python3 /workspace/A1Z/scripts/resolve_ros_tf.py \
        --source-frame-id '$WAIT_SOURCE_FRAME' \
        --target-frame-id '$WAIT_TARGET_FRAME' \
        --output-path /tmp/a1z_ros2_motion_wait.npy \
        --timeout-s 3.0 \
        --cache-time-s 10.0 \
        --allow-latest >/dev/null
    "
    then
      exit 0
    fi
    sleep 1
  done
  exit 1
fi

DOCKER_TTY_ARGS=()
if [[ "$ACTION" == "run" && -t 0 && -t 1 ]]; then
  DOCKER_TTY_ARGS=(-it)
fi

if [[ "$ACTION" == "stop" || "$ACTION" == "restart" || "$ACTION" == "status" ]]; then
  docker exec "$ROS_CONTAINER_NAME" bash -lc "
    set -euo pipefail
    cleanup_a1z_motion() {
      local pattern
      local line
      local pid
      for pattern in \
        '/opt/ros/humble/bin/ros2 launch a1z_motion a1z_stack.launch.py' \
        '/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/isaac_d405_bridge' \
        '/opt/ros/humble/lib/realsense2_camera/realsense2_camera_node' \
        '/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state' \
        '/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor'
      do
        while IFS= read -r line; do
          read -r pid _ <<<\"\$line\"
          if [[ -n \"\$pid\" ]]; then
            kill \"\$pid\" >/dev/null 2>&1 || true
          fi
        done < <(ps -eo pid=,args= | grep -F \"\$pattern\" | grep -v -F 'grep -F')
      done
    }
    if [[ '$ACTION' == 'stop' || '$ACTION' == 'restart' ]]; then
      cleanup_a1z_motion
      rm -f '$RUN_PID_PATH'
      exit 0
    fi
    ps -eo pid=,args= | grep -E 'a1z_stack.launch.py|a1z_motion/robot_state|a1z_motion/motion_executor|a1z_d405/isaac_d405_bridge|realsense2_camera_node' | grep -v grep
  "
  [[ "$ACTION" == "status" || "$ACTION" == "stop" ]] && exit 0
fi

DOCKER_EXEC_ARGS=()
if [[ "$ACTION" == "start" || "$ACTION" == "restart" ]]; then
  DOCKER_EXEC_ARGS+=(-d)
fi

docker exec \
  -u "$(id -u):$(id -g)" \
  "${DOCKER_EXEC_ARGS[@]}" \
  -e COLCON_LOG_PATH="/tmp/a1z-colcon-log-$(id -u)" \
  -e ROS_LOG_DIR="/tmp/a1z-ros-log-$(id -u)" \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-62}" \
  -e A1Z_PROFILE="${A1Z_PROFILE:-sim}" \
  -e A1Z_CAMERA_SOURCE="${A1Z_CAMERA_SOURCE}" \
  -e A1Z_CONTROL_URDF="${A1Z_CONTROL_URDF:-/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf}" \
  -e A1Z_SDK_DIR="${A1Z_SDK_DIR:-/workspace/A1Z/vendor/GALAXEA-A1Z}" \
  -e A1Z_REPO_ROOT="${A1Z_REPO_ROOT:-/workspace/A1Z}" \
  -e A1Z_TCP_HOST="${A1Z_TCP_HOST:-127.0.0.1}" \
  -e A1Z_TCP_PORT="${A1Z_TCP_PORT:-37103}" \
  -e A1Z_BASE_LINK_FRAME="${A1Z_BASE_LINK_FRAME:-base_link}" \
  -e A1Z_ROBOT_BASE_FRAME="${A1Z_ROBOT_BASE_FRAME:-robot_base_frame}" \
  -e A1Z_TOOL_LINK_FRAME="${A1Z_TOOL_LINK_FRAME:-grasp_tcp}" \
  -e A1Z_TOOL_FRAME="${A1Z_TOOL_FRAME:-grasp_tcp}" \
  -e A1Z_D405_LINK_FRAME="${A1Z_D405_LINK_FRAME:-d405_link}" \
  -e A1Z_D405_RECTIFIED_FRAME_ID="${A1Z_D405_RECTIFIED_FRAME_ID:-d405_rectified_link}" \
  -e A1Z_D405_COLOR_FRAME_ID="${A1Z_D405_COLOR_FRAME_ID:-d405_color_optical_frame}" \
  -e A1Z_D405_DEPTH_FRAME_ID="${A1Z_D405_DEPTH_FRAME_ID:-d405_depth_optical_frame}" \
  -e A1Z_D405_SERIAL_NO="${A1Z_D405_SERIAL_NO:-}" \
  -e A1Z_D405_WIDTH="${A1Z_D405_WIDTH:-640}" \
  -e A1Z_D405_HEIGHT="${A1Z_D405_HEIGHT:-480}" \
  -e A1Z_D405_FPS="${A1Z_D405_FPS:-30}" \
  "${DOCKER_TTY_ARGS[@]}" "$ROS_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    cleanup_a1z_motion() {
      local pattern
      local line
      local pid
      for pattern in \
        "/opt/ros/humble/bin/ros2 launch a1z_motion a1z_stack.launch.py" \
        "/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/isaac_d405_bridge" \
        "/opt/ros/humble/lib/realsense2_camera/realsense2_camera_node" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor"
      do
        while IFS= read -r line; do
          read -r pid _ <<<"$line"
          if [[ -n "$pid" && "$pid" != "$$" ]]; then
            kill "$pid" >/dev/null 2>&1 || true
          fi
        done < <(ps -eo pid=,args= | grep -F "$pattern" | grep -v -F "grep -F")
      done
      sleep 1
      for pattern in \
        "/opt/ros/humble/bin/ros2 launch a1z_motion a1z_stack.launch.py" \
        "/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/isaac_d405_bridge" \
        "/opt/ros/humble/lib/realsense2_camera/realsense2_camera_node" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor"
      do
        while IFS= read -r line; do
          read -r pid _ <<<"$line"
          if [[ -n "$pid" && "$pid" != "$$" ]]; then
            kill -9 "$pid" >/dev/null 2>&1 || true
          fi
        done < <(ps -eo pid=,args= | grep -F "$pattern" | grep -v -F "grep -F")
      done
    }
    set +u
    source /opt/ros/humble/setup.bash
    set -u
    mkdir -p "$COLCON_LOG_PATH" "$ROS_LOG_DIR"
    cd /workspace/A1Z/ros2_ws
    colcon --log-base "$COLCON_LOG_PATH" build
    set +u
    source install/setup.bash
    set -u
    export PYTHONPATH="/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z${PYTHONPATH:+:$PYTHONPATH}"
    cleanup_a1z_motion
    sleep 1
    if [[ "'"$ACTION"'" == "start" || "'"$ACTION"'" == "restart" ]]; then
      : > "'"$RUN_LOG_PATH"'"
      nohup ros2 launch a1z_motion a1z_stack.launch.py >"'"$RUN_LOG_PATH"'" 2>&1 &
      echo "$!" >"'"$RUN_PID_PATH"'"
      disown || true
      exit 0
    fi
    if [[ "'"$ACTION"'" == "stop" ]]; then
      exit 0
    fi
    exec ros2 launch a1z_motion a1z_stack.launch.py
  '
