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
SERVICE_DEPLOYMENT="${A1Z_SERVICE_DEPLOYMENT:-docker}"
case "$SERVICE_DEPLOYMENT" in
  host|docker) ;;
  *)
    echo "Unsupported A1Z_SERVICE_DEPLOYMENT='$SERVICE_DEPLOYMENT' (expected host or docker)" >&2
    exit 2
    ;;
esac
SIM_LAUNCH_MODE="${A1Z_ISAAC_LAUNCH_MODE:-container}"
CAN_BITRATE="${A1Z_CAN_BITRATE:-1000000}"
LOG_DIR="$ROOT_DIR/runtime/logs"
if [[ "$PROFILE_NAME" == "real" && "$SERVICE_DEPLOYMENT" == "host" ]]; then
  LOG_PATH="$LOG_DIR/a1z-control-${PROFILE_NAME}-host.log"
else
  LOG_PATH="$LOG_DIR/a1z-control-${PROFILE_NAME}.log"
fi
HOST_PID_PATH="$LOG_DIR/a1z-control-${PROFILE_NAME}-host.pid"
mkdir -p "$LOG_DIR"

run_control_cli() {
  if [[ "$PROFILE_NAME" == "real" && "$SERVICE_DEPLOYMENT" == "host" ]]; then
    env \
      A1Z_SOCKET_PATH="${A1Z_SOCKET_PATH:-}" \
      A1Z_TCP_HOST="${A1Z_TCP_HOST:-127.0.0.1}" \
      A1Z_TCP_PORT="${A1Z_TCP_PORT:-37104}" \
      PYTHONPATH="$ROOT_DIR/vendor/GALAXEA-A1Z:$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
      "${A1Z_PYTHON:-python3}" "$ROOT_DIR/tools/a1zctl" "$@"
    return
  fi
  A1Z_PROFILE="$PROFILE_NAME" \
    "$ROOT_DIR/scripts/a1zctl_in_container.sh" "$@"
}

probe_identity() {
  local output
  if ! output="$(
    run_control_cli --json info 2>/dev/null
  )"; then
    return 1
  fi
  python3 - "$EXPECTED_BACKEND" "$output" <<'PY'
import json
import sys

expected = sys.argv[1]
payload = json.loads(sys.argv[2])
payload = payload.get("data", payload)
raise SystemExit(0 if payload.get("backend") == expected else 3)
PY
}

probe_healthy() {
  local output
  if ! output="$(
    run_control_cli --json info 2>/dev/null
  )"; then
    return 1
  fi
  python3 - "$EXPECTED_BACKEND" "$output" <<'PY'
import json
import sys

expected = sys.argv[1]
payload = json.loads(sys.argv[2])
payload = payload.get("data", payload)
healthy = (
    payload.get("backend") == expected
    and payload.get("running") is True
    and not payload.get("faulted", False)
)
raise SystemExit(0 if healthy else 3)
PY
}

probe_terminal_fault() {
  local output
  if ! output="$(
    run_control_cli --json info 2>/dev/null
  )"; then
    return 1
  fi
  python3 - "$EXPECTED_BACKEND" "$output" <<'PY'
import json
import sys

expected = sys.argv[1]
payload = json.loads(sys.argv[2])
payload = payload.get("data", payload)
message = str(payload.get("fault_message", "") or "").strip()
terminal = (
    payload.get("backend") == expected
    and (payload.get("faulted") is True or bool(message))
)
if terminal:
    print(message or "robot control loop reported a fault")
raise SystemExit(0 if terminal else 3)
PY
}

