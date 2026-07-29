#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
VENV_PYTHON="${A1Z_SDK_VENV_DIR:-/home/ubuntu/.venvs/a1z-sdk}/bin/python"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "import os; import pinocchio as pin; import a1z; from a1z_ext.config import get_default_backend; from a1z_ext.robots.get_robot import _DEFAULT_URDF_PATH; control_urdf='/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf'; isaac_urdf='/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf'; [(_ for _ in ()).throw(SystemExit(f'Missing expected URDF: {p}')) for p in (control_urdf, isaac_urdf, _DEFAULT_URDF_PATH) if not os.path.isfile(p)]; control_model=pin.buildModelFromUrdf(control_urdf); isaac_model=pin.buildModelFromUrdf(isaac_urdf); assert (control_model.nq, control_model.nv)==(6,6), f'Unexpected control model DoF: nq={control_model.nq}, nv={control_model.nv}'; assert (isaac_model.nq, isaac_model.nv)==(8,8), f'Unexpected Isaac model DoF: nq={isaac_model.nq}, nv={isaac_model.nv}'; assert control_model.existFrame('d405_link'), 'Control URDF missing d405_link frame'; assert isaac_model.existFrame('d405_link'), 'Isaac URDF missing d405_link frame'; assert _DEFAULT_URDF_PATH==control_urdf, f'Extension default control URDF drifted: {_DEFAULT_URDF_PATH}'; print('a1z ok'); print(f'Extension default control URDF: {_DEFAULT_URDF_PATH}'); print(f'Default backend: {get_default_backend()}'); print(f'Control URDF DoF: nq={control_model.nq}, nv={control_model.nv}'); print(f'Isaac URDF DoF:   nq={isaac_model.nq}, nv={isaac_model.nv}')"

echo "Visible CAN interfaces in container:"
docker exec "$CONTAINER_NAME" bash -lc 'ip -o link show type can || true'

echo "SDK container verification passed."
