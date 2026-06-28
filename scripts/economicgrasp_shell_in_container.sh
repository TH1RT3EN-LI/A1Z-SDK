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

DOCKER_TTY_ARGS=()
if [[ -t 0 && -t 1 ]]; then
  DOCKER_TTY_ARGS=(-it)
fi

docker exec "${DOCKER_TTY_ARGS[@]}" "$ECONOMICGRASP_CONTAINER_NAME" bash -lc "
  set -euo pipefail
  if [[ -d '$ECONOMICGRASP_VENV_DIR' ]]; then
    source '$ECONOMICGRASP_VENV_DIR/bin/activate'
  fi
  export PYTHONPATH='$ECONOMICGRASP_REPO_DIR:/workspace/A1Z'
  cd '$ECONOMICGRASP_REPO_DIR'
  exec bash -i
"
