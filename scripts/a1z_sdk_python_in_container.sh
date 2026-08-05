#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"
CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:?selected profile must define A1Z_ROS2_CONTAINER_NAME}"
REQUIRE_CONTROL_SERVER_STOPPED=0
if [[ "${1:-}" == "--require-control-server-stopped" ]]; then
  REQUIRE_CONTROL_SERVER_STOPPED=1
  shift
fi

if ! docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  "$ROOT_DIR/scripts/create_a1z_ros2_container.sh"
fi
if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

if [[ "$REQUIRE_CONTROL_SERVER_STOPPED" == "1" ]] && \
   docker exec "$CONTAINER_NAME" \
     bash -lc "pgrep -af '/workspace/A1Z/tools/[a]1zctl serve'"; then
  echo "Refusing direct CAN access: an A1Z SDK control-server process is still running." >&2
  echo "Stop the control service and verify its process has exited before retrying." >&2
  exit 4
fi

ENV_ARGS=()
for name in \
  A1Z_PROFILE A1Z_BACKEND A1Z_CAN_CHANNEL A1Z_CONTROL_FREQ_HZ \
  A1Z_MIN_CONTROL_FREQ_HZ A1Z_CAN_INTER_COMMAND_DELAY_S \
  A1Z_GRIPPER_MAX_TORQUE \
  A1Z_GRIPPER_EMPTY_CLOSE_THRESHOLD A1Z_ARM_FEEDBACK_STARTUP_TIMEOUT_S \
  A1Z_SOCKET_PATH \
  A1Z_TCP_HOST A1Z_TCP_PORT A1Z_WITH_GRIPPER ROS_DOMAIN_ID \
  A1Z_D405_ENABLED; do
  if [[ -n "${!name:-}" ]]; then
    ENV_ARGS+=(-e "$name=${!name}")
  fi
done
ENV_ARGS+=(-e "PYTHONPATH=/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z")

exec docker exec \
  -u "$(id -u):$(id -g)" \
  -w /workspace/A1Z \
  "${ENV_ARGS[@]}" \
  "$CONTAINER_NAME" \
  /usr/bin/python3 "$@"
