#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_IMAGE_TAG="${A1Z_VISION_IMAGE_TAG:-a1z-vision-gpu:local}"
VISION_BASE_IMAGE="${A1Z_VISION_BASE_IMAGE:-docker.m.daocloud.io/nvidia/cuda:12.8.1-devel-ubuntu22.04}"
DOCKERFILE_PATH="$ROOT_DIR/docker/vision-gpu/Dockerfile"

if docker inspect "$VISION_CONTAINER_NAME" >/dev/null 2>&1; then
  exec "$ROOT_DIR/scripts/ensure_a1z_vision_container.sh"
fi

docker build \
  --build-arg BASE_IMAGE="$VISION_BASE_IMAGE" \
  -t "$VISION_IMAGE_TAG" \
  -f "$DOCKERFILE_PATH" \
  "$ROOT_DIR"

docker create \
  --name "$VISION_CONTAINER_NAME" \
  --gpus all \
  --ipc host \
  --network host \
  -v "$ROOT_DIR:/workspace/A1Z" \
  -w /workspace/A1Z \
  "$VISION_IMAGE_TAG" \
  bash -lc "sleep infinity" >/dev/null

echo "Created vision container: $VISION_CONTAINER_NAME"
