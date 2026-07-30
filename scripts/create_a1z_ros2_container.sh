#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

ROS_CONTAINER_NAME="${A1Z_ROS2_CONTAINER_NAME:-a1z-ros2-humble}"
ROS_BASE_IMAGE_TAG="${A1Z_ROS2_BASE_IMAGE_TAG:-a1z-ros2-humble-base:local}"
ROS_IMAGE_TAG="${A1Z_ROS2_IMAGE_TAG:-a1z-ros2-humble:local}"
BASE_DOCKERFILE_PATH="$ROOT_DIR/docker/ros2-humble/Dockerfile.base"
DOCKERFILE_PATH="$ROOT_DIR/docker/ros2-humble/Dockerfile"

is_realsense_device_node() {
  local node="$1"
  local sys_path
  local current
  local product
  sys_path="$(udevadm info -q path -n "$node" 2>/dev/null || true)"
  [[ -n "$sys_path" ]] || return 1
  current="/sys$sys_path"
  while [[ "$current" == /sys/* ]]; do
    if [[ -r "$current/product" ]]; then
      product="$(<"$current/product")"
      if [[ "${product,,}" == *realsense* ]]; then
        return 0
      fi
    fi
    current="${current%/*}"
  done
  return 1
}

discover_realsense_device_nodes() {
  local node
  for node in /dev/video* /dev/media*; do
    [[ -e "$node" ]] || continue
    if is_realsense_device_node "$node"; then
      printf '%s\n' "$node"
    fi
  done
}

REALSENSE_DEVICE_NODES=()
if [[ "${A1Z_PROFILE:-sim}" == "real" ]]; then
  mapfile -t REALSENSE_DEVICE_NODES < <(discover_realsense_device_nodes)
fi

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
    if [[ "$EXISTING_CONFIG" != *"/dev/bus/usb:/dev/bus/usb"* ]] || \
       [[ "$EXISTING_CONFIG" != *"c 189:* rmw"* ]] || \
       [[ "$EXISTING_CONFIG" != *"NET_ADMIN"* ]] || \
       [[ "$EXISTING_GROUPS" != *'"0"'* ]]; then
      echo "Existing real container lacks the required USB/SocketCAN access: $ROS_CONTAINER_NAME" >&2
      echo "Remove that container explicitly, then rerun this command." >&2
      exit 3
    fi
    for node in "${REALSENSE_DEVICE_NODES[@]}"; do
      if [[ "$EXISTING_DEVICES" != *"\"PathOnHost\":\"$node\""* ]]; then
        echo "Existing real container does not map discovered RealSense node: $node" >&2
        echo "Remove that container explicitly, then rerun this command." >&2
        exit 3
      fi
    done
  fi
  echo "ROS 2 container already exists: $ROS_CONTAINER_NAME"
  exit 0
fi

DEVICE_ARGS=()
if [[ "${A1Z_PROFILE:-sim}" == "real" ]]; then
  DEVICE_ARGS=(
    --cap-add NET_ADMIN
    --device-cgroup-rule "c 189:* rmw"
    # Hosts without RealSense udev rules commonly expose USB nodes as
    # root:root 0664. Add the owning group to the numeric container user
    # without rewriting host permissions or selecting a device path.
    --group-add 0
    -v /dev/bus/usb:/dev/bus/usb
  )
  if [[ "${#REALSENSE_DEVICE_NODES[@]}" -eq 0 ]]; then
    echo "Warning: no RealSense V4L2/media nodes were discovered; reconnect the camera and recreate the container." >&2
  fi
  declare -A DEVICE_GROUPS=(["0"]=1)
  for node in "${REALSENSE_DEVICE_NODES[@]}"; do
    DEVICE_ARGS+=(--device "$node:$node")
    DEVICE_GROUPS["$(stat -c '%g' "$node")"]=1
  done
  for group_id in "${!DEVICE_GROUPS[@]}"; do
    if [[ "$group_id" != "0" ]]; then
      DEVICE_ARGS+=(--group-add "$group_id")
    fi
  done
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
