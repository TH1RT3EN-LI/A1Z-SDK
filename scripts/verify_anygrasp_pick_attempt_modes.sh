#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_DIR="$ROOT_DIR/tests/fixtures/anygrasp_execution_modes"
VERIFY_ROOT="$ROOT_DIR/runtime/anygrasp_pick_attempt_modes_verify"

rm -rf "$VERIFY_ROOT"
mkdir -p "$VERIFY_ROOT/adapter_selected/adapter" "$VERIFY_ROOT/best_direct/adapter/best_direct"

cp "$FIXTURE_DIR/adapter/selected_plan.json" "$VERIFY_ROOT/adapter_selected/adapter/selected_plan.json"
cp "$FIXTURE_DIR/adapter/selected_plan.json" "$VERIFY_ROOT/best_direct/adapter/selected_plan.json"
cp "$FIXTURE_DIR/adapter/best_direct/selected_plan.json" "$VERIFY_ROOT/best_direct/adapter/best_direct/selected_plan.json"

run_mode() {
  local mode="$1"
  local output_dir="/workspace/A1Z/runtime/anygrasp_pick_attempt_modes_verify/${mode}"
  local host_dir="$VERIFY_ROOT/${mode}"
  local plan_path
  if [[ "$mode" == "adapter_selected" ]]; then
    plan_path="$output_dir/adapter/selected_plan.json"
  else
    plan_path="$output_dir/adapter/best_direct/selected_plan.json"
  fi

  mkdir -p "$host_dir/execute"

  "$ROOT_DIR/scripts/execute_a1z_plan_in_container.sh" \
    --plan "$plan_path" \
    --output "$output_dir/execute/execution_result.json" \
    --pre-open \
    --dry-run \
    --arm-speed 0.3 \
    --settle-s 0.01 >/dev/null

  python3 - <<PY
import json
from pathlib import Path

output_dir = Path(r"$host_dir")
execute_dir = output_dir / "execute"
payload = {
    "execution_mode": r"$mode",
    "selected_plan_path": r"$plan_path",
    "execution_result_path": "/workspace/A1Z/runtime/anygrasp_pick_attempt_modes_verify/" + r"$mode" + "/execute/execution_result.json",
}
(execute_dir / "execution_manifest.json").write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

result = json.loads((execute_dir / "execution_result.json").read_text(encoding="utf-8"))
status = {
    "execution_mode": r"$mode",
    "execution_plan_present": True,
    "execution_result_present": True,
    "execution_plan_path": r"$plan_path",
    "dry_run": bool(result.get("dry_run", False)),
    "success": bool(result.get("success", False)),
}
(output_dir / "pipeline_status.json").write_text(json.dumps(status, ensure_ascii=True, indent=2), encoding="utf-8")

manifest = {
    "execute": {
        "dir": str(execute_dir),
        "execution_mode": r"$mode",
        "selected_plan_json": r"$plan_path",
        "execution_result_json": str(execute_dir / "execution_result.json"),
        "execution_manifest_json": str(execute_dir / "execution_manifest.json"),
    },
    "summary": {
        "execution_mode": r"$mode",
    },
}
(output_dir / "pipeline_manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
PY
}

run_mode adapter_selected
run_mode best_direct

python3 - <<PY
import json
from pathlib import Path

root = Path(r"$VERIFY_ROOT")
for mode, expected_suffix in {
    "adapter_selected": "/adapter/selected_plan.json",
    "best_direct": "/adapter/best_direct/selected_plan.json",
}.items():
    mode_dir = root / mode
    result = json.loads((mode_dir / "execute" / "execution_result.json").read_text(encoding="utf-8"))
    manifest = json.loads((mode_dir / "execute" / "execution_manifest.json").read_text(encoding="utf-8"))
    pipeline_status = json.loads((mode_dir / "pipeline_status.json").read_text(encoding="utf-8"))
    pipeline_manifest = json.loads((mode_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))

    assert result["dry_run"] is True, (mode, result)
    assert result["success"] is True, (mode, result)
    assert manifest["execution_mode"] == mode, (mode, manifest)
    assert manifest["selected_plan_path"].endswith(expected_suffix), (mode, manifest)
    assert pipeline_status["execution_mode"] == mode, (mode, pipeline_status)
    assert pipeline_status["execution_plan_present"] is True, (mode, pipeline_status)
    assert pipeline_status["execution_result_present"] is True, (mode, pipeline_status)
    assert pipeline_status["execution_plan_path"].endswith(expected_suffix), (mode, pipeline_status)
    assert pipeline_manifest["execute"]["execution_mode"] == mode, (mode, pipeline_manifest)
    assert pipeline_manifest["execute"]["selected_plan_json"].endswith(expected_suffix), (mode, pipeline_manifest)
    assert pipeline_manifest["summary"]["execution_mode"] == mode, (mode, pipeline_manifest)

print("AnyGrasp pick-attempt execution-mode verification passed")
PY

echo "AnyGrasp pick-attempt execution-mode verification passed."
