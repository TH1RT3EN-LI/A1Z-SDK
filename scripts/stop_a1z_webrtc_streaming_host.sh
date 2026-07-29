#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
SOCKET_PATH="${A1Z_SOCKET_PATH:-/tmp/a1z.sock}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  echo "Container is not running: $CONTAINER_NAME"
  exit 0
fi

docker exec -u ubuntu "$CONTAINER_NAME" /workspace/A1Z/scripts/stop_a1z_webrtc_streaming.sh

for _ in $(seq 1 20); do
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
    if [[ -S '$SOCKET_PATH' ]] && ! ss -xl | grep -F '$SOCKET_PATH' >/dev/null; then
      rm -f '$SOCKET_PATH'
    fi
  " >/dev/null 2>&1 || true

  if ! docker exec -u ubuntu "$CONTAINER_NAME" test -S "$SOCKET_PATH"; then
    echo "A1Z SDK socket is stopped: $SOCKET_PATH"
    exit 0
  fi
  sleep 0.5
done

echo "Warning: A1Z SDK socket is still present: $SOCKET_PATH" >&2
