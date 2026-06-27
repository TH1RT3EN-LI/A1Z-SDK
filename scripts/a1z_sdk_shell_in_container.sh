#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
VENV_DIR="${A1Z_SDK_VENV_DIR:-/home/ubuntu/.venvs/a1z-sdk}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

exec docker exec -it -u ubuntu "$CONTAINER_NAME" bash -lc "source '$VENV_DIR/bin/activate' && export PYTHONPATH=/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z\${PYTHONPATH:+:\$PYTHONPATH} && cd /workspace/A1Z && exec bash"
