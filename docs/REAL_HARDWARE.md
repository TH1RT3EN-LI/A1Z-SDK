# Physical A1Z bring-up

## Required hardware

- GALAXEA A1Z/G1Z arm with gripper.
- Linux SocketCAN adapter exposed as `can0`, configured for 1 Mbit/s.
- Intel RealSense D405 connected over USB 3.
- Emergency stop and a clear robot workspace.

The official SDK uses motor CAN IDs 1–6 and gripper ID 7. The repository tracks
the official `gripper` branch revision in `vendor/GALAXEA-A1Z_UPSTREAM`.
The SDK soft-stop latch is exposed as `a1zctl estop`; resume only with an
intentional `a1zctl estop-release`. This does not replace a physical emergency
stop or power disconnect.

## Container boundary

The real ROS container uses host networking for SocketCAN visibility, mounts
`/dev/bus/usb`, grants USB character devices (`major 189`), and has
`NET_ADMIN` for explicit CAN setup. These permissions are added only by the
`real` profile.

The image includes `python3-can`, `iproute2`, `can-utils`, and
`ros-humble-realsense2-camera`.

## Safe acceptance order

1. Run `A1Z_PROFILE=real ./scripts/verify_a1z_socketcan_preflight_in_container.sh`.
2. Confirm passive CAN traffic and D405 enumeration.
3. Start `A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh serve`.
4. Confirm `a1zctl status` and `a1zctl info`.
5. Run `run_pick_pipeline.py --profile real ...` without `--execute`.
6. Inspect `capture/`, target selection, AnyGrasp result, and
   `planning/selected_plan.json`.
7. Run once with `--execute --dry-run`.
8. Record the measured hand-eye transform in the D405 mount values in
   `config/real.env`, regenerate the robot description with
   `python3 scripts/prepare_a1z_urdfs.py --env-file config/real.env`, validate
   camera-to-base projection, and set
   `A1Z_HAND_EYE_CALIBRATION_STATUS=verified`.
9. Only then perform a supervised `--execute` run.

No powered-arm motion was used for repository validation; final joint signs,
camera hand-eye calibration, gripper empty-close threshold, and safe poses must
be verified on the target robot.

Target perception and AnyGrasp may run on a separate NVIDIA host while every
artifact, plan, and execution record stays on this machine. Configure that
optional real-only deployment using [`REMOTE_GPU.md`](REMOTE_GPU.md).
