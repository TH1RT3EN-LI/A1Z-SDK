#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="/workspace/A1Z/runtime/contact_graspnet_adapter_verify"

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
kin = Kinematics(get_default_control_urdf_path(), end_effector_frame='arm_link6')
ee_pose = kin.fk(q, frame_name='arm_link6')

cfg = ContactGraspNetA1ZAdapterConfig(
    use_ik=False,
    require_approach_downward=False,
)
ee_to_grasp = cfg.ee_to_grasp_transform()
grasp_pose = ee_pose @ ee_to_grasp

pred_path = root / 'predictions.npz'
extrinsic_path = root / 'extrinsic_camera_to_base.npy'
q_path = root / 'current_q.npy'

np.savez(
    pred_path,
    pred_grasps_cam=np.expand_dims(grasp_pose, axis=0),
    scores=np.array([0.95], dtype=np.float64),
    gripper_openings=np.array([0.045], dtype=np.float64),
    contact_pts=np.array([[grasp_pose[0, 3], grasp_pose[1, 3], grasp_pose[2, 3]]], dtype=np.float64),
)
np.save(extrinsic_path, np.eye(4, dtype=np.float64))
np.save(q_path, q)

manifest = {
    'predictions': str(pred_path),
    'extrinsic_camera_to_base': str(extrinsic_path),
    'current_q': str(q_path),
}
(root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=True))
"

"$ROOT_DIR/scripts/run_contact_graspnet_adapter_in_container.sh" \
  --predictions "$OUTPUT_DIR/predictions.npz" \
  --extrinsic-camera-to-base "$OUTPUT_DIR/extrinsic_camera_to_base.npy" \
  --current-joints-rad "$OUTPUT_DIR/current_q.npy" \
  --output-dir "$OUTPUT_DIR/result" \
  --task-id verify-contact-graspnet-adapter \
  --object-id verify-object \
  --backend mock \
  --pregrasp-offset-m 0.0 \
  --lift-offset-m 0.0 \
  --retreat-offset-m 0.0 \
  --max-approach-deviation-deg 180 \
  --min-joint-margin-deg 0

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
import json
from pathlib import Path

result_path = Path('$OUTPUT_DIR/result/contact_graspnet_adapter_result.json')
plan_path = Path('$OUTPUT_DIR/result/selected_plan.json')

if not result_path.is_file():
    raise SystemExit(f'missing result: {result_path}')
if not plan_path.is_file():
    raise SystemExit(f'missing selected plan: {plan_path}')

result = json.loads(result_path.read_text(encoding='utf-8'))
plan = json.loads(plan_path.read_text(encoding='utf-8'))

assert result['summary']['candidate_count'] >= 1, result
assert result['selected_plan'] is not None, result
assert len(result['candidates']) >= 1, result
candidate = result['candidates'][0]
assert candidate['frame_id'] == 'robot_base_frame', candidate
assert 'pregrasp_pose' in candidate, candidate
assert 'grasp_pose' in candidate, candidate
assert 'lift_pose' in candidate, candidate
assert plan['selected_grasp_candidate_id'] == candidate['candidate_id'], plan
assert len(plan['joint_trajectory_segments']) == 4, plan
print('contact_graspnet adapter container verification passed')
"

echo "Contact-GraspNet adapter container verification passed."
