# Script entry points

Primary commands:

- `run_pick_pipeline.py`: complete acquisition, VLM/SAM, AnyGrasp, planning,
  and optional execution workflow.
- `run_a1z_ros2_stack_in_container.sh`: profile-selected ROS camera and
  robot-state stack.
- `verify_a1z_socketcan_preflight_in_container.sh`: read-only physical
  hardware/container preflight.
- `a1zctl_in_container.sh`: start or query the control server.

Pipeline stages remain independently runnable:

- `capture_rgbd.py`
- `run_target_mask_pipeline.py`
- `run_anygrasp_from_selected_mask.py`
- `run_anygrasp_adapter.py` or `run_anygrasp_best_plan.py`
- `execute_a1z_plan.py`

All container helpers source `load_a1z_env.sh`. Set `A1Z_PROFILE=sim` or
`A1Z_PROFILE=real`; simulation is the safe default.
