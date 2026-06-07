#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${A1Z_WORKSPACE_CONTAINER:-/workspace/A1Z}"

# Rebuild flow:
# 1. Prepare derived URDF variants used by Isaac/SDK, including the D405 wrist-camera
#    mechanical chain under arm_link6.
# 2. Import the prepared Isaac URDF into USD and regenerate the robot/world USD assets.
/isaac-sim/python.sh "$ROOT_DIR/scripts/prepare_a1z_urdfs.py"

/isaac-sim/python.sh \
  "$ROOT_DIR/scripts/import_a1z_g1z_to_usd.py"
