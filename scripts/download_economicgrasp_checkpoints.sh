#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

MODEL_ROOT="${A1Z_ECONOMICGRASP_MODEL_ROOT:-$ROOT_DIR/runtime/models/economicgrasp}"
if [[ "$MODEL_ROOT" == /workspace/A1Z/* ]]; then
  MODEL_ROOT="$ROOT_DIR/${MODEL_ROOT#/workspace/A1Z/}"
fi

mkdir -p "$MODEL_ROOT"

is_valid_checkpoint() {
  local checkpoint_path="$1"
  python3 - "$checkpoint_path" <<'PY'
import sys
import zipfile

path = sys.argv[1]
raise SystemExit(0 if zipfile.is_zipfile(path) else 1)
PY
}

get_remote_content_length() {
  local url="$1"
  wget --spider --server-response "$url" 2>&1 | awk 'BEGIN{IGNORECASE=1} /Content-Length:/ {size=$2} END{gsub("\r","",size); print size}'
}

download_checkpoint() {
  local camera="$1"
  local file_name="economicgrasp_${camera}.tar"
  local url="https://github.com/iSEE-Laboratory/EconomicGrasp/releases/download/v1/${file_name}"
  local output_path="$MODEL_ROOT/$file_name"
  local temp_path="${output_path}.part"
  local remote_size
  local actual_size

  if [[ -f "$output_path" ]]; then
    if is_valid_checkpoint "$output_path"; then
      echo "Checkpoint already exists and looks valid: $output_path"
      return 0
    fi
    echo "Checkpoint exists but is invalid, redownloading: $output_path" >&2
    rm -f "$output_path"
  fi

  remote_size="$(get_remote_content_length "$url")"
  if [[ -z "${remote_size:-}" ]] || ! [[ "$remote_size" =~ ^[0-9]+$ ]]; then
    echo "Failed to resolve remote Content-Length for $url" >&2
    exit 1
  fi

  if [[ -f "$temp_path" ]]; then
    actual_size="$(stat -c '%s' "$temp_path")"
    if (( actual_size > remote_size )); then
      echo "Removing oversized partial download: $temp_path" >&2
      rm -f "$temp_path"
    fi
  fi

  echo "Downloading $file_name ($remote_size bytes) to $temp_path"
  wget -c -O "$temp_path" "$url"

  actual_size="$(stat -c '%s' "$temp_path")"
  if (( actual_size != remote_size )); then
    echo "Downloaded checkpoint size mismatch for $file_name: expected $remote_size bytes, got $actual_size bytes" >&2
    exit 1
  fi

  if ! is_valid_checkpoint "$temp_path"; then
    echo "Downloaded checkpoint is invalid: $temp_path" >&2
    exit 1
  fi

  mv -f "$temp_path" "$output_path"
  if ! is_valid_checkpoint "$output_path"; then
    echo "Installed checkpoint is invalid after rename: $output_path" >&2
    exit 1
  fi

  echo "Checkpoint downloaded and verified: $output_path"
}

if [[ "$#" -eq 0 ]]; then
  set -- realsense kinect
fi

for camera in "$@"; do
  case "$camera" in
    realsense|kinect)
      download_checkpoint "$camera"
      ;;
    *)
      echo "Unsupported EconomicGrasp checkpoint target: $camera" >&2
      exit 2
      ;;
  esac
done
