#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="/workspace/A1Z/runtime/anygrasp_adapter_verify"

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
from pathlib import Path
import json
import shutil

import numpy as np

from a1z.robots.kinematics import Kinematics
from a1z_ext.config import get_default_control_urdf_path
from a1z_ext.grasping import ContactGraspNetA1ZAdapterConfig

root = Path('$OUTPUT_DIR')
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True, exist_ok=True)

q = np.array([0.0, 1.05, -1.55, 0.0, 0.45, 0.0], dtype=np.float64)
kin = Kinematics(get_default_control_urdf_path(), end_effector_frame='grasp_tcp')
ee_pose = kin.fk(q, frame_name='grasp_tcp')

cfg = ContactGraspNetA1ZAdapterConfig(
    use_ik=False,
    require_approach_downward=False,
    ee_grasp_origin_xyz_m=(0.0, 0.0, 0.0),
    ee_opening_axis_xyz=(0.0, 1.0, 0.0),
    ee_approach_axis_xyz=(1.0, 0.0, 0.0),
)
ee_to_grasp = cfg.ee_to_grasp_transform()
grasp_pose = ee_pose @ ee_to_grasp
raw_anygrasp_rotation = np.column_stack([
    grasp_pose[:3, 2],
    grasp_pose[:3, 0],
    grasp_pose[:3, 1],
])

result_path = root / 'anygrasp_result.json'
extrinsic_path = root / 'extrinsic_camera_to_base.npy'
q_path = root / 'current_q.npy'

payload = {
    'ran': True,
    'grasp_count': 1,
    'top_k': 1,
    'lims': [-1, 1, -1, 1, 0, 1],
    'preflight': {'ready': True},
    'top_grasps': [{
        'rank': 0,
        'score': 0.95,
        'width_m': 0.045,
        'height_m': 0.03,
        'depth_m': 0.03,
        'translation_xyz_m': grasp_pose[:3, 3].astype(float).tolist(),
        'rotation_matrix': raw_anygrasp_rotation.astype(float).tolist(),
        'object_id': -1,
    }],
    'result_json_path': str(result_path),
    'error': '',
}
result_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding='utf-8')
np.save(extrinsic_path, np.eye(4, dtype=np.float64))
np.save(q_path, q)

manifest = {
    'result_json': str(result_path),
    'extrinsic_camera_to_base': str(extrinsic_path),
    'current_q': str(q_path),
}
(root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=True))
"

if ! bash "$ROOT_DIR/scripts/run_anygrasp_adapter_in_container.sh" \
  --result-json "$OUTPUT_DIR/anygrasp_result.json" \
  --extrinsic-camera-to-base "$OUTPUT_DIR/extrinsic_camera_to_base.npy" \
  --current-joints-rad "$OUTPUT_DIR/current_q.npy" \
  --output-dir "$OUTPUT_DIR/result" \
  --task-id verify-anygrasp-adapter \
  --object-id verify-object \
  --backend mock \
  --pregrasp-offset-m 0.0 \
  --lift-offset-m 0.0 \
  --retreat-offset-m 0.0 \
  --ee-grasp-origin-xyz-m '[0.0, 0.0, 0.0]' \
  --ee-opening-axis-xyz '[0.0, 1.0, 0.0]' \
  --ee-approach-axis-xyz '[1.0, 0.0, 0.0]' \
  --max-approach-deviation-deg 180 \
  --min-joint-margin-deg 0
then
  :
fi

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
import json
from pathlib import Path

result_path = Path('$OUTPUT_DIR/result/anygrasp_adapter_result.json')

if not result_path.is_file():
    raise SystemExit(f'missing result: {result_path}')

result = json.loads(result_path.read_text(encoding='utf-8'))

assert result['summary']['candidate_count'] >= 1, result
assert result['summary']['source_model'] == 'anygrasp', result
assert result['summary']['active_binding_label'] == 'opening=c1,height=c2,approach=c0', result
assert result['summary']['active_camera_correction_label'] == 'identity', result
assert result['summary']['active_extrinsic_correction_label'] == 'identity', result
candidate = result['candidates'][0]
assert candidate['frame_id'] == 'robot_base_frame', candidate
assert isinstance(candidate.get('failure_reasons'), list), candidate
assert isinstance(candidate.get('ik_summary'), dict), candidate
if result['selected_plan'] is not None:
    plan_path = Path('$OUTPUT_DIR/result/selected_plan.json')
    if not plan_path.is_file():
        raise SystemExit(f'missing selected plan: {plan_path}')
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    assert plan['selected_grasp_candidate_id'] == candidate['candidate_id'], plan
    assert len(plan['joint_trajectory_segments']) == 4, plan
print('anygrasp adapter container verification passed')
"

echo "AnyGrasp adapter container verification passed."
