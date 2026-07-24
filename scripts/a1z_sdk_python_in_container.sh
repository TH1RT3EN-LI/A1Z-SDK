#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-a1z-isaac-sim-6-0-1}"
A1Z_SDK_VENV_DIR="${A1Z_SDK_VENV_DIR:?A1Z_SDK_VENV_DIR must be set by the selected runtime environment}"
VENV_PYTHON="$A1Z_SDK_VENV_DIR/bin/python"
PYTHON_COMMAND=("$VENV_PYTHON")
DOCKER_USER_ARGS=(-u ubuntu)
DOCKER_ENV_ARGS=()

# Isaac 6 mounts the project read-only and its /isaac-sim tree is private to
# uid 1234. Client-side planning/execution belongs in the isolated ROS tools
# container, which has Pinocchio, NumPy, a writable project mount, and the same
# host-network A1Z TCP endpoint.
if [[ "$CONTAINER_NAME" == *"6-0-1"* || "$CONTAINER_NAME" == *"isaac6"* ]]; then
  ROS_TOOLS_CONTAINER="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble-isaac6}"
  CONTAINER_NAME="$ROS_TOOLS_CONTAINER"
  VENV_PYTHON=/usr/bin/python3
  PYTHON_COMMAND=(/usr/bin/python3)
  DOCKER_USER_ARGS=(-u "$(id -u):$(id -g)")
fi

for var_name in \
  ROS_DOMAIN_ID \
  A1Z_CAN_CHANNEL \
  A1Z_SOCKET_PATH \
  A1Z_TCP_HOST \
  A1Z_TCP_PORT \
  A1Z_BACKEND \
  A1Z_D405_COMPUTE_INSTALL_RPY_DEG \
  A1Z_D405_COMPUTE_RECTIFY_RPY_DEG \
  A1Z_D405_COMPUTE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M; do
  if [[ -n "${!var_name:-}" ]]; then
    DOCKER_ENV_ARGS+=(-e "$var_name=${!var_name}")
  fi
done

DOCKER_ENV_ARGS+=(-e "PYTHONPATH=/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z")

if ! docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  ROS_IMAGE_TAG="${A1Z_ROS2_IMAGE_TAG:-a1z-ros2-humble:local}"
  if ! docker image inspect "$ROS_IMAGE_TAG" >/dev/null 2>&1; then
    echo "A1Z ROS tools container and image are unavailable: $CONTAINER_NAME / $ROS_IMAGE_TAG" >&2
    exit 4
  fi
  exec docker run --rm \
    --network host \
    "${DOCKER_USER_ARGS[@]}" \
    "${DOCKER_ENV_ARGS[@]}" \
    -v "$ROOT_DIR:/workspace/A1Z" \
    -w /workspace/A1Z \
    "$ROS_IMAGE_TAG" \
    "${PYTHON_COMMAND[@]}" "$@"
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

if ! docker exec "$CONTAINER_NAME" test -x "$VENV_PYTHON" >/dev/null 2>&1; then
  if docker exec "$CONTAINER_NAME" test -x /isaac-sim/python.sh >/dev/null 2>&1; then
    PYTHON_COMMAND=(bash /isaac-sim/python.sh)
  else
    echo "A1Z Python runtime is unavailable in $CONTAINER_NAME: $VENV_PYTHON" >&2
    exit 4
  fi
fi

exec docker exec \
  -w /workspace/A1Z \
  "${DOCKER_USER_ARGS[@]}" \
  "${DOCKER_ENV_ARGS[@]}" \
  "$CONTAINER_NAME" \
  "${PYTHON_COMMAND[@]}" "$@"
