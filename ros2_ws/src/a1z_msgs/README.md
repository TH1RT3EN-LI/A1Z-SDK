# a1z_msgs

ROS 2 interface package for the Docker-first A1Z motion stack.

The primary API is `a1z_msgs/action/MoveEndEffector`, which accepts a desired
tool pose expressed in `goal_pose.header.frame_id`.
