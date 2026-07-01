#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUTPUT_JSON="$(python3 "$ROOT_DIR/scripts/find_anygrasp_alignment_runs.py" --runtime-dir "$ROOT_DIR/runtime" --limit 5 --json)"

python3 - <<PY
import json

payload = json.loads(r'''$OUTPUT_JSON''')
runs = payload["runs"]
assert isinstance(runs, list), payload
assert len(runs) >= 1, payload
for row in runs:
    assert "/runtime/" in row["pipeline_dir"], row
    assert row["pipeline_dir"].startswith("/home/th1rt3en/dev/forge/A1Z/runtime/"), row
    assert isinstance(row["run_name"], str) and row["run_name"], row
    assert row["is_fixture_dir"] is False, row
    assert isinstance(row["analysis_present"], bool), row
    assert isinstance(row["current_joints_present"], bool), row
    assert isinstance(row["best_direct_reference_state_reliable"], bool), row
    assert isinstance(row["alignment_fit_for_decision"], bool), row
print("AnyGrasp alignment-run finder verification passed")
PY

echo "AnyGrasp alignment-run finder verification passed."
