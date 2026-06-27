#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
VENV_DIR="${A1Z_SDK_VENV_DIR:-/home/ubuntu/.venvs/a1z-sdk}"
SDK_DIR="${A1Z_SDK_DIR:-/workspace/A1Z/vendor/GALAXEA-A1Z}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

docker exec "$CONTAINER_NAME" bash -lc 'export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y iproute2 can-utils'

# Remove the SDK-related user-site packages we previously injected into Isaac Python.
docker exec -u ubuntu "$CONTAINER_NAME" bash -lc '
set -euo pipefail
SITE=/home/ubuntu/.local/lib/python3.11/site-packages
BIN=/home/ubuntu/.local/bin
if [[ -d "$SITE" ]]; then
  rm -rf \
    "$SITE"/a1z* \
    "$SITE"/can \
    "$SITE"/cmeel* \
    "$SITE"/coal* \
    "$SITE"/eigenpy* \
    "$SITE"/libcoal* \
    "$SITE"/libpinocchio* \
    "$SITE"/numpy \
    "$SITE"/numpy-*.dist-info \
    "$SITE"/numpy.libs \
    "$SITE"/packaging \
    "$SITE"/packaging-*.dist-info \
    "$SITE"/pin-*.dist-info \
    "$SITE"/python_can-*.dist-info
fi
if [[ -d "$BIN" ]]; then
  rm -f \
    "$BIN"/assimp \
    "$BIN"/binvox2bt \
    "$BIN"/bt2vrml \
    "$BIN"/can_bridge \
    "$BIN"/can_logconvert \
    "$BIN"/can_logger \
    "$BIN"/can_player \
    "$BIN"/can_viewer \
    "$BIN"/check_urdf \
    "$BIN"/cmeel \
    "$BIN"/compare_octrees \
    "$BIN"/convert_octree \
    "$BIN"/edit_octree \
    "$BIN"/eval_octree_accuracy \
    "$BIN"/f2py \
    "$BIN"/graph2tree \
    "$BIN"/log2graph \
    "$BIN"/numpy-config \
    "$BIN"/qconvex \
    "$BIN"/qdelaunay \
    "$BIN"/qhalf \
    "$BIN"/qhull \
    "$BIN"/qvoronoi \
    "$BIN"/rbox \
    "$BIN"/urdf_mem_test \
    "$BIN"/urdf_to_graphviz
fi
'

docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
set -euo pipefail
/isaac-sim/kit/python/bin/python3 -m venv '$VENV_DIR'
source '$VENV_DIR/bin/activate'
python -m pip install --upgrade pip
python -m pip install python-can pin
python -m pip install -e '$SDK_DIR'
"

echo "A1Z SDK venv is ready in $CONTAINER_NAME."
echo "Venv: $VENV_DIR"
echo "SDK path: $SDK_DIR"
echo "Workspace Python path: /workspace/A1Z"
echo "Use host wrappers in scripts/ to run the SDK without touching Isaac Python."
echo "Note: bring up SocketCAN on the host before using the real robot."
