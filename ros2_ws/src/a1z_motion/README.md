# a1z_motion

Docker-first ROS 2 motion integration for A1Z.

This package assumes:

- Isaac Sim runs in one Docker container and starts the A1Z socket server.
- A separate ROS 2 container runs this package and connects to the A1Z server
  over TCP via `A1Z_TCP_HOST` / `A1Z_TCP_PORT`.

Primary nodes:

- `a1z_robot_state`: publishes `/joint_states` and the minimal TF tree.
- `a1z_motion_executor`: exposes `/a1z/move_ee` as an action server.

Primary action:

- `a1z_msgs/action/MoveEndEffector`

The action goal pose may be expressed in `world_frame`, `robot_base_frame`, or
any frame already resolvable through TF.
