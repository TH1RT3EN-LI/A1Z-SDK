"""Pinocchio-backed FK/IK utilities for ROS 2 motion execution."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from .config import MotionConfig


class KinematicsBridge:
    def __init__(self, config: MotionConfig) -> None:
        if str(config.repo_root) not in sys.path:
            sys.path.insert(0, str(config.repo_root))
        if str(config.sdk_root) not in sys.path:
            sys.path.insert(0, str(config.sdk_root))
        from a1z.robots.kinematics import Kinematics
        import pinocchio

        self._pinocchio = pinocchio
        self._kinematics = Kinematics(str(Path(config.control_urdf)), end_effector_frame=config.tool_link_frame)
        self._model = self._kinematics._model
        self._data = self._kinematics._data
        self._tool_link_frame = config.tool_link_frame
        self._d405_link_frame = config.d405_link_frame

    @property
    def joint_lower_limits(self) -> np.ndarray:
        return np.asarray(self._model.lowerPositionLimit, dtype=np.float64).reshape(-1)

    @property
    def joint_upper_limits(self) -> np.ndarray:
        return np.asarray(self._model.upperPositionLimit, dtype=np.float64).reshape(-1)

    def fk(self, q: np.ndarray, *, frame_name: str) -> np.ndarray:
        return self._kinematics.fk(q, frame_name=frame_name)

    def ik(
        self,
        target_pose: np.ndarray,
        *,
        init_q: np.ndarray,
        frame_name: str,
        max_iters: int = 300,
        dt: float = 0.1,
        damping: float = 1e-6,
        pos_threshold: float = 5e-4,
        ori_threshold: float = 0.05,
    ) -> tuple[bool, np.ndarray]:
        return self._kinematics.ik(
            target_pose,
            init_q=init_q,
            frame_name=frame_name,
            max_iters=max_iters,
            dt=dt,
            damping=damping,
            pos_threshold=pos_threshold,
            ori_threshold=ori_threshold,
        )

    def fixed_relative_transform(self, *, parent_frame: str, child_frame: str) -> np.ndarray:
        q_zero = np.zeros(self._model.nq, dtype=np.float64)
        parent_in_base = self.fk(q_zero, frame_name=parent_frame)
        child_in_base = self.fk(q_zero, frame_name=child_frame)
        return np.linalg.inv(parent_in_base) @ child_in_base
