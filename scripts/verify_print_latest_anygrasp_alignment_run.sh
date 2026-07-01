#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if bash "$ROOT_DIR/scripts/print_latest_anygrasp_alignment_run.sh" >/tmp/a1z_latest_anygrasp_alignment_run.txt 2>/tmp/a1z_latest_anygrasp_alignment_run.err
then
  python3 - <<PY
from pathlib import Path

path = Path("/tmp/a1z_latest_anygrasp_alignment_run.txt").read_text(encoding="utf-8").strip()
assert path, path
assert path.startswith("/home/th1rt3en/dev/forge/A1Z/runtime/"), path
print("Latest AnyGrasp alignment-run printer verification passed with reliable run")
PY
else
  python3 - <<PY
from pathlib import Path

err = Path("/tmp/a1z_latest_anygrasp_alignment_run.err").read_text(encoding="utf-8")
assert "no reliable AnyGrasp alignment run found" in err, err
print("Latest AnyGrasp alignment-run printer verification passed with empty reliable set")
PY
fi

echo "Latest AnyGrasp alignment-run printer verification passed."
