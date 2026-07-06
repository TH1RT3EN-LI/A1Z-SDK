#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DRY_RUN=0
ARM_SPEED="${A1Z_EXEC_ARM_SPEED:-0.3}"
SETTLE_S="${A1Z_EXEC_SETTLE_S:-0.05}"
EXECUTION_MODE="${A1Z_ANYGRASP_EXECUTION_MODE:-best_direct}"
BINDING_LABEL=""
CAMERA_CORRECTION_LABEL=""
EXTRINSIC_CORRECTION_LABEL=""
EE_GRASP_ORIGIN=""
EE_OPENING_AXIS=""
EE_APPROACH_AXIS=""
REQUIRE_CURRENT_JOINTS=0
TARGET_PRIM_PATH=""

POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --arm-speed)
      ARM_SPEED="${2:?missing value for --arm-speed}"
      shift 2
      ;;
    --settle-s)
      SETTLE_S="${2:?missing value for --settle-s}"
      shift 2
      ;;
    --execution-mode)
      EXECUTION_MODE="${2:?missing value for --execution-mode}"
      shift 2
      ;;
    --binding-label)
      BINDING_LABEL="${2:?missing value for --binding-label}"
      shift 2
      ;;
    --camera-correction-label)
      CAMERA_CORRECTION_LABEL="${2:?missing value for --camera-correction-label}"
      shift 2
      ;;
    --extrinsic-correction-label)
      EXTRINSIC_CORRECTION_LABEL="${2:?missing value for --extrinsic-correction-label}"
      shift 2
      ;;
    --ee-grasp-origin-xyz-m)
      EE_GRASP_ORIGIN="${2:?missing value for --ee-grasp-origin-xyz-m}"
      shift 2
      ;;
    --ee-opening-axis-xyz)
      EE_OPENING_AXIS="${2:?missing value for --ee-opening-axis-xyz}"
      shift 2
      ;;
    --ee-approach-axis-xyz)
      EE_APPROACH_AXIS="${2:?missing value for --ee-approach-axis-xyz}"
      shift 2
      ;;
    --require-current-joints)
      REQUIRE_CURRENT_JOINTS=1
      shift
      ;;
    --target-prim-path)
      TARGET_PRIM_PATH="${2:?missing value for --target-prim-path}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
usage: run_target_mask_to_anygrasp_pick_attempt.sh [--dry-run] [--arm-speed <value>] [--settle-s <value>] [--execution-mode <adapter_selected|best_direct>] [--binding-label <label>] [--camera-correction-label <label>] [--extrinsic-correction-label <label>] [--ee-grasp-origin-xyz-m <json>] [--ee-opening-axis-xyz <json>] [--ee-approach-axis-xyz <json>] [--require-current-joints] '<instruction>' [output_dir] [provider]

One-shot pipeline:
  natural-language target -> ROS RGB-D capture -> target mask selection -> AnyGrasp -> adapter/best-direct -> execute chosen plan
EOF
      exit 0
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}"

INSTRUCTION="${1:-}"
if [[ -z "$INSTRUCTION" ]]; then
  echo "usage: $0 [--dry-run] [--arm-speed <value>] [--settle-s <value>] [--execution-mode <adapter_selected|best_direct>] [--binding-label <label>] [--camera-correction-label <label>] [--extrinsic-correction-label <label>] [--ee-grasp-origin-xyz-m <json>] [--ee-opening-axis-xyz <json>] [--ee-approach-axis-xyz <json>] [--require-current-joints] [--target-prim-path <path>] '<instruction>' [output_dir] [provider]" >&2
  exit 2
fi

RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${2:-/workspace/A1Z/runtime/anygrasp_target_pick_attempt_${RUN_ID}}"
PROVIDER="${3:-kimi}"
EXEC_DIR="$OUTPUT_DIR/execute"
HOST_OUTPUT_DIR="$ROOT_DIR/${OUTPUT_DIR#/workspace/A1Z/}"

case "$EXECUTION_MODE" in
  adapter_selected)
    PLAN_PATH_WS="$OUTPUT_DIR/adapter/selected_plan.json"
    ;;
  best_direct)
    PLAN_PATH_WS="$OUTPUT_DIR/adapter/best_direct/selected_plan.json"
    ;;
  *)
    echo "error: unsupported --execution-mode '$EXECUTION_MODE' (expected adapter_selected or best_direct)" >&2
    exit 2
    ;;
esac

PIPELINE_ARGS=()
if [[ -n "$BINDING_LABEL" ]]; then
  PIPELINE_ARGS+=(--binding-label "$BINDING_LABEL")
