# AnyGrasp TCP Mapping Update (2026-07-04)

## What changed

The active AnyGrasp-to-TCP mapping was updated to:

- `grasp_tcp` fixed offset from `arm_link6`: `[0.08, 0.0, 0.0]`
- `ee_grasp_origin_xyz_m = [0.0, 0.0, 0.0]`
- `ee_opening_axis_xyz = [0.0, 1.0, 0.0]`
- `ee_approach_axis_xyz = [1.0, 0.0, 0.0]`
- active AnyGrasp binding remains `opening=c1,height=c2,approach=c0`

## Resulting TCP semantics

With the adapter's `ee_to_grasp_transform` convention:

- grasp-frame `opening` maps to TCP `+y`
- grasp-frame `height` maps to TCP `+z`
- grasp-frame `approach` maps to TCP `+x`

So the effective target TCP interpretation is:

- `tcp_x = approach`
- `tcp_y = opening`
- `tcp_z = height`

## Why this was selected

For the latest runtime under `runtime/anygrasp_target_pick_attempt_20260704_130502`, this mapping produced the most promising wrist result among the tested legal axis/sign combinations:

- target pregrasp TCP axes in `base_link`:
  - `tcp_x = [0.586963, 0.155846, -0.794473]`
  - `tcp_y = [0.781744, 0.146160, 0.606230]`
  - `tcp_z = [0.210598, -0.976908, -0.036041]`
- pregrasp IK wrist result:
  - `J4 = 20.43`
  - `J5 = 12.05`
  - `J6 = 76.90`

This was the closest tested legal mapping to the observed wrist posture, especially on `J5/J6`.

## Scope

The update changes default semantics for:

- adapter config defaults
- container environment defaults
- AnyGrasp-related script defaults
- verification expectations

It does not solve remaining issues such as:

- possible `J3/J5` sign-semantic mismatch between SDK and URDF/IK
- possible additional roll freedom around `approach`
- final real-robot TCP calibration beyond the current `0.08 m` offset

## Current pregrasp default

The current default `pregrasp_offset_m` should be treated separately from TCP semantics.

- active default `pregrasp_offset_m = 0.15`

This is intentionally conservative. Based on the current URDF + finger mesh geometry,
the finger bodies extend about `0.103 m` ahead of `grasp_tcp` along TCP `+x`, so `0.15 m`
leaves additional clearance before the grasp target plane.
