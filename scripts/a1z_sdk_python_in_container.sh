#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"
CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:?selected profile must define A1Z_ROS2_CONTAINER_NAME}"

if ! docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  "$ROOT_DIR/scripts/create_a1z_ros2_container.sh"
fi
if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

ENV_ARGS=()
for name in \
  A1Z_PROFILE A1Z_BACKEND A1Z_CAN_CHANNEL A1Z_CONTROL_FREQ_HZ \
  A1Z_MIN_CONTROL_FREQ_HZ A1Z_GRIPPER_MAX_TORQUE \
  A1Z_GRIPPER_EMPTY_CLOSE_THRESHOLD A1Z_SOCKET_PATH \
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
