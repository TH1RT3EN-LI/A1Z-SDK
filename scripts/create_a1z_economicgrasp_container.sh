#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ECONOMICGRASP_CONTAINER_NAME="${A1Z_ECONOMICGRASP_CONTAINER_NAME:-a1z-economicgrasp-gpu}"
ECONOMICGRASP_IMAGE_TAG="${A1Z_ECONOMICGRASP_IMAGE_TAG:-a1z-economicgrasp-gpu:local}"
ECONOMICGRASP_BASE_IMAGE="${A1Z_ECONOMICGRASP_BASE_IMAGE:-nvidia/cuda:12.8.1-devel-ubuntu22.04}"
DOCKERFILE_PATH="$ROOT_DIR/docker/economicgrasp-gpu/Dockerfile"

docker build \
  --build-arg "BASE_IMAGE=$ECONOMICGRASP_BASE_IMAGE" \
  -t "$ECONOMICGRASP_IMAGE_TAG" \
  -f "$DOCKERFILE_PATH" \
  "$ROOT_DIR"

if docker inspect "$ECONOMICGRASP_CONTAINER_NAME" >/dev/null 2>&1; then
  echo "EconomicGrasp container already exists: $ECONOMICGRASP_CONTAINER_NAME"
  exit 0
fi

docker create \
  --name "$ECONOMICGRASP_CONTAINER_NAME" \
  --gpus all \
  --ipc host \
  --network host \
  -v "$ROOT_DIR:/workspace/A1Z" \
  -w /workspace/A1Z \
  "$ECONOMICGRASP_IMAGE_TAG" \
  bash -lc "sleep infinity" >/dev/null

echo "Created EconomicGrasp container: $ECONOMICGRASP_CONTAINER_NAME"
