#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

BASE_IMAGE="${A1Z_ROS2_IMAGE_TAG:-a1z-ros2-humble:local}"
RVIZ_IMAGE="${A1Z_RVIZ_IMAGE_TAG:-a1z-ros2-humble-rviz:local}"
DOCKERFILE_PATH="$ROOT_DIR/docker/ros2-humble-rviz/Dockerfile"
XAUTH_FILE="${A1Z_RVIZ_XAUTH_FILE:-/tmp/a1z-rviz-docker.xauth}"
DEFAULT_RVIZ_CONFIG="${A1Z_RVIZ_CONFIG:-/workspace/A1Z/ros2_ws/rviz/a1z_d405.rviz}"
REBUILD=0

usage() {
  cat <<'EOF'
Usage: ./scripts/open_a1z_rviz_in_container.sh [--rebuild] [rviz2 args...]

Runs RViz2 from a throwaway ROS 2 Humble container using the host X11/Xwayland
display. The container uses host networking, so it can see the same ROS graph as
the a1z-ros2-humble runtime container.

Options:
  --rebuild   Rebuild the RViz image before launching.
  -h, --help  Show this help.

By default this loads the A1Z D405 RViz config. Pass -d/--display-config in
rviz2 args, or set A1Z_RVIZ_NO_DEFAULT_CONFIG=1, to override that behavior.
EOF
}

RVIZ_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild)
      REBUILD=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      RVIZ_ARGS+=("$@")
      break
      ;;
    *)
      RVIZ_ARGS+=("$1")
      ;;
  esac
  shift
done

USES_DISPLAY_CONFIG=0
for arg in "${RVIZ_ARGS[@]}"; do
  case "$arg" in
    -d|--display-config|--display-config=*)
      USES_DISPLAY_CONFIG=1
      ;;
  esac
done

if [[ "${A1Z_RVIZ_NO_DEFAULT_CONFIG:-0}" != "1" && "$USES_DISPLAY_CONFIG" == "0" ]]; then
  RVIZ_ARGS=(-d "$DEFAULT_RVIZ_CONFIG" "${RVIZ_ARGS[@]}")
fi

if [[ -z "${DISPLAY:-}" ]]; then
  echo "DISPLAY is not set. Start a graphical desktop session before launching RViz." >&2
  exit 1
fi

if [[ ! -d /tmp/.X11-unix ]]; then
  echo "Host X11 socket directory not found: /tmp/.X11-unix" >&2
  exit 1
fi

if ! docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
  "$ROOT_DIR/scripts/create_a1z_ros2_container.sh"
fi

if [[ "$REBUILD" == "1" ]] || ! docker image inspect "$RVIZ_IMAGE" >/dev/null 2>&1; then
  docker build \
    --build-arg "BASE_IMAGE=$BASE_IMAGE" \
    -t "$RVIZ_IMAGE" \
    -f "$DOCKERFILE_PATH" \
    "$ROOT_DIR"
fi

rm -f "$XAUTH_FILE"
touch "$XAUTH_FILE"
chmod 600 "$XAUTH_FILE"
if command -v xauth >/dev/null 2>&1; then
  if ! xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$XAUTH_FILE" nmerge - >/dev/null 2>&1; then
    echo "Warning: failed to generate Xauthority file; falling back to xhost local access." >&2
  fi
fi

if [[ ! -s "$XAUTH_FILE" ]] && command -v xhost >/dev/null 2>&1; then
  xhost +SI:localuser:root >/dev/null
fi

DOCKER_ENV_ARGS=(
  -e "DISPLAY=${DISPLAY}"
  -e "FASTDDS_BUILTIN_TRANSPORTS=${FASTDDS_BUILTIN_TRANSPORTS:-UDPv4}"
  -e "QT_X11_NO_MITSHM=1"
  -e "XAUTHORITY=/tmp/.docker.xauth"
  -e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-}"
  -e "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-}"
)

DOCKER_TTY_ARGS=()
if [[ -t 0 && -t 1 ]]; then
  DOCKER_TTY_ARGS=(-it)
fi

exec docker run --rm \
  "${DOCKER_TTY_ARGS[@]}" \
  --network host \
  --ipc host \
  "${DOCKER_ENV_ARGS[@]}" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$XAUTH_FILE:/tmp/.docker.xauth:ro" \
  -v "$ROOT_DIR:/workspace/A1Z" \
  -w /workspace/A1Z/ros2_ws \
  "$RVIZ_IMAGE" \
  bash -lc '
    set -eo pipefail
    source /opt/ros/humble/setup.bash
    if [[ -f /workspace/A1Z/ros2_ws/install/setup.bash ]]; then
      source /workspace/A1Z/ros2_ws/install/setup.bash
    fi
    exec rviz2 "$@"
  ' bash "${RVIZ_ARGS[@]}"
