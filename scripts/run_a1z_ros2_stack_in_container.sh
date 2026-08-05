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
RUN_LOG_MAX_BYTES="${A1Z_ROS2_MOTION_LOG_MAX_BYTES:-67108864}"
RUN_LOG_BACKUP_COUNT="${A1Z_ROS2_MOTION_LOG_BACKUP_COUNT:-3}"
CAMERA_MODE="${A1Z_CAMERA_MODE:-auto}"
CAMERA_ENABLED=0

case "$ACTION" in
  run|start|ensure|stop|restart|status|wait) ;;
  *)
    echo "usage: $0 [run|start|ensure|stop|restart|status|wait]" >&2
    exit 2
    ;;
esac

case "$CAMERA_MODE" in
  auto|on|off) ;;
  *)
    echo "A1Z_CAMERA_MODE must be auto, on, or off; got '$CAMERA_MODE'" >&2
    exit 2
    ;;
esac

realsense_usb_speed_mbps() {
  local device
  local speed
  local max_speed=0
  for device in /sys/bus/usb/devices/*; do
    [[ -r "$device/idVendor" && -r "$device/idProduct" && -r "$device/speed" ]] || continue
    [[ "$(<"$device/idVendor")" == "8086" && "$(<"$device/idProduct")" == "0b5b" ]] || continue
    speed="$(<"$device/speed")"
    speed="${speed%%.*}"
    if [[ "$speed" =~ ^[0-9]+$ ]] && (( speed > max_speed )); then
      max_speed="$speed"
    fi
  done
  (( max_speed > 0 )) || return 1
  printf '%s\n' "$max_speed"
}

validate_realsense_usb_link() {
  local actual_speed
  local minimum_speed="${A1Z_REALSENSE_MIN_USB_SPEED_MBPS:-5000}"
  [[ "$A1Z_PROFILE" == "real" ]] || return 0
  if ! actual_speed="$(realsense_usb_speed_mbps)"; then
    echo "RealSense D405 is not present on the host USB bus" >&2
    return 1
  fi
  if (( actual_speed < minimum_speed )); then
    echo "RealSense D405 USB link is ${actual_speed} Mb/s; this profile requires at least ${minimum_speed} Mb/s" >&2
    echo "Reconnect the D405 through its USB 3.x cable/port before starting the ROS 2 stack" >&2
    return 1
  fi
  echo "RealSense D405 USB link: ${actual_speed} Mb/s"
}

resolve_camera_mode() {
  local actual_speed=""
  local minimum_speed="${A1Z_REALSENSE_MIN_USB_SPEED_MBPS:-5000}"
  if [[ "$CAMERA_MODE" == "off" ]]; then
    CAMERA_ENABLED=0
    echo "Camera disabled by A1Z_CAMERA_MODE=off."
    return 0
  fi
  if [[ "$A1Z_CAMERA_SOURCE" != "realsense" ]]; then
    CAMERA_ENABLED=1
    return 0
  fi
  if [[ "$CAMERA_MODE" == "on" ]]; then
    validate_realsense_usb_link
    CAMERA_ENABLED=1
    return 0
  fi
  if ! actual_speed="$(realsense_usb_speed_mbps)"; then
    CAMERA_ENABLED=0
    echo "No RealSense D405 detected; starting the ROS 2 stack without camera nodes."
    return 0
  fi
  if (( actual_speed < minimum_speed )); then
    CAMERA_ENABLED=0
    echo "RealSense D405 USB link is ${actual_speed} Mb/s; camera nodes remain disabled in auto mode." >&2
    echo "Reconnect through USB 3.x, then run this command with restart or ensure." >&2
    return 0
  fi
  CAMERA_ENABLED=1
  echo "RealSense D405 detected at ${actual_speed} Mb/s; enabling camera nodes."
}

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

if [[ "$ACTION" != "stop" ]]; then
  resolve_camera_mode
fi

check_a1z_ros_stack() {
  local process_status=0
  local camera_response=""
  docker exec -i "$ROS_CONTAINER_NAME" bash -s -- "$A1Z_CAMERA_SOURCE" "$CAMERA_ENABLED" <<'EOF' || process_status=$?
set -uo pipefail

camera_source="$1"
camera_enabled="$2"
case "$camera_source" in
  isaac)
    camera_pattern="/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/isaac_d405_bridge"
    ;;
  realsense)
    camera_pattern="/opt/ros/humble/lib/realsense2_camera/realsense2_camera_node"
    ;;
  *)
    echo "Unsupported ROS camera source: $1" >&2
    exit 2
    ;;
esac

missing=0
for item in \
  "robot_state:/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
  "motion_executor:/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor"
do
  label="${item%%:*}"
  pattern="${item#*:}"
  line="$(ps -eo pid=,stat=,args= | grep -F "$pattern" | grep -v -F "grep -F" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    echo "MISSING $label: $pattern" >&2
    missing=1
  else
    echo "RUNNING $label: $line"
  fi
done
camera_bridge_pattern="/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/camera_console_bridge"
if [[ "$camera_enabled" == "1" ]]; then
  for item in "camera:$camera_pattern" "console_bridge:$camera_bridge_pattern"; do
    label="${item%%:*}"
    pattern="${item#*:}"
    line="$(ps -eo pid=,stat=,args= | grep -F "$pattern" | grep -v -F "grep -F" | head -n 1 || true)"
    if [[ -z "$line" ]]; then
      echo "MISSING $label: $pattern" >&2
      missing=1
    else
      echo "RUNNING $label: $line"
    fi
  done
else
  for pattern in "$camera_pattern" "$camera_bridge_pattern"; do
    line="$(ps -eo pid=,stat=,args= | grep -F "$pattern" | grep -v -F "grep -F" | head -n 1 || true)"
    if [[ -n "$line" ]]; then
      echo "UNEXPECTED camera process while camera mode is disabled: $line" >&2
      missing=1
    fi
  done
fi
exit "$missing"
EOF
  if [[ "$process_status" -ne 0 ]]; then
    return "$process_status"
  fi

  if [[ "$CAMERA_ENABLED" != "1" ]]; then
    echo "RUNNING camera: disabled (${CAMERA_MODE})"
    return 0
  fi

  if ! camera_response="$(
    exec 3<>"/dev/tcp/${A1Z_CAMERA_BRIDGE_HOST}/${A1Z_CAMERA_BRIDGE_PORT}"
    printf '%s\n' '{"cmd":"camera_status","args":{}}' >&3
    IFS= read -r -t 3 response <&3
    printf '%s' "$response"
  )"; then
    echo "MISSING camera_frames: camera bridge is unreachable at ${A1Z_CAMERA_BRIDGE_HOST}:${A1Z_CAMERA_BRIDGE_PORT}" >&2
    return 1
  fi
  if [[ "$camera_response" != *'"ready":true'* ]]; then
    echo "MISSING camera_frames: camera bridge reports stale or incomplete RGB-D data" >&2
    return 1
  fi
  echo "RUNNING camera_frames: fresh synchronized RGB-D data"
}

if [[ "$ACTION" == "status" ]]; then
  check_a1z_ros_stack
  exit $?
fi

if [[ "$ACTION" == "ensure" ]]; then
  if check_a1z_ros_stack; then
    echo "ROS 2 stack is already healthy: $ROS_CONTAINER_NAME"
    exit 0
  fi
  echo "ROS 2 stack is incomplete; starting it in $ROS_CONTAINER_NAME"
  ACTION="start"
fi

if [[ "$ACTION" == "wait" ]]; then
  if [[ "$CAMERA_ENABLED" != "1" ]]; then
    echo "Camera frames are unavailable because the camera is disabled or not detected." >&2
    exit 1
  fi
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

if [[ "$ACTION" == "stop" || "$ACTION" == "restart" ]]; then
  docker exec "$ROS_CONTAINER_NAME" bash -lc "
    set -euo pipefail
    cleanup_a1z_motion() {
      local pattern
      local line
      local pid
      for pattern in \
        '/opt/ros/humble/bin/ros2 launch a1z_motion a1z_stack.launch.py' \
        '/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/isaac_d405_bridge' \
        '/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/camera_console_bridge' \
        '/opt/ros/humble/lib/realsense2_camera/realsense2_camera_node' \
        '/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state' \
        '/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor' \
        '/workspace/A1Z/scripts/run_ros2_launch_with_rotating_log.sh'
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
  "
  [[ "$ACTION" == "stop" ]] && exit 0
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
  -e A1Z_CAMERA_ENABLED="${CAMERA_ENABLED}" \
  -e A1Z_CAMERA_BRIDGE_HOST="${A1Z_CAMERA_BRIDGE_HOST:-127.0.0.1}" \
  -e A1Z_CAMERA_BRIDGE_PORT="${A1Z_CAMERA_BRIDGE_PORT}" \
  -e A1Z_CAMERA_PREVIEW_MAX_WIDTH="${A1Z_CAMERA_PREVIEW_MAX_WIDTH:-960}" \
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
  -e A1Z_REALSENSE_CAMERA_NAME="${A1Z_REALSENSE_CAMERA_NAME:-d405}" \
  -e A1Z_REALSENSE_BASE_FRAME_ID="${A1Z_REALSENSE_BASE_FRAME_ID:-link}" \
  -e A1Z_REALSENSE_INITIAL_RESET="${A1Z_REALSENSE_INITIAL_RESET:-0}" \
  -e LRS_LOG_LEVEL="${LRS_LOG_LEVEL:-fatal}" \
  -e A1Z_D405_WIDTH="${A1Z_D405_WIDTH:-640}" \
  -e A1Z_D405_HEIGHT="${A1Z_D405_HEIGHT:-480}" \
  -e A1Z_D405_FPS="${A1Z_D405_FPS:-30}" \
  -e A1Z_RGBD_TARGET_FRAME="${A1Z_RGBD_TARGET_FRAME:-base_link}" \
  -e A1Z_RGBD_COLOR_TOPIC="${A1Z_RGBD_COLOR_TOPIC}" \
  -e A1Z_RGBD_COLOR_INFO_TOPIC="${A1Z_RGBD_COLOR_INFO_TOPIC}" \
  -e A1Z_RGBD_DEPTH_TOPIC="${A1Z_RGBD_DEPTH_TOPIC}" \
  -e A1Z_RGBD_DEPTH_INFO_TOPIC="${A1Z_RGBD_DEPTH_INFO_TOPIC}" \
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
        "/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/camera_console_bridge" \
        "/opt/ros/humble/lib/realsense2_camera/realsense2_camera_node" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor" \
        "/workspace/A1Z/scripts/run_ros2_launch_with_rotating_log.sh"
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
        "/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/camera_console_bridge" \
        "/opt/ros/humble/lib/realsense2_camera/realsense2_camera_node" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
        "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor" \
        "/workspace/A1Z/scripts/run_ros2_launch_with_rotating_log.sh"
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
      nohup /workspace/A1Z/scripts/run_ros2_launch_with_rotating_log.sh \
        "'"$RUN_LOG_PATH"'" \
        "'"$RUN_LOG_MAX_BYTES"'" \
        "'"$RUN_LOG_BACKUP_COUNT"'" \
        >/dev/null 2>&1 &
      echo "$!" >"'"$RUN_PID_PATH"'"
      disown || true
      exit 0
    fi
    if [[ "'"$ACTION"'" == "stop" ]]; then
      exit 0
    fi
    exec ros2 launch a1z_motion a1z_stack.launch.py
  '
