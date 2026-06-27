#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="/workspace/A1Z/runtime/open_vocab_loop_verify"

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
from pathlib import Path
import shutil
root = Path('$OUTPUT_DIR')
if root.exists():
    shutil.rmtree(root)
"

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" /workspace/A1Z/scripts/run_open_vocab_data_loop.py \
  --instruction "pick the red mug on the table" \
  --output-dir "$OUTPUT_DIR"

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
import json
from pathlib import Path

bundle_path = Path('$OUTPUT_DIR/bundle.json')
observation_path = Path('$OUTPUT_DIR/observation.json')
if not bundle_path.is_file():
    raise SystemExit(f'missing bundle: {bundle_path}')
if not observation_path.is_file():
    raise SystemExit(f'missing observation: {observation_path}')
data = json.loads(bundle_path.read_text(encoding='utf-8'))
observation = json.loads(observation_path.read_text(encoding='utf-8'))
assert data['task']['action_type'] == 'pick', data
assert observation['source_backend'] == 'sample', observation
assert observation['camera_frame_id'] == 'camera_color_frame', observation
assert observation['target_frame_id'] == 'robot_base_frame', observation
assert len(data['grounding_candidates']) == 3, data
assert len(data['mask_candidates']) == 3, data
assert len(data['object_descriptors']) >= 1, data
first = data['object_descriptors'][0]
assert first['frame_id'] == 'robot_base_frame', first
assert first['point_count'] > 0, first
assert len(first['centroid_xyz']) == 3, first
assert len(first['bbox_extent_xyz_m']) == 3, first
print('open vocab data loop verification passed')
"

echo "Open-vocabulary data loop verification passed."
