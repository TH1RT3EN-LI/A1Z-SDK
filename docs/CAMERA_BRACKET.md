# A1Z camera bracket

The camera bracket is a fixed visual payload on `arm_link6`. It belongs to the
same rigid wrist tree as the gripper, but it is not parented to either moving
finger and therefore does not add a controllable degree of freedom.

## Authoritative pose

Edit only:

```text
config/camera_bracket.json
```

The current link6-local mount transform is:

```text
xyz = (0.06842, 0.0, 0.06546) m
orient = (-90.0, -90.0, 0.0) deg
```

This is the absolute Euler value shown by Isaac's `Orient` editor. Isaac
composes it as `Rz * Ry * Rx`; the fixed joint and link both use the equivalent
quaternion `(w, x, y, z) = (0.5, -0.5, -0.5, 0.5)`.
The generator converts this to the equivalent URDF fixed-axis
`rpy=(-90°, 0°, 90°)`; that derived triple is not a second pose input.

The imported `camera_bracket_link` deliberately keeps direct local
Translate/Orient/Scale xformOps instead of receiving the world-pose matrix used
for the other nested rigid bodies. Do not add a second `Rotate XYZ` operation:
it would be a separate transform and could override or compound the intended
Orient pose.

`scripts/prepare_a1z_urdfs.py` reads this file and writes the same fixed
`camera_bracket_mount_joint` into both the control and Isaac URDF variants.
There is intentionally no environment-variable override for this pose.

The mating D405 pose is defined separately in `config/d405.json`; see
`docs/D405_MOUNT.md`. Aligning the camera must not modify this bracket
transform.

## Geometry convention

The original CAD is stored as:

```text
assets/camera_bracket/camera_bracket.step
```

The simulation mesh is:

```text
assets/camera_bracket/camera_bracket.stl
```

The conversion centers the CAD bounds on X/Y and puts the lowest CAD Z point at
the mesh origin. Consequently, the JSON transform describes the lower-center
mounting datum rather than the arbitrary origin embedded in the STEP file. The
exact conversion translation, bounds, tolerances, and file hashes are recorded
in `assets/camera_bracket/camera_bracket.conversion.json`.

To regenerate the normalized STL when the STEP file changes:

```bash
${ISAAC_SIM_ROOT:-$HOME/isaacsim}/python.sh scripts/convert_camera_bracket_step.py
```

The converter requires the OpenCascade `OCP` Python bindings. They are a CAD
authoring dependency only; neither simulation nor robot control loads them.

## Rebuild and launch

Regenerate both URDF variants and import them into the project USD scene:

```bash
./scripts/rebuild_a1z_world.sh
```

Launch the local Isaac Sim GUI with the project world and end-effector drag
control:

```bash
./scripts/open_workstation_ee_drag.sh
```

Generate a headless RTX wrist preview:

```bash
${ISAAC_SIM_ROOT:-$HOME/isaacsim}/python.sh \
  scripts/render_camera_bracket_preview.py
```

The collision mesh is intentionally disabled until clearances are checked on
the physical assembly. The CAD volume is `24.3922 cm³`. The current mass,
center of mass, and inertia tensor use a uniform generic engineering-plastic
estimate of `1200 kg/m³`, giving `29.2707 g`. A broad `1000–1400 kg/m³`
material range gives `24.39–34.15 g`; both the assumption and range are stored
in `config/camera_bracket.json`. After weighing the bracket, scale all six
inertia values by `measured_mass / 0.029270651684159033`.
