#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ECONOMICGRASP_CONTAINER_NAME="${A1Z_ECONOMICGRASP_CONTAINER_NAME:-a1z-economicgrasp-gpu}"
ECONOMICGRASP_VENV_DIR="${A1Z_ECONOMICGRASP_VENV_DIR:-/opt/venvs/economicgrasp}"
ECONOMICGRASP_REPO_DIR="${A1Z_ECONOMICGRASP_REPO_DIR:-/workspace/A1Z/vendor/vision/EconomicGrasp}"
ECONOMICGRASP_MODEL_ROOT="${A1Z_ECONOMICGRASP_MODEL_ROOT:-/workspace/A1Z/runtime/models/economicgrasp}"
ECONOMICGRASP_REALSENSE_CKPT="${A1Z_ECONOMICGRASP_REALSENSE_CKPT:-$ECONOMICGRASP_MODEL_ROOT/economicgrasp_realsense.tar}"
ECONOMICGRASP_KINECT_CKPT="${A1Z_ECONOMICGRASP_KINECT_CKPT:-$ECONOMICGRASP_MODEL_ROOT/economicgrasp_kinect.tar}"
ECONOMICGRASP_TORCH_CUDA_ARCH_LIST="${A1Z_ECONOMICGRASP_TORCH_CUDA_ARCH_LIST:-8.6;8.9;9.0;12.0+PTX}"
ECONOMICGRASP_MAX_JOBS="${A1Z_ECONOMICGRASP_MAX_JOBS:-1}"
ECONOMICGRASP_SKIP_CHECKPOINT_DOWNLOAD="${A1Z_ECONOMICGRASP_SKIP_CHECKPOINT_DOWNLOAD:-0}"
ECONOMICGRASP_INSTALL_GRASPNETAPI="${A1Z_ECONOMICGRASP_INSTALL_GRASPNETAPI:-0}"

bash "$ROOT_DIR/scripts/fetch_economicgrasp_vendor_repo.sh"
if [[ "$ECONOMICGRASP_SKIP_CHECKPOINT_DOWNLOAD" != "1" ]]; then
  bash "$ROOT_DIR/scripts/download_economicgrasp_checkpoints.sh" realsense kinect
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$ECONOMICGRASP_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ECONOMICGRASP_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_ECONOMICGRASP_VENV_DIR="$ECONOMICGRASP_VENV_DIR" \
  -e A1Z_ECONOMICGRASP_REPO_DIR="$ECONOMICGRASP_REPO_DIR" \
  -e A1Z_ECONOMICGRASP_MODEL_ROOT="$ECONOMICGRASP_MODEL_ROOT" \
  -e A1Z_ECONOMICGRASP_REALSENSE_CKPT="$ECONOMICGRASP_REALSENSE_CKPT" \
  -e A1Z_ECONOMICGRASP_KINECT_CKPT="$ECONOMICGRASP_KINECT_CKPT" \
  -e A1Z_ECONOMICGRASP_INSTALL_GRASPNETAPI="$ECONOMICGRASP_INSTALL_GRASPNETAPI" \
  -e TORCH_CUDA_ARCH_LIST="$ECONOMICGRASP_TORCH_CUDA_ARCH_LIST" \
  -e MAX_JOBS="$ECONOMICGRASP_MAX_JOBS" \
  -e CUDA_HOME=/usr/local/cuda \
  "$ECONOMICGRASP_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail

    python3 -m venv "$A1Z_ECONOMICGRASP_VENV_DIR"
    source "$A1Z_ECONOMICGRASP_VENV_DIR/bin/activate"

    python -m pip install --upgrade pip
    python -m pip install --upgrade wheel packaging ninja
    python -m pip install "setuptools==59.8.0"
    python -m pip install \
      --index-url https://download.pytorch.org/whl/cu128 \
      torch==2.7.0 \
      torchvision==0.22.0 \
      torchaudio==2.7.0

    python -m pip install \
      numpy==1.23.4 \
      scipy \
      open3d==0.19.0 \
      Pillow \
      tqdm \
      pyyaml \
      opencv-python \
      transforms3d \
      trimesh \
      tensorboard==2.3

    export CUDA_HOME=/usr/local/cuda
    export CXX=g++
    export CC=gcc

    cd "$A1Z_ECONOMICGRASP_REPO_DIR/libs/MinkowskiEngine"
    python setup.py install \
      --force_cuda \
      --cuda_home="$CUDA_HOME" \
      --blas_include_dirs=/usr/include \
      --blas=openblas

    cd "$A1Z_ECONOMICGRASP_REPO_DIR/libs/pointnet2"
    python setup.py install

    cd "$A1Z_ECONOMICGRASP_REPO_DIR/libs/knn"
    python setup.py install

    python - <<'"'"'PY'"'"'
import site
from pathlib import Path

repo_dir = Path("/workspace/A1Z/vendor/vision/EconomicGrasp")
pth_path = Path(site.getsitepackages()[0]) / "a1z_economicgrasp_repo.pth"
pth_path.write_text(f"{repo_dir}\n", encoding="utf-8")
print(f"Registered EconomicGrasp repo path: {pth_path}")
PY

    if [[ "$A1Z_ECONOMICGRASP_INSTALL_GRASPNETAPI" == "1" ]]; then
      python -m pip install \
        matplotlib \
        pywavefront \
        scikit-image \
        h5py \
        dill \
        scikit-learn
      python -m pip install graspnetAPI==1.2.11 --no-deps
    fi
  '
