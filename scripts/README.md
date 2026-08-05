# Script entry points

Primary commands:

- `run_pick_pipeline.py`: complete acquisition, VLM/SAM, AnyGrasp, planning,
  and optional execution workflow.
- `run_a1z_ros2_stack_in_container.sh`: profile-selected ROS robot-state stack
  with `A1Z_CAMERA_MODE=auto|on|off` camera lifecycle control.
- `verify_a1z_socketcan_preflight_in_container.sh`: read-only physical
  hardware/container preflight.
- `a1zctl_in_container.sh`: start or query the control server.
- `configure_remote_gpu_client.sh`: write the ignored laptop-side SSH GPU
  configuration.
- `run_remote_vision_job.py`: preflight or submit one physical RGB-D vision
  job without running planning/execution.
- `a1z_remote_gpu_worker.py`: GPU-host stdin/stdout worker invoked over SSH.

Pipeline stages remain independently runnable:

- `capture_rgbd.py`
- `run_target_mask_pipeline.py`
- `run_anygrasp_from_selected_mask.py`
- `run_anygrasp_adapter.py` or `run_anygrasp_best_plan.py`
- `execute_a1z_plan.py`

All container helpers source `load_a1z_env.sh`. Set `A1Z_PROFILE=sim` or
`A1Z_PROFILE=real`; simulation is the safe default.

The real profile sets `A1Z_CAN_INTER_COMMAND_DELAY_S=0.0001`. The SocketCAN
robot factory uses this delay between adjacent official SDK MIT frames to work
around the documented `gs_usb`/CAN-box burst compatibility fault. Set it to
zero only after validating the official kernel/driver fix or a replacement CAN
adapter; feedback freshness limits remain unchanged.

Remote GPU offload is restricted to `A1Z_PROFILE=real`; see
[`docs/REMOTE_GPU.md`](../docs/REMOTE_GPU.md).