find_real_server_pids() {
  [[ "$PROFILE_NAME" == "real" ]] || return 1
  if [[ "$SERVICE_DEPLOYMENT" == "host" ]]; then
    local pid="" command_line=""
    pid="$(cat "$HOST_PID_PATH" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    [[ -r "/proc/$pid/cmdline" ]] || return 1
    command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
    [[ "$command_line" == *"/tools/a1zctl serve"* ]] || return 1
    printf '%s\n' "$pid"
    return 0
  fi
  local container_name="${A1Z_ROS2_CONTAINER_NAME:-}"
  [[ -n "$container_name" ]] || return 1
  docker inspect "$container_name" >/dev/null 2>&1 || return 1
  [[ "$(docker inspect -f '{{.State.Running}}' "$container_name")" == "true" ]] || return 1
  docker exec "$container_name" \
    bash -lc "pgrep -f '/workspace/A1Z/tools/[a]1zctl serve'" 2>/dev/null
}

ensure_real_can_ready() {
  [[ "$PROFILE_NAME" == "real" ]] || return 0
  local container_name="${A1Z_ROS2_CONTAINER_NAME:-}"
  local can_channel="${A1Z_CAN_CHANNEL:?real profile needs A1Z_CAN_CHANNEL}"
  local details="" flags

  if [[ "$SERVICE_DEPLOYMENT" == "docker" && -z "$container_name" ]]; then
    echo "Docker deployment requires A1Z_ROS2_CONTAINER_NAME." >&2
    return 2
  fi

  if [[ ! "$CAN_BITRATE" =~ ^[1-9][0-9]*$ ]]; then
    echo "Invalid A1Z_CAN_BITRATE='$CAN_BITRATE'; expected a positive integer." >&2
    return 2
  fi
  for _ in $(seq 1 20); do
    if [[ "$SERVICE_DEPLOYMENT" == "host" ]]; then
      details="$(ip -details link show "$can_channel" 2>/dev/null || true)"
    else
      details="$(docker exec "$container_name" ip -details link show "$can_channel" 2>/dev/null || true)"
    fi
    if [[ -n "$details" ]]; then
      break
    fi
    details=""
    sleep 0.25
  done
  if [[ -z "$details" ]]; then
    echo "SocketCAN interface '$can_channel' is missing." >&2
    echo "Connect the CAN adapter and wait for its gs_usb interface before starting the service." >&2
    return 1
  fi

  flags="${details#*<}"
  flags="${flags%%>*}"
  if [[ ",$flags," == *",UP,"* ]] && \
     [[ "$details" == *"bitrate $CAN_BITRATE"* ]]; then
    echo "Reusing ${can_channel}: UP at ${CAN_BITRATE} bit/s."
    return 0
  fi

  if [[ "$SERVICE_DEPLOYMENT" == "host" ]]; then
    echo "Host SocketCAN '$can_channel' must already be UP at ${CAN_BITRATE} bit/s." >&2
    echo "Configure the host interface explicitly or select Docker for managed CAN setup." >&2
    return 1
  fi

  echo "Configuring ${can_channel}: ${CAN_BITRATE} bit/s and UP."
  docker exec "$container_name" ip link set "$can_channel" down
  docker exec "$container_name" \
    ip link set "$can_channel" type can bitrate "$CAN_BITRATE"
  docker exec "$container_name" ip link set "$can_channel" up

  details="$(docker exec "$container_name" ip -details link show "$can_channel")"
  flags="${details#*<}"
  flags="${flags%%>*}"
  if [[ ",$flags," != *",UP,"* ]] || \
     [[ "$details" != *"bitrate $CAN_BITRATE"* ]]; then
    echo "Failed to bring ${can_channel} UP at ${CAN_BITRATE} bit/s." >&2
    echo "$details" >&2
    return 1
  fi
  echo "SocketCAN ready: ${can_channel} is UP at ${CAN_BITRATE} bit/s."
}

