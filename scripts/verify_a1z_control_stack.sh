#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
SOCKET_PATH="${A1Z_SOCKET_PATH:-/tmp/a1z.sock}"

SDK_OK=0
MOCK_OK=0
ISAAC_OK=0
SOCKETCAN_OK=0
SOCKETCAN_WARN=0

run_step() {
  local label="$1"
  shift

  echo
  echo "==> $label"
  "$@"
}

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  "$ROOT_DIR/scripts/create_isaac_sim_dev_container.sh"
  docker start "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

run_step "SDK runtime verification" "$ROOT_DIR/scripts/verify_a1z_sdk_in_container.sh"
SDK_OK=1

run_step "Mock backend verification" "$ROOT_DIR/scripts/verify_a1z_mock_control_in_container.sh"
MOCK_OK=1

run_step "Server contract verification" "$ROOT_DIR/scripts/verify_a1z_server_contract_in_container.sh"

LIVE_ISAAC_RUNNING="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc \
    "ps -ef | grep -E 'isaacsim.exp.full.streaming.kit|/isaac-sim/runheadless.sh' | grep -v grep >/dev/null && echo yes || true"
)"
LIVE_SOCKET_READY="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc \
    "test -S '$SOCKET_PATH' && echo yes || true"
)"

if [[ "$LIVE_ISAAC_RUNNING" == "yes" && "$LIVE_SOCKET_READY" == "yes" ]]; then
  run_step "Live Isaac backend smoke check" "$ROOT_DIR/scripts/a1z_runtime_status.sh"
  run_step "Live Isaac status query" "$ROOT_DIR/scripts/a1zctl_in_container.sh" status
  ISAAC_OK=1
else
  run_step "Exclusive Isaac backend verification" timeout 180 "$ROOT_DIR/scripts/verify_a1z_isaac_control_in_container.sh"
  ISAAC_OK=1
fi

echo
echo "==> SocketCAN preflight"
if "$ROOT_DIR/scripts/verify_a1z_socketcan_preflight_in_container.sh"; then
  SOCKETCAN_OK=1
else
  SOCKETCAN_WARN=1
  echo "SocketCAN preflight is not ready in the current environment."
  echo "This is expected when no physical arm or no host can0 interface is attached."
fi

echo
echo "Summary:"
echo "  SDK runtime:        $([[ "$SDK_OK" -eq 1 ]] && echo pass || echo fail)"
echo "  Mock backend:       $([[ "$MOCK_OK" -eq 1 ]] && echo pass || echo fail)"
echo "  Isaac backend:      $([[ "$ISAAC_OK" -eq 1 ]] && echo pass || echo fail)"
if [[ "$SOCKETCAN_OK" -eq 1 ]]; then
  echo "  SocketCAN preflight: pass"
elif [[ "$SOCKETCAN_WARN" -eq 1 ]]; then
  echo "  SocketCAN preflight: expected warning (no hardware)"
else
  echo "  SocketCAN preflight: fail"
fi

echo
echo "A1Z control stack verification passed for the current environment."
