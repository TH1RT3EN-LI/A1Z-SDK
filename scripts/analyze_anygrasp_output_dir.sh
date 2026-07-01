#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PIPELINE_DIR="${1:-}"
if [[ -z "$PIPELINE_DIR" ]]; then
  echo "usage: $0 <pipeline_dir> [--observed-tool-delta-xyz '[dx,dy,dz]'] [--top-k N] [--output-dir DIR]" >&2
  exit 2
fi
shift

OBSERVED_TOOL_DELTA=""
TOP_K=3
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --observed-tool-delta-xyz)
      OBSERVED_TOOL_DELTA="${2:?missing value for --observed-tool-delta-xyz}"
      shift 2
      ;;
    --top-k)
      TOP_K="${2:?missing value for --top-k}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:?missing value for --output-dir}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

PIPELINE_DIR_HOST="$PIPELINE_DIR"
if [[ "$PIPELINE_DIR_HOST" == /workspace/A1Z/* ]]; then
  PIPELINE_DIR_HOST="$ROOT_DIR/${PIPELINE_DIR_HOST#/workspace/A1Z/}"
fi
if [[ ! -d "$PIPELINE_DIR_HOST" ]]; then
  echo "pipeline_dir not found: $PIPELINE_DIR" >&2
  exit 2
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR_HOST="$PIPELINE_DIR_HOST/analysis"
  OUTPUT_DIR_WS="/workspace/A1Z/${OUTPUT_DIR_HOST#$ROOT_DIR/}"
else
  OUTPUT_DIR_HOST="$OUTPUT_DIR"
  if [[ "$OUTPUT_DIR_HOST" == /workspace/A1Z/* ]]; then
    OUTPUT_DIR_HOST="$ROOT_DIR/${OUTPUT_DIR_HOST#/workspace/A1Z/}"
  fi
  OUTPUT_DIR_WS="/workspace/A1Z/${OUTPUT_DIR_HOST#$ROOT_DIR/}"
fi

PIPELINE_DIR_WS="/workspace/A1Z/${PIPELINE_DIR_HOST#$ROOT_DIR/}"

python3 "$ROOT_DIR/scripts/analyze_anygrasp_output_dir.py" \
  --pipeline-dir "$PIPELINE_DIR_HOST" \
  ${OBSERVED_TOOL_DELTA:+--observed-tool-delta-xyz "$OBSERVED_TOOL_DELTA"} \
  --top-k "$TOP_K" \
  --output-dir "$OUTPUT_DIR_HOST" >/dev/null

if [[ -n "$OBSERVED_TOOL_DELTA" ]]; then
  ARTIFACTS_JSON="$(python3 - <<PY
import json
from pathlib import Path
manifest = json.loads(Path(r"$PIPELINE_DIR_HOST/pipeline_manifest.json").read_text(encoding="utf-8"))
print(json.dumps({
    "alignment_report_json": manifest["adapter"].get("alignment_report_json", ""),
    "mapping_hypotheses_json": manifest["adapter"].get("mapping_hypotheses_json", ""),
}, ensure_ascii=True))
PY
)"
  MAPPING_HYPOTHESES_HOST="$(python3 - <<PY
import json
payload = json.loads(r'''$ARTIFACTS_JSON''')
print(payload.get("mapping_hypotheses_json", ""))
PY
)"
  ALIGNMENT_REPORT_HOST="$(python3 - <<PY
import json
payload = json.loads(r'''$ARTIFACTS_JSON''')
print(payload.get("alignment_report_json", ""))
PY
)"
  if [[ -n "$MAPPING_HYPOTHESES_HOST" ]]; then
    if [[ "$MAPPING_HYPOTHESES_HOST" == /workspace/A1Z/* ]]; then
      MAPPING_HYPOTHESES_WS="$MAPPING_HYPOTHESES_HOST"
    else
      MAPPING_HYPOTHESES_WS="/workspace/A1Z/${MAPPING_HYPOTHESES_HOST#$ROOT_DIR/}"
    fi
    "$ROOT_DIR/scripts/rank_anygrasp_binding_hypotheses_in_container.sh" \
      --mapping-hypotheses "$MAPPING_HYPOTHESES_WS" \
      --observed-tool-delta-xyz "$OBSERVED_TOOL_DELTA" \
      --top-k "$TOP_K" \
      --output "$OUTPUT_DIR_WS/binding_hypotheses.json" >/dev/null
  else
    if [[ "$ALIGNMENT_REPORT_HOST" == /workspace/A1Z/* ]]; then
      ALIGNMENT_REPORT_WS="$ALIGNMENT_REPORT_HOST"
    else
      ALIGNMENT_REPORT_WS="/workspace/A1Z/${ALIGNMENT_REPORT_HOST#$ROOT_DIR/}"
    fi
    "$ROOT_DIR/scripts/rank_anygrasp_binding_hypotheses_in_container.sh" \
      --alignment-report "$ALIGNMENT_REPORT_WS" \
      --observed-tool-delta-xyz "$OBSERVED_TOOL_DELTA" \
      --top-k "$TOP_K" \
      --output "$OUTPUT_DIR_WS/binding_hypotheses.json" >/dev/null
  fi
fi

echo "anygrasp analysis output: $OUTPUT_DIR_HOST"
