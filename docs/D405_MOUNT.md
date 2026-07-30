# D405 wrist mount

The D405 body, its rectified frame, both optical frames, and both USD camera
prims form one rigid subtree rooted at `d405_link`. The only mechanical pose
input is:

```text
config/d405.json
```

The current fixed transform from `arm_link6` to `d405_link` is:

```text
xyz = (0.065054390129681, 0.0, 0.083769274318288) m
rpy = (0.0, -10.395299107104066, 0.0) deg
```

This transform places the two D405 rear mounting-hole axes on the two holes in
the bracket's tilted upper section. The D405 rear surface normal is exactly
opposite the bracket lower-surface normal, so the two mating planes are
coincident. The bracket pose in `config/camera_bracket.json` is unchanged.

`body_visual_rpy_deg`, `stage_frames`, and `compute_frames` describe the
existing D405 mesh and optical-axis conventions. They are not additional
mechanical mount inputs. Both the URDF generator and runtime camera/TF code read
these values from the same JSON file; pose overrides through profile
environment files are intentionally unsupported.

The generator writes the fixed mount into both:

```text
build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf
build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf
```

The control URDF drives the true-robot FK and static camera TF. The Isaac URDF
drives the imported model. At runtime, `RectifiedFrame`, `DepthOpticalFrame`,
`ColorOpticalFrame`, `DepthCamera`, and `ColorCamera` are authored below the
imported `d405_link`, so they inherit every future mechanical mount change
without a second pose update.

Rebuild the generated robot and world assets after editing the config:

```bash
./scripts/rebuild_a1z_world.sh
```

Run the contract tests:

```bash
pytest -q tests/test_d405_mount_contract.py
```
