#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${A1Z_WORKSPACE_CONTAINER:-/workspace/A1Z}"
if [[ -f "$ROOT_DIR/scripts/load_a1z_container_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
fi

LOG_DIR="$ROOT_DIR/runtime/logs"
PID_FILE="$LOG_DIR/isaac-sim-streaming.pid"
LOG_FILE="$LOG_DIR/isaac-sim-streaming.log"
SERVER_IP_FILE="$LOG_DIR/isaac-sim-streaming.server-ip"
MODE_FILE="$LOG_DIR/isaac-sim-streaming.mode"
WORLD_USD="${A1Z_WORLD_USD:-$ROOT_DIR/build/scenes/A1Z_G1Z_world.usd}"
SERVER_IP="${1:-${A1Z_SERVER_IP:-10.66.0.11}}"
PORTABLE_ROOT="${A1Z_STREAMING_PORTABLE_ROOT:-${A1Z_PORTABLE_ROOT:-$ROOT_DIR/runtime/isaac-sim-portable/streaming}}"
STARTUP_SCRIPT="${A1Z_ISAAC_STARTUP_SCRIPT:-$ROOT_DIR/scripts/open_a1z_world_with_a1z_sdk.py}"
SIGNAL_PORT="${A1Z_WEBRTC_SIGNAL_PORT:-49100}"
STREAM_PORT="${A1Z_WEBRTC_STREAM_PORT:-47998}"
GRAVITY_MODE="${A1Z_ISAAC_GRAVITY_MODE:-0}"
WITH_GRIPPER="${A1Z_WITH_GRIPPER:-1}"
CONTROL_FREQ_HZ="${A1Z_ISAAC_CONTROL_FREQ_HZ:-60}"
ARTICULATION_ROOT="${A1Z_ISAAC_ARTICULATION_ROOT:-}"
TCP_HOST="${A1Z_TCP_HOST:-}"
TCP_PORT="${A1Z_TCP_PORT:-}"
RUN_SIGNATURE="gravity=${GRAVITY_MODE};gripper=${WITH_GRIPPER};freq=${CONTROL_FREQ_HZ};root=${ARTICULATION_ROOT};world=${WORLD_USD};signal=${SIGNAL_PORT};stream=${STREAM_PORT}"
SIGNATURE_INPUTS=(
  "$ROOT_DIR/scripts/open_a1z_world_with_a1z_sdk.py"
  "$ROOT_DIR/a1z_ext/robots/server.py"
  "$ROOT_DIR/a1z_ext/robots/isaacsim_robot.py"
  "$ROOT_DIR/a1z_ext/robots/get_robot.py"
)
SIGNATURE_HASH="$(
  {
    for path in "${SIGNATURE_INPUTS[@]}"; do
      if [[ -f "$path" ]]; then
        sha256sum "$path"
      else
        echo "missing  $path"
      fi
    done
  } | sha256sum | awk '{print $1}'
)"
RUN_SIGNATURE="${RUN_SIGNATURE};code=${SIGNATURE_HASH}"
RUNNING_KIT_PID="$(
  ps -ef \
    | grep -F "$STARTUP_SCRIPT" \
    | grep 'isaacsim.exp.full.streaming.kit' \
    | grep -v grep \
    | awk 'NR==1 {print $2}' \
    || true
)"
RUNNING_SHELL_PID="$(
  ps -ef \
    | grep -F "$STARTUP_SCRIPT" \
    | grep '/isaac-sim/runheadless.sh' \
    | grep -v grep \
    | awk 'NR==1 {print $2}' \
    || true
)"

mkdir -p "$LOG_DIR"
RUNHEADLESS_ARGS=()
if [[ -n "$PORTABLE_ROOT" ]]; then
  mkdir -p \
    "$PORTABLE_ROOT" \
    "$PORTABLE_ROOT/cache/DerivedDataCache" \
    "$PORTABLE_ROOT/cache/shadercache" \
    "$PORTABLE_ROOT/data" \
    "$PORTABLE_ROOT/logs"
  RUNHEADLESS_ARGS+=(--portable-root "$PORTABLE_ROOT")
fi

if [[ ! -f "$WORLD_USD" ]]; then
  echo "World USD not found: $WORLD_USD" >&2
  exit 1
fi

