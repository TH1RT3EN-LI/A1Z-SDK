#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_VENV_DIR="${A1Z_VISION_VENV_DIR:-/opt/venvs/a1z-vision}"
SAM2_DEFAULT_CKPT="${A1Z_SAM2_DEFAULT_CKPT:-/workspace/A1Z/runtime/models/sam2/sam2.1_hiera_small.pt}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_VISION_VENV_DIR="$VISION_VENV_DIR" \
  -e A1Z_SAM2_DEFAULT_CKPT="$SAM2_DEFAULT_CKPT" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source "$A1Z_VISION_VENV_DIR/bin/activate"

    python - <<'"'"'PY'"'"'
import os
import sys

import cv2
import open3d
import torch
from sam2.sam2_image_predictor import SAM2ImagePredictor
from graspnetAPI.grasp import GraspGroup

sdk_dir = "/workspace/A1Z/vendor/vision/anygrasp_sdk"
sys.path.insert(0, f"{sdk_dir}/grasp_detection")
sys.path.insert(0, f"{sdk_dir}/grasp_tracking")
import gsnet  # noqa: F401
import tracker  # noqa: F401

print("torch:", torch.__version__)
print("torch.cuda.is_available:", torch.cuda.is_available())
print("torch.cuda.device_count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("torch.cuda.device_name:", torch.cuda.get_device_name(0))
print("cv2:", cv2.__version__)
print("open3d:", open3d.__version__)
print("graspnetAPI:", GraspGroup.__module__)
print("sam2 predictor import: OK", SAM2ImagePredictor.__name__)
print("AnyGrasp gsnet import: OK")
print("AnyGrasp tracker import: OK")
if hasattr(gsnet, "get_feature_id"):
    print("AnyGrasp feature id:", gsnet.get_feature_id())
print("SAM2 checkpoint exists:", os.path.exists(os.environ["A1Z_SAM2_DEFAULT_CKPT"]))
PY
  '
