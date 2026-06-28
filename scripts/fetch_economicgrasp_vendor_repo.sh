#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VISION_VENDOR_DIR="$ROOT_DIR/vendor/vision"
ECONOMICGRASP_REPO_DIR="$VISION_VENDOR_DIR/EconomicGrasp"
ECONOMICGRASP_SHA="4119bdcd6bf5d3712a110f78ca87504dd359eec0"

mkdir -p "$VISION_VENDOR_DIR"

if [[ ! -d "$ECONOMICGRASP_REPO_DIR/.git" ]]; then
  git clone --depth 1 https://github.com/iSEE-Laboratory/EconomicGrasp.git "$ECONOMICGRASP_REPO_DIR"
fi

git -C "$ECONOMICGRASP_REPO_DIR" fetch --tags --depth 1 origin "$ECONOMICGRASP_SHA"
git -C "$ECONOMICGRASP_REPO_DIR" checkout "$ECONOMICGRASP_SHA"

echo "Pinned EconomicGrasp under $ECONOMICGRASP_REPO_DIR"