fi
if [[ -n "$CAMERA_CORRECTION_LABEL" ]]; then
  PIPELINE_ARGS+=(--camera-correction-label "$CAMERA_CORRECTION_LABEL")
fi
if [[ -n "$EXTRINSIC_CORRECTION_LABEL" ]]; then
  PIPELINE_ARGS+=(--extrinsic-correction-label "$EXTRINSIC_CORRECTION_LABEL")
fi
if [[ -n "$EE_GRASP_ORIGIN" ]]; then
  PIPELINE_ARGS+=(--ee-grasp-origin-xyz-m "$EE_GRASP_ORIGIN")
fi
if [[ -n "$EE_OPENING_AXIS" ]]; then
  PIPELINE_ARGS+=(--ee-opening-axis-xyz "$EE_OPENING_AXIS")
fi
if [[ -n "$EE_APPROACH_AXIS" ]]; then
  PIPELINE_ARGS+=(--ee-approach-axis-xyz "$EE_APPROACH_AXIS")
fi
if [[ "$REQUIRE_CURRENT_JOINTS" == "1" ]]; then
  PIPELINE_ARGS+=(--require-current-joints)
fi

"$ROOT_DIR/scripts/run_target_mask_to_anygrasp_from_ros.sh" \
  "${PIPELINE_ARGS[@]}" \
  "$INSTRUCTION" \
  "$OUTPUT_DIR" \
  "$PROVIDER"

if [[ ! -f "$ROOT_DIR/${PLAN_PATH_WS#/workspace/A1Z/}" ]]; then
  echo "warning: no execution plan was produced for mode '$EXECUTION_MODE'; skipping execution stage" >&2
  exit 1
fi

EXEC_ARGS=(
  --plan "$PLAN_PATH_WS"
  --output "$EXEC_DIR/execution_result.json"
  --pre-open
  --arm-speed "$ARM_SPEED"
  --settle-s "$SETTLE_S"
)

if [[ "$DRY_RUN" == "1" ]]; then
  EXEC_ARGS+=(--dry-run)
fi

if [[ -n "$TARGET_PRIM_PATH" && -f "$ROOT_DIR/${PLAN_PATH_WS#/workspace/A1Z/}" ]]; then
  python3 - <<PY
import json
from pathlib import Path

plan_path = Path(r"$ROOT_DIR/${PLAN_PATH_WS#/workspace/A1Z/}")
plan = json.loads(plan_path.read_text(encoding="utf-8"))
policy = dict(plan.get("execution_policy", {}) or {})
policy["target_prim_path"] = r"$TARGET_PRIM_PATH"
plan["execution_policy"] = policy
plan_path.write_text(json.dumps(plan, ensure_ascii=True, indent=2), encoding="utf-8")
PY
fi

"$ROOT_DIR/scripts/execute_a1z_plan_in_container.sh" "${EXEC_ARGS[@]}"

mkdir -p "$HOST_OUTPUT_DIR/execute"
python3 - <<PY
import json
from pathlib import Path

output_dir = Path(r"$HOST_OUTPUT_DIR")
execute_dir = output_dir / "execute"
execute_dir.mkdir(parents=True, exist_ok=True)

payload = {
    "execution_mode": r"$EXECUTION_MODE",
    "selected_plan_path": r"$PLAN_PATH_WS",
    "execution_result_path": r"$OUTPUT_DIR/execute/execution_result.json",
}
(execute_dir / "execution_manifest.json").write_text(
    json.dumps(payload, ensure_ascii=True, indent=2),
    encoding="utf-8",
)

manifest_path = output_dir / "pipeline_manifest.json"
if manifest_path.is_file():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execute"] = {
        "dir": str(output_dir / "execute"),
        "execution_mode": r"$EXECUTION_MODE",
        "selected_plan_json": r"$PLAN_PATH_WS",
        "execution_result_json": str(output_dir / "execute" / "execution_result.json"),
        "execution_manifest_json": str(output_dir / "execute" / "execution_manifest.json"),
    }
    manifest["summary"]["execution_mode"] = r"$EXECUTION_MODE"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")

status_path = output_dir / "pipeline_status.json"
if status_path.is_file():
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["execution_mode"] = r"$EXECUTION_MODE"
    status["execution_plan_present"] = True
    status["execution_result_present"] = (output_dir / "execute" / "execution_result.json").is_file()
    status["execution_plan_path"] = r"$PLAN_PATH_WS"
    status_path.write_text(json.dumps(status, ensure_ascii=True, indent=2), encoding="utf-8")
PY

echo "target-mask anygrasp pick attempt output: $OUTPUT_DIR"
echo "execution mode: $EXECUTION_MODE"
