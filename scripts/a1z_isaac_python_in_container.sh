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
  A1Z_ISAAC_CONTROL_FREQ_HZ; do
  if [[ -n "${!var_name:-}" ]]; then
    DOCKER_ENV_ARGS+=(-e "$var_name=${!var_name}")
  fi
done

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

exec docker exec -u ubuntu "${DOCKER_ENV_ARGS[@]}" "$CONTAINER_NAME" /isaac-sim/python.sh "$@"
