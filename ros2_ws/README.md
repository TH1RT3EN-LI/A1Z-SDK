# A1Z ROS 2 workspace

The ROS workspace is a device-integration layer:

- `a1z_motion` publishes live arm state/TF and exposes the optional motion
  action adapter.
- `a1z_d405` publishes Isaac D405 frames into the shared topic contract.
- the real profile launches the upstream `realsense2_camera` node instead.
- `a1z_msgs` contains the motion action definition.

Build and launch through the profile-aware host wrapper:

```bash
A1Z_PROFILE=sim ./scripts/run_a1z_ros2_stack_in_container.sh start
A1Z_PROFILE=real ./scripts/run_a1z_ros2_stack_in_container.sh start
```

The real profile defaults to `A1Z_CAMERA_MODE=auto`: the robot-state and
motion nodes can run without a D405, while RealSense and the camera console
bridge are started only when a USB 3.x D405 is detected. Use
`A1Z_CAMERA_MODE=on` to require it or `A1Z_CAMERA_MODE=off` to disable camera
nodes explicitly. Device re-enumeration does not require container recreation;
run the wrapper with `restart` or `ensure` after plugging or unplugging it.

Do not put VLM, segmentation, grasp detection, planning, or task orchestration
inside this workspace.
