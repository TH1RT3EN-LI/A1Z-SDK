"""Mock A1Z robot backend for offline SDK validation."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from a1z_ext.robots.trajectory import RecordingSession, Trajectory, play_trajectory_blocking


class MockArmRobot:
    """Lightweight offline robot backend with the same control surface as ArmRobot."""

    def __init__(
        self,
        num_joints: int = 6,
        gravity_comp_factor: float = 1.0,
        zero_gravity_mode: bool = True,
        default_kp: Optional[np.ndarray] = None,
        default_kd: Optional[np.ndarray] = None,
        joint_limits: Optional[List[Tuple[float, float]]] = None,
        with_gripper: bool = False,
        control_freq_hz: int = 250,
    ) -> None:
        self._num_joints = num_joints
        self.gravity_comp_factor = gravity_comp_factor
        self.zero_gravity_mode = zero_gravity_mode
        self._default_kp = default_kp.copy() if default_kp is not None else np.array(
            [30.0, 30.0, 30.0, 20.0, 5.0, 5.0], dtype=np.float64
        )
        self._default_kd = default_kd.copy() if default_kd is not None else np.array(
            [1.0, 1.0, 1.0, 0.5, 0.5, 0.5], dtype=np.float64
        )
        self._joint_limits = joint_limits
        self._with_gripper = with_gripper
        self._control_freq_hz = control_freq_hz
        self._control_period_s = 1.0 / max(1, control_freq_hz)
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._sampler_thread: Optional[threading.Thread] = None
        self._pos = np.zeros(num_joints, dtype=np.float64)
        self._vel = np.zeros(num_joints, dtype=np.float64)
        self._eff = np.zeros(num_joints, dtype=np.float64)
        self._gripper_pos: Optional[float] = 1.0 if with_gripper else None
        self._recording = RecordingSession()

    def num_dofs(self) -> int:
        return self._num_joints + (1 if self._with_gripper else 0)

    def start(
        self,
        initial_kp: Optional[np.ndarray] = None,
        initial_kd: Optional[np.ndarray] = None,
    ) -> None:
        del initial_kp, initial_kd
        with self._lock:
            self._running = True
            self._vel = np.zeros(self._num_joints, dtype=np.float64)
            self._eff = np.zeros(self._num_joints, dtype=np.float64)
        self._stop_event.clear()
        self._sampler_thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._sampler_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._sampler_thread is not None and self._sampler_thread.is_alive():
            self._sampler_thread.join(timeout=1.0)
        with self._lock:
            self._running = False
            self._vel = np.zeros(self._num_joints, dtype=np.float64)
            self._eff = np.zeros(self._num_joints, dtype=np.float64)

    @property
    def is_running(self) -> bool:
        return self._running

    def _clip_joint_pos(self, pos: np.ndarray) -> np.ndarray:
        pos = np.asarray(pos, dtype=np.float64).reshape(-1)
        if pos.shape[0] != self._num_joints:
            raise ValueError(f"Expected {self._num_joints} arm joints, got {pos.shape[0]}")
        if self._joint_limits is None:
            return pos.copy()
        clipped = pos.copy()
        for idx, (lo, hi) in enumerate(self._joint_limits):
            clipped[idx] = np.clip(clipped[idx], lo, hi)
        return clipped

    def _set_arm_state(
        self,
        pos: np.ndarray,
        vel: Optional[np.ndarray] = None,
        eff: Optional[np.ndarray] = None,
    ) -> None:
        with self._lock:
            self._pos = pos.copy()
            self._vel = np.zeros(self._num_joints, dtype=np.float64) if vel is None else vel.copy()
            self._eff = np.zeros(self._num_joints, dtype=np.float64) if eff is None else eff.copy()

    def get_joint_pos(self) -> np.ndarray:
        with self._lock:
            arm_pos = self._pos.copy()
            gripper_pos = self._gripper_pos
        if gripper_pos is not None:
            return np.append(arm_pos, gripper_pos)
        return arm_pos

    def get_joint_state(self) -> Dict[str, np.ndarray]:
        with self._lock:
            return {
                "pos": self._pos.copy(),
                "vel": self._vel.copy(),
                "eff": self._eff.copy(),
            }

    def get_observations(self) -> Dict[str, np.ndarray]:
        state = self.get_joint_state()
        if self._gripper_pos is not None:
            return {
                "joint_pos": state["pos"],
                "gripper_pos": np.array([self._gripper_pos], dtype=np.float64),
                "joint_vel": state["vel"],
                "joint_eff": state["eff"],
            }
        return state

    def get_robot_info(self) -> Dict[str, Any]:
        return {
            "backend": "mock",
            "num_joints": self._num_joints,
            "default_kp": self._default_kp.copy(),
            "default_kd": self._default_kd.copy(),
            "joint_limits": self._joint_limits,
            "gravity_comp_factor": self.gravity_comp_factor,
            "control_freq_hz": self._control_freq_hz,
            "with_gripper": self._with_gripper,
            "zero_gravity_mode": self.zero_gravity_mode,
            "control_mode": "gravity_comp_effort" if self.zero_gravity_mode else "position_hold",
        }

    def command_gripper(self, value: float) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if self._gripper_pos is None:
            raise RuntimeError("No gripper attached. Start the backend with gripper enabled.")
        with self._lock:
            self._gripper_pos = float(np.clip(value, 0.0, 1.0))

    def get_gripper_pos(self) -> Optional[float]:
        with self._lock:
            return self._gripper_pos

    def grasp_close_and_attach(
        self,
        target_prim_path: str = "",
        *,
        timeout_s: float = 2.0,
        contact_window_s: float = 0.15,
        require_bilateral_contact: bool = True,
    ) -> Dict[str, Any]:
        del timeout_s, contact_window_s, require_bilateral_contact
        self.command_gripper(0.0)
        attached_object_path = str(target_prim_path or "")
        return {
            "success": True,
            "target_prim_path": str(target_prim_path or ""),
            "attached_object_path": attached_object_path or None,
            "attachment_joint_path": None,
            "contact_summary": {"mode": "mock", "simulated": True},
            "failure_reason": None,
            "timing": {},
        }

    def release_attached_object(
        self,
        *,
        open_gripper: bool = True,
        timeout_s: float = 2.0,
    ) -> Dict[str, Any]:
        del timeout_s
        if open_gripper:
            self.command_gripper(1.0)
        return {
            "success": True,
            "released": True,
            "attached_object_path": None,
            "attachment_joint_path": None,
            "failure_reason": None,
        }

    def get_sim_grasp_status(self) -> Dict[str, Any]:
        return {
            "has_attached_object": False,
            "attached_object_path": None,
            "attachment_joint_path": None,
            "grasp_state": "idle",
            "last_contact_time": None,
            "last_failure_reason": None,
        }

    def command_joint_pos(self, pos: np.ndarray) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        pos = np.asarray(pos, dtype=np.float64).reshape(-1)
        if self._gripper_pos is not None and pos.shape[0] == self._num_joints + 1:
            self.command_gripper(float(pos[self._num_joints]))
            pos = pos[:self._num_joints]
        arm_pos = self._clip_joint_pos(pos[:self._num_joints])
        self._set_arm_state(arm_pos)

    def command_joint_state(self, joint_state: Dict[str, np.ndarray]) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        pos = self._clip_joint_pos(joint_state["pos"])
        vel = np.asarray(joint_state.get("vel", np.zeros(self._num_joints)), dtype=np.float64)
        eff = np.asarray(joint_state.get("eff", np.zeros(self._num_joints)), dtype=np.float64)
        self._set_arm_state(pos, vel=vel, eff=eff)

    def move_joints(
        self,
        target_pos: np.ndarray,
        speed: float = 0.5,
        kp: Optional[np.ndarray] = None,
        kd: Optional[np.ndarray] = None,
    ) -> None:
        del kp, kd
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if speed <= 0:
            raise ValueError("speed must be > 0")

        target_pos = np.asarray(target_pos, dtype=np.float64).reshape(-1)
        gripper_target: Optional[float] = None
        if self._gripper_pos is not None and target_pos.shape[0] == self._num_joints + 1:
            gripper_target = float(target_pos[self._num_joints])
            target_pos = target_pos[:self._num_joints]
        if gripper_target is not None:
            self.command_gripper(gripper_target)

        target_pos = self._clip_joint_pos(target_pos)
        current_state = self.get_joint_state()
        current_pos = current_state["pos"]
        delta = target_pos - current_pos
        max_dist = float(np.max(np.abs(delta)))
        if max_dist < 1e-6:
            self._set_arm_state(target_pos)
            return

        duration = max_dist / speed
        steps = max(1, int(duration / self._control_period_s))
        dt = duration / steps
        last_pos = current_pos.copy()

        for step in range(1, steps + 1):
            t = step / steps
            alpha = 10 * t**3 - 15 * t**4 + 6 * t**5
            next_pos = current_pos + alpha * delta
            vel = (next_pos - last_pos) / dt if dt > 0 else np.zeros(self._num_joints)
            self._set_arm_state(next_pos, vel=vel)
            last_pos = next_pos
            time.sleep(dt)

        self._set_arm_state(target_pos)

    def set_gravity_mode(self, enabled: bool) -> None:
        self.zero_gravity_mode = enabled

    def start_recording(self, sample_hz: int = 50) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        self._recording.start(sample_hz)

    def stop_recording(self) -> Trajectory:
        return self._recording.stop()

    def play_trajectory(
        self,
        trajectory: Trajectory,
        speed_factor: float = 1.0,
    ) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        prev_mode = self.zero_gravity_mode
        self.set_gravity_mode(False)
        try:
            play_trajectory_blocking(
                trajectory=trajectory,
                speed_factor=speed_factor,
                command_position=self.command_joint_pos,
            )
        finally:
            if prev_mode != self.zero_gravity_mode:
                self.set_gravity_mode(prev_mode)

    def sample_recording(self) -> None:
        with self._lock:
            pos = self._pos.copy()
        self._recording.maybe_sample(now_s=time.time(), pos=pos)

    def _sampling_loop(self) -> None:
        while not self._stop_event.is_set():
            self.sample_recording()
            time.sleep(min(0.01, self._control_period_s))
