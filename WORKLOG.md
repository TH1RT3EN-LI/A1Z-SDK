# A1Z Isaac Sim 6 force-closed-loop migration worklog

## Capability to skill mapping

| Capability | Skill / procedure |
|---|---|
| Isaac Sim 5.1 to 6.0.1 runtime migration and phased acceptance | `isaac-sim-orchestrator` version-migration gate |
| URDF import, generated USD composition, articulation schema | `urdf-mjcf-to-usd-conversion`, `usd-composition-architecture`, `usd-articulation` |
| Physics scene, rigid bodies, drives, contacts, constraint audit | `physics-simulation` |
| D405 RTX camera and coherent RGB-D capture | `isaac-camera`, `isaac-sim-sensor` |
| ROS 2 image transport and QoS | `isaac-sim-ros2-bridge` |
| Headless runtime acceptance | `isaac-sim-headless-deployment` |
| Final source/runtime/output validation | `isaac-sim-validator` |
| Host desktop launcher, operator workflow, and persistent status | `qt-ui-design` principles with the repository's dependency-free Tk runtime |
| Headed Isaac App lifecycle and native control routing | `isaac-sim-orchestrator`; existing A1Z TCP/ROS/AnyGrasp entry points |
| Live joint-drive diagnosis and response validation | `physics-simulation` closed-loop and joint-drive checks |

## Migration baseline

- Source contract: `docs/A1Z_ISAAC6_FORCE_CLOSED_LOOP_MIGRATION.md`.
- Reference implementation: sibling `../Paw/external/A1Z` and
  `../Paw/config/grasping/controllers/a1z_physical_gripper_v1.json`.
- Current GPU: NVIDIA GeForce RTX 5070, 12227 MiB.
- Repository has pre-existing uncommitted edits in:
  `a1z_ext/robots/get_robot.py`, `a1z_ext/robots/isaacsim_robot.py`, and
  `scripts/test_mock_grasp_attach_lifecycle.py`; preserve and integrate them.
- Known old endpoints and behavior to audit: TCP 18080, `/tmp/a1z.sock`,
  `grasp_attach`, temporary `FixedJoint`, kinematic/gravity mutation, joint-state
  teleport, synchronous D405 capture, deprecated/private Isaac APIs.
- Acceptance must distinguish pre-existing failures from migration regressions.

## Iteration log

- 2026-07-23: Read the migration contract, captured the runtime/GPU fingerprint,
  and recorded the dirty-worktree baseline before implementation.
- 2026-07-23: Added the A1Z-owned native Kit 110 adapter, physical grasp v2
  types/FSM/contact reducer/parallel-jaw mapping, server protocol, controller
  profile, AnyGrasp physical execution audit, and standalone/mounted configs.
- 2026-07-23: Migrated D405 to one native `CameraSensor` RGB-D generation,
  320x240 at 10 Hz, CUDA readback, zlib-1 worker encoding, latest-frame ROS
  publishing, sensor QoS, and monotonic timestamp suppression.
- 2026-07-23: Regenerated the source URDF and used the actual Isaac Sim 6.0.1
  `URDFImporter` plus Asset Transformer. Verified gripper ranges
  `0..0.048 m` / `-0.048..0 m`, 0.02 kg finger masses, max effort 120, and no
  target constraint in the generated USD.
- 2026-07-23: Added `validate_a1z_isaac6_runtime.py` and ran it in the pinned
  Isaac Sim 6.0.1 image on RTX 5070. Native articulation readback/live command,
  60 Hz callbacks, five dynamic TrashSet rigid bodies, zero target constraints,
  and two monotonic D405 RGB-D frames passed.
- 2026-07-23: Host contract suite passed 36 tests; ROS tools-container suite
  passed 60 tests; AnyGrasp active defaults and all execution-mode verifiers
  passed. The pre-migration system-Python mock import failure was caused by the
  missing NumPy dependency and was covered by the container rerun.
- 2026-07-23: Started a host GUI console lane. The console deliberately owns
  only its child process groups, launches the full host Isaac Sim App (no
  WebRTC), talks to the native A1Z TCP server, and delegates AnyGrasp/ROS work
  to the existing project scripts so there is no second physics-control path.
- 2026-07-23: Completed the host GUI console and headed-App acceptance. The
  full Isaac Sim 6.0.1 App exposed the native A1Z articulation, returned six
  joint positions plus gripper state, produced a coherent 320x240 D405 RGB-D
  frame, and exited with code 0 after the scoped A1Z stop request. Fixed the
  headed CameraSensor first-frame race by treating the initial Hydra AOV
  readback failure as warm-up and marking ready only after a valid RGB-D pair.
- 2026-07-23: Changed the general host-console EE drag target to opt-in. It is
  disabled by default in both the full-App launcher and generated host
  environment, and can be enabled for the next launch from the console.
- 2026-07-23: Began live diagnosis of the newly launched headed instance after
  joint commands appeared not to drive the articulation correctly. Preserve
  the running console's process ownership while comparing targets, measured
  state, joint order, live gains, physics cadence, and bounded joint response.
- 2026-07-23: Live readback showed loaded axes J2/J3 pinned at hard limits and
  J4-J6 far from their commanded targets while gravity-axis J1 tracked. Changed
  the arm position loop from acceleration semantics to torque-limited force
  drives, authoring the mode and per-degree USD gains before PhysX cooks the
  articulation, while retaining the independent acceleration-driven gripper.
- 2026-07-23: Re-launched the host full-App path with PhysX and verified live
  drive readback (`force` on J1-J6, `acceleration` on both gripper DOFs),
  gains `[240,280,240,150,42,48]`, and effort limits
  `[50,50,50,27,10,10] Nm`. Home settled within 1.25 degrees and salute within
  0.66 degrees across all six axes; blocking `move home` and `move wave_l`
  both returned `Arrived`.

## Remaining live acceptance

- The migration implementation and Isaac runtime/data-path acceptance are
  complete. A real `physical_v2` close -> preload -> holding -> lift -> release
  run remains site/scene dependent and must produce the executor acceptance JSON
  before force/friction calibration is declared complete.
