#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

export A1Z_ISAAC_STARTUP_SCRIPT="${A1Z_ISAAC_STARTUP_SCRIPT:-/workspace/A1Z/scripts/open_a1z_world_with_a1z_sdk.py}"
export A1Z_EE_DRAG_TARGET_ENABLED=1
export A1Z_VIEWPORT_ENABLED=1
export A1Z_EE_TARGET_OFFSET_X_M="${A1Z_EE_TARGET_OFFSET_X_M:-0.08}"
export A1Z_EE_TARGET_OFFSET_Y_M="${A1Z_EE_TARGET_OFFSET_Y_M:--0.10}"
export A1Z_EE_TARGET_OFFSET_Z_M="${A1Z_EE_TARGET_OFFSET_Z_M:-0.05}"

exec "$ROOT_DIR/scripts/open_a1z_webrtc_host.sh" "$@"
