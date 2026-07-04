#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT_DIR" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
env_text = (root / "config" / "a1z_container.env").read_text(encoding="utf-8")
frames_text = (root / "a1z_ext" / "grasping" / "anygrasp_frames.py").read_text(encoding="utf-8")
pick_text = (root / "scripts" / "run_target_mask_to_anygrasp_pick_attempt.sh").read_text(encoding="utf-8")
from_ros_text = (root / "scripts" / "run_target_mask_to_anygrasp_from_ros.sh").read_text(encoding="utf-8")
replay_text = (root / "scripts" / "replay_anygrasp_from_capture.sh").read_text(encoding="utf-8")

def extract(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    assert match, pattern
    return match.group(1)

frame_binding = extract(r'^ANYGRASP_ACTIVE_BINDING_LABEL = "([^"]+)"$', frames_text)
frame_camera = extract(r'^ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL = "([^"]+)"$', frames_text)
frame_extrinsic = extract(r'^ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL = "([^"]+)"$', frames_text)

expected_env = {
    "A1Z_ANYGRASP_BINDING_LABEL": frame_binding,
    "A1Z_ANYGRASP_CAMERA_CORRECTION_LABEL": frame_camera,
    "A1Z_ANYGRASP_EXTRINSIC_CORRECTION_LABEL": frame_extrinsic,
    "A1Z_ANYGRASP_EXECUTION_MODE": "best_direct",
    "A1Z_ANYGRASP_EE_GRASP_ORIGIN": "[0.0, 0.0, 0.0]",
    "A1Z_ANYGRASP_EE_OPENING_AXIS": "[0.0, 0.0, 1.0]",
    "A1Z_ANYGRASP_EE_APPROACH_AXIS": "[1.0, 0.0, 0.0]",
}

for key, value in expected_env.items():
    actual = extract(rf'^{re.escape(key)}=(.+)$', env_text)
    assert actual == value, (key, actual, value)

assert 'EXECUTION_MODE="${A1Z_ANYGRASP_EXECUTION_MODE:-best_direct}"' in pick_text, pick_text
assert f'ANYGRASP_BINDING_LABEL="${{A1Z_ANYGRASP_BINDING_LABEL:-{frame_binding}}}"' in from_ros_text, from_ros_text
assert f'ANYGRASP_CAMERA_CORRECTION_LABEL="${{A1Z_ANYGRASP_CAMERA_CORRECTION_LABEL:-{frame_camera}}}"' in from_ros_text, from_ros_text
assert f'ANYGRASP_EXTRINSIC_CORRECTION_LABEL="${{A1Z_ANYGRASP_EXTRINSIC_CORRECTION_LABEL:-{frame_extrinsic}}}"' in from_ros_text, from_ros_text
assert f'ANYGRASP_BINDING_LABEL="${{A1Z_ANYGRASP_BINDING_LABEL:-{frame_binding}}}"' in replay_text, replay_text
assert f'ANYGRASP_CAMERA_CORRECTION_LABEL="${{A1Z_ANYGRASP_CAMERA_CORRECTION_LABEL:-{frame_camera}}}"' in replay_text, replay_text
assert f'ANYGRASP_EXTRINSIC_CORRECTION_LABEL="${{A1Z_ANYGRASP_EXTRINSIC_CORRECTION_LABEL:-{frame_extrinsic}}}"' in replay_text, replay_text

print("AnyGrasp active-default verification passed")
PY

echo "AnyGrasp active-default verification passed."
