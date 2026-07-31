#!/usr/bin/env bash

# Start/stop the one SDK-owning control service selected by A1Z_PROFILE.
# Real and simulation use different TCP ports; this script never kills a
# process belonging to the other profile.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

ACTION="${1:-status}"
shift || true
GRAVITY_MODE=0
GRAVITY_FACTOR="${A1Z_GRAVITY_COMP_FACTOR:-1.0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --gravity-mode)
      GRAVITY_MODE=1
      ;;
    --gravity-factor)
      GRAVITY_FACTOR="${2:?missing value for --gravity-factor}"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$ACTION" in
  start|stop|restart|status) ;;
  *)
    echo "Usage: $0 {start|stop|restart|status} [--gravity-mode] [--gravity-factor 0..1]" >&2
    exit 2
    ;;
esac

EXPECTED_BACKEND="${A1Z_BACKEND:?profile must define A1Z_BACKEND}"
PROFILE_NAME="${A1Z_PROFILE:?profile must be explicit}"
SIM_LAUNCH_MODE="${A1Z_ISAAC_LAUNCH_MODE:-container}"
LOG_DIR="$ROOT_DIR/runtime/logs"
LOG_PATH="$LOG_DIR/a1z-control-${PROFILE_NAME}.log"
mkdir -p "$LOG_DIR"

probe_identity() {
  local output
  if ! output="$(
    A1Z_PROFILE="$PROFILE_NAME" \
      "$ROOT_DIR/scripts/a1zctl_in_container.sh" --json info 2>/dev/null
  )"; then
    return 1
  fi
  python3 - "$EXPECTED_BACKEND" "$output" <<'PY'
import json
import sys

expected = sys.argv[1]
payload = json.loads(sys.argv[2])
raise SystemExit(0 if payload.get("backend") == expected else 3)
PY
}

probe_healthy() {
  local output
  if ! output="$(
    A1Z_PROFILE="$PROFILE_NAME" \
      "$ROOT_DIR/scripts/a1zctl_in_container.sh" --json info 2>/dev/null
  )"; then
    return 1
  fi
  python3 - "$EXPECTED_BACKEND" "$output" <<'PY'
import json
import sys

expected = sys.argv[1]
payload = json.loads(sys.argv[2])
healthy = (
    payload.get("backend") == expected
    and payload.get("running") is True
    and not payload.get("faulted", False)
)
raise SystemExit(0 if healthy else 3)
PY
}

find_native_kit_pid() {
  [[ "$PROFILE_NAME" == "sim" && "$SIM_LAUNCH_MODE" == "native" ]] || return 1
  [[ "${A1Z_TCP_PORT:-}" =~ ^[0-9]+$ ]] || return 1
  local socket_line pid command_line
  socket_line="$(ss -H -ltnp "sport = :$A1Z_TCP_PORT" 2>/dev/null || true)"
  pid="$(sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' <<<"$socket_line" | head -n 1)"
  [[ -n "$pid" && -r "/proc/$pid/cmdline" ]] || return 1
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
  [[ "$command_line" == *"/kit/kit "* ]] || return 1
  [[ "$command_line" == *"open_a1z_world_with_a1z_sdk.py"* ]] || return 1
  printf '%s\n' "$pid"
}

stop_native_kit() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null || return 0
  kill -INT "$pid"
  for _ in $(seq 1 60); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.25
  done
  echo "Native Isaac Kit did not exit after SIGINT (pid=$pid)." >&2
  return 1
}

stop_service() {
  local native_pid=""
  native_pid="$(find_native_kit_pid || true)"
  if ! probe_identity; then
    if [[ -n "$native_pid" ]]; then
      stop_native_kit "$native_pid"
      echo "A1Z ${PROFILE_NAME} native Isaac runtime stopped."
      return 0
    fi
    echo "A1Z ${PROFILE_NAME} control service is already stopped."
    return 0
  fi
  A1Z_PROFILE="$PROFILE_NAME" \
    "$ROOT_DIR/scripts/a1zctl_in_container.sh" --json stop
  for _ in $(seq 1 30); do
    if ! probe_identity; then
      if [[ -n "$native_pid" ]]; then
        stop_native_kit "$native_pid"
      fi
      echo "A1Z ${PROFILE_NAME} control service stopped."
      return 0
    fi
    sleep 0.2
  done
  echo "Timed out waiting for A1Z ${PROFILE_NAME} control service to stop." >&2
  return 1
}

if [[ "$ACTION" == "status" ]]; then
  if probe_healthy; then
    echo "A1Z ${PROFILE_NAME} control service is online: ${EXPECTED_BACKEND} at ${A1Z_TCP_HOST}:${A1Z_TCP_PORT}"
    exit 0
  fi
  if probe_identity; then
    echo "A1Z ${PROFILE_NAME} endpoint is reachable, but its robot control loop is not healthy." >&2
    exit 1
  fi
  echo "A1Z ${PROFILE_NAME} control service is offline or has the wrong backend." >&2
  exit 1
fi

if [[ "$ACTION" == "stop" ]]; then
  stop_service
  exit $?
