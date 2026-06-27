"""ROS 2 action server for end-effector IK execution on top of the A1Z socket API."""

from __future__ import annotations

from typing import Optional

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.node import Node
from tf2_geometry_msgs import do_transform_pose_stamped
from tf2_ros import Buffer, TransformException, TransformListener

from a1z_msgs.action import MoveEndEffector

from .config import load_motion_config
from .kinematics_bridge import KinematicsBridge
from .socket_client import A1ZSocketClient
from .transforms import (
    matrix_to_pose_stamped,
    orientation_error_rad,
    pose_to_matrix,
    transform_stamped_to_matrix,
)


class A1ZMotionExecutor(Node):
    def __init__(self) -> None:
        super().__init__("a1z_motion_executor")
        self._cfg = load_motion_config()
        self._client = A1ZSocketClient(
            tcp_host=self._cfg.tcp_host,
            tcp_port=self._cfg.tcp_port,
        )
        self._kinematics = KinematicsBridge(self._cfg)
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._action_server = ActionServer(
            self,
            MoveEndEffector,
            "/a1z/move_ee",
            execute_callback=self._execute_callback,
            goal_callback=self._goal_callback,
            cancel_callback=self._cancel_callback,
        )

    def destroy_node(self) -> bool:
        self._action_server.destroy()
        return super().destroy_node()

    def _goal_callback(self, _goal_request: MoveEndEffector.Goal) -> GoalResponse:
        return GoalResponse.ACCEPT

    def _cancel_callback(self, _goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    def _publish_feedback(self, goal_handle, stage: str, message: str) -> None:
        feedback = MoveEndEffector.Feedback()
        feedback.stage = stage
        feedback.message = message
        goal_handle.publish_feedback(feedback)

    def _current_joint_state(self) -> tuple[np.ndarray, dict]:
        status = self._client.call("status")
        joint_deg = status.get("pos_deg", [])
        if len(joint_deg) < 6:
            raise RuntimeError(f"Unexpected status payload: {status}")
        return np.deg2rad(np.asarray(joint_deg[:6], dtype=np.float64)), status

    def _info(self) -> dict:
        return self._client.call("info")

    def _resolve_goal_pose(self, goal_pose: PoseStamped) -> PoseStamped:
        if goal_pose.header.frame_id == self._cfg.robot_base_frame:
            return goal_pose
        transform = self._tf_buffer.lookup_transform(
            self._cfg.robot_base_frame,
            goal_pose.header.frame_id,
            rclpy.time.Time(),
        )
        return do_transform_pose_stamped(goal_pose, transform)

    def _apply_constraints(
        self,
        *,
        current_q: np.ndarray,
        target_q: np.ndarray,
        joint_margin_rad: float,
        max_joint_step_rad: float,
    ) -> None:
        lower = self._kinematics.joint_lower_limits + joint_margin_rad
        upper = self._kinematics.joint_upper_limits - joint_margin_rad
        if np.any(target_q < lower) or np.any(target_q > upper):
            raise RuntimeError(
                "IK solution violates joint margin constraints "
                f"(deg={np.rad2deg(target_q).round(2).tolist()})"
            )
        max_step = float(np.max(np.abs(target_q - current_q)))
        if max_joint_step_rad > 0.0 and max_step > max_joint_step_rad:
            raise RuntimeError(
                f"IK solution exceeds max_joint_step_rad: {max_step:.4f} > {max_joint_step_rad:.4f}"
            )

    async def _execute_callback(self, goal_handle) -> MoveEndEffector.Result:
        goal = goal_handle.request
        result = MoveEndEffector.Result()
        try:
            self._publish_feedback(goal_handle, "task_received", "received end-effector target")
            target_pose = self._resolve_goal_pose(goal.goal_pose)
            self._publish_feedback(goal_handle, "tf_resolved", "goal pose transformed into robot_base_frame")

            if target_pose.pose.position.z < goal.min_target_z_m or target_pose.pose.position.z > goal.max_target_z_m:
                raise RuntimeError(
                    f"Target z out of bounds: {target_pose.pose.position.z:.4f} not in "
                    f"[{goal.min_target_z_m:.4f}, {goal.max_target_z_m:.4f}]"
                )

            current_q, status = self._current_joint_state()
            current_tool_pose = self._kinematics.fk(current_q, frame_name=self._cfg.tool_link_frame)
            target_matrix = pose_to_matrix(target_pose)

            if np.linalg.norm(
                np.array(
                    [
                        target_pose.pose.orientation.x,
                        target_pose.pose.orientation.y,
                        target_pose.pose.orientation.z,
                        target_pose.pose.orientation.w,
                    ],
                    dtype=np.float64,
                )
            ) < 1e-8:
                target_matrix[:3, :3] = current_tool_pose[:3, :3]

            self._publish_feedback(goal_handle, "ik_started", "solving IK")
            converged, target_q = self._kinematics.ik(
                target_matrix,
                init_q=current_q,
                frame_name=self._cfg.tool_link_frame,
                max_iters=300,
                dt=0.1,
                damping=1e-6,
                pos_threshold=max(1e-4, goal.position_tolerance_m * 0.5),
                ori_threshold=max(1e-3, goal.orientation_tolerance_rad * 0.5),
            )
            result.ik_converged = bool(converged)
            if not converged:
                raise RuntimeError("IK did not converge")

            self._apply_constraints(
                current_q=current_q,
                target_q=target_q,
                joint_margin_rad=float(goal.joint_margin_rad),
                max_joint_step_rad=float(goal.max_joint_step_rad),
            )

            self._publish_feedback(goal_handle, "move_started", "sending joint-space motion")
            self._client.call(
                "move",
                {
                    "joints": [float(v) for v in np.rad2deg(target_q).tolist()],
                    "speed": float(goal.speed),
                },
            )

            if goal.command_gripper:
                self._publish_feedback(goal_handle, "gripper_commanded", "commanding gripper")
                self._client.call("gripper", {"value": float(goal.gripper_opening)})

            final_q, final_status = self._current_joint_state()
            final_tool_pose = self._kinematics.fk(final_q, frame_name=self._cfg.tool_link_frame)
            final_pose_msg = matrix_to_pose_stamped(
                final_tool_pose,
                frame_id=self._cfg.robot_base_frame,
                stamp=self.get_clock().now().to_msg(),
            )
            pos_error = float(np.linalg.norm(final_tool_pose[:3, 3] - target_matrix[:3, 3]))
            ori_error = float(orientation_error_rad(final_tool_pose[:3, :3], target_matrix[:3, :3]))

            result.success = True
            result.status = "success"
            result.failure_reason = ""
            result.final_joint_positions_rad = [float(v) for v in final_q.tolist()]
            result.final_pose = final_pose_msg
            result.final_gripper_opening = float(final_status.get("gripper", 0.0) or 0.0)
            result.position_error_m = pos_error
            result.orientation_error_rad = ori_error
            goal_handle.succeed()
            self._publish_feedback(goal_handle, "task_completed", "motion finished")
            return result
        except TransformException as exc:
            result.success = False
            result.status = "failed"
            result.failure_reason = f"TF resolution failed: {exc}"
        except Exception as exc:
            result.success = False
            result.status = "failed"
            result.failure_reason = str(exc)

        goal_handle.abort()
        return result


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    node = A1ZMotionExecutor()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
