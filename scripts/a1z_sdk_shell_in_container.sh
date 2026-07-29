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

exec docker exec -it \
  -u "$(id -u):$(id -g)" \
  -e "A1Z_PROFILE=$A1Z_PROFILE" \
  -e "A1Z_BACKEND=$A1Z_BACKEND" \
  -e "A1Z_CAN_CHANNEL=$A1Z_CAN_CHANNEL" \
  -e "A1Z_TCP_HOST=$A1Z_TCP_HOST" \
  -e "A1Z_TCP_PORT=$A1Z_TCP_PORT" \
  -e "PYTHONPATH=/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z" \
  -w /workspace/A1Z \
  "$CONTAINER_NAME" bash
