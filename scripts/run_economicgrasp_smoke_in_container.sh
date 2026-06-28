#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ECONOMICGRASP_CONTAINER_NAME="${A1Z_ECONOMICGRASP_CONTAINER_NAME:-a1z-economicgrasp-gpu}"
ECONOMICGRASP_VENV_DIR="${A1Z_ECONOMICGRASP_VENV_DIR:-/opt/venvs/economicgrasp}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ECONOMICGRASP_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ECONOMICGRASP_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -u "${HOST_UID}:${HOST_GID}" \
  -e A1Z_ECONOMICGRASP_VENV_DIR="$ECONOMICGRASP_VENV_DIR" \
  "$ECONOMICGRASP_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source "'"$ECONOMICGRASP_VENV_DIR"'/bin/activate"
    cd /workspace/A1Z
    python3 scripts/run_economicgrasp_smoke.py "$@"
  ' -- "$@"
