#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${1:-$SCRIPT_DIR/raw/poly_pizza}"

mkdir -p "$OUT_DIR"

download_glb() {
  local asset_name="$1"
  local resource_id="$2"
  local url="https://static.poly.pizza/${resource_id}.glb"
  local out_path="$OUT_DIR/${asset_name}.glb"

  if [[ -f "$out_path" ]]; then
    echo "[skip] $asset_name -> $out_path"
    return 0
  fi

  echo "[get ] $asset_name"
  curl -L --fail --output "$out_path" "$url"
}

download_glb "can_crushed" "f8a372c6-3fb7-4446-b66d-a3723d9493f3"
download_glb "can_upright" "e16e13cf-fbc4-48c8-9927-ae34920a498e"
download_glb "bottle_plastic" "de99ad4e-faf0-478c-860e-7ea70d5a963e"
download_glb "bottle_water" "3ebef9a3-c2df-49ee-abe1-df38b5777bcd"
download_glb "paper_debris" "11eab449-ceb6-4d45-9151-bd4d1e288e56"

echo
echo "Done. Assets downloaded to:"
echo "  $OUT_DIR"
