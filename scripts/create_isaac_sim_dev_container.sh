#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
IMAGE_NAME="${ISAAC_SIM_IMAGE:-nvcr.io/nvidia/isaac-sim:5.1.0}"
WORKSPACE_HOST="${A1Z_WORKSPACE_HOST:-$ROOT_DIR}"
WORKSPACE_CONTAINER="${A1Z_WORKSPACE_CONTAINER:-/workspace/A1Z}"
HOME_HOST="${ISAAC_SIM_HOME_HOST:-/home/th1rt3en/.local/share/isaac-sim-5.1-dev/home}"
HOME_CONTAINER="${ISAAC_SIM_HOME_CONTAINER:-/home/ubuntu}"

mkdir -p "$HOME_HOST"

if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "Container already exists: $CONTAINER_NAME"
  echo "Start it with: docker start $CONTAINER_NAME"
  exit 0
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  --runtime=nvidia \
  --gpus all \
  --network host \
  --ipc host \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --shm-size=4g \
  -u 0:0 \
  -e ACCEPT_EULA=Y \
  -e PRIVACY_CONSENT=Y \
  -w "$WORKSPACE_CONTAINER" \
  -v "$WORKSPACE_HOST:$WORKSPACE_CONTAINER" \
  -v "$HOME_HOST:$HOME_CONTAINER" \
  --entrypoint /bin/bash \
  "$IMAGE_NAME" \
  -lc 'set -e; usermod -aG isaac-sim ubuntu; mkdir -p /home/ubuntu; chown -R 1000:1000 /home/ubuntu; trap : TERM INT; sleep infinity & wait'

echo "Created container: $CONTAINER_NAME"
