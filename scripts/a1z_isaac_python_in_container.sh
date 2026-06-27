#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
DOCKER_ENV_ARGS=()

for var_name in \
  A1Z_WORLD_USD \
  A1Z_SERVER_IP \
  A1Z_SOCKET_PATH \
  A1Z_WITH_GRIPPER \
  A1Z_ISAAC_ARTICULATION_ROOT \
  A1Z_ISAAC_CONTROL_FREQ_HZ \
  A1Z_D405_ENABLED \
  A1Z_D405_PARENT_PRIM \
  A1Z_D405_FALLBACK_PARENT_PRIM \
  A1Z_D405_FK_FRAME \
  A1Z_D405_MOUNT_OFFSET \
  A1Z_D405_MOUNT_RPY_DEG \
  A1Z_D405_CAMERA_OPTICAL_RPY_DEG \
  A1Z_D405_CAMERA_PRIMS_ENABLED \
  A1Z_D405_CENTER_MESH_Y \
  A1Z_D405_CENTER_ON_AXIS \
  A1Z_D405_STATUS_PATH \
  A1Z_D405_ROS2_NAMESPACE \
  A1Z_D405_COLOR_FRAME_ID \
  A1Z_D405_DEPTH_FRAME_ID \
  A1Z_D405_WIDTH \
  A1Z_D405_HEIGHT \
  A1Z_D405_FRAME_SKIP_COUNT \
  A1Z_WORKSPACE_CONTAINER; do
  if [[ -n "${!var_name:-}" ]]; then
    DOCKER_ENV_ARGS+=(-e "$var_name=${!var_name}")
  fi
done

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

exec docker exec -u ubuntu "${DOCKER_ENV_ARGS[@]}" "$CONTAINER_NAME" /isaac-sim/python.sh "$@"
