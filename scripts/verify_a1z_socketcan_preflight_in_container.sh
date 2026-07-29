#!/usr/bin/env bash

# Read-only real-hardware preflight. It never enables motors or changes CAN state.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${A1Z_PROFILE:-}" != "real" ]]; then
  echo "Refusing implicit hardware selection. Run with A1Z_PROFILE=real." >&2
  exit 2
fi
source "$ROOT_DIR/scripts/load_a1z_env.sh"
CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:?}"
CAN_CHANNEL="${A1Z_CAN_CHANNEL:-can0}"

if ! docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  "$ROOT_DIR/scripts/create_a1z_ros2_container.sh"
fi
if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

echo "Profile: $A1Z_PROFILE"
echo "Container: $CONTAINER_NAME"
echo "Backend: $A1Z_BACKEND"
echo "CAN: $CAN_CHANNEL"

docker exec "$CONTAINER_NAME" bash -lc \
  "command -v ip && command -v candump && python3 -c 'import can; print(can.__version__)'"

failures=0
if ! docker exec "$CONTAINER_NAME" ip link show "$CAN_CHANNEL" >/dev/null 2>&1; then
  echo "Missing SocketCAN interface: $CAN_CHANNEL" >&2
  failures=$((failures + 1))
else
  docker exec "$CONTAINER_NAME" ip -details link show "$CAN_CHANNEL"
fi

if [[ ! -d /dev/bus/usb ]]; then
  echo "Host USB bus is unavailable." >&2
  failures=$((failures + 1))
elif ! docker exec "$CONTAINER_NAME" test -d /dev/bus/usb; then
  echo "Container does not have the host USB bus mounted." >&2
  failures=$((failures + 1))
fi

if command -v lsusb >/dev/null 2>&1; then
  if ! lsusb | grep -Ei 'Intel.*RealSense|8086:'; then
    echo "No Intel RealSense device detected on the host." >&2
    failures=$((failures + 1))
  fi
fi

if (( failures > 0 )); then
  echo "Physical preflight failed with $failures missing prerequisite(s)." >&2
  exit 1
fi

echo "Read-only SocketCAN and D405 container preflight passed."
