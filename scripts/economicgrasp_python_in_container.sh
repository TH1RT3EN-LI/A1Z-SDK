#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ECONOMICGRASP_CONTAINER_NAME="${A1Z_ECONOMICGRASP_CONTAINER_NAME:-a1z-economicgrasp-gpu}"
ECONOMICGRASP_VENV_DIR="${A1Z_ECONOMICGRASP_VENV_DIR:-/opt/venvs/economicgrasp}"
ECONOMICGRASP_REPO_DIR="${A1Z_ECONOMICGRASP_REPO_DIR:-/workspace/A1Z/vendor/vision/EconomicGrasp}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ECONOMICGRASP_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ECONOMICGRASP_CONTAINER_NAME" >/dev/null
fi

exec docker exec \
  -e PYTHONPATH="$ECONOMICGRASP_REPO_DIR:/workspace/A1Z" \
  "$ECONOMICGRASP_CONTAINER_NAME" \
  "$ECONOMICGRASP_VENV_DIR/bin/python" "$@"
