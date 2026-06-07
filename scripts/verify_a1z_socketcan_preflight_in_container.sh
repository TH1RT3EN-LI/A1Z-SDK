#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
CAN_CHANNEL="${A1Z_CAN_CHANNEL:-can0}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

echo "Container: $CONTAINER_NAME"
echo "Expected backend: socketcan"
echo "CAN channel: $CAN_CHANNEL"
echo

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c '
from a1z.config import get_default_backend, get_default_can_channel, get_socket_path
print(f"default backend: {get_default_backend()}")
print(f"default can: {get_default_can_channel()}")
print(f"socket path: {get_socket_path()}")
'

echo
echo "Visible CAN interfaces in container:"
docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "ip -brief link show type can || true"
echo

if ! docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "ip link show '$CAN_CHANNEL' >/dev/null 2>&1"; then
  echo "SocketCAN interface not found in container: $CAN_CHANNEL" >&2
  echo "If no physical arm is attached yet, this is expected." >&2
  echo "When hardware is ready, bring up the host CAN interface first, then rerun this preflight." >&2
  exit 1
fi

echo "SocketCAN interface is present: $CAN_CHANNEL"
echo "The real-arm control path is ready for hardware bring-up."
