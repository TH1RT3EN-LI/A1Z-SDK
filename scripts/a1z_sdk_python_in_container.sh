#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
VENV_PYTHON="${A1Z_SDK_VENV_DIR:-/home/ubuntu/.venvs/a1z-sdk}/bin/python"
DOCKER_ENV_ARGS=()

for var_name in \
  A1Z_CAN_CHANNEL \
  A1Z_SOCKET_PATH \
  A1Z_BACKEND \
  A1Z_D405_COMPUTE_INSTALL_RPY_DEG \
  A1Z_D405_COMPUTE_RECTIFY_RPY_DEG \
  A1Z_D405_COMPUTE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M; do
  if [[ -n "${!var_name:-}" ]]; then
    DOCKER_ENV_ARGS+=(-e "$var_name=${!var_name}")
  fi
done

DOCKER_ENV_ARGS+=(-e "PYTHONPATH=/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z")

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

exec docker exec -u ubuntu "${DOCKER_ENV_ARGS[@]}" "$CONTAINER_NAME" "$VENV_PYTHON" "$@"
