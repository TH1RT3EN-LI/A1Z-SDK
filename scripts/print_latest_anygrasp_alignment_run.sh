#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUTPUT_JSON="$(python3 "$ROOT_DIR/scripts/find_anygrasp_alignment_runs.py" \
  --runtime-dir "$ROOT_DIR/runtime" \
  --require-analysis \
  --require-current-joints \
  --require-reliable \
  --limit 1 \
  --json)"

python3 - <<PY
import json

payload = json.loads(r'''$OUTPUT_JSON''')
runs = payload.get("runs", [])
if not runs:
    raise SystemExit("no reliable AnyGrasp alignment run found")
print(runs[0]["pipeline_dir"])
PY
