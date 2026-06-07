"""Robot protocol interface."""

from abc import abstractmethod
from typing import Any, Dict, List, Protocol, Tuple, runtime_checkable

import numpy as np


@runtime_checkable
class Robot(Protocol):
    """A generic Robot protocol for the a1z SDK."""

    @abstractmethod
    def num_dofs(self) -> int:
        """Get the number of controllable degrees of freedom."""
        raise NotImplementedError

    def get_joint_pos(self) -> np.ndarray:
        """Get current joint positions (rad)."""
        ...

    def get_joint_state(self) -> Dict[str, np.ndarray]:
        """Get current joint positions and velocities.

        Returns:
            Dict with keys 'pos', 'vel', 'eff' (all np.ndarray).
        """
        ...

    def command_joint_pos(self, joint_pos: np.ndarray) -> None:
        """Command target joint positions (rad) with default PD gains."""
        ...

    def command_joint_state(self, joint_state: Dict[str, np.ndarray]) -> None:
        """Command target joint state (pos, vel, kp, kd)."""
        ...

    @abstractmethod
    def get_observations(self) -> Dict[str, np.ndarray]:
        """Get all available observations (pos, vel, eff, etc.)."""
        raise NotImplementedError

    def get_robot_info(self) -> Dict[str, Any]:
        """Get robot configuration info (kp, kd, joint limits, etc.)."""
        return {}

    def start(
        self,
        initial_kp: np.ndarray | None = None,
        initial_kd: np.ndarray | None = None,
    ) -> None:
        """Start the backend and enter the controllable state."""
        ...

    def stop(self) -> None:
        """Stop the backend and leave the controllable state."""
        ...

    def move_joints(
        self,
        target_pos: np.ndarray,
        speed: float = 0.5,
        kp: np.ndarray | None = None,
        kd: np.ndarray | None = None,
    ) -> None:
        """Move to a target joint configuration and block until settled."""
        ...

    def set_gravity_mode(self, enabled: bool) -> None:
        """Switch between position-hold and gravity-comp modes."""
        ...

    def start_recording(self, sample_hz: int = 50) -> None:
        """Start recording a trajectory."""
        ...

    def stop_recording(self) -> List[Tuple[float, np.ndarray]]:
        """Stop recording and return the captured trajectory."""
        ...

    def play_trajectory(
        self,
        trajectory: List[Tuple[float, np.ndarray]],
        speed_factor: float = 1.0,
    ) -> None:
        """Play back a previously recorded trajectory and block until complete."""
        ...

    def command_gripper(self, value: float) -> None:
        """Command the gripper normalized position."""
        ...

    def get_gripper_pos(self) -> float | None:
        """Get the current gripper normalized position."""
        ...

    @property
    def is_running(self) -> bool:
        """Whether the backend is started and controllable."""
        ...
