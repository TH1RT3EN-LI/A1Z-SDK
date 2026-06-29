#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VISION_VENDOR_DIR="$ROOT_DIR/vendor/vision"

mkdir -p "$VISION_VENDOR_DIR"

clone_and_pin() {
  local url="$1"
  local path="$2"
  local sha="$3"

  if [[ ! -d "$path/.git" ]]; then
    git clone --depth 1 "$url" "$path"
  fi

  git -C "$path" fetch --tags --depth 1 origin "$sha"
  git -C "$path" checkout "$sha"
}

clone_and_pin \
  "https://github.com/facebookresearch/sam2.git" \
  "$VISION_VENDOR_DIR/sam2" \
  "2b90b9f5ceec907a1c18123530e92e794ad901a4"

clone_and_pin \
  "https://github.com/facebookresearch/sam3.git" \
  "$VISION_VENDOR_DIR/sam3" \
  "5dd401d1c5c1d5c3eedff06d41b77af824517619"

clone_and_pin \
  "https://github.com/graspnet/anygrasp_sdk.git" \
  "$VISION_VENDOR_DIR/anygrasp_sdk" \
  "554fc2410c57b3c02b99b970bd7239b0d2db26d5"

echo "Pinned vision vendor repos under $VISION_VENDOR_DIR"
