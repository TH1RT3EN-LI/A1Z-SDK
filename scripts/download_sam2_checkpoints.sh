#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

MODEL_ROOT="${A1Z_VISION_MODEL_ROOT:-/workspace/A1Z/runtime/models}"
MODEL_ROOT="${MODEL_ROOT/\/workspace\/A1Z/$ROOT_DIR}"
SAM2_DIR="$MODEL_ROOT/sam2"

mkdir -p "$SAM2_DIR"

if [[ "$#" -eq 0 ]]; then
  set -- small tiny
fi

download_variant() {
  local variant="$1"
  local filename
  local url

  case "$variant" in
    tiny)
      filename="sam2.1_hiera_tiny.pt"
      ;;
    small)
      filename="sam2.1_hiera_small.pt"
      ;;
    base_plus)
      filename="sam2.1_hiera_base_plus.pt"
      ;;
    large)
      filename="sam2.1_hiera_large.pt"
      ;;
    *)
      echo "Unsupported SAM2 variant: $variant" >&2
      exit 1
      ;;
  esac

  url="https://dl.fbaipublicfiles.com/segment_anything_2/092824/$filename"
  if [[ -f "$SAM2_DIR/$filename" ]]; then
    echo "Checkpoint already exists: $SAM2_DIR/$filename"
    return
  fi

  curl -L --fail --output "$SAM2_DIR/$filename" "$url"
}

for variant in "$@"; do
  download_variant "$variant"
done
