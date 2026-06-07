#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"

"$ROOT_DIR/scripts/create_isaac_sim_dev_container.sh"
"$ROOT_DIR/scripts/extract_a1z_g1z.sh"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

docker exec -u ubuntu "$CONTAINER_NAME" /isaac-sim/python.sh -c "import isaacsim; print('isaacsim ok')"
docker exec -u ubuntu "$CONTAINER_NAME" /workspace/A1Z/scripts/rebuild_a1z_world.sh

echo "A1Z assets are ready in Isaac Sim."
echo "Container: $CONTAINER_NAME"
echo "World USD: /workspace/A1Z/build/scenes/A1Z_G1Z_world.usd"
