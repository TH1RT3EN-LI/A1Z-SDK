#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DRY_RUN=0
ARM_SPEED="${A1Z_EXEC_ARM_SPEED:-0.12}"
SETTLE_S="${A1Z_EXEC_SETTLE_S:-0.75}"

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
    -h|--help)
      cat <<'EOF'
usage: run_target_mask_to_economicgrasp_pick_attempt.sh [--dry-run] [--arm-speed <value>] [--settle-s <value>] '<instruction>' [output_dir] [provider]

One-shot pipeline:
  natural-language target -> ROS RGB-D capture -> target mask selection -> EconomicGrasp -> adapter -> execute selected plan

Examples:
  ./scripts/run_target_mask_to_economicgrasp_pick_attempt.sh "抓住笔"
  ./scripts/run_target_mask_to_economicgrasp_pick_attempt.sh --dry-run "抓住笔"
  ./scripts/run_target_mask_to_economicgrasp_pick_attempt.sh "抓住笔" /workspace/A1Z/runtime/economicgrasp_target_pick kimi
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
  echo "usage: $0 [--dry-run] [--arm-speed <value>] [--settle-s <value>] '<instruction>' [output_dir] [provider]" >&2
  exit 2
fi

RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${2:-/workspace/A1Z/runtime/economicgrasp_target_pick_attempt_${RUN_ID}}"
PROVIDER="${3:-kimi}"
EXEC_DIR="$OUTPUT_DIR/execute"

"$ROOT_DIR/scripts/run_target_mask_to_economicgrasp_from_ros.sh" \
  "$INSTRUCTION" \
  "$OUTPUT_DIR" \
  "$PROVIDER"

EXEC_ARGS=(
  --plan "$OUTPUT_DIR/adapter/selected_plan.json"
  --output "$EXEC_DIR/execution_result.json"
  --pre-open
  --arm-speed "$ARM_SPEED"
  --settle-s "$SETTLE_S"
)

if [[ "$DRY_RUN" == "1" ]]; then
  EXEC_ARGS+=(--dry-run)
fi

"$ROOT_DIR/scripts/execute_a1z_plan_in_container.sh" "${EXEC_ARGS[@]}"

echo "target-mask economicgrasp pick attempt output: $OUTPUT_DIR"
