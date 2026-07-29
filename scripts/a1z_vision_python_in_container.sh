#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_VENV_DIR="${A1Z_VISION_VENV_DIR:-/opt/venvs/a1z-vision}"
DOCKER_USER="${A1Z_CONTAINER_DOCKER_USER:-$(id -u):$(id -g)}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

exec docker exec \
  -u "$DOCKER_USER" \
  -e HOME="/tmp/a1z-home-$(id -u)" \
  -e XDG_RUNTIME_DIR="/tmp/a1z-runtime-$(id -u)" \
  -e MPLCONFIGDIR="/tmp/a1z-mpl-$(id -u)" \
  -e PYTHONPATH="/workspace/A1Z" \
  "$VISION_CONTAINER_NAME" \
  bash -lc 'mkdir -p "$HOME" "$MPLCONFIGDIR" "$XDG_RUNTIME_DIR" && exec "$0" "$@"' \
  "$VISION_VENV_DIR/bin/python" "$@"
