# A1Z architecture worklog

## Capability map

| Capability | Implementation |
|---|---|
| Official arm/gripper driver | `vendor/GALAXEA-A1Z`, official `gripper` branch |
| Physical control | `SocketCANArmRobot` over Linux SocketCAN at 1 Mbit/s |
| Simulation control | `IsaacSimArmRobot` |
| Shared control protocol | `move`, `status`, `grasp_close`, `grasp_status`, `grasp_release` |
| RGB-D acquisition | ROS topic/TF contract consumed by `RosRGBDFrameSource` |
| Simulated camera adapter | Isaac D405 ROS publisher |
| Physical camera adapter | `realsense2_camera` D405 node |
| Target perception | VLM + SAM in the GPU vision container |
| Grasp perception | AnyGrasp in the GPU vision container |
| Planning | backend-neutral AnyGrasp adapter |
| Task orchestration | `scripts/run_pick_pipeline.py` |
| Camera-bracket STEP conversion and asset insertion | `usd-pipeline` |
| Camera-bracket placement from the link6 local bounds | `spatial-reasoning` |
| Camera-bracket fixed attachment in the robot tree | generated URDF fixed joint, routed by `isaac-sim-orchestrator` |
| Camera-bracket simulation QA | `isaac-sim-validator` |

## Supported boundary

The task layer consumes files and the shared control protocol. It does not
import Isaac, RealSense, SocketCAN, or vendor motor drivers. `config/sim.env`
and `config/real.env` select only device adapters.

Legacy Isaac 5 launchers, direct Isaac frame sources, synthetic frame sources,
simulated attachment commands, `physical_v2`, the old ROS VLM bridge, the old
GUI, and monolithic shell pipelines were deleted rather than retained as
compatibility paths.

## 2026-07-30 grasp-pipeline verification map

| Feature under test | Skill / acceptance |
|---|---|
| ROS environment, D405 topics, and TF capture | `isaac-sim-ros2-bridge`; matching UID/GID, writable `HOME`, nounset-safe setup sourcing |
| AnyGrasp-to-arm motion generation | `manipulation-ik`; selected plan contains pregrasp, grasp, lift, and retreat joint solutions |
| End-to-end simulation execution | `isaac-sim-orchestrator`; foundations pass before the combined `--execute` run |
| Final artifacts | `isaac-sim-validator`; reject missing plan/execution traces even if the wrapper exits successfully |

The requested acceptance target is generation and submission of the simulated
grasp action sequence. Object retention after gripper closure is informative
but is not required for this verification run.

## Upstream revision

The official SDK revision is recorded in `vendor/GALAXEA-A1Z_UPSTREAM`.

# A1Z real-control gravity compensation simulation

## Feature-to-skill mapping

- Existing A1Z USD/URDF asset and articulation loading: `isaac-sim-orchestrator`
- Gravity, articulation drives, effort control, and physics stepping: `physics-simulation`
- Headless script/output acceptance checks: `isaac-sim-validator`

## Requested experiment

Run the physical-arm control semantics in Isaac Sim and compare J4 behavior in:

1. gravity-compensation mode (`Kp=0`, `Kd=0.25`, URDF inverse-dynamics feedforward),
2. position-hold mode (`Kp=20`, `Kd=0.5`, same feedforward),
3. controlled J4 gravity under-compensation cases if the nominal model does not reproduce the physical droop.

Record joint positions, velocities, applied/model gravity torques, and J4 drift over time.

## Foundation checks

- [x] Runtime/GPU fingerprint: Isaac Sim 6.0.1 / Kit 110, RTX 5070 12 GB
- [x] A1Z stage and articulation assets exist at the configured project paths
- [x] Joint/body ordering and effort-control interface are implemented by the Isaac 6 adapter
- [x] Test harness explicitly selects PhysX, 250 Hz physics/control, gravity, and audits the fixed base
- [x] Result validation and machine-readable report

## Control-profile finding

The production Isaac profile is intentionally much stiffer than the physical SDK:

- physical position hold J4: `Kp=20`, `Kd=0.5`
- physical gravity mode J4: `Kp=0`, `Kd=0.25`
- default Isaac position hold J4: `Kp=150`, `Kd=16`
- default Isaac gravity mode J4 damping: `Kd=8`

The dedicated experiment overrides only its local robot instance with the physical
SDK gains. It leaves the production Isaac profile unchanged.

## Validated result

The production Physics USD was stale relative to the restored control URDF, so it
was rejected as a gravity-compensation baseline. An isolated robot USD was rebuilt
under `runtime/validation/a1z_j4_gravity/generated/`; its link masses match the
control URDF within `1e-6 kg`.

At `[0, 60, -60, 0, 0, 0] deg`, each case ran for 3 seconds at 250 Hz:

| Case | J4 drift | End-effector drop |
|---|---:|---:|
| nominal gravity compensation, factor 1.0 | +5.016 deg | 35.949 mm |
| gravity compensation, J4 factor 0.9 | +90.775 deg | 184.278 mm |
| gravity compensation, J4 factor 0.75 | +98.312 deg | 181.556 mm |
| position hold, J4 factor 0.75 | +1.456 deg | 4.807 mm |

All eight report checks pass, including PhysX activation, 250 Hz clock readback,
DOF order, URDF/USD mass agreement, non-black capture, and the expected relative
behavior of under-compensation versus position hold.

## Production mass synchronization and rerun

The production rebuild initially exposed a stale `A1Z_GRIPPER_FINGER_MASS_KG=0.02`
override in `config/sim.env`. It was removed so the generator preserves the official
`0.137868 kg` inertial for each finger, matching the control URDF, Isaac URDF, and
production Physics USD. A regression test now rejects this profile-level override.

The production `build/scenes/A1Z_G1Z_world.usd` was rebuilt and rerun at the same
250 Hz, 3-second test conditions. All 11 dynamic link masses match the control URDF
within `1e-6 kg`. The factor-1 case produced `+5.016 deg` J4 drift and `35.929 mm`
end-effector drop; the 75% J4 position-hold control produced `+1.482 deg` drift and
`4.842 mm` drop. The machine-readable report is under
`runtime/validation/a1z_j4_gravity/production_sync/`.

## arm_link6 CAD inertial restoration

A follow-up physical-validity audit found that the vendored `arm_link6` inertia was
positive definite but violated the principal-inertia triangle inequality. The URDF
generator now reads the traceable `arm_link6` mass, COM, and tensor directly from
`A1Z_nogripper.csv`; a contract test prevents both generated URDF variants from
returning to the invalid vendor tensor. The production USD was rebuilt and now has
`arm_link6` mass `0.42335647 kg` and principal inertias
`[0.0002880457, 0.00050818577, 0.0006302085] kg m^2`.

The post-fix production simulation passed all eight report checks. At the same pose,
the factor-1 initial J4 gravity torque became `-1.86902033 N m`; the 3-second J4 drift
was `+5.041 deg` with `36.596 mm` end-effector drop. The report is under
`runtime/validation/a1z_j4_gravity/link6_cad_fix/`.
