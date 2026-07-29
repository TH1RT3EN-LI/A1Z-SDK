#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${A1Z_WORKSPACE_CONTAINER:-/workspace/A1Z}"
if [[ -f "$ROOT_DIR/scripts/load_a1z_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/scripts/load_a1z_env.sh"
fi

PID_FILE="$ROOT_DIR/runtime/logs/isaac-sim-streaming.pid"
SERVER_IP_FILE="$ROOT_DIR/runtime/logs/isaac-sim-streaming.server-ip"
MODE_FILE="$ROOT_DIR/runtime/logs/isaac-sim-streaming.mode"
STARTUP_SCRIPT="$ROOT_DIR/scripts/open_a1z_world_with_a1z_sdk.py"
SOCKET_PATH="${A1Z_SOCKET_PATH:-/tmp/a1z.sock}"
VENV_PYTHON="${A1Z_SDK_VENV_DIR:-/home/ubuntu/.venvs/a1z-sdk}/bin/python"

if [[ -S "$SOCKET_PATH" ]]; then
  A1Z_SOCKET_PATH="$SOCKET_PATH" \
    PYTHONPATH="$ROOT_DIR/vendor/GALAXEA-A1Z:$ROOT_DIR" \
    "$VENV_PYTHON" "$ROOT_DIR/tools/a1zctl" stop >/dev/null 2>&1 || true
fi

if [[ -f "$PID_FILE" ]]; then
  STREAM_PID="$(cat "$PID_FILE")"
  if [[ -n "$STREAM_PID" ]] && kill -0 "$STREAM_PID" 2>/dev/null; then
    kill "$STREAM_PID"
    echo "Stopped Isaac Sim streaming PID $STREAM_PID"
  else
    echo "PID $STREAM_PID is not running."
  fi
else
  echo "No PID file found. Falling back to process-name cleanup."
fi

while read -r pid; do
  [[ -n "$pid" ]] || continue
  kill "$pid" >/dev/null 2>&1 || true
done < <(
  ps -ef \
    | grep -F "$STARTUP_SCRIPT" \
    | grep -E 'isaacsim.exp.full.streaming.kit|/isaac-sim/runheadless.sh' \
    | grep -v grep \
    | awk '{print $2}' \
    || true
)

for _ in $(seq 1 20); do
  STILL_RUNNING="$(
    ps -ef \
      | grep -F "$STARTUP_SCRIPT" \
      | grep -E 'isaacsim.exp.full.streaming.kit|/isaac-sim/runheadless.sh' \
      | grep -v grep \
      | awk '{print $2}' \
      || true
  )"
  if [[ -z "$STILL_RUNNING" ]]; then
    break
  fi
  sleep 0.5
done

if [[ -n "${STILL_RUNNING:-}" ]]; then
  echo "Warning: some Isaac streaming processes are still running: $STILL_RUNNING" >&2
fi

rm -f "$PID_FILE"
rm -f "$SERVER_IP_FILE"
rm -f "$MODE_FILE"
