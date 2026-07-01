#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])

active_scripts = [
    root / "scripts" / "run_target_mask_to_anygrasp_pick_attempt.sh",
    root / "scripts" / "run_target_mask_to_anygrasp_from_ros.sh",
    root / "scripts" / "replay_anygrasp_from_capture.sh",
    root / "scripts" / "analyze_anygrasp_output_dir.sh",
    root / "scripts" / "find_anygrasp_alignment_runs.sh",
    root / "scripts" / "print_latest_anygrasp_alignment_run.sh",
]

for path in active_scripts:
    text = path.read_text(encoding="utf-8")
    assert "economicgrasp" not in text, path

for path in (root / "scripts").glob("*economicgrasp*"):
    raise AssertionError(path)

removed_legacy_modules = [
    root / "a1z_ext" / "grasping" / "economicgrasp_adapter.py",
    root / "a1z_ext" / "perception" / "economicgrasp.py",
]

for path in removed_legacy_modules:
    assert not path.exists(), path

for path in [
    root / "a1z_ext" / "grasping" / "__init__.py",
    root / "a1z_ext" / "perception" / "__init__.py",
]:
    assert "economicgrasp" not in path.read_text(encoding="utf-8"), path

print("AnyGrasp-only active-path verification passed")
PY

echo "AnyGrasp-only active-path verification passed."
