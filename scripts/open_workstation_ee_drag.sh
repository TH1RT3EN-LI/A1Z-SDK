#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAAC_SIM_ROOT="${ISAAC_SIM_ROOT:-$HOME/isaacsim}"
ISAAC_SIM_KIT="$ISAAC_SIM_ROOT/kit/kit"
ISAAC_SIM_APP="$ISAAC_SIM_ROOT/apps/isaacsim.exp.base.python.kit"
STARTUP_SCRIPT="$ROOT_DIR/scripts/open_a1z_world_with_a1z_sdk.py"
WORLD_USD="$ROOT_DIR/build/scenes/A1Z_G1Z_world.usd"
EXT_DIR="$ROOT_DIR/exts"
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

if [[ ! -x "$ISAAC_SIM_KIT" ]]; then
  echo "Isaac Sim kit binary not found or not executable: $ISAAC_SIM_KIT" >&2
  echo "Set ISAAC_SIM_ROOT to your Isaac Sim install directory if needed." >&2
  exit 1
fi

if [[ ! -f "$ISAAC_SIM_APP" ]]; then
  echo "Isaac Sim base app not found: $ISAAC_SIM_APP" >&2
  echo "Set ISAAC_SIM_ROOT to your Isaac Sim install directory if needed." >&2
  exit 1
fi

if [[ ! -f "$STARTUP_SCRIPT" ]]; then
  echo "Startup script not found: $STARTUP_SCRIPT" >&2
  exit 1
fi

if [[ ! -f "$WORLD_USD" ]]; then
  echo "World USD not found: $WORLD_USD" >&2
  exit 1
fi

cd "$ROOT_DIR"

export A1Z_EE_DRAG_TARGET_ENABLED="${A1Z_EE_DRAG_TARGET_ENABLED:-1}"
export A1Z_VIEWPORT_ENABLED="${A1Z_VIEWPORT_ENABLED:-1}"

CMD=(
  "$ISAAC_SIM_KIT"
  "$ISAAC_SIM_APP"
  --ext-folder "$EXT_DIR"
  --exec "$STARTUP_SCRIPT"
  --stage-path "$WORLD_USD"
)

for i in "${!EXCLUDED_EXTENSIONS[@]}"; do
  CMD+=("--/app/extensions/excluded/$i=${EXCLUDED_EXTENSIONS[$i]}")
done

CMD+=("--/exts/omni.services.facilities.monitoring.metrics/enabled=0")
CMD+=("--/app/extensions/registryEnabled=0")
CMD+=("--/app/extensions/precacheMode=0")
CMD+=("--/isaac/startup/ros_bridge_extension=")

CMD+=("$@")

exec "${CMD[@]}"
