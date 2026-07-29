#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
SOCKET_PATH="${A1Z_SOCKET_PATH:-/tmp/a1z.sock}"

CONTAINER_RUNNING="$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)"
if [[ "$CONTAINER_RUNNING" != "true" ]]; then
  echo "Container: $CONTAINER_NAME (stopped)"
  exit 0
fi

echo "Container: $CONTAINER_NAME (running)"

PID_FILE_VALUE="$(docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "cat /workspace/A1Z/runtime/logs/isaac-sim-streaming.pid 2>/dev/null || true")"
if [[ -n "$PID_FILE_VALUE" ]]; then
  echo "PID file:   $PID_FILE_VALUE"
else
  echo "PID file:   missing"
fi

echo "Processes:"
docker exec -u ubuntu "$CONTAINER_NAME" bash -lc \
  "ps -ef | grep -E 'isaacsim.exp.full.streaming.kit|runheadless|open_a1z_world_with_a1z_sdk' | grep -v grep || true"

echo
echo "Socket:"
docker exec -u ubuntu "$CONTAINER_NAME" bash -lc \
  "ss -xlp | grep -F '$SOCKET_PATH' || true"

echo
echo "Backend:"
if INFO_OUTPUT="$("$ROOT_DIR/scripts/a1zctl_in_container.sh" info 2>/dev/null)"; then
  echo "$INFO_OUTPUT"
else
  echo "a1zctl info unavailable"
fi
