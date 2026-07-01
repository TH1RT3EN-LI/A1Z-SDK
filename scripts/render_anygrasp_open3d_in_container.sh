#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "$ROOT_DIR/scripts/a1z_vision_python_in_container.sh" \
  /workspace/A1Z/scripts/render_anygrasp_open3d.py \
  "$@"
