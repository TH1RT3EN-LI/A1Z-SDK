# A1Z task architecture

```text
sim D405 ──┐
           ├─ ROS RGB-D + TF ─ capture ─ VLM/SAM ─ AnyGrasp ─ planner ─ executor
real D405 ─┘                                                       │
                                                                  ▼
                                             common TCP control protocol
                                                    ┌─────────────┴────────────┐
                                               Isaac adapter          SocketCAN adapter
```

## Layer rules

1. Device adapters own Isaac, RealSense, SocketCAN, and motor-driver imports.
2. Acquisition writes one RGB-D observation artifact set: RGB, depth in
   metres, intrinsics, camera-to-base transform, metadata, and current joints.
3. Perception reads artifacts and writes target-mask and grasp candidates.
4. Planning reads candidates plus the captured robot state and writes a
   backend-neutral joint/grasp plan.
5. Execution knows only joint moves and the common grasp protocol.

The control server is the only component that selects `isaacsim` or
`socketcan`. The task pipeline is selected with `--profile`, which only changes
the device configuration and never changes task semantics.

## Grasp protocol

- `grasp_close(timeout_s)`: close and verify that an object is held.
- `grasp_status()`: report `phase`, `success`, and `object_detected`.
- `grasp_release(timeout_s)`: open and verify release.

Isaac uses its contact/force model internally. The physical adapter uses the
official gripper's motor-enforced torque limit and live jaw-position feedback.
Simulator prim paths and contact details are not part of the task protocol.

## AnyGrasp runtime boundary

AnyGrasp stays in the separate GPU vision container. Its pinned machine
fingerprint is stored at `runtime/anygrasp/ifconfig.snapshot`. When migrating,
copy the ignored `runtime/anygrasp/` snapshot and `runtime/licenses/anygrasp/`
license bundle with the deployment data. The repository mount makes them
available in the new container, and the pipeline exposes the snapshot through
a temporary `ifconfig` wrapper only while AnyGrasp runs. `runtime/` is ignored
so fingerprints, licenses, checkpoints, and captures are never committed.
Dockerfiles remain tracked.

The current AnyGrasp binary stack requires NVIDIA CUDA. An AMD integrated GPU
cannot run this container as configured; moving the vision stage to AMD would
require replacing or porting AnyGrasp rather than changing the robot adapter.
