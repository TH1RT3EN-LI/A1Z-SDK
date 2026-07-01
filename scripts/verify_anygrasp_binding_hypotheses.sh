#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="/workspace/A1Z/runtime/anygrasp_replay_compare_summary_v4/adapter/anygrasp_alignment_report.json"
OUTPUT="/workspace/A1Z/runtime/anygrasp_binding_hypotheses_verify.json"

bash "$ROOT_DIR/scripts/rank_anygrasp_binding_hypotheses_in_container.sh" \
  --alignment-report "$REPORT" \
  --observed-tool-delta-xyz '[0.0704, 0.1026, -0.0778]' \
  --top-k 2 \
  --output "$OUTPUT" >/dev/null

python3 - <<PY
import json
from pathlib import Path

payload = json.loads(Path("/home/th1rt3en/dev/forge/A1Z/runtime/anygrasp_binding_hypotheses_verify.json").read_text(encoding="utf-8"))
top = payload["top_matches"]
assert len(top) >= 2, payload
assert payload["source_kind"] in {"alignment_report", "mapping_hypotheses"}, payload
assert isinstance(top[0]["binding_label"], str) and top[0]["binding_label"], payload
assert top[0]["residual_norm_m"] >= 0.0, payload
print("AnyGrasp binding-hypothesis ranking verification passed")
PY

echo "AnyGrasp binding-hypothesis ranking verification passed."
