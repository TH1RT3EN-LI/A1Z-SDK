#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
ROS_BASE_IMAGE_TAG="${A1Z_ROS2_BASE_IMAGE_TAG:-a1z-ros2-humble-base:local}"
ROS_IMAGE_TAG="${A1Z_ROS2_IMAGE_TAG:-a1z-ros2-humble:local}"
BASE_DOCKERFILE_PATH="$ROOT_DIR/docker/ros2-humble/Dockerfile.base"
DOCKERFILE_PATH="$ROOT_DIR/docker/ros2-humble/Dockerfile"

if [[ "${A1Z_ROS2_REBUILD_BASE_IMAGE:-0}" == "1" ]] || \
   ! docker image inspect "$ROS_BASE_IMAGE_TAG" >/dev/null 2>&1; then
  docker build -t "$ROS_BASE_IMAGE_TAG" -f "$BASE_DOCKERFILE_PATH" "$ROOT_DIR"
else
  echo "Reusing ROS 2 base image: $ROS_BASE_IMAGE_TAG"
fi

if [[ "${A1Z_ROS2_REBUILD_IMAGE:-0}" == "1" ]] || \
   ! docker image inspect "$ROS_IMAGE_TAG" >/dev/null 2>&1; then
  docker build \
    --build-arg "BASE_IMAGE=$ROS_BASE_IMAGE_TAG" \
    -t "$ROS_IMAGE_TAG" \
    -f "$DOCKERFILE_PATH" \
    "$ROOT_DIR"
else
  echo "Reusing ROS 2 image: $ROS_IMAGE_TAG"
fi

if docker inspect "$ROS_CONTAINER_NAME" >/dev/null 2>&1; then
  if [[ "${A1Z_PROFILE:-sim}" == "real" ]]; then
    EXISTING_CONFIG="$(docker inspect -f '{{json .HostConfig}}' "$ROS_CONTAINER_NAME")"
    if [[ "$EXISTING_CONFIG" != *"/dev/bus/usb:/dev/bus/usb"* ]] || \
       [[ "$EXISTING_CONFIG" != *"c 189:* rmw"* ]] || \
       [[ "$EXISTING_CONFIG" != *"NET_ADMIN"* ]]; then
      echo "Existing real container lacks the required USB/SocketCAN permissions: $ROS_CONTAINER_NAME" >&2
      echo "Remove that container explicitly, then rerun this command." >&2
      exit 3
    fi
  fi
  echo "ROS 2 container already exists: $ROS_CONTAINER_NAME"
  exit 0
fi

DEVICE_ARGS=()
if [[ "${A1Z_PROFILE:-sim}" == "real" ]]; then
  DEVICE_ARGS=(
    --cap-add NET_ADMIN
    --device-cgroup-rule "c 189:* rmw"
    -v /dev/bus/usb:/dev/bus/usb
  )
fi

docker create \
  --name "$ROS_CONTAINER_NAME" \
  --network host \
  "${DEVICE_ARGS[@]}" \
  -e "A1Z_PROFILE=${A1Z_PROFILE:-sim}" \
  -e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-61}" \
  -e "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}" \
  -v "$ROOT_DIR:/workspace/A1Z" \
  -w /workspace/A1Z/ros2_ws \
  "$ROS_IMAGE_TAG" \
  bash -lc "sleep infinity" >/dev/null

echo "Created ROS 2 container: $ROS_CONTAINER_NAME"
