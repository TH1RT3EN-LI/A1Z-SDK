#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
SERVER_IP="${A1Z_SERVER_IP:-10.66.0.11}"
SOCKET_PATH="${A1Z_SOCKET_PATH:-/tmp/a1z.sock}"
TCP_HOST="${A1Z_TCP_HOST:-0.0.0.0}"
TCP_PORT="${A1Z_TCP_PORT:-18080}"
RESTART=0

usage() {
  cat <<'EOF'
Usage: ./scripts/start_a1z_webrtc_streaming_host.sh [--restart] [server-ip]

Starts the shared headless Isaac Sim WebRTC stream. By default this is
idempotent: if the stream is already running, it is reused so local and remote
clients stay on the same session.

Options:
  --restart   Stop any existing Isaac WebRTC stream first, then start a fresh one.
  -h, --help  Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --restart)
      RESTART=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      SERVER_IP="$1"
      ;;
  esac
  shift
done

"$ROOT_DIR/scripts/create_isaac_sim_dev_container.sh"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

if [[ "$RESTART" == "1" ]]; then
  docker exec -u ubuntu "$CONTAINER_NAME" /workspace/A1Z/scripts/stop_a1z_webrtc_streaming.sh >/dev/null 2>&1 || true
fi

DOCKER_ENV_ARGS=(
  -e "A1Z_ISAAC_GRAVITY_MODE=${A1Z_ISAAC_GRAVITY_MODE:-}"
  -e "A1Z_WITH_GRIPPER=${A1Z_WITH_GRIPPER:-}"
  -e "A1Z_ISAAC_CONTROL_FREQ_HZ=${A1Z_ISAAC_CONTROL_FREQ_HZ:-}"
  -e "A1Z_ISAAC_ARTICULATION_ROOT=${A1Z_ISAAC_ARTICULATION_ROOT:-}"
  -e "A1Z_D405_ENABLED=${A1Z_D405_ENABLED:-}"
  -e "A1Z_D405_PARENT_PRIM=${A1Z_D405_PARENT_PRIM:-}"
  -e "A1Z_D405_FALLBACK_PARENT_PRIM=${A1Z_D405_FALLBACK_PARENT_PRIM:-}"
  -e "A1Z_D405_FK_FRAME=${A1Z_D405_FK_FRAME:-}"
  -e "A1Z_D405_MOUNT_OFFSET=${A1Z_D405_MOUNT_OFFSET:-}"
  -e "A1Z_D405_MOUNT_RPY_DEG=${A1Z_D405_MOUNT_RPY_DEG:-}"
  -e "A1Z_D405_CAMERA_PRIMS_ENABLED=${A1Z_D405_CAMERA_PRIMS_ENABLED:-}"
  -e "A1Z_D405_CENTER_MESH_Y=${A1Z_D405_CENTER_MESH_Y:-}"
  -e "A1Z_D405_CENTER_ON_AXIS=${A1Z_D405_CENTER_ON_AXIS:-}"
  -e "A1Z_D405_STATUS_PATH=${A1Z_D405_STATUS_PATH:-}"
  -e "A1Z_D405_ROS2_NAMESPACE=${A1Z_D405_ROS2_NAMESPACE:-}"
  -e "A1Z_D405_COLOR_FRAME_ID=${A1Z_D405_COLOR_FRAME_ID:-}"
  -e "A1Z_D405_DEPTH_FRAME_ID=${A1Z_D405_DEPTH_FRAME_ID:-}"
  -e "A1Z_D405_WIDTH=${A1Z_D405_WIDTH:-}"
  -e "A1Z_D405_HEIGHT=${A1Z_D405_HEIGHT:-}"
  -e "A1Z_D405_FRAME_SKIP_COUNT=${A1Z_D405_FRAME_SKIP_COUNT:-}"
  -e "A1Z_ISAAC_STARTUP_SCRIPT=${A1Z_ISAAC_STARTUP_SCRIPT:-}"
  -e "A1Z_EE_DRAG_TARGET_ENABLED=${A1Z_EE_DRAG_TARGET_ENABLED:-}"
  -e "A1Z_EE_TARGET_PRIM_PATH=${A1Z_EE_TARGET_PRIM_PATH:-}"
  -e "A1Z_EE_FRAME=${A1Z_EE_FRAME:-}"
  -e "A1Z_EE_POS_EPSILON_MM=${A1Z_EE_POS_EPSILON_MM:-}"
  -e "A1Z_EE_ORI_EPSILON_DEG=${A1Z_EE_ORI_EPSILON_DEG:-}"
  -e "A1Z_EE_IK_DT=${A1Z_EE_IK_DT:-}"
  -e "A1Z_EE_IK_DAMPING=${A1Z_EE_IK_DAMPING:-}"
  -e "A1Z_EE_IK_MAX_ITERS=${A1Z_EE_IK_MAX_ITERS:-}"
  -e "A1Z_EE_TARGET_OFFSET_X_M=${A1Z_EE_TARGET_OFFSET_X_M:-}"
  -e "A1Z_EE_TARGET_OFFSET_Y_M=${A1Z_EE_TARGET_OFFSET_Y_M:-}"
  -e "A1Z_EE_TARGET_OFFSET_Z_M=${A1Z_EE_TARGET_OFFSET_Z_M:-}"
  -e "A1Z_EE_TARGET_STATUS_PATH=${A1Z_EE_TARGET_STATUS_PATH:-}"
  -e "A1Z_VIEWPORT_ENABLED=${A1Z_VIEWPORT_ENABLED:-}"
  -e "A1Z_WORLD_USD=${A1Z_WORLD_USD:-}"
  -e "A1Z_SOCKET_PATH=${A1Z_SOCKET_PATH:-}"
  -e "A1Z_TCP_HOST=${A1Z_TCP_HOST:-}"
  -e "A1Z_TCP_PORT=${A1Z_TCP_PORT:-}"
)