fi

if [[ "$ACTION" == "restart" ]]; then
  stop_service
fi

if probe_healthy; then
  echo "Reusing verified A1Z ${PROFILE_NAME} service at ${A1Z_TCP_HOST}:${A1Z_TCP_PORT}."
  exit 0
fi
if probe_identity; then
  echo "Stopping reachable but unhealthy A1Z ${PROFILE_NAME} service before restart."
  stop_service
fi

if [[ "$PROFILE_NAME" == "sim" ]]; then
  export A1Z_ISAAC_GRAVITY_MODE="$GRAVITY_MODE"
  export A1Z_GRAVITY_COMP_FACTOR="$GRAVITY_FACTOR"
  if [[ "$SIM_LAUNCH_MODE" == "native" ]]; then
    stale_pid="$(find_native_kit_pid || true)"
    if [[ -n "$stale_pid" ]]; then
      echo "Native Isaac Kit pid=$stale_pid owns port $A1Z_TCP_PORT but the SDK endpoint is not healthy." >&2
      echo "Stop it explicitly before starting another SDK owner." >&2
      exit 1
    fi
    /usr/bin/setsid --fork env \
      A1Z_PROFILE=sim \
      A1Z_EE_DRAG_TARGET_ENABLED=0 \
      A1Z_WORLD_USD="$ROOT_DIR/build/scenes/A1Z_G1Z_world.usd" \
      A1Z_CONTROL_URDF="$ROOT_DIR/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf" \
      A1Z_D405_STATUS_PATH="$ROOT_DIR/runtime/logs/d405-link-camera.status" \
      "$ROOT_DIR/scripts/open_a1z_isaac_app.sh" \
      >"$LOG_PATH" 2>&1 </dev/null &
  elif [[ "$SIM_LAUNCH_MODE" == "container" ]]; then
    A1Z_PROFILE=sim "$ROOT_DIR/scripts/open_a1z_webrtc_host.sh" --no-client
  else
    echo "Unsupported A1Z_ISAAC_LAUNCH_MODE='$SIM_LAUNCH_MODE'." >&2
    exit 2
  fi
else
  "$ROOT_DIR/scripts/create_a1z_ros2_container.sh"
  CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:?real profile needs a ROS container}"
  docker start "$CONTAINER_NAME" >/dev/null

  ENV_ARGS=()
  for name in \
    A1Z_PROFILE A1Z_BACKEND A1Z_CAN_CHANNEL A1Z_CONTROL_FREQ_HZ \
    A1Z_MIN_CONTROL_FREQ_HZ A1Z_GRIPPER_MAX_TORQUE \
    A1Z_GRIPPER_EMPTY_CLOSE_THRESHOLD A1Z_SOCKET_PATH \
    A1Z_TCP_HOST A1Z_TCP_PORT A1Z_WITH_GRIPPER; do
    if [[ -n "${!name:-}" ]]; then
      ENV_ARGS+=(-e "$name=${!name}")
    fi
  done
  ENV_ARGS+=(-e "PYTHONPATH=/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z")

  SERVER_ARGS=(
    /usr/bin/python3
    /workspace/A1Z/tools/a1zctl
    serve
    --backend "$A1Z_BACKEND"
    --can "$A1Z_CAN_CHANNEL"
    --tcp-host "$A1Z_TCP_HOST"
    --tcp-port "$A1Z_TCP_PORT"
    --with-gripper
    --control-freq "$A1Z_CONTROL_FREQ_HZ"
    --min-control-freq "$A1Z_MIN_CONTROL_FREQ_HZ"
    --gripper-max-torque "$A1Z_GRIPPER_MAX_TORQUE"
    --gripper-empty-close-threshold "$A1Z_GRIPPER_EMPTY_CLOSE_THRESHOLD"
    --gravity-factor "$GRAVITY_FACTOR"
  )
  if [[ "$GRAVITY_MODE" == "1" ]]; then
    SERVER_ARGS+=(--gravity-mode)
  fi

  docker exec -d \
    -u "$(id -u):$(id -g)" \
    -w /workspace/A1Z \
    "${ENV_ARGS[@]}" \
    "$CONTAINER_NAME" \
    bash -lc 'log_path="$1"; shift; exec "$@" > "$log_path" 2>&1' bash \
    "/workspace/A1Z/runtime/logs/a1z-control-${A1Z_PROFILE}.log" \
    "${SERVER_ARGS[@]}"
fi

READY_COUNT=0
for _ in $(seq 1 90); do
  if probe_healthy; then
    READY_COUNT=$((READY_COUNT + 1))
    if [[ "$READY_COUNT" -ge 3 ]]; then
      echo "A1Z ${PROFILE_NAME} control service ready: ${EXPECTED_BACKEND} at ${A1Z_TCP_HOST}:${A1Z_TCP_PORT}"
      echo "Log: $LOG_PATH"
      exit 0
    fi
  else
    READY_COUNT=0
  fi
  sleep 1
done

echo "A1Z ${PROFILE_NAME} service did not become ready. Log: $LOG_PATH" >&2
exit 1
