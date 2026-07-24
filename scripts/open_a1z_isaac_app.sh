#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAAC_SIM_ROOT="${ISAAC_SIM_ROOT:-$HOME/isaacsim}"
WORLD_USD="${A1Z_WORLD_USD:-$ROOT_DIR/build/scenes/A1Z_G1Z_world.usd}"
STARTUP_SCRIPT="$ROOT_DIR/scripts/open_a1z_world_with_a1z_sdk.py"
EXT_DIR="$ROOT_DIR/exts"
EXTRA_ARGS=()
EXCLUDED_EXTENSIONS=(
  "omni.kit.asset_converter"
  "omni.kit.tool.asset_importer"
  "omni.kit.tool.asset_exporter"
  "omni.services.convert.asset"
  "isaacsim.asset.importer.mjcf.ui"
  "isaacsim.asset.importer.urdf.ui"
  "omni.kit.converter.hoops"
  "omni.kit.converter.jt"
  "omni.kit.converter.dgn"
  "omni.kit.converter.gsplat"
)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --isaac-sim-root)
      ISAAC_SIM_ROOT="${2:?missing value for --isaac-sim-root}"
      shift 2
      ;;
    --world-usd)
      WORLD_USD="${2:?missing value for --world-usd}"
      shift 2
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

ISAAC_SIM_LAUNCHER="$ISAAC_SIM_ROOT/isaac-sim.sh"
if [[ ! -x "$ISAAC_SIM_LAUNCHER" ]]; then
  echo "Isaac Sim App launcher not found or not executable: $ISAAC_SIM_LAUNCHER" >&2
  exit 1
fi
if [[ ! -f "$WORLD_USD" ]]; then
  echo "A1Z world USD not found: $WORLD_USD" >&2
  exit 1
fi
if [[ ! -f "$STARTUP_SCRIPT" ]]; then
  echo "A1Z startup script not found: $STARTUP_SCRIPT" >&2
  exit 1
fi

export A1Z_WORLD_USD="$WORLD_USD"
export A1Z_VIEWPORT_ENABLED="${A1Z_VIEWPORT_ENABLED:-1}"
export A1Z_EE_DRAG_TARGET_ENABLED="${A1Z_EE_DRAG_TARGET_ENABLED:-0}"

cd "$ROOT_DIR"
CMD=(
  "$ISAAC_SIM_LAUNCHER"
  --no-ros-env \
  --ext-folder "$EXT_DIR" \
  --exec "$STARTUP_SCRIPT" \
  --stage-path "$WORLD_USD" \
  --/app/extensions/registryEnabled=0 \
  --/app/extensions/precacheMode=0 \
  --/exts/isaacsim.core.simulation_manager/default_engine=physx \
  --/exts/isaacsim.physics.newton/auto_switch_on_startup=false \
  --/isaac/startup/ros_bridge_extension=
)
for i in "${!EXCLUDED_EXTENSIONS[@]}"; do
  CMD+=("--/app/extensions/excluded/$i=${EXCLUDED_EXTENSIONS[$i]}")
done
CMD+=("${EXTRA_ARGS[@]}")
exec "${CMD[@]}"
