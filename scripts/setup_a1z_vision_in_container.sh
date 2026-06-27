#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_VENV_DIR="${A1Z_VISION_VENV_DIR:-/opt/venvs/a1z-vision}"
SAM2_REPO_DIR="${A1Z_SAM2_REPO_DIR:-/workspace/A1Z/vendor/vision/sam2}"

"$ROOT_DIR/scripts/fetch_vision_vendor_repos.sh"
"$ROOT_DIR/scripts/download_sam2_checkpoints.sh" small tiny

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_VISION_VENV_DIR="$VISION_VENV_DIR" \
  -e A1Z_SAM2_REPO_DIR="$SAM2_REPO_DIR" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail

    python3 -m venv "$A1Z_VISION_VENV_DIR"
    source "$A1Z_VISION_VENV_DIR/bin/activate"

    python -m pip install --upgrade pip setuptools wheel
    python -m pip install \
      --index-url https://download.pytorch.org/whl/cu128 \
      torch==2.7.0 \
      torchvision==0.22.0 \
      torchaudio==2.7.0
    python -m pip install \
      numpy==1.26.4 \
      addict \
      configargparse \
      dash \
      flask \
      hydra-core \
      huggingface_hub \
      iopath \
      ipywidgets \
      matplotlib \
      nbformat \
      graspnetAPI==1.2.11 --no-deps \
      open3d==0.19.0 \
      opencv-python-headless==4.11.0.86 \
      pandas \
      pillow \
      pyquaternion \
      pyyaml \
      transforms3d \
      trimesh \
      scipy \
      tqdm
    SAM2_BUILD_CUDA=0 python -m pip install --no-build-isolation --no-deps -e "$A1Z_SAM2_REPO_DIR"
  '

"$ROOT_DIR/scripts/setup_anygrasp_sdk_in_container.sh"