stop_orphaned_real_servers() {
  local container_name="${A1Z_ROS2_CONTAINER_NAME:?}"
  local pids="$1"
  local pid
  local pid_args=()
  while IFS= read -r pid; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    pid_args+=("$pid")
  done <<<"$pids"
  [[ "${#pid_args[@]}" -gt 0 ]] || return 0
  if [[ "$SERVICE_DEPLOYMENT" == "host" ]]; then
    for pid in "${pid_args[@]}"; do
      kill -INT "$pid" 2>/dev/null || true
    done
    for _ in $(seq 1 40); do
      if ! find_real_server_pids >/dev/null; then
        rm -f "$HOST_PID_PATH"
        echo "Stopped orphaned A1Z real host control-server process."
        return 0
      fi
      sleep 0.25
    done
    echo "Timed out waiting for orphaned A1Z real host control-server process to stop." >&2
    return 1
  fi
  docker exec "$container_name" bash -lc '
    for pid in "$@"; do
      kill -INT "$pid" 2>/dev/null || true
    done
  ' bash "${pid_args[@]}"
  for _ in $(seq 1 40); do
    if ! find_real_server_pids >/dev/null; then
      echo "Stopped orphaned A1Z real control-server process."
      return 0
    fi
    sleep 0.25
  done
  echo "Timed out waiting for orphaned A1Z real control-server process to stop." >&2
  return 1
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
  local real_pids=""
  native_pid="$(find_native_kit_pid || true)"
  if ! probe_identity; then
    real_pids="$(find_real_server_pids || true)"
    if [[ -n "$real_pids" ]]; then
      stop_orphaned_real_servers "$real_pids"
      return $?
    fi
    if [[ -n "$native_pid" ]]; then
      stop_native_kit "$native_pid"
      echo "A1Z ${PROFILE_NAME} native Isaac runtime stopped."
      return 0
    fi
    echo "A1Z ${PROFILE_NAME} control service is already stopped."
    return 0
  fi
  run_control_cli --json stop
  for _ in $(seq 1 30); do
    if ! probe_identity; then
      if [[ -n "$native_pid" ]]; then
        stop_native_kit "$native_pid"
      fi
      if [[ "$PROFILE_NAME" == "real" && "$SERVICE_DEPLOYMENT" == "host" ]]; then
        rm -f "$HOST_PID_PATH"
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
    TERMINAL_FAULT="$(probe_terminal_fault || true)"
    if [[ -n "$TERMINAL_FAULT" ]]; then
      echo "A1Z ${PROFILE_NAME} endpoint is reachable, but its robot control loop faulted: $TERMINAL_FAULT" >&2
      exit 1
    fi
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
  SERVER_OPTIONS=(
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
    SERVER_OPTIONS+=(--gravity-mode)
  fi

  if [[ "$SERVICE_DEPLOYMENT" == "host" ]]; then
    ensure_real_can_ready
    ORPHANED_REAL_PIDS="$(find_real_server_pids || true)"
    if [[ -n "$ORPHANED_REAL_PIDS" ]]; then
      echo "Refusing to start a second SDK owner; existing host control-server pid(s): $ORPHANED_REAL_PIDS" >&2
      echo "Run '$0 stop' with A1Z_SERVICE_DEPLOYMENT=host before retrying." >&2
      exit 1
    fi
    setsid env \
      A1Z_PROFILE="$A1Z_PROFILE" \
      A1Z_BACKEND="$A1Z_BACKEND" \
      A1Z_CAN_CHANNEL="$A1Z_CAN_CHANNEL" \
      A1Z_SOCKET_PATH="$A1Z_SOCKET_PATH" \
      A1Z_TCP_HOST="$A1Z_TCP_HOST" \
      A1Z_TCP_PORT="$A1Z_TCP_PORT" \
      PYTHONPATH="$ROOT_DIR/vendor/GALAXEA-A1Z:$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
      "${A1Z_PYTHON:-python3}" "$ROOT_DIR/tools/a1zctl" serve \
      "${SERVER_OPTIONS[@]}" \
      >"$LOG_PATH" 2>&1 </dev/null &
    printf '%s\n' "$!" >"$HOST_PID_PATH"
  else
    "$ROOT_DIR/scripts/create_a1z_ros2_container.sh"
    CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:?real profile needs a ROS container}"
    docker start "$CONTAINER_NAME" >/dev/null
    ORPHANED_REAL_PIDS="$(find_real_server_pids || true)"
    if [[ -n "$ORPHANED_REAL_PIDS" ]]; then
      echo "Refusing to start a second SDK owner; existing control-server pid(s): $ORPHANED_REAL_PIDS" >&2
      echo "Run '$0 stop' to terminate the selected profile's stale owner first." >&2
      exit 1
    fi
    ensure_real_can_ready

	ENV_ARGS=()
	for name in \
	  A1Z_PROFILE A1Z_BACKEND A1Z_CAN_CHANNEL A1Z_CONTROL_FREQ_HZ \
      A1Z_MIN_CONTROL_FREQ_HZ A1Z_CAN_INTER_COMMAND_DELAY_S \
      A1Z_GRIPPER_MAX_TORQUE \
      A1Z_GRIPPER_EMPTY_CLOSE_THRESHOLD A1Z_ARM_FEEDBACK_STARTUP_TIMEOUT_S \
      A1Z_SOCKET_PATH \
      A1Z_TCP_HOST A1Z_TCP_PORT A1Z_WITH_GRIPPER; do
      if [[ -n "${!name:-}" ]]; then
	    ENV_ARGS+=(-e "$name=${!name}")
	  fi
	done
	if [[ -n "${A1Z_CONTROL_SERVER_URDF:-}" ]]; then
	  ENV_ARGS+=(-e "A1Z_CONTROL_URDF=$A1Z_CONTROL_SERVER_URDF")
	fi
	ENV_ARGS+=(-e "PYTHONPATH=/workspace/A1Z/vendor/GALAXEA-A1Z:/workspace/A1Z")

    docker exec -d \
      -u "$(id -u):$(id -g)" \
      -w /workspace/A1Z \
      "${ENV_ARGS[@]}" \
      "$CONTAINER_NAME" \
      bash -lc 'log_path="$1"; shift; exec "$@" > "$log_path" 2>&1' bash \
      "/workspace/A1Z/runtime/logs/a1z-control-${A1Z_PROFILE}.log" \
      /usr/bin/python3 /workspace/A1Z/tools/a1zctl serve \
      "${SERVER_OPTIONS[@]}"
  fi
fi

READY_COUNT=0
REAL_SERVER_OBSERVED=0
for READY_ATTEMPT in $(seq 1 90); do
  if probe_healthy; then
    READY_COUNT=$((READY_COUNT + 1))
    if [[ "$READY_COUNT" -ge 3 ]]; then
      echo "A1Z ${PROFILE_NAME} control service ready: ${EXPECTED_BACKEND} at ${A1Z_TCP_HOST}:${A1Z_TCP_PORT}"
      echo "Log: $LOG_PATH"
      exit 0
    fi
  else
    READY_COUNT=0
    TERMINAL_FAULT="$(probe_terminal_fault || true)"
    if [[ -n "$TERMINAL_FAULT" ]]; then
      echo "A1Z ${PROFILE_NAME} control loop faulted before becoming ready: $TERMINAL_FAULT" >&2
      echo "Log: $LOG_PATH" >&2
      tail -n 20 "$LOG_PATH" >&2 || true
      exit 1
    fi
  fi
  if [[ "$PROFILE_NAME" == "real" ]]; then
    if find_real_server_pids >/dev/null; then
      REAL_SERVER_OBSERVED=1
    elif [[ "$REAL_SERVER_OBSERVED" == "1" || "$READY_ATTEMPT" -ge 3 ]]; then
      echo "A1Z real control-server process exited before becoming ready." >&2
      echo "Log: $LOG_PATH" >&2
      tail -n 20 "$LOG_PATH" >&2 || true
      exit 1
    fi
  fi
  sleep 1
done

echo "A1Z ${PROFILE_NAME} service did not become ready. Log: $LOG_PATH" >&2
tail -n 20 "$LOG_PATH" >&2 || true
exit 1
