#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_VENV_DIR="${A1Z_VISION_VENV_DIR:-/opt/venvs/a1z-vision}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -u "${HOST_UID}:${HOST_GID}" \
  -e A1Z_VISION_VENV_DIR="$VISION_VENV_DIR" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source "'"$VISION_VENV_DIR"'/bin/activate"
    cd /workspace/A1Z
    python3 scripts/run_grconvnet_inference.py "$@"
  ' -- "$@"
