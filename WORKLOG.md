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
