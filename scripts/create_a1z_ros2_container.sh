#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
ROS_BASE_IMAGE_TAG="${A1Z_ROS2_BASE_IMAGE_TAG:-a1z-ros2-humble-base:local}"
ROS_IMAGE_TAG="${A1Z_ROS2_IMAGE_TAG:-a1z-ros2-humble:local}"
BASE_DOCKERFILE_PATH="$ROOT_DIR/docker/ros2-humble/Dockerfile.base"
DOCKERFILE_PATH="$ROOT_DIR/docker/ros2-humble/Dockerfile"

device_major() {
  local device_class="$1"
  awk -v device_class="$device_class" '$2 == device_class { print $1; exit }' /proc/devices
}

VIDEO_DEVICE_MAJOR="$(device_major video4linux)"
USB_DEVICE_MAJOR="$(device_major usb_device)"
MEDIA_DEVICE_MAJOR="$(device_major media)"
# These two Linux device classes have stable assigned majors. Keep the
# container camera-optional even when neither subsystem is loaded yet.
VIDEO_DEVICE_MAJOR="${VIDEO_DEVICE_MAJOR:-81}"
USB_DEVICE_MAJOR="${USB_DEVICE_MAJOR:-189}"

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
    EXISTING_GROUPS="$(docker inspect -f '{{json .HostConfig.GroupAdd}}' "$ROS_CONTAINER_NAME")"
    EXISTING_DEVICES="$(docker inspect -f '{{json .HostConfig.Devices}}' "$ROS_CONTAINER_NAME")"
    if [[ "$EXISTING_CONFIG" != *'"/dev:/dev"'* ]] || \
       [[ "$EXISTING_CONFIG" != *"c ${USB_DEVICE_MAJOR}:* rmw"* ]] || \
       [[ "$EXISTING_CONFIG" != *"c ${VIDEO_DEVICE_MAJOR}:* rmw"* ]] || \
       [[ -n "$MEDIA_DEVICE_MAJOR" && "$EXISTING_CONFIG" != *"c ${MEDIA_DEVICE_MAJOR}:* rmw"* ]] || \
       [[ "$EXISTING_CONFIG" != *"NET_ADMIN"* ]] || \
       [[ "$EXISTING_GROUPS" != *'"0"'* ]]; then
      echo "Existing real container lacks dynamic camera/SocketCAN access: $ROS_CONTAINER_NAME" >&2
      echo "Remove that container explicitly, then rerun this command." >&2
      exit 3
    fi
    if [[ "$EXISTING_DEVICES" != "null" && "$EXISTING_DEVICES" != "[]" ]]; then
      echo "Existing real container uses legacy fixed host device mappings." >&2
      echo "Remove that container explicitly once, then rerun this command." >&2
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
    --device-cgroup-rule "c ${USB_DEVICE_MAJOR}:* rmw"
    --device-cgroup-rule "c ${VIDEO_DEVICE_MAJOR}:* rmw"
    # Mount the device namespace rather than individual video/media nodes.
    # New udev nodes then become visible without recreating the container;
    # cgroup rules still limit which device classes can be opened.
    -v /dev:/dev
    # USB nodes are commonly root:root and V4L2 nodes belong to video.
    --group-add 0
  )
  if [[ "$MEDIA_DEVICE_MAJOR" =~ ^[0-9]+$ ]]; then
    DEVICE_ARGS+=(--device-cgroup-rule "c ${MEDIA_DEVICE_MAJOR}:* rmw")
  fi
  VIDEO_GROUP_ID="$(getent group video 2>/dev/null | cut -d: -f3 || true)"
  if [[ "$VIDEO_GROUP_ID" =~ ^[0-9]+$ && "$VIDEO_GROUP_ID" != "0" ]]; then
    DEVICE_ARGS+=(--group-add "$VIDEO_GROUP_ID")
  fi
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
