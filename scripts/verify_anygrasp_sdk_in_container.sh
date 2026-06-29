#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_VENV_DIR="${A1Z_VISION_VENV_DIR:-/opt/venvs/a1z-vision}"
ANYGRASP_SDK_DIR="${A1Z_ANYGRASP_SDK_DIR:-/workspace/A1Z/vendor/vision/anygrasp_sdk}"
ANYGRASP_DETECTION_CKPT="${A1Z_ANYGRASP_DETECTION_CKPT:-/workspace/A1Z/runtime/models/anygrasp/checkpoint_detection.tar}"
ANYGRASP_TRACKING_CKPT="${A1Z_ANYGRASP_TRACKING_CKPT:-/workspace/A1Z/runtime/models/anygrasp/checkpoint_tracking.tar}"
ANYGRASP_LICENSE_DIR="${A1Z_ANYGRASP_LICENSE_DIR:-/workspace/A1Z/runtime/licenses/anygrasp}"
ANYGRASP_IFCONFIG_SNAPSHOT="${A1Z_ANYGRASP_IFCONFIG_SNAPSHOT:-/workspace/A1Z/runtime/anygrasp/ifconfig.snapshot}"

"$ROOT_DIR/scripts/bootstrap_anygrasp_assets.sh"
"$ROOT_DIR/scripts/setup_anygrasp_sdk_in_container.sh"

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_VISION_VENV_DIR="$VISION_VENV_DIR" \
  -e A1Z_ANYGRASP_SDK_DIR="$ANYGRASP_SDK_DIR" \
  -e A1Z_ANYGRASP_DETECTION_CKPT="$ANYGRASP_DETECTION_CKPT" \
  -e A1Z_ANYGRASP_TRACKING_CKPT="$ANYGRASP_TRACKING_CKPT" \
  -e A1Z_ANYGRASP_LICENSE_DIR="$ANYGRASP_LICENSE_DIR" \
  -e A1Z_ANYGRASP_IFCONFIG_SNAPSHOT="$ANYGRASP_IFCONFIG_SNAPSHOT" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source "$A1Z_VISION_VENV_DIR/bin/activate"
    if [[ -f "$A1Z_ANYGRASP_IFCONFIG_SNAPSHOT" ]]; then
      tmp_anygrasp_bin="/tmp/a1z-anygrasp-bin-$(id -u)"
      rm -rf "$tmp_anygrasp_bin"
      mkdir -p "$tmp_anygrasp_bin"
      cat >"$tmp_anygrasp_bin/ifconfig" <<EOF
#!/usr/bin/env bash
cat "$A1Z_ANYGRASP_IFCONFIG_SNAPSHOT"
EOF
      chmod +x "$tmp_anygrasp_bin/ifconfig"
      export PATH="$tmp_anygrasp_bin:$PATH"
    fi
    cd "$A1Z_ANYGRASP_SDK_DIR/grasp_detection"
    python demo.py --checkpoint_path "$A1Z_ANYGRASP_DETECTION_CKPT" --top_down_grasp

    cd /workspace/A1Z
    python - <<'"'"'PY'"'"'
import json
from pathlib import Path

import numpy as np

from a1z_ext.perception import check_anygrasp_runtime, run_anygrasp_detection

sdk_dir = Path("/workspace/A1Z/vendor/vision/anygrasp_sdk")
checkpoint_path = Path("/workspace/A1Z/runtime/models/anygrasp/checkpoint_detection.tar")
license_dir = Path("/workspace/A1Z/runtime/licenses/anygrasp")
example_dir = sdk_dir / "grasp_detection" / "example_data"

preflight = check_anygrasp_runtime(
    sdk_dir=sdk_dir,
    checkpoint_path=checkpoint_path,
    license_dir=license_dir,
)
print("A1Z AnyGrasp preflight:", json.dumps(preflight.to_dict(), ensure_ascii=True))
if not preflight.ready:
    raise SystemExit("A1Z AnyGrasp preflight failed")

from PIL import Image

colors = np.array(Image.open(example_dir / "color.png"), dtype=np.float32) / 255.0
depths = np.array(Image.open(example_dir / "depth.png"))
fx, fy = 927.17, 927.37
cx, cy = 651.32, 349.62
scale = 1000.0
lims = [-0.19, 0.12, 0.02, 0.15, 0.0, 1.0]

xmap, ymap = np.meshgrid(np.arange(depths.shape[1]), np.arange(depths.shape[0]))
points_z = depths / scale
points_x = (xmap - cx) / fx * points_z
points_y = (ymap - cy) / fy * points_z
mask = (points_z > 0) & (points_z < 1)
points = np.stack([points_x, points_y, points_z], axis=-1)[mask].astype(np.float32)
sample_colors = colors[mask].astype(np.float32)

result = run_anygrasp_detection(
    points=points,
    colors=sample_colors,
    lims=lims,
    output_dir=Path("/workspace/A1Z/runtime/anygrasp_verify"),
    sdk_dir=sdk_dir,
    checkpoint_path=checkpoint_path,
    license_dir=license_dir,
    top_down_grasp=True,
    top_k=5,
)
print("A1Z AnyGrasp smoke:", json.dumps(result.to_dict(), ensure_ascii=True))
if not result.ran or result.grasp_count <= 0:
    raise SystemExit("A1Z AnyGrasp smoke failed")
PY
  '
