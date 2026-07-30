#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"
EXCLUDED_EXTENSIONS=(
  "omni.kit.asset_converter"
  "omni.kit.tool.asset_importer"
  "omni.kit.tool.asset_exporter"
  "omni.services.convert.asset"
  "isaacsim.asset.importer.mjcf.ui"
  "isaacsim.asset.importer.urdf.ui"
  "omni.kit.converter.hoops"
  "omni.kit.converter.jt"
)

if [[ -x "/isaac-sim/python.sh" ]]; then
  ISAAC_PYTHON="/isaac-sim/python.sh"
elif [[ -x "${ISAAC_SIM_ROOT:-$HOME/isaacsim}/python.sh" ]]; then
  ISAAC_PYTHON="${ISAAC_SIM_ROOT:-$HOME/isaacsim}/python.sh"
else
  echo "Isaac Sim python.sh not found." >&2
  echo "Expected one of:" >&2
  echo "  /isaac-sim/python.sh" >&2
  echo "  ${ISAAC_SIM_ROOT:-$HOME/isaacsim}/python.sh" >&2
  echo "Set ISAAC_SIM_ROOT if your Isaac Sim is installed elsewhere." >&2
  exit 1
fi

# Rebuild flow:
# 1. Prepare derived URDF variants used by Isaac/SDK, including the fixed
#    camera-bracket and D405 wrist-camera chains under arm_link6.
# 2. Import the prepared Isaac URDF into USD and regenerate the robot/world USD assets.
python3 "$ROOT_DIR/scripts/prepare_a1z_urdfs.py"

IMPORT_ARGS=(
  "$ROOT_DIR/scripts/import_a1z_g1z_to_usd.py"
  "--rebuild-world"
  "--/exts/omni.services.facilities.monitoring.metrics/enabled=0"
)

for i in "${!EXCLUDED_EXTENSIONS[@]}"; do
  IMPORT_ARGS+=("--/app/extensions/excluded/$i=${EXCLUDED_EXTENSIONS[$i]}")
done

"$ISAAC_PYTHON" "${IMPORT_ARGS[@]}"
python3 "$ROOT_DIR/scripts/normalize_generated_usd_text.py"
