#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c "
import numpy as np
from a1z_ext.grasping import anygrasp_rotation_to_planner_rotation_with_binding_label

raw = np.array([
    [0.0, 0.0, 1.0],
    [1.0, 0.0, 0.0],
    [0.0, 0.8115343414514943, -0.5843047258450759],
], dtype=np.float64)
r0 = anygrasp_rotation_to_planner_rotation_with_binding_label(raw, binding_label='opening=c1,height=mc2,approach=c0')
r1 = anygrasp_rotation_to_planner_rotation_with_binding_label(raw, binding_label='opening=c2,height=mc1,approach=c0')

assert r0.shape == (3, 3), r0
assert r1.shape == (3, 3), r1
assert not np.allclose(r0, r1), (r0, r1)
print('AnyGrasp binding-config helper verification passed')
"

echo "AnyGrasp binding-config helper verification passed."
