"""Isaac Sim-backed A1Z robot backend."""

from __future__ import annotations

import queue
import threading
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import carb
import numpy as np
import omni.usd
from isaacsim.core.api import World
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from pxr import Sdf, Usd, UsdPhysics
from a1z_ext.config import get_control_defaults
from a1z_ext.robots.trajectory import RecordingSession, Trajectory, play_trajectory_blocking


def _smoothstep(t: float) -> float:
    return 10.0 * t**3 - 15.0 * t**4 + 6.0 * t**5


@dataclass
class _MainThreadRequest:
    callback: Callable[[], Any]
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: Optional[BaseException] = None


@dataclass
class _Trajectory:
    start_pos: np.ndarray
    start_vel: np.ndarray
    target_pos: np.ndarray
    start_time: float
    duration_s: float
    done_event: Optional[threading.Event] = None


@dataclass
class _JointCommand:
    pos: np.ndarray
    vel: np.ndarray
    acc: np.ndarray
    kp: np.ndarray
    kd: np.ndarray
    torque_ff: np.ndarray


class IsaacSimArmRobot:
    """Drive the imported A1Z articulation from inside the Isaac Kit thread."""

    _REQUEST_TIMEOUT_S = 120.0
    _ARM_SETTLE_TOL_RAD = np.deg2rad(0.75)
    _GRIPPER_SETTLE_TOL = 0.03

    @staticmethod
    def _flatten_gain_array(values: Any) -> np.ndarray:
        arr = np.asarray(values, dtype=np.float64)
        if arr.ndim == 0:
            return arr.reshape(1)
        if arr.ndim > 1:
            arr = arr.reshape(-1)
        return arr

    def __init__(
        self,
        num_joints: int = 6,
        with_gripper: bool = False,
        control_freq_hz: int = 60,
        articulation_root_prim: Optional[str] = None,
        default_kp: Optional[np.ndarray] = None,
        default_kd: Optional[np.ndarray] = None,
        urdf_path: Optional[str] = None,
        gravity_comp_factor: float = 1.0,
        zero_gravity_mode: bool = False,
        gravity_torque_scale: Optional[np.ndarray] = None,
        max_gravity_torque: Optional[np.ndarray] = None,
        torque_clip: Optional[np.ndarray] = None,
    ) -> None:
        control_defaults = get_control_defaults()
        isaac_cfg = control_defaults["isaacsim"]

        self._num_joints = num_joints
        self._with_gripper = with_gripper
        self._control_freq_hz = control_freq_hz
        self._control_period_s = 1.0 / max(1, control_freq_hz)
        self._articulation_root_prim = articulation_root_prim or isaac_cfg["articulation_root_prim"]
        self._arm_joint_names = list(isaac_cfg["arm_joint_names"])
        self._gripper_joint_names = list(isaac_cfg["gripper_joint_names"])

        self._arm_soft_joint_limits = np.deg2rad(
            np.asarray(control_defaults["arm_soft_joint_limits_deg"], dtype=np.float64).reshape(-1, 2)
        )[: self._num_joints].copy()
        self._arm_hard_joint_limits = np.deg2rad(
            np.asarray(control_defaults["arm_hard_joint_limits_deg"], dtype=np.float64).reshape(-1, 2)
        )[: self._num_joints].copy()
        self._hold_kp = np.asarray(isaac_cfg["position_hold_kp"], dtype=np.float64).reshape(-1)
        self._hold_kd = np.asarray(isaac_cfg["position_hold_kd"], dtype=np.float64).reshape(-1)
        self._arm_max_effort = np.asarray(isaac_cfg["arm_max_effort"], dtype=np.float64).reshape(-1)
        self._arm_max_velocity = np.asarray(isaac_cfg["arm_max_velocity"], dtype=np.float64).reshape(-1)
        self._arm_peak_velocity = np.asarray(control_defaults["arm_peak_velocity_rad_s"], dtype=np.float64).reshape(-1)
        self._gravity_mode_kd_scale = float(isaac_cfg["gravity_mode_kd_scale"])
        self._gripper_kp = np.asarray(isaac_cfg["gripper_kp"], dtype=np.float64).reshape(-1)
        self._gripper_kd = np.asarray(isaac_cfg["gripper_kd"], dtype=np.float64).reshape(-1)
        self._gripper_max_effort = np.asarray(isaac_cfg["gripper_max_effort"], dtype=np.float64).reshape(-1)
        self._gripper_max_velocity = np.asarray(isaac_cfg["gripper_max_velocity"], dtype=np.float64).reshape(-1)

        self._default_kp = (
            np.asarray(default_kp, dtype=np.float64).reshape(-1).copy()
            if default_kp is not None
            else self._hold_kp.copy()
        )
        self._default_kd = (
            np.asarray(default_kd, dtype=np.float64).reshape(-1).copy()
            if default_kd is not None
            else self._hold_kd.copy()
        )
        self._gravity_comp_factor = float(gravity_comp_factor)
        self.zero_gravity_mode = bool(zero_gravity_mode)
        self._gravity_torque_scale = (
            np.asarray(gravity_torque_scale, dtype=np.float64).reshape(-1).copy()
            if gravity_torque_scale is not None
            else np.ones(self._num_joints, dtype=np.float64)
        )
        self._max_gravity_torque = (
            np.asarray(max_gravity_torque, dtype=np.float64).reshape(-1).copy()
            if max_gravity_torque is not None
            else self._arm_max_effort[: self._num_joints].copy()
        )
        self._torque_clip = (
            np.asarray(torque_clip, dtype=np.float64).reshape(-1).copy()
            if torque_clip is not None
            else self._arm_max_effort[: self._num_joints].copy()
        )

        self._gravity_model = None
        if urdf_path:
            try:
                from a1z.dynamics.gravity_model import GravityModel

                self._gravity_model = GravityModel(urdf_path)
            except Exception as exc:
                warnings.warn(
                    f"Isaac Sim backend could not enable gravity compensation from {urdf_path}: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )

        self._main_thread_id = threading.get_ident()
        self._world: Optional[World] = None
        self._articulation: Optional[SingleArticulation] = None
        self._running = False

        self._request_queue: queue.Queue[_MainThreadRequest] = queue.Queue()
        self._state_lock = threading.Lock()
        self._command_lock = threading.Lock()

        self._full_pos = np.zeros(self._num_joints + 2, dtype=np.float64)
        self._full_vel = np.zeros_like(self._full_pos)
        self._full_eff = np.zeros_like(self._full_pos)
        self._joint_limits: Optional[np.ndarray] = None
        self._dof_names: list[str] = []
        self._arm_joint_indices = np.arange(self._num_joints, dtype=np.int64)
        self._gripper_joint_indices = np.array([], dtype=np.int64)
        self._last_control_action_time = 0.0
        self._last_gripper_action_time = 0.0
        self._last_hard_limit_log_time = 0.0

        self._gripper_open_value = 1.0
        self._gripper_left_open = 0.0
        self._gripper_left_closed = 0.048
        self._gripper_right_open = 0.0
        self._gripper_right_closed = -0.048

        initial_kp = self._active_arm_kp()
        initial_kd = self._active_arm_kd()
        self._command = _JointCommand(
            pos=np.zeros(self._num_joints, dtype=np.float64),
            vel=np.zeros(self._num_joints, dtype=np.float64),
            acc=np.zeros(self._num_joints, dtype=np.float64),
            kp=initial_kp,
            kd=initial_kd,
            torque_ff=np.zeros(self._num_joints, dtype=np.float64),
        )
        self._gripper_target_value = 1.0
        self._trajectory: Optional[_Trajectory] = None
        self._debug_last_gravity_log = 0.0
        self._last_gravity_q = np.zeros(self._num_joints, dtype=np.float64)
        self._last_gravity_qd = np.zeros(self._num_joints, dtype=np.float64)
        self._last_gravity_pos_err = np.zeros(self._num_joints, dtype=np.float64)
        self._last_gravity_vel_err = np.zeros(self._num_joints, dtype=np.float64)
        self._last_gravity_tau_id = np.zeros(self._num_joints, dtype=np.float64)
        self._last_gravity_effort = np.zeros(self._num_joints, dtype=np.float64)
        self._recording = RecordingSession()

    def num_dofs(self) -> int:
        return self._num_joints + (1 if self._with_gripper else 0)

    def _resolve_articulation(self) -> tuple[str, SingleArticulation]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is not available while resolving articulation root.")
        prim = stage.GetPrimAtPath(self._articulation_root_prim)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid articulation root prim: {self._articulation_root_prim}")

        articulation = SingleArticulation(prim_path=self._articulation_root_prim, name="a1z")
        articulation.initialize()
        if not articulation.is_valid():
            raise RuntimeError(f"Invalid articulation at requested root: {self._articulation_root_prim}")

        dof_names = list(articulation.dof_names)
        if len(dof_names) < self._num_joints:
            raise RuntimeError(
                f"Expected at least {self._num_joints} DOFs, found {len(dof_names)} at "
                f"{self._articulation_root_prim}"
            )

        return self._articulation_root_prim, articulation

    def start(
        self,
        initial_kp: Optional[np.ndarray] = None,
        initial_kd: Optional[np.ndarray] = None,
    ) -> None:
        self._run_on_main_thread(
            lambda: self._start_impl(initial_kp=initial_kp, initial_kd=initial_kd)
        )

    def _start_impl(
        self,
        initial_kp: Optional[np.ndarray] = None,
        initial_kd: Optional[np.ndarray] = None,
    ) -> None:
        self._world = World(stage_units_in_meters=1.0)
        self._world.reset()
        resolved_root, articulation = self._resolve_articulation()
        self._articulation_root_prim = resolved_root
        self._articulation = articulation
        self._dof_names = list(self._articulation.dof_names)
        if len(self._dof_names) < self._num_joints:
            raise RuntimeError(
                f"Expected at least {self._num_joints} DOFs, found {len(self._dof_names)} at "
                f"{self._articulation_root_prim}"
            )

        self._resolve_joint_indices()
        self._refresh_joint_limits()
        self._running = True

        self._update_state_cache()
        with self._command_lock:
            self._command.pos = self._clip_arm_pos(self._full_pos[self._arm_joint_indices].copy())
            self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.kp = (
                np.asarray(initial_kp, dtype=np.float64).reshape(-1)[: self._num_joints].copy()
                if initial_kp is not None
                else self._active_arm_kp()
            )
            self._command.kd = (
                np.asarray(initial_kd, dtype=np.float64).reshape(-1)[: self._num_joints].copy()
                if initial_kd is not None
                else self._active_arm_kd()
            )
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)
        self._gripper_target_value = float(self._gripper_open_value)
        self._trajectory = None
        self._configure_actuators()
        self._apply_control_action()

    def stop(self) -> None:
        if threading.get_ident() == self._main_thread_id:
            self._stop_impl()
            return
        try:
            self._run_on_main_thread(self._stop_impl)
        except RuntimeError:
            self._stop_impl()

    def _stop_impl(self) -> None:
        self._trajectory = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def process_pending(self) -> None:
        self._ensure_main_thread()
        while True:
            try:
                request = self._request_queue.get_nowait()
            except queue.Empty:
                break
            try:
                request.result = request.callback()
            except BaseException as exc:
                request.error = exc
            finally:
                request.event.set()

        if not self._running or self._articulation is None:
            return

        self._update_state_cache()
        self._check_arm_hard_limits()
        self._recording.maybe_sample(
            now_s=time.time(),
            pos=self._full_pos[self._arm_joint_indices].copy(),
        )
        self._advance_trajectory()
        self._apply_control_action()
        self._update_state_cache()

    def get_joint_pos(self) -> np.ndarray:
        with self._state_lock:
            arm_pos = self._full_pos[self._arm_joint_indices].copy()
            gripper_value = self._gripper_open_value
        if self._with_gripper:
            return np.append(arm_pos, gripper_value)
        return arm_pos

    def get_joint_state(self) -> Dict[str, np.ndarray]:
        with self._state_lock:
            return {
                "pos": self._full_pos[self._arm_joint_indices].copy(),
                "vel": self._full_vel[self._arm_joint_indices].copy(),
                "eff": self._full_eff[self._arm_joint_indices].copy(),
            }

    def get_observations(self) -> Dict[str, np.ndarray]:
        state = self.get_joint_state()
        if self._with_gripper:
            return {
                "joint_pos": state["pos"],
                "gripper_pos": np.array([self.get_gripper_pos()], dtype=np.float64),
                "joint_vel": state["vel"],
                "joint_eff": state["eff"],
            }
        return state

    def get_robot_info(self) -> Dict[str, Any]:
        with self._state_lock:
            articulation_joint_limits = None if self._joint_limits is None else self._joint_limits.copy()
        actual_kp = None
        actual_kd = None
        effort_modes = None
        if self._articulation is not None:
            try:
                dof_props = self._articulation.dof_properties
                actual_kp = np.asarray(dof_props["stiffness"], dtype=np.float64).reshape(-1).copy()
                actual_kd = np.asarray(dof_props["damping"], dtype=np.float64).reshape(-1).copy()
            except Exception:
                pass
            try:
                effort_modes = list(self._controller().get_effort_modes())
            except Exception:
                pass
        with self._command_lock:
            command_pos = self._command.pos.copy()
            command_vel = self._command.vel.copy()
        return {
            "backend": "isaacsim",
            "num_joints": self._num_joints,
            "control_freq_hz": self._control_freq_hz,
            "with_gripper": self._with_gripper,
            "default_kp": self._default_kp.copy(),
            "default_kd": self._default_kd.copy(),
            "joint_limits": self._arm_soft_joint_limits.copy(),
            "hard_joint_limits": self._arm_hard_joint_limits.copy(),
            "articulation_joint_limits": articulation_joint_limits,
            "arm_max_velocity": self._arm_max_velocity.copy(),
            "arm_peak_velocity": self._arm_peak_velocity.copy(),
            "articulation_root_prim": self._articulation_root_prim,
            "dof_names": list(self._dof_names),
            "arm_joint_indices": self._arm_joint_indices.copy(),
            "gripper_joint_indices": self._gripper_joint_indices.copy(),
            "gravity_comp_factor": self._gravity_comp_factor,
            "zero_gravity_mode": self.zero_gravity_mode,
            "gravity_torque_scale": self._gravity_torque_scale.copy(),
            "max_gravity_torque": self._max_gravity_torque.copy(),
            "torque_clip": self._torque_clip.copy(),
            "actual_kp": actual_kp,
            "actual_kd": actual_kd,
            "controller_kp": self._command.kp.copy(),
            "controller_kd": self._command.kd.copy(),
            "gravity_debug_q": self._last_gravity_q.copy(),
            "gravity_debug_qd": self._last_gravity_qd.copy(),
            "gravity_debug_pos_err": self._last_gravity_pos_err.copy(),
            "gravity_debug_vel_err": self._last_gravity_vel_err.copy(),
            "gravity_debug_tau_id": self._last_gravity_tau_id.copy(),
            "gravity_debug_effort": self._last_gravity_effort.copy(),
            "effort_modes": effort_modes,
            "command_pos": command_pos,
            "command_vel": command_vel,
            "control_mode": "gravity_comp_effort" if self.zero_gravity_mode else "position_hold",
        }

    def command_gripper(self, value: float) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if not self._with_gripper:
            raise RuntimeError("No gripper attached. Start the backend with gripper enabled.")
        value = float(np.clip(value, 0.0, 1.0))
        self._run_on_main_thread(lambda: self._set_gripper_target(value))
        self._wait_for_gripper_target(value, timeout_s=2.0)

    def get_gripper_pos(self) -> Optional[float]:
        if not self._with_gripper:
            return None
        with self._state_lock:
            return float(self._gripper_open_value)

    def command_joint_pos(self, pos: np.ndarray) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        pos = np.asarray(pos, dtype=np.float64).reshape(-1)
        arm_target = self._clip_arm_pos(pos[: self._num_joints])
        gripper_target = None
        if self._with_gripper and pos.shape[0] == self._num_joints + 1:
            gripper_target = float(np.clip(pos[self._num_joints], 0.0, 1.0))
        self._run_on_main_thread(lambda: self._set_command_now(arm_target, gripper_target))

    def command_joint_state(self, joint_state: Dict[str, np.ndarray]) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        pos = np.asarray(joint_state["pos"], dtype=np.float64).reshape(-1)
        vel = np.asarray(
            joint_state.get("vel", np.zeros(self._num_joints, dtype=np.float64)),
            dtype=np.float64,
        ).reshape(-1)[: self._num_joints]
        kp = np.asarray(joint_state.get("kp", self._active_arm_kp()), dtype=np.float64).reshape(-1)[: self._num_joints]
        kd = np.asarray(joint_state.get("kd", self._active_arm_kd()), dtype=np.float64).reshape(-1)[: self._num_joints]
        eff = np.asarray(
            joint_state.get("eff", np.zeros(self._num_joints, dtype=np.float64)),
            dtype=np.float64,
        ).reshape(-1)[: self._num_joints]
        self._run_on_main_thread(lambda: self._set_joint_state_now(pos, vel, kp, kd, eff))

    def move_joints(
        self,
        target_pos: np.ndarray,
        speed: float = 0.5,
        kp: Optional[np.ndarray] = None,
        kd: Optional[np.ndarray] = None,
    ) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if speed <= 0:
            raise ValueError("speed must be > 0")

        target_pos = np.asarray(target_pos, dtype=np.float64).reshape(-1)
        arm_target = self._clip_arm_pos(target_pos[: self._num_joints])
        gripper_target = None
        if self._with_gripper and target_pos.shape[0] == self._num_joints + 1:
            gripper_target = float(np.clip(target_pos[self._num_joints], 0.0, 1.0))

        current_arm = self.get_joint_state()["pos"]
        duration_estimate_s = self._trajectory_duration_for_limits(current_arm, arm_target, speed)
        done_event = threading.Event()

        kp_arr = None if kp is None else np.asarray(kp, dtype=np.float64).reshape(-1)[: self._num_joints]
        kd_arr = None if kd is None else np.asarray(kd, dtype=np.float64).reshape(-1)[: self._num_joints]

        self._run_on_main_thread(
            lambda: self._start_trajectory(
                target_arm=arm_target,
                speed=speed,
                kp=kp_arr,
                kd=kd_arr,
                done_event=done_event,
                gripper_target=gripper_target,
            )
        )

        wait_timeout_s = max(5.0, duration_estimate_s + 5.0)
        if not done_event.wait(timeout=wait_timeout_s):
            raise TimeoutError("Timed out waiting for Isaac Sim arm motion to complete.")
        self._wait_for_arm_target(arm_target, timeout_s=max(2.0, wait_timeout_s))

    def set_gravity_mode(self, enabled: bool) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        self._run_on_main_thread(lambda: self._set_gravity_mode_impl(enabled))

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

    def _set_gravity_mode_impl(self, enabled: bool) -> None:
        self.zero_gravity_mode = bool(enabled)
        with self._command_lock:
            self._command.kp = self._active_arm_kp()
            self._command.kd = self._active_arm_kd()
        self._configure_actuators()
        self._apply_control_action()

    def _set_gripper_target(self, value: float) -> None:
        self._gripper_target_value = float(np.clip(value, 0.0, 1.0))
        self._apply_control_action()

    def _set_command_now(
        self,
        arm_target: np.ndarray,
        gripper_target: Optional[float],
    ) -> None:
        with self._command_lock:
            self._command.pos = arm_target.copy()
            self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.kp = self._default_command_kp()
            self._command.kd = self._default_command_kd()
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)
        self._trajectory = None
        if gripper_target is not None:
            self._gripper_target_value = gripper_target
        self._apply_control_action()

    def _set_joint_state_now(
        self,
        pos: np.ndarray,
        vel: np.ndarray,
        kp: np.ndarray,
        kd: np.ndarray,
        eff: np.ndarray,
    ) -> None:
        with self._command_lock:
            self._command.pos = self._clip_arm_pos(pos[: self._num_joints])
            self._command.vel = self._clip_arm_vel(vel.copy())
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.kp = kp.copy()
            self._command.kd = kd.copy()
            self._command.torque_ff = self._clip_arm_effort(eff.copy())
        self._trajectory = None
        self._apply_control_action()

    def _start_trajectory(
        self,
        target_arm: np.ndarray,
        speed: float,
        kp: Optional[np.ndarray],
        kd: Optional[np.ndarray],
        done_event: threading.Event,
        gripper_target: Optional[float],
    ) -> None:
        current_state = self.get_joint_state()
        current_arm = current_state["pos"]
        current_vel = current_state["vel"]
        max_dist = float(np.max(np.abs(target_arm - current_arm)))

        with self._command_lock:
            self._command.kp = self._default_command_kp() if kp is None else kp.copy()
            self._command.kd = self._default_command_kd() if kd is None else kd.copy()

        if gripper_target is not None:
            self._gripper_target_value = gripper_target

        if max_dist < 1e-4:
            with self._command_lock:
                self._command.pos = target_arm.copy()
                self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
                self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._trajectory = None
            self._apply_control_action()
            done_event.set()
            return

        duration_s = self._trajectory_duration_for_limits(current_arm, target_arm, speed)
        self._trajectory = _Trajectory(
            start_pos=current_arm.copy(),
            start_vel=current_vel.copy(),
            target_pos=target_arm.copy(),
            start_time=time.monotonic(),
            duration_s=duration_s,
            done_event=done_event,
        )

    def _advance_trajectory(self) -> None:
        if self._trajectory is None:
            return

        now = time.monotonic()
        traj = self._trajectory
        elapsed = max(0.0, now - traj.start_time)
        alpha = min(1.0, elapsed / traj.duration_s)
        alpha_dot = (30.0 * alpha**2 - 60.0 * alpha**3 + 30.0 * alpha**4) / traj.duration_s
        alpha_ddot = (60.0 * alpha - 180.0 * alpha**2 + 120.0 * alpha**3) / (traj.duration_s**2)
        delta = traj.target_pos - traj.start_pos

        with self._command_lock:
            self._command.pos = traj.start_pos + _smoothstep(alpha) * delta
            self._command.vel = alpha_dot * delta
            self._command.acc = alpha_ddot * delta

        if alpha >= 1.0:
            with self._command_lock:
                self._command.pos = traj.target_pos.copy()
                self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
                self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._trajectory = None
            if traj.done_event is not None:
                traj.done_event.set()

    def _trajectory_duration_for_limits(
        self,
        start_pos: np.ndarray,
        target_pos: np.ndarray,
        requested_speed: float,
    ) -> float:
        start_pos = np.asarray(start_pos, dtype=np.float64).reshape(-1)[: self._num_joints]
        target_pos = np.asarray(target_pos, dtype=np.float64).reshape(-1)[: self._num_joints]
        delta = np.abs(target_pos - start_pos)
        velocity_limits = np.minimum(
            self._arm_max_velocity[: self._num_joints],
            np.full(self._num_joints, float(requested_speed), dtype=np.float64),
        )
        velocity_limits = np.maximum(velocity_limits, 1e-6)
        # Minimum-jerk alpha_dot peaks at 1.875 / duration.
        per_joint_duration = 1.875 * delta / velocity_limits
        return max(self._control_period_s, float(np.max(per_joint_duration)))

    def _resolve_joint_indices(self) -> None:
        dof_map = {name: idx for idx, name in enumerate(self._dof_names)}
        try:
            self._arm_joint_indices = np.array([dof_map[name] for name in self._arm_joint_names], dtype=np.int64)
        except KeyError as exc:
            raise RuntimeError(f"Missing arm joint in Isaac articulation: {exc}") from exc

        if self._with_gripper:
            try:
                self._gripper_joint_indices = np.array(
                    [dof_map[name] for name in self._gripper_joint_names],
                    dtype=np.int64,
                )
            except KeyError as exc:
                raise RuntimeError(f"Missing gripper joint in Isaac articulation: {exc}") from exc
        else:
            self._gripper_joint_indices = np.array([], dtype=np.int64)

    def _configure_actuators(self) -> None:
        if self._articulation is None:
            return

        if self.zero_gravity_mode:
            arm_kp = np.zeros(self._num_joints, dtype=np.float64)
            arm_kd = np.zeros(self._num_joints, dtype=np.float64)
        else:
            arm_kp = self._hold_kp.copy()
            arm_kd = self._hold_kd.copy()

        # SingleArticulation only exposes the articulation controller for drive
        # configuration. The controller accepts full gain arrays, while control
        # mode and effort mode can still be set per DOF.
        self._set_subset_effort_mode("force", self._arm_joint_indices)
        self._set_subset_gains(self._arm_joint_indices, arm_kp, arm_kd)
        self._set_subset_max_efforts(self._arm_joint_indices, self._arm_max_effort)
        for dof_index in self._arm_joint_indices.tolist():
            self._switch_dof_control_mode(
                "effort" if self.zero_gravity_mode else "position",
                int(dof_index),
            )

        if self._with_gripper and self._gripper_joint_indices.size == 2:
            self._set_subset_effort_mode("force", self._gripper_joint_indices)
            self._set_subset_gains(self._gripper_joint_indices, self._gripper_kp, self._gripper_kd)
            self._set_subset_max_efforts(self._gripper_joint_indices, self._gripper_max_effort)
            for dof_index in self._gripper_joint_indices.tolist():
                self._switch_dof_control_mode("position", int(dof_index))

        try:
            dof_props = self._articulation.dof_properties
            actual_kp = np.asarray(dof_props["stiffness"], dtype=np.float64).reshape(-1)
            actual_kd = np.asarray(dof_props["damping"], dtype=np.float64).reshape(-1)
            carb.log_info(
                "A1Z Isaac actuator config: "
                f"mode={'gravity_comp_effort' if self.zero_gravity_mode else 'position_hold'} "
                f"arm_idx={self._arm_joint_indices.tolist()} "
                f"gripper_idx={self._gripper_joint_indices.tolist()} "
                f"actual_arm_kp={np.round(actual_kp[self._arm_joint_indices], 2).tolist()} "
                f"actual_arm_kd={np.round(actual_kd[self._arm_joint_indices], 2).tolist()}"
            )
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac actuator introspection failed: {exc}")

    def _compute_gravity_feedforward(self, q: np.ndarray, qd: np.ndarray, qdd: np.ndarray) -> np.ndarray:
        if self._gravity_model is None:
            return np.zeros(self._num_joints, dtype=np.float64)
        tau = self._gravity_model.compute_inverse_dynamics(q, qd, qdd)
        tau = tau[: self._num_joints]
        if np.any(np.abs(tau) > self._max_gravity_torque):
            raise RuntimeError(
                f"Inverse dynamics torques too large! tau={np.round(tau, 2)} Nm. "
                f"Max allowed: {self._max_gravity_torque} Nm."
            )
        return tau * self._gravity_torque_scale * self._gravity_comp_factor

    def _apply_control_action(self) -> None:
        if self._articulation is None:
            return

        with self._command_lock:
            pos_target = self._clip_arm_pos(self._command.pos.copy())
            vel_target = self._clip_arm_vel(self._command.vel.copy())
            acc_target = self._command.acc.copy()
            torque_ff = self._clip_arm_effort(self._command.torque_ff.copy())
            kp = self._command.kp.copy()
            kd = self._command.kd.copy()

        pos_target = self._rate_limit_arm_target(pos_target)

        if self.zero_gravity_mode:
            q = self._full_pos[self._arm_joint_indices].copy()
            qd = self._full_vel[self._arm_joint_indices].copy()
            pos_err = pos_target - q
            vel_err = vel_target - qd
            tau_id = self._compute_gravity_feedforward(q, vel_target, acc_target)
            arm_effort = tau_id + (kp * pos_err) + (kd * vel_err) + torque_ff
            arm_effort = np.clip(
                arm_effort,
                -self._torque_clip[: self._num_joints],
                self._torque_clip[: self._num_joints],
            )
            self._last_gravity_q = q.copy()
            self._last_gravity_qd = qd.copy()
            self._last_gravity_pos_err = pos_err.copy()
            self._last_gravity_vel_err = vel_err.copy()
            self._last_gravity_tau_id = tau_id.copy()
            self._last_gravity_effort = arm_effort.copy()
            now = time.monotonic()
            if now - self._debug_last_gravity_log >= 1.0:
                carb.log_info(
                    "A1Z gravity effort debug: "
                    f"pos_err_deg={np.round(np.rad2deg(pos_err), 2).tolist()} "
                    f"vel_err={np.round(vel_err, 3).tolist()} "
                    f"kp={np.round(kp, 2).tolist()} "
                    f"kd={np.round(kd, 2).tolist()} "
                    f"tau_id={np.round(tau_id, 3).tolist()} "
                    f"eff={np.round(arm_effort, 3).tolist()}"
                )
                self._debug_last_gravity_log = now
            self._controller().apply_action(
                ArticulationAction(
                    joint_efforts=arm_effort.astype(np.float32),
                    joint_indices=self._arm_joint_indices.astype(np.int64),
                )
            )
        else:
            self._controller().apply_action(
                ArticulationAction(
                    joint_positions=pos_target.astype(np.float32),
                    joint_velocities=vel_target.astype(np.float32),
                    joint_indices=self._arm_joint_indices.astype(np.int64),
                )
            )

        if self._with_gripper and self._gripper_joint_indices.size == 2:
            grip = self._rate_limit_gripper_dofs(self._normalized_to_gripper_dofs(self._gripper_target_value))
            self._controller().apply_action(
                ArticulationAction(
                    joint_positions=grip.astype(np.float32),
                    joint_indices=self._gripper_joint_indices.astype(np.int64),
                )
            )

    def _normalized_to_gripper_dofs(self, value: float) -> np.ndarray:
        open_fraction = float(np.clip(value, 0.0, 1.0))
        closed_fraction = 1.0 - open_fraction
        left = (open_fraction * self._gripper_left_open) + (closed_fraction * self._gripper_left_closed)
        right = (open_fraction * self._gripper_right_open) + (closed_fraction * self._gripper_right_closed)
        return self._clip_gripper_dofs(np.array([left, right], dtype=np.float64))

    def _coerce_arm_vector(self, values: np.ndarray, *, name: str) -> np.ndarray:
        arr = np.asarray(values, dtype=np.float64).reshape(-1)
        if arr.shape[0] != self._num_joints:
            raise ValueError(f"Expected {self._num_joints} arm {name} values, got {arr.shape[0]}")
        return arr

    def _clip_arm_pos(self, pos: np.ndarray) -> np.ndarray:
        pos = self._coerce_arm_vector(pos, name="position")
        clipped = pos.copy()
        for local_idx, (lo, hi) in enumerate(self._arm_soft_joint_limits[: self._num_joints]):
            clipped[local_idx] = np.clip(clipped[local_idx], lo, hi)
        return clipped

    def _clip_arm_vel(self, vel: np.ndarray) -> np.ndarray:
        vel = self._coerce_arm_vector(vel, name="velocity")
        limits = self._arm_max_velocity[: self._num_joints]
        return np.clip(vel, -limits, limits)

    def _clip_arm_effort(self, effort: np.ndarray) -> np.ndarray:
        effort = self._coerce_arm_vector(effort, name="effort")
        limits = self._torque_clip[: self._num_joints]
        return np.clip(effort, -limits, limits)

    def _rate_limit_arm_target(self, target_pos: np.ndarray) -> np.ndarray:
        now = time.monotonic()
        if self._last_control_action_time <= 0.0:
            dt = self._control_period_s
        else:
            dt = now - self._last_control_action_time
        self._last_control_action_time = now

        dt = min(max(dt, self._control_period_s), 0.25)
        current_pos = self._full_pos[self._arm_joint_indices].copy()
        max_step = self._arm_max_velocity[: self._num_joints] * dt
        return current_pos + np.clip(target_pos - current_pos, -max_step, max_step)

    def _clip_gripper_dofs(self, pos: np.ndarray) -> np.ndarray:
        pos = np.asarray(pos, dtype=np.float64).reshape(-1)
        clipped = pos.copy()
        if self._joint_limits is not None and self._gripper_joint_indices.size == 2:
            for local_idx, dof_idx in enumerate(self._gripper_joint_indices):
                lo, hi = self._joint_limits[dof_idx]
                clipped[local_idx] = np.clip(clipped[local_idx], lo, hi)
        return clipped

    def _rate_limit_gripper_dofs(self, target_pos: np.ndarray) -> np.ndarray:
        if self._gripper_joint_indices.size != 2:
            return target_pos

        now = time.monotonic()
        if self._last_gripper_action_time <= 0.0:
            dt = self._control_period_s
        else:
            dt = now - self._last_gripper_action_time
        self._last_gripper_action_time = now

        dt = min(max(dt, self._control_period_s), 0.25)
        current_pos = self._full_pos[self._gripper_joint_indices].copy()
        max_step = self._gripper_max_velocity[:2] * dt
        return self._clip_gripper_dofs(current_pos + np.clip(target_pos - current_pos, -max_step, max_step))

    def _refresh_joint_limits(self) -> None:
        if self._articulation is None:
            return
        dof_props = self._articulation.dof_properties
        limits = np.column_stack(
            [
                np.asarray(dof_props["lower"], dtype=np.float64).reshape(-1),
                np.asarray(dof_props["upper"], dtype=np.float64).reshape(-1),
            ]
        )
        self._joint_limits = limits
        if self._gripper_joint_indices.size == 2:
            left_idx, right_idx = self._gripper_joint_indices.tolist()
            self._gripper_left_open = float(limits[left_idx, 0])
            self._gripper_left_closed = float(limits[left_idx, 1])
            self._gripper_right_closed = float(limits[right_idx, 0])
            self._gripper_right_open = float(limits[right_idx, 1])

        if self._arm_joint_indices.size == self._num_joints:
            arm_articulation_limits = limits[self._arm_joint_indices]
            if not np.allclose(arm_articulation_limits, self._arm_hard_joint_limits, atol=np.deg2rad(0.5)):
                carb.log_warn(
                    "A1Z Isaac USD hard joint limits differ from Galaxea config. "
                    f"usd_deg={np.round(np.rad2deg(arm_articulation_limits), 2).tolist()} "
                    f"cfg_deg={np.round(np.rad2deg(self._arm_hard_joint_limits), 2).tolist()}"
                )

    def _check_arm_hard_limits(self) -> None:
        if self._arm_joint_indices.size != self._num_joints:
            return

        q = self._full_pos[self._arm_joint_indices].copy()
        lower = self._arm_hard_joint_limits[:, 0] - np.deg2rad(0.5)
        upper = self._arm_hard_joint_limits[:, 1] + np.deg2rad(0.5)
        violation = (q < lower) | (q > upper)
        if not np.any(violation):
            return

        self._trajectory = None
        with self._command_lock:
            self._command.pos = self._clip_arm_pos(q)
            self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)

        now = time.monotonic()
        if now - self._last_hard_limit_log_time >= 1.0:
            bad = np.where(violation)[0]
            carb.log_warn(
                "A1Z Isaac hard joint limit violation; holding clipped soft target. "
                f"joints={(bad + 1).tolist()} q_deg={np.round(np.rad2deg(q), 2).tolist()}"
            )
            self._last_hard_limit_log_time = now

    def _update_state_cache(self) -> None:
        if self._articulation is None:
            return
        full_pos = np.asarray(self._articulation.get_joint_positions(), dtype=np.float64).reshape(-1)
        full_vel = np.asarray(self._articulation.get_joint_velocities(), dtype=np.float64).reshape(-1)
        try:
            full_eff = np.asarray(self._articulation.get_measured_joint_efforts(), dtype=np.float64).reshape(-1)
        except Exception:
            full_eff = np.zeros_like(full_pos)
        if full_vel.shape[0] != full_pos.shape[0]:
            full_vel = np.zeros_like(full_pos)
        if full_eff.shape[0] != full_pos.shape[0]:
            full_eff = np.zeros_like(full_pos)

        gripper_open_value = self._gripper_open_value
        if self._gripper_joint_indices.size >= 1:
            left = full_pos[self._gripper_joint_indices[0]]
            span = self._gripper_left_closed - self._gripper_left_open
            if abs(span) >= 1e-6:
                closed_fraction = (left - self._gripper_left_open) / span
                gripper_open_value = float(np.clip(1.0 - closed_fraction, 0.0, 1.0))

        with self._state_lock:
            self._full_pos = full_pos.copy()
            self._full_vel = full_vel.copy()
            self._full_eff = full_eff.copy()
            self._gripper_open_value = gripper_open_value

    def _active_arm_kp(self) -> np.ndarray:
        if self.zero_gravity_mode:
            return np.zeros(self._num_joints, dtype=np.float64)
        return self._hold_kp.copy()

    def _active_arm_kd(self) -> np.ndarray:
        if self.zero_gravity_mode:
            return self._hold_kd.copy() * self._gravity_mode_kd_scale
        return self._hold_kd.copy()

    def _default_command_kp(self) -> np.ndarray:
        return self._default_kp.copy()

    def _default_command_kd(self) -> np.ndarray:
        if self.zero_gravity_mode:
            return self._default_kd.copy() * self._gravity_mode_kd_scale
        return self._default_kd.copy()

    def _controller(self):
        if self._articulation is None:
            raise RuntimeError("Isaac articulation is not initialized.")
        return self._articulation.get_articulation_controller()

    def _set_subset_effort_mode(self, mode: str, joint_indices: np.ndarray) -> None:
        if self._articulation is None or joint_indices.size == 0:
            return
        joint_indices = np.asarray(joint_indices, dtype=np.int64).reshape(-1)
        self._controller().set_effort_modes(mode=mode, joint_indices=joint_indices)

    def _set_subset_gains(self, joint_indices: np.ndarray, kps: np.ndarray, kds: np.ndarray) -> None:
        if self._articulation is None or joint_indices.size == 0:
            return
        joint_indices = np.asarray(joint_indices, dtype=np.int64).reshape(-1)
        kps = np.asarray(kps, dtype=np.float32).reshape(-1)
        kds = np.asarray(kds, dtype=np.float32).reshape(-1)

        dof_props = self._articulation.dof_properties
        full_kp = np.asarray(dof_props["stiffness"], dtype=np.float32).reshape(-1).copy()
        full_kd = np.asarray(dof_props["damping"], dtype=np.float32).reshape(-1).copy()
        full_kp[joint_indices] = kps
        full_kd[joint_indices] = kds
        self._controller().set_gains(kps=full_kp, kds=full_kd)

    def _set_subset_max_efforts(self, joint_indices: np.ndarray, values: np.ndarray) -> None:
        if self._articulation is None or joint_indices.size == 0:
            return
        joint_indices = np.asarray(joint_indices, dtype=np.int64).reshape(-1)
        values = np.asarray(values, dtype=np.float32).reshape(-1)
        self._controller().set_max_efforts(values=values, joint_indices=joint_indices)

    def _switch_dof_control_mode(self, mode: str, dof_index: int) -> None:
        if self._articulation is None:
            return
        self._controller().switch_dof_control_mode(dof_index=dof_index, mode=mode)

    def _run_on_main_thread(self, callback: Callable[[], Any]) -> Any:
        if threading.get_ident() == self._main_thread_id:
            return callback()
        request = _MainThreadRequest(callback=callback)
        self._request_queue.put(request)
        if not request.event.wait(timeout=self._REQUEST_TIMEOUT_S):
            raise TimeoutError("Timed out waiting for the Isaac Kit main thread.")
        if request.error is not None:
            raise RuntimeError(str(request.error)) from request.error
        return request.result

    def _ensure_main_thread(self) -> None:
        if threading.get_ident() != self._main_thread_id:
            raise RuntimeError("Isaac Sim backend operations must run on the Kit main thread.")

    def _wait_for_arm_target(self, target_arm: np.ndarray, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            current_arm = self.get_joint_state()["pos"]
            if np.max(np.abs(current_arm - target_arm)) <= self._ARM_SETTLE_TOL_RAD:
                return
            time.sleep(min(0.02, self._control_period_s))
        current_arm = self.get_joint_state()["pos"]
        max_err = float(np.max(np.abs(current_arm - target_arm)))
        raise TimeoutError(
            f"Timed out waiting for Isaac Sim arm to settle. max_err_rad={max_err:.4f}"
        )

    def _wait_for_gripper_target(self, target_value: float, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            current_value = self.get_gripper_pos()
            if current_value is not None and abs(current_value - target_value) <= self._GRIPPER_SETTLE_TOL:
                return
            time.sleep(min(0.02, self._control_period_s))
        current_value = self.get_gripper_pos()
        raise TimeoutError(
            f"Timed out waiting for Isaac Sim gripper to settle. "
            f"target={target_value:.3f} current={current_value}"
        )
