#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
OUTPUT_DIR="/workspace/A1Z/runtime/open_vocab_loop_isaac_verify"
LOG_FILE="/workspace/A1Z/runtime/logs/open-vocab-isaac-verify.log"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
from pathlib import Path
import shutil
root = Path('$OUTPUT_DIR')
if root.exists():
    shutil.rmtree(root)
"
docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "rm -f '$LOG_FILE'"
docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
  ps -eo pid,args \
    | awk '/isaacsim\\.exp\\.full\\.streaming\\.kit/ && /run_open_vocab_data_loop_from_isaac\\.py/ {print \$1}' \
    | xargs -r kill -9 >/dev/null 2>&1 || true
"

VERIFY_PID="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
    export A1Z_WORLD_USD='${A1Z_WORLD_USD:-/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd}'
    export A1Z_D405_ENABLED='1'
    export A1Z_D405_PARENT_PRIM='${A1Z_D405_PARENT_PRIM:-/World}'
    export A1Z_D405_FALLBACK_PARENT_PRIM='${A1Z_D405_FALLBACK_PARENT_PRIM:-/World}'
    export A1Z_D405_FK_FRAME='${A1Z_D405_FK_FRAME:-arm_link6}'
    export A1Z_D405_MOUNT_OFFSET='${A1Z_D405_MOUNT_OFFSET:-0,0,0.05623718}'
    export A1Z_D405_MOUNT_RPY_DEG='${A1Z_D405_MOUNT_RPY_DEG:-0,0,0}'
    export A1Z_D405_CAMERA_OPTICAL_RPY_DEG='${A1Z_D405_CAMERA_OPTICAL_RPY_DEG:-}'
    export A1Z_D405_CAMERA_PRIMS_ENABLED='${A1Z_D405_CAMERA_PRIMS_ENABLED:-1}'
    export A1Z_D405_CENTER_MESH_Y='${A1Z_D405_CENTER_MESH_Y:-1}'
    export A1Z_D405_CENTER_ON_AXIS='${A1Z_D405_CENTER_ON_AXIS:-1}'
    export A1Z_D405_STATUS_PATH='${A1Z_D405_STATUS_PATH:-/workspace/A1Z/runtime/logs/d405-wrist-camera.status}'
    export A1Z_D405_ROS2_NAMESPACE='${A1Z_D405_ROS2_NAMESPACE:-/a1z/d405}'
    export A1Z_D405_COLOR_FRAME_ID='${A1Z_D405_COLOR_FRAME_ID:-d405_color_optical_frame}'
    export A1Z_D405_DEPTH_FRAME_ID='${A1Z_D405_DEPTH_FRAME_ID:-d405_depth_optical_frame}'
    export A1Z_D405_WIDTH='${A1Z_D405_WIDTH:-1280}'
    export A1Z_D405_HEIGHT='${A1Z_D405_HEIGHT:-720}'
    export A1Z_D405_FRAME_SKIP_COUNT='${A1Z_D405_FRAME_SKIP_COUNT:-1}'
    export A1Z_OPEN_VOCAB_INSTRUCTION='pick the red mug on the table'
    export A1Z_OPEN_VOCAB_OUTPUT_DIR='$OUTPUT_DIR'
    nohup /isaac-sim/runheadless.sh \
      --ext-folder /workspace/A1Z/exts \
      --exec '/workspace/A1Z/scripts/run_open_vocab_data_loop_from_isaac.py --output-dir \"$OUTPUT_DIR\"' \
      >'$LOG_FILE' 2>&1 &
    echo \$!
  "
)"
KIT_VERIFY_PID="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
    for _ in \$(seq 1 40); do
      pid=\$(ps -o pid= --ppid '$VERIFY_PID' | awk 'NR==1 {print \$1}')
      if [[ -n \"\$pid\" ]]; then
        echo \"\$pid\"
        break
      fi
      sleep 0.5
    done
  "
)"

cleanup() {
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
    if [[ -n '$KIT_VERIFY_PID' ]] && kill -0 '$KIT_VERIFY_PID' 2>/dev/null; then
      kill '$KIT_VERIFY_PID' 2>/dev/null || true
      wait '$KIT_VERIFY_PID' 2>/dev/null || true
    fi
    if [[ -n '$VERIFY_PID' ]] && kill -0 '$VERIFY_PID' 2>/dev/null; then
      kill '$VERIFY_PID' 2>/dev/null || true
      wait '$VERIFY_PID' 2>/dev/null || true
    fi
    ps -eo pid,args \
      | awk '/isaacsim\\.exp\\.full\\.streaming\\.kit/ && /run_open_vocab_data_loop_from_isaac\\.py/ {print \$1}' \
      | xargs -r kill -9 >/dev/null 2>&1 || true
  " >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 240); do
  if docker exec -u ubuntu "$CONTAINER_NAME" test -f "$OUTPUT_DIR/bundle.json"; then
    break
  fi
  if docker exec -u ubuntu "$CONTAINER_NAME" test -f "$OUTPUT_DIR/error.txt"; then
    break
  fi
  sleep 1
done

if ! docker exec -u ubuntu "$CONTAINER_NAME" test -f "$OUTPUT_DIR/bundle.json"; then
  echo "Isaac open-vocab bundle was not produced: $OUTPUT_DIR/bundle.json" >&2
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "cat '$OUTPUT_DIR/progress.json' 2>/dev/null || true; echo; cat '$OUTPUT_DIR/error.txt' 2>/dev/null || true; echo; tail -n 120 '$LOG_FILE' 2>/dev/null || true" >&2
  exit 1
fi

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
import json
from pathlib import Path
import numpy as np

root = Path('$OUTPUT_DIR')
bundle_path = root / 'bundle.json'
observation_path = root / 'observation.json'
metadata_path = root / 'observation_metadata.json'
rgb_path = root / 'rgb.npy'
depth_path = root / 'depth_m.npy'

if not bundle_path.is_file():
    raise SystemExit(f'missing bundle: {bundle_path}')
if not observation_path.is_file():
    raise SystemExit(f'missing observation: {observation_path}')
if not metadata_path.is_file():
    raise SystemExit(f'missing metadata: {metadata_path}')
if not rgb_path.is_file():
    raise SystemExit(f'missing rgb: {rgb_path}')
if not depth_path.is_file():
    raise SystemExit(f'missing depth: {depth_path}')

data = json.loads(bundle_path.read_text(encoding='utf-8'))
observation = json.loads(observation_path.read_text(encoding='utf-8'))
meta = json.loads(metadata_path.read_text(encoding='utf-8'))
rgb = np.load(rgb_path)
depth = np.load(depth_path)

assert data['task']['action_type'] == 'pick', data
assert observation['source_backend'] == 'isaacsim_d405', observation
assert observation['camera_frame_id'] == 'd405_color_optical_frame', observation
assert observation['target_frame_id'] == 'robot_base_frame', observation
assert meta['source_backend'] == 'isaacsim_d405', meta
assert 'ColorCamera' in meta['color_camera_path'], meta
assert 'DepthCamera' in meta['depth_camera_path'], meta
assert rgb.ndim == 3 and rgb.shape[2] == 3, rgb.shape
assert depth.ndim == 2, depth.shape
assert rgb.shape[:2] == depth.shape[:2], (rgb.shape, depth.shape)
assert rgb.shape[0] > 0 and rgb.shape[1] > 0, rgb.shape
assert float(np.isfinite(depth).mean()) > 0.05, float(np.isfinite(depth).mean())
assert len(data['grounding_candidates']) == 3, data
assert len(data['mask_candidates']) == 3, data
assert len(data['object_descriptors']) >= 1, data
first = data['object_descriptors'][0]
assert first['frame_id'] == 'robot_base_frame', first
assert first['point_count'] > 0, first
assert float(first['point_cloud_quality']) > 0.05, first
print('open vocab data loop from isaac verification passed')
"

for _ in $(seq 1 30); do
  if ! docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "kill -0 '${KIT_VERIFY_PID:-$VERIFY_PID}' 2>/dev/null"; then
    break
  fi
  sleep 1
done

echo "Open-vocabulary Isaac data loop verification passed."
echo "Log: $LOG_FILE"
