#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

SDK_DIR="${1:-$ROOT_DIR/vendor/vision/anygrasp_sdk}"
RUNTIME_MODELS_DIR="${2:-$ROOT_DIR/runtime/models/anygrasp}"
RUNTIME_LICENSES_ROOT="${3:-$ROOT_DIR/runtime/licenses}"
RUNTIME_LICENSE_DIR="$RUNTIME_LICENSES_ROOT/anygrasp"
VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"

LICENSE_ZIP="$SDK_DIR/license_TianshunLi.zip"
DETECTION_CKPT_SRC="$SDK_DIR/checkpoint_detection.tar"
TRACKING_CKPT_SRC="$SDK_DIR/checkpoint_tracking.tar"

if [[ ! -d "$SDK_DIR" ]]; then
  echo "AnyGrasp SDK dir not found: $SDK_DIR" >&2
  exit 1
fi

if [[ ! -f "$LICENSE_ZIP" ]]; then
  echo "AnyGrasp license zip not found: $LICENSE_ZIP" >&2
  exit 1
fi

if [[ ! -f "$DETECTION_CKPT_SRC" ]]; then
  echo "AnyGrasp detection checkpoint not found: $DETECTION_CKPT_SRC" >&2
  exit 1
fi

if [[ ! -f "$TRACKING_CKPT_SRC" ]]; then
  echo "AnyGrasp tracking checkpoint not found: $TRACKING_CKPT_SRC" >&2
  exit 1
fi

mkdir -p "$RUNTIME_MODELS_DIR" "$RUNTIME_LICENSES_ROOT"

host_path_to_container_path() {
  local host_path="$1"
  if [[ "$host_path" == "$ROOT_DIR"* ]]; then
    printf '/workspace/A1Z%s\n' "${host_path#$ROOT_DIR}"
  fi
}

ensure_host_dir_writable() {
  local host_dir="$1"
  local container_dir

  if [[ ! -e "$host_dir" || -w "$host_dir" ]]; then
    return 0
  fi

  container_dir="$(host_path_to_container_path "$host_dir")"
  if [[ -z "$container_dir" ]]; then
    echo "Path is not writable and cannot be remapped into the vision container: $host_dir" >&2
    return 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required to repair permissions for $host_dir" >&2
    return 1
  fi

  if ! docker inspect "$VISION_CONTAINER_NAME" >/dev/null 2>&1; then
    echo "Vision container not found while repairing permissions for $host_dir: $VISION_CONTAINER_NAME" >&2
    return 1
  fi

  if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME")" != "true" ]]; then
    docker start "$VISION_CONTAINER_NAME" >/dev/null
  fi

  docker exec -u 0:0 "$VISION_CONTAINER_NAME" \
    bash -lc "chown -R $(id -u):$(id -g) '$container_dir'"
}

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

unzip -oq "$LICENSE_ZIP" -d "$tmp_dir"

license_src_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$license_src_dir" ]]; then
  echo "No license directory found after unzip: $LICENSE_ZIP" >&2
  exit 1
fi

ensure_host_dir_writable "$RUNTIME_LICENSE_DIR"
rm -rf "$RUNTIME_LICENSE_DIR"
mkdir -p "$RUNTIME_LICENSE_DIR"
cp -a "$license_src_dir"/. "$RUNTIME_LICENSE_DIR"/

relative_detection_ckpt="$(python3 - <<'PY' "$DETECTION_CKPT_SRC" "$RUNTIME_MODELS_DIR"
import os
import sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))
PY
)"
relative_tracking_ckpt="$(python3 - <<'PY' "$TRACKING_CKPT_SRC" "$RUNTIME_MODELS_DIR"
import os
import sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))
PY
)"

ln -sfn "$relative_detection_ckpt" "$RUNTIME_MODELS_DIR/checkpoint_detection.tar"
ln -sfn "$relative_tracking_ckpt" "$RUNTIME_MODELS_DIR/checkpoint_tracking.tar"

python3 - <<'PY' "$RUNTIME_LICENSE_DIR/licenseCfg.json"
import json
import sys
from pathlib import Path

license_cfg = Path(sys.argv[1])
payload = json.loads(license_cfg.read_text(encoding="utf-8"))
print("AnyGrasp license feature_id:", payload.get("feature_id", ""))
PY

printf 'Detection checkpoint -> %s\n' "$(readlink -f "$RUNTIME_MODELS_DIR/checkpoint_detection.tar")"
printf 'Tracking checkpoint  -> %s\n' "$(readlink -f "$RUNTIME_MODELS_DIR/checkpoint_tracking.tar")"
printf 'License dir          -> %s\n' "$RUNTIME_LICENSE_DIR"
