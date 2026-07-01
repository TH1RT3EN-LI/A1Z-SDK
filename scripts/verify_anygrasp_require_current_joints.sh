#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/runtime/target_mask_to_anygrasp/from_ros_live"
OUTPUT_DIR="$ROOT_DIR/runtime/anygrasp_require_current_joints_verify"

rm -rf "$OUTPUT_DIR"

if bash "$ROOT_DIR/scripts/replay_anygrasp_from_capture.sh" \
  --require-current-joints \
  "$SOURCE_DIR" \
  "$OUTPUT_DIR" >/tmp/a1z_require_current_joints.out 2>/tmp/a1z_require_current_joints.err
then
  echo "expected replay_anygrasp_from_capture.sh to fail when current_joints_rad.json is required but missing" >&2
  exit 1
fi

python3 - <<PY
from pathlib import Path

err = Path("/tmp/a1z_require_current_joints.err").read_text(encoding="utf-8")
assert "missing required current_joints_rad.json" in err, err
assert not Path(r"$OUTPUT_DIR").exists(), "unexpected output dir created"
print("AnyGrasp require-current-joints verification passed")
PY

echo "AnyGrasp require-current-joints verification passed."
