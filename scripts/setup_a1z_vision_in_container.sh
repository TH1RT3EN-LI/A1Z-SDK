#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_VENV_DIR="${A1Z_VISION_VENV_DIR:-/opt/venvs/a1z-vision}"
SAM2_REPO_DIR="${A1Z_SAM2_REPO_DIR:-/workspace/A1Z/vendor/vision/sam2}"
ANYGRASP_SDK_DIR="${A1Z_ANYGRASP_SDK_DIR:-/workspace/A1Z/vendor/vision/anygrasp_sdk}"
MINKOWSKIENGINE_SOURCE_DIR="${A1Z_MINKOWSKIENGINE_SOURCE_DIR:-/workspace/A1Z/vendor/vision/EconomicGrasp/libs/MinkowskiEngine}"
GRCONVNET_REPO_DIR="${A1Z_GRCONVNET_REPO_DIR:-/workspace/A1Z/vendor/vision/robotic-grasping}"
GRCONVNET_MODEL_DIR="${A1Z_GRCONVNET_MODEL_DIR:-/workspace/A1Z/runtime/models/grconvnet/jacquard-rgbd-grconvnet3-drop0-ch32}"
GRCONVNET_MODEL_PATH="$GRCONVNET_MODEL_DIR/epoch_48_iou_0.93"
VISION_TORCH_CUDA_ARCH_LIST="${A1Z_VISION_TORCH_CUDA_ARCH_LIST:-8.6;8.9;9.0;12.0+PTX}"
VISION_PIP_INDEX_URL="${A1Z_VISION_PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"

"$ROOT_DIR/scripts/fetch_vision_vendor_repos.sh"
"$ROOT_DIR/scripts/download_sam2_checkpoints.sh" small tiny

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_VISION_VENV_DIR="$VISION_VENV_DIR" \
  -e A1Z_SAM2_REPO_DIR="$SAM2_REPO_DIR" \
  -e A1Z_ANYGRASP_SDK_DIR="$ANYGRASP_SDK_DIR" \
  -e A1Z_MINKOWSKIENGINE_SOURCE_DIR="$MINKOWSKIENGINE_SOURCE_DIR" \
  -e A1Z_GRCONVNET_REPO_DIR="$GRCONVNET_REPO_DIR" \
  -e A1Z_GRCONVNET_MODEL_DIR="$GRCONVNET_MODEL_DIR" \
  -e A1Z_GRCONVNET_MODEL_PATH="$GRCONVNET_MODEL_PATH" \
  -e TORCH_CUDA_ARCH_LIST="$VISION_TORCH_CUDA_ARCH_LIST" \
  -e PIP_INDEX_URL="$VISION_PIP_INDEX_URL" \
  -e CUDA_HOME=/usr/local/cuda \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail

    python3 -m venv "$A1Z_VISION_VENV_DIR"
    source "$A1Z_VISION_VENV_DIR/bin/activate"

    python -m pip install --upgrade pip
    python -m pip install --upgrade wheel packaging ninja
    python -m pip install "setuptools==59.8.0"
    python -m pip install \
      --index-url https://download.pytorch.org/whl/cu128 \
      torch==2.7.0 \
      torchvision==0.22.0 \
      torchaudio==2.7.0
    python -m pip install \
      addict \
      configargparse \
      colorlog \
      dill \
      hydra-core \
      imageio \
      iopath \
      matplotlib \
      multiprocess \
      numpy \
      open3d==0.19.0 \
      opencv-python-headless==4.11.0.86 \
      pillow \
      pyquaternion \
      pyyaml \
      ruamel.yaml \
      ruamel.yaml.clib \
      scikit-image \
      scikit-learn \
      scipy \
      setproctitle \
      tifffile \
      tqdm \
      transforms3d \
      trimesh \
      PyWavefront \
      h5py \
      cvxopt
    python -m pip install --no-deps \
      autolab-core==1.1.1 \
      grasp_nms \
      graspnetAPI==1.2.11

    export CUDA_HOME=/usr/local/cuda
    export PATH="$CUDA_HOME/bin:$PATH"
    export CXX=g++
    export CC=gcc

    if [[ ! -d "$A1Z_MINKOWSKIENGINE_SOURCE_DIR" ]]; then
      echo "MinkowskiEngine source not found: $A1Z_MINKOWSKIENGINE_SOURCE_DIR" >&2
      exit 1
    fi

    cd "$A1Z_MINKOWSKIENGINE_SOURCE_DIR"
    sed -i "s/\\bauto __raw = __to_address(__r.get());/auto __raw = std::__to_address(__r.get());/" \
      /usr/include/c++/11/bits/shared_ptr_base.h || true
    python setup.py install \
      --force_cuda \
      --cuda_home="$CUDA_HOME" \
      --blas_include_dirs=/usr/include \
      --blas=openblas

    cd "$A1Z_ANYGRASP_SDK_DIR/pointnet2"
    python setup.py install

    SAM2_BUILD_CUDA=0 python -m pip install --no-build-isolation --no-deps "$A1Z_SAM2_REPO_DIR"

    mkdir -p "$A1Z_GRCONVNET_MODEL_DIR"
    if [[ ! -f "$A1Z_GRCONVNET_MODEL_PATH" ]]; then
      curl -L \
        "https://raw.githubusercontent.com/skumra/robotic-grasping/183c6f68c44c1c7ff0f07707e2db6fcfd6840d2d/trained-models/jacquard-rgbd-grconvnet3-drop0-ch32/epoch_48_iou_0.93" \
        -o "$A1Z_GRCONVNET_MODEL_PATH"
    fi
  '

"$ROOT_DIR/scripts/setup_anygrasp_sdk_in_container.sh"