if [[ -f "$PID_FILE" ]]; then
  CURRENT_PID="$(cat "$PID_FILE")"
  if [[ -n "$CURRENT_PID" ]] && kill -0 "$CURRENT_PID" 2>/dev/null; then
    CURRENT_SIGNATURE="$(cat "$MODE_FILE" 2>/dev/null || true)"
    if [[ "$CURRENT_SIGNATURE" == "$RUN_SIGNATURE" ]]; then
      echo "Isaac Sim streaming is already running with PID $CURRENT_PID"
      if [[ -f "$SERVER_IP_FILE" ]]; then
        echo "Server IP: $(cat "$SERVER_IP_FILE")"
      fi
      exit 0
    fi
    "$ROOT_DIR/scripts/stop_a1z_webrtc_streaming.sh" >/dev/null 2>&1 || true
  fi
  rm -f "$PID_FILE"
fi

if [[ -n "$RUNNING_KIT_PID" || -n "$RUNNING_SHELL_PID" ]]; then
  ACTIVE_PID="${RUNNING_KIT_PID:-$RUNNING_SHELL_PID}"
  CURRENT_SIGNATURE="$(cat "$MODE_FILE" 2>/dev/null || true)"
  if [[ "$CURRENT_SIGNATURE" == "$RUN_SIGNATURE" ]]; then
    echo "$ACTIVE_PID" >"$PID_FILE"
    echo "Isaac Sim streaming is already running with PID $ACTIVE_PID"
    if [[ -f "$SERVER_IP_FILE" ]]; then
      echo "Server IP: $(cat "$SERVER_IP_FILE")"
    else
      echo "Server IP: unknown; use stop/start or --restart from the host wrapper if the endpoint changed."
    fi
    exit 0
  fi
  "$ROOT_DIR/scripts/stop_a1z_webrtc_streaming.sh" >/dev/null 2>&1 || true
fi

nohup env \
  A1Z_WORLD_USD="$WORLD_USD" \
  A1Z_ISAAC_GRAVITY_MODE="$GRAVITY_MODE" \
  A1Z_WITH_GRIPPER="$WITH_GRIPPER" \
  A1Z_ISAAC_CONTROL_FREQ_HZ="$CONTROL_FREQ_HZ" \
  A1Z_ISAAC_ARTICULATION_ROOT="$ARTICULATION_ROOT" \
  A1Z_TCP_HOST="$TCP_HOST" \
  A1Z_TCP_PORT="$TCP_PORT" \
  /isaac-sim/runheadless.sh \
  "${RUNHEADLESS_ARGS[@]}" \
  --ext-folder "$ROOT_DIR/exts" \
  --/app/livestream/publicEndpointAddress="$SERVER_IP" \
  --/exts/omni.kit.livestream.app/primaryStream/publicIp="$SERVER_IP" \
  --/exts/omni.kit.livestream.app/primaryStream/signalPort="$SIGNAL_PORT" \
  --/exts/omni.kit.livestream.app/primaryStream/streamPort="$STREAM_PORT" \
  --exec "$STARTUP_SCRIPT" \
  >"$LOG_FILE" 2>&1 &

STREAM_PID=$!
KIT_PID="$(
  for _ in $(seq 1 40); do
    pid="$(
      ps -ef \
        | awk -v ppid="$STREAM_PID" '
            $3 == ppid && $0 ~ /isaacsim\.exp\.full\.streaming\.kit/ { print $2; exit }
          '
    )"
    if [[ -n "$pid" ]]; then
      echo "$pid"
      break
    fi
    sleep 0.5
  done
)"

if [[ -n "$KIT_PID" ]]; then
  echo "$KIT_PID" >"$PID_FILE"
else
  echo "$STREAM_PID" >"$PID_FILE"
fi
echo "$SERVER_IP" >"$SERVER_IP_FILE"
echo "$RUN_SIGNATURE" >"$MODE_FILE"

echo "Started Isaac Sim WebRTC streaming."
echo "PID: $STREAM_PID"
if [[ -n "$KIT_PID" ]]; then
  echo "Kit PID: $KIT_PID"
fi
echo "Server IP: $SERVER_IP"
echo "Signal port: $SIGNAL_PORT"
echo "Stream port: $STREAM_PORT"
echo "World USD: $WORLD_USD"
echo "Startup script: $STARTUP_SCRIPT"
if [[ -n "$PORTABLE_ROOT" ]]; then
  echo "Portable root: $PORTABLE_ROOT"
fi
echo "Log: $LOG_FILE"