docker exec -u ubuntu "${DOCKER_ENV_ARGS[@]}" "$CONTAINER_NAME" \
  /workspace/A1Z/scripts/start_a1z_webrtc_streaming.sh "$SERVER_IP"

ACTIVE_SERVER_IP="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc \
    "cat /workspace/A1Z/runtime/logs/isaac-sim-streaming.server-ip 2>/dev/null || true"
)"
if [[ -n "$ACTIVE_SERVER_IP" ]]; then
  SERVER_IP="$ACTIVE_SERVER_IP"
fi

for _ in $(seq 1 120); do
  SOCKET_READY=0
  TCP_READY=0
  if docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "ss -xl | grep -F '$SOCKET_PATH' >/dev/null"; then
    SOCKET_READY=1
  fi
  if [[ "$TCP_PORT" =~ ^[0-9]+$ ]] && [[ "$TCP_PORT" -gt 0 ]]; then
    if docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "ss -ltn | awk '{print \$4}' | grep -E '(^|:)$TCP_PORT$' >/dev/null"; then
      TCP_READY=1
    fi
  else
    TCP_READY=1
  fi
  if [[ "$SOCKET_READY" == "1" && "$TCP_READY" == "1" ]]; then
    echo "A1Z SDK socket is ready: $SOCKET_PATH"
    if [[ "$TCP_PORT" =~ ^[0-9]+$ ]] && [[ "$TCP_PORT" -gt 0 ]]; then
      echo "A1Z SDK TCP server is ready: $TCP_HOST:$TCP_PORT"
    fi
    break
  fi
  sleep 1
done

if ! docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "ss -xl | grep -F '$SOCKET_PATH' >/dev/null"; then
  echo "A1Z SDK socket did not appear: $SOCKET_PATH" >&2
  echo "If an old stream is running without the SDK bridge, retry with --restart." >&2
  docker exec -u ubuntu "$CONTAINER_NAME" tail -n 80 /workspace/A1Z/runtime/logs/isaac-sim-streaming.log >&2 || true
  exit 1
fi

if [[ "$TCP_PORT" =~ ^[0-9]+$ ]] && [[ "$TCP_PORT" -gt 0 ]]; then
  if ! docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "ss -ltn | awk '{print \$4}' | grep -E '(^|:)$TCP_PORT$' >/dev/null"; then
    echo "A1Z SDK TCP server did not appear: $TCP_HOST:$TCP_PORT" >&2
    docker exec -u ubuntu "$CONTAINER_NAME" tail -n 80 /workspace/A1Z/runtime/logs/isaac-sim-streaming.log >&2 || true
    exit 1
  fi
fi

echo "Shared WebRTC session is ready."
echo "Remote client target: $SERVER_IP:49100"
echo "Media UDP port: $SERVER_IP:47998"
