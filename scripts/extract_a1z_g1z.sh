#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE_PATH="${1:-$ROOT_DIR/artifacts/A1Z_G1Z.zip}"
TARGET_ROOT="${2:-$ROOT_DIR/build/robot_packages}"
TARGET_DIR="$TARGET_ROOT/A1Z_G1Z"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Archive not found: $ARCHIVE_PATH" >&2
  exit 1
fi

mkdir -p "$TARGET_ROOT"
rm -rf "$TARGET_DIR"
unzip -q "$ARCHIVE_PATH" -d "$TARGET_ROOT"

if [[ ! -f "$TARGET_DIR/urdf/A1Z_G1Z.urdf" ]]; then
  echo "Extracted package is incomplete: $TARGET_DIR" >&2
  exit 1
fi

python3 "$ROOT_DIR/scripts/prepare_a1z_urdfs.py"

echo "Archive: $ARCHIVE_PATH"
echo "Extracted to: $TARGET_DIR"
