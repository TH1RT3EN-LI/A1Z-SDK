#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

ECONOMICGRASP_CONTAINER_NAME="${A1Z_ECONOMICGRASP_CONTAINER_NAME:-a1z-economicgrasp-gpu}"
ECONOMICGRASP_VENV_DIR="${A1Z_ECONOMICGRASP_VENV_DIR:-/opt/venvs/economicgrasp}"
ECONOMICGRASP_REPO_DIR="${A1Z_ECONOMICGRASP_REPO_DIR:-/workspace/A1Z/vendor/vision/EconomicGrasp}"
ECONOMICGRASP_REALSENSE_CKPT="${A1Z_ECONOMICGRASP_REALSENSE_CKPT:-/workspace/A1Z/runtime/models/economicgrasp/economicgrasp_realsense.tar}"
ECONOMICGRASP_KINECT_CKPT="${A1Z_ECONOMICGRASP_KINECT_CKPT:-/workspace/A1Z/runtime/models/economicgrasp/economicgrasp_kinect.tar}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$ECONOMICGRASP_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$ECONOMICGRASP_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_ECONOMICGRASP_VENV_DIR="$ECONOMICGRASP_VENV_DIR" \
  -e A1Z_ECONOMICGRASP_REPO_DIR="$ECONOMICGRASP_REPO_DIR" \
  -e A1Z_ECONOMICGRASP_REALSENSE_CKPT="$ECONOMICGRASP_REALSENSE_CKPT" \
  -e A1Z_ECONOMICGRASP_KINECT_CKPT="$ECONOMICGRASP_KINECT_CKPT" \
  "$ECONOMICGRASP_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source "$A1Z_ECONOMICGRASP_VENV_DIR/bin/activate"
    export PYTHONPATH="$A1Z_ECONOMICGRASP_REPO_DIR:/workspace/A1Z"

    python - <<'"'"'PY'"'"'
import os
import sys

import MinkowskiEngine as ME
import numpy as np
import open3d
import torch
import pointnet2._ext as pointnet2_ext
import knn_pytorch

sys.argv = [
    "verify_economicgrasp",
    "--dataset_root", "/tmp/graspnet_stub",
    "--camera", "realsense",
]
from models.economicgrasp import economicgrasp

net = economicgrasp(seed_feat_dim=512, is_training=False)

print("torch:", torch.__version__)
print("torch.cuda.is_available:", torch.cuda.is_available())
print("torch.cuda.device_count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("torch.cuda.device_name:", torch.cuda.get_device_name(0))
print("numpy:", np.__version__)
print("open3d:", open3d.__version__)
print("MinkowskiEngine:", ME.__version__)
print("pointnet2 ext:", pointnet2_ext.__name__)
print("knn module:", knn_pytorch.__name__)
try:
    import graspnetAPI
except Exception as exc:
    print("graspnetAPI: not installed or unavailable:", repr(exc))
else:
    print("graspnetAPI:", graspnetAPI.__file__)
print("economicgrasp model init: OK", net.__class__.__name__)
print("realsense checkpoint exists:", os.path.exists(os.environ["A1Z_ECONOMICGRASP_REALSENSE_CKPT"]))
print("kinect checkpoint exists:", os.path.exists(os.environ["A1Z_ECONOMICGRASP_KINECT_CKPT"]))
PY
  '
