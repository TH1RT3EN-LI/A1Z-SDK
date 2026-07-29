"""SocketCAN hardware adapter for the upstream A1Z arm implementation."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict

from a1z.robots.arm_robot import ArmRobot


class SocketCANArmRobot(ArmRobot):
    """Add the backend-neutral grasp contract to the official hardware SDK.

    The upstream gripper already performs force-position hybrid control in the
    motor.  This adapter only waits for real position feedback and determines
    whether the jaws stopped on an object; it does not estimate contact force.
    """

    def __init__(
        self,
        *args: Any,
        gripper_max_torque_nm: float,
        empty_close_threshold: float = 0.04,
        feedback_tolerance: float = 0.01,
        stable_samples: int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._gripper_max_torque_nm = float(gripper_max_torque_nm)
        self._empty_close_threshold = float(empty_close_threshold)
        self._grasp_feedback_tolerance = float(feedback_tolerance)
        self._grasp_stable_samples = int(stable_samples)
        self._grasp_lock = threading.Lock()
        self._grasp_status: Dict[str, Any] = self._idle_grasp_status()

    def _idle_grasp_status(self) -> Dict[str, Any]:
        return {
            "backend": "socketcan",
            "phase": "idle",
            "success": False,
            "object_detected": False,
            "gripper_position": None,
            "force_limited": True,
            "torque_limit_nm": self._gripper_max_torque_nm,
            "failure_reason": None,
        }

    def get_robot_info(self) -> Dict[str, Any]:
        info = dict(super().get_robot_info())
        info.update(
            {
                "backend": "socketcan",
                "with_gripper": self.gripper is not None,
                "zero_gravity_mode": self.zero_gravity_mode,
                "control_mode": (
                    "gravity_comp_effort" if self.zero_gravity_mode else "position_hold"
                ),
                "gripper_torque_limit_nm": (
                    self._gripper_max_torque_nm if self.gripper is not None else None
                ),
            }
        )
        return info

    def _require_live_gripper_feedback(self) -> float:
        if not self.is_running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self.gripper is None:
            raise RuntimeError("No gripper attached. Start with --with-gripper.")
        if self.is_estopped:
            raise RuntimeError("Robot is in estop.")
        if self.gripper._motor.last_feedback is None:
            raise RuntimeError("No live gripper CAN feedback is available.")
        return float(self.gripper.get_feedback_norm())

    def grasp_close(self, *, timeout_s: float = 5.0) -> Dict[str, Any]:
        """Close with the configured hardware torque limit and detect an object."""

        timeout = float(timeout_s)
        if timeout <= 0.0:
            raise ValueError("timeout_s must be positive")
        initial_position = self._require_live_gripper_feedback()
        self.command_gripper(0.0)
        deadline = time.monotonic() + timeout
        last_position = initial_position
        stable_count = 0
        movement_seen = False

        while time.monotonic() < deadline:
            time.sleep(0.02)
            position = self._require_live_gripper_feedback()
            if position < initial_position - self._grasp_feedback_tolerance:
                movement_seen = True
            if movement_seen and abs(position - last_position) <= self._grasp_feedback_tolerance:
                stable_count += 1
            else:
                stable_count = 0
            last_position = position
            if stable_count < self._grasp_stable_samples:
                continue

            object_detected = position > self._empty_close_threshold
            status = {
                "backend": "socketcan",
                "phase": "holding" if object_detected else "empty",
                "success": object_detected,
                "object_detected": object_detected,
                "gripper_position": position,
                "initial_gripper_position": initial_position,
                "force_limited": True,
                "torque_limit_nm": self._gripper_max_torque_nm,
                "stable_samples": stable_count,
                "failure_reason": None if object_detected else "no_object_detected",
            }
            with self._grasp_lock:
                self._grasp_status = status
            return dict(status)

        status = {
            "backend": "socketcan",
            "phase": "failed",
            "success": False,
            "object_detected": False,
            "gripper_position": last_position,
            "initial_gripper_position": initial_position,
            "force_limited": True,
            "torque_limit_nm": self._gripper_max_torque_nm,
            "stable_samples": stable_count,
            "failure_reason": "gripper_close_timeout",
        }
        with self._grasp_lock:
            self._grasp_status = status
        return dict(status)

    def grasp_release(self, *, timeout_s: float = 3.0) -> Dict[str, Any]:
        """Open the jaws and wait for live position feedback."""

        timeout = float(timeout_s)
        if timeout <= 0.0:
            raise ValueError("timeout_s must be positive")
        self._require_live_gripper_feedback()
        self.command_gripper(1.0)
        deadline = time.monotonic() + timeout
        last_position = 0.0
        while time.monotonic() < deadline:
            time.sleep(0.02)
            last_position = self._require_live_gripper_feedback()
            if last_position >= 0.95:
                status = {
                    "backend": "socketcan",
                    "phase": "released",
                    "success": True,
                    "object_detected": False,
                    "gripper_position": last_position,
                    "force_limited": True,
                    "torque_limit_nm": self._gripper_max_torque_nm,
                    "failure_reason": None,
                }
                with self._grasp_lock:
                    self._grasp_status = status
                return dict(status)

        status = {
            "backend": "socketcan",
            "phase": "failed",
            "success": False,
            "object_detected": False,
            "gripper_position": last_position,
            "force_limited": True,
            "torque_limit_nm": self._gripper_max_torque_nm,
            "failure_reason": "gripper_release_timeout",
        }
        with self._grasp_lock:
            self._grasp_status = status
        return dict(status)

    def get_grasp_status(self) -> Dict[str, Any]:
        with self._grasp_lock:
            status = dict(self._grasp_status)
        if self.gripper is not None and self.gripper._motor.last_feedback is not None:
            current_position = float(self.gripper.get_feedback_norm())
            held_position = status.get("gripper_position")
            status["gripper_position"] = current_position
            if (
                status.get("phase") == "holding"
                and isinstance(held_position, (int, float))
                and current_position
                < max(self._empty_close_threshold, float(held_position) - 0.08)
            ):
                status.update(
                    {
                        "phase": "lost",
                        "success": False,
                        "object_detected": False,
                        "failure_reason": "object_lost",
                    }
                )
                with self._grasp_lock:
                    self._grasp_status = dict(status)
        status["estopped"] = self.is_estopped
        return status
