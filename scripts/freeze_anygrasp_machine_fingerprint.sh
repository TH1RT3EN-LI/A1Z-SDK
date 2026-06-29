#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

OUTPUT_PATH="${1:-${A1Z_ANYGRASP_IFCONFIG_SNAPSHOT:-$ROOT_DIR/runtime/anygrasp/ifconfig.snapshot}}"
OUTPUT_DIR="$(dirname "$OUTPUT_PATH")"
FORCE_REFRESH="${A1Z_ANYGRASP_REFRESH_FINGERPRINT_SNAPSHOT:-0}"

mkdir -p "$OUTPUT_DIR"

if ! command -v ifconfig >/dev/null 2>&1; then
  echo "ifconfig not found on host; cannot freeze AnyGrasp machine fingerprint" >&2
  exit 1
fi

if [[ -f "$OUTPUT_PATH" && "$FORCE_REFRESH" != "1" ]]; then
  echo "AnyGrasp ifconfig snapshot exists, keeping pinned copy -> $OUTPUT_PATH"
  exit 0
fi

ifconfig -a >"$OUTPUT_PATH"

echo "AnyGrasp ifconfig snapshot -> $OUTPUT_PATH"
