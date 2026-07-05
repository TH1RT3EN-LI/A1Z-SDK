"""Isaac Sim-backed A1Z robot backend."""

from __future__ import annotations

import os
import queue
import threading
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import carb
import numpy as np
import omni.physx
import omni.usd
from isaacsim.core.api import World
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.utils.types import ArticulationAction
from omni.physx import get_physx_simulation_interface
from omni.physx.bindings._physx import ContactEventType
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics
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


@dataclass
class _SimGraspState:
    grasp_state: str = "idle"
    attached_object_path: Optional[str] = None
    attachment_joint_path: Optional[str] = None
    target_prim_path: Optional[str] = None
    target_body_path: Optional[str] = None
    last_contact_time: Optional[float] = None
    last_failure_reason: Optional[str] = None


class IsaacSimArmRobot:
    """Drive the imported A1Z articulation from inside the Isaac Kit thread."""

    _REQUEST_TIMEOUT_S = 120.0
    _ARM_SETTLE_TOL_RAD = np.deg2rad(0.75)
    _ARM_FORCE_SNAP_TOL_RAD = np.deg2rad(6.0)
    _ARM_LEAD_JOINT_SNAP_TOL_RAD = np.deg2rad(5.0)
    _ARM_WRIST_JOINT_SNAP_TOL_RAD = np.deg2rad(70.0)
    _ARM_POST_MOVE_WRIST_RECOVERY_TOL_RAD = np.deg2rad(10.0)
    _ARM_STAGE_WRIST_DELTA_RAD = np.deg2rad(12.0)
    _ARM_STAGE_SPEED_RAD_S = 0.30
    _GRIPPER_SETTLE_TOL = 0.03
    _GRASP_ATTACH_REQUIRED_CONTACT_COUNT = 3
    _GRASP_ATTACH_CLOSED_TOL = 0.05
    _GRASP_ATTACH_FULL_CLOSE_EXTRA_TIMEOUT_S = 4.0
    _GRASP_ATTACH_FULL_CLOSE_MIN_TIMEOUT_S = 6.0
    _DEFAULT_LEFT_CONTACT_SENSOR_LOCAL_OFFSET_M = np.array((0.100, 0.048, 0.000), dtype=np.float64)
    _DEFAULT_RIGHT_CONTACT_SENSOR_LOCAL_OFFSET_M = np.array((0.100, -0.048, 0.000), dtype=np.float64)

    @staticmethod
    def _flatten_gain_array(values: Any) -> np.ndarray:
        arr = np.asarray(values, dtype=np.float64)
        if arr.ndim == 0:
            return arr.reshape(1)
        if arr.ndim > 1:
            arr = arr.reshape(-1)
        return arr

    @classmethod
    def _load_contact_sensor_offset(
        cls,
        env_name: str,
        default: np.ndarray,
    ) -> np.ndarray:
        raw = os.environ.get(env_name)
        if raw is None or raw.strip() == "":
            return default.copy()
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 3:
            carb.log_warn(
                f"A1Z Isaac ignored invalid {env_name}={raw!r}; expected three comma-separated floats."
            )
            return default.copy()
        try:
            return np.asarray([float(part) for part in parts], dtype=np.float64).reshape(3)
        except ValueError:
            carb.log_warn(
                f"A1Z Isaac ignored invalid {env_name}={raw!r}; expected three comma-separated floats."
            )
            return default.copy()

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
        self._gripper_soft_kp = self._gripper_kp.copy() * 0.15
        self._gripper_soft_kd = self._gripper_kd.copy() * 0.35
        self._gripper_soft_max_effort = np.maximum(self._gripper_max_effort.copy() * 0.20, np.array([8.0, 8.0], dtype=np.float64))
        self._gripper_hold_kp = self._gripper_kp.copy() * 0.08
        self._gripper_hold_kd = self._gripper_kd.copy() * 0.25
        self._gripper_hold_max_effort = np.maximum(self._gripper_max_effort.copy() * 0.10, np.array([4.0, 4.0], dtype=np.float64))

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
        self._arm_joint_paths: list[str] = []
        self._gripper_joint_indices = np.array([], dtype=np.int64)
        self._gripper_joint_paths: list[str] = []
        self._last_control_action_time = 0.0
        self._last_gripper_action_time = 0.0
        self._last_hard_limit_log_time = 0.0

        self._gripper_open_value = 1.0
        self._gripper_left_open = 0.048
        self._gripper_left_closed = 0.0
        self._gripper_right_open = -0.048
        self._gripper_right_closed = 0.0
        self._gripper_carrier_body_path = ""
        self._left_finger_body_path = ""
        self._right_finger_body_path = ""
        self._left_contact_sensor_local_offset = self._load_contact_sensor_offset(
            "A1Z_LEFT_CONTACT_SENSOR_OFFSET_XYZ_M",
            self._DEFAULT_LEFT_CONTACT_SENSOR_LOCAL_OFFSET_M,
        )
        self._right_contact_sensor_local_offset = self._load_contact_sensor_offset(
            "A1Z_RIGHT_CONTACT_SENSOR_OFFSET_XYZ_M",
            self._DEFAULT_RIGHT_CONTACT_SENSOR_LOCAL_OFFSET_M,
        )
        self._contact_sensor_handles: dict[str, Any] = {}
        self._contact_sensor_backend: Optional[str] = None
        self._sim_grasp_state = _SimGraspState()

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
        self._ensure_gripper_contact_sensors()
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
        gripper_target_value = float(self._gripper_target_value)
        gripper_target_dofs = None
        gripper_current_dofs = None
        if self._with_gripper and self._gripper_joint_indices.size == 2:
            gripper_target_dofs = self._normalized_to_gripper_dofs(gripper_target_value).copy()
            with self._state_lock:
                gripper_current_dofs = self._full_pos[self._gripper_joint_indices].copy()
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
            "gripper_joint_paths": list(self._gripper_joint_paths),
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
            "gripper_target_value": gripper_target_value,
            "gripper_target_dofs": gripper_target_dofs,
            "gripper_current_dofs": gripper_current_dofs,
            "gripper_carrier_body_path": self._gripper_carrier_body_path,
            "left_finger_body_path": self._left_finger_body_path,
            "right_finger_body_path": self._right_finger_body_path,
            "left_contact_sensor_offset_m": self._left_contact_sensor_local_offset.copy(),
            "right_contact_sensor_offset_m": self._right_contact_sensor_local_offset.copy(),
            "sim_grasp_state": self.get_sim_grasp_status(),
            "control_mode": "gravity_comp_effort" if self.zero_gravity_mode else "position_hold",
        }

    def command_gripper(self, value: float) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if not self._with_gripper:
            raise RuntimeError("No gripper attached. Start the backend with gripper enabled.")
        value = float(np.clip(value, 0.0, 1.0))
        if self._sim_grasp_state.attached_object_path and value > float(self._gripper_open_value) + 1e-3:
            self._run_on_main_thread(lambda: self._release_attached_object_impl(open_gripper=False, timeout_s=2.0))
        self._run_on_main_thread(lambda: self._set_gripper_target(value))
        try:
            self._wait_for_gripper_target(value, timeout_s=2.0)
        except TimeoutError as exc:
            target_dofs = self._normalized_to_gripper_dofs(value)
            carb.log_warn(
                "A1Z Isaac gripper target did not settle via controller; "
                f"forcing joint positions target={np.round(target_dofs, 6).tolist()}"
            )
            self._run_on_main_thread(lambda: self._force_gripper_positions(target_dofs))
            try:
                self._wait_for_gripper_target(value, timeout_s=0.75)
            except TimeoutError:
                raise exc

    def get_gripper_pos(self) -> Optional[float]:
        if not self._with_gripper:
            return None
        with self._state_lock:
            return float(self._gripper_open_value)

    def get_sim_grasp_status(self) -> Dict[str, Any]:
        return {
            "has_attached_object": bool(self._sim_grasp_state.attached_object_path),
            "attached_object_path": self._sim_grasp_state.attached_object_path,
            "attachment_joint_path": self._sim_grasp_state.attachment_joint_path,
            "target_prim_path": self._sim_grasp_state.target_prim_path,
            "target_body_path": self._sim_grasp_state.target_body_path,
            "grasp_state": self._sim_grasp_state.grasp_state,
            "last_contact_time": self._sim_grasp_state.last_contact_time,
            "last_failure_reason": self._sim_grasp_state.last_failure_reason,
        }

    def grasp_close_and_attach(
        self,
        target_prim_path: str = "",
        *,
        timeout_s: float = 2.0,
        contact_window_s: float = 0.15,
        require_bilateral_contact: bool = True,
    ) -> Dict[str, Any]:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if not self._with_gripper:
            raise RuntimeError("No gripper attached. Start the backend with gripper enabled.")
        return self._run_on_main_thread(
            lambda: self._grasp_close_and_attach_impl(
                target_prim_path=str(target_prim_path or ""),
                timeout_s=float(timeout_s),
                contact_window_s=float(contact_window_s),
                require_bilateral_contact=bool(require_bilateral_contact),
            )
        )

    def release_attached_object(
        self,
        *,
        open_gripper: bool = True,
        timeout_s: float = 2.0,
    ) -> Dict[str, Any]:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        return self._run_on_main_thread(
            lambda: self._release_attached_object_impl(
                open_gripper=bool(open_gripper),
                timeout_s=float(timeout_s),
            )
        )

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

        kp_arr = None if kp is None else np.asarray(kp, dtype=np.float64).reshape(-1)[: self._num_joints]
        kd_arr = None if kd is None else np.asarray(kd, dtype=np.float64).reshape(-1)[: self._num_joints]
        try:
            self._execute_move_target_once(
                arm_target=arm_target,
                speed=speed,
                kp=kp_arr,
                kd=kd_arr,
                gripper_target=gripper_target,
            )
        except TimeoutError as exc:
            raise exc

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

    def _execute_move_target_once(
        self,
        *,
        arm_target: np.ndarray,
        speed: float,
        kp: Optional[np.ndarray],
        kd: Optional[np.ndarray],
        gripper_target: Optional[float],
    ) -> None:
        current_arm = self.get_joint_state()["pos"]
        duration_estimate_s = self._trajectory_duration_for_limits(current_arm, arm_target, speed)
        done_event = threading.Event()

        self._run_on_main_thread(
            lambda: self._start_trajectory(
                target_arm=arm_target,
                speed=speed,
                kp=kp,
                kd=kd,
                done_event=done_event,
                gripper_target=gripper_target,
            )
        )

        wait_timeout_s = max(5.0, duration_estimate_s + 5.0)
        if not done_event.wait(timeout=wait_timeout_s):
            raise TimeoutError("Timed out waiting for Isaac Sim arm motion to complete.")
        self._wait_for_arm_target(arm_target, timeout_s=max(2.0, wait_timeout_s))

    def _try_staged_move_recovery(
        self,
        *,
        arm_target: np.ndarray,
        speed: float,
        kp: Optional[np.ndarray],
        kd: Optional[np.ndarray],
        gripper_target: Optional[float],
    ) -> bool:
        current_arm = self.get_joint_state()["pos"]
        waypoints: list[np.ndarray] = []

        # When simultaneous 6-axis motion fails in Isaac, decouple wrist closure
        # from the lead joints to keep the arm on the intended configuration branch.
        wp = current_arm.copy()
        wp[:4] = arm_target[:4]
        if not np.allclose(wp, current_arm, atol=1e-4):
            waypoints.append(wp.copy())

        wp_j5 = wp.copy()
        wp_j5[4] = arm_target[4]
        if not np.allclose(wp_j5, waypoints[-1] if waypoints else current_arm, atol=1e-4):
            waypoints.append(wp_j5.copy())

        wp_final = wp_j5.copy()
        wp_final[5] = arm_target[5]
        if not np.allclose(wp_final, waypoints[-1] if waypoints else current_arm, atol=1e-4):
            waypoints.append(wp_final.copy())

        stage_speed = min(float(speed), 0.30)
        for index, waypoint in enumerate(waypoints):
            try:
                self._execute_move_target_once(
                    arm_target=waypoint,
                    speed=stage_speed,
                    kp=kp,
                    kd=kd,
                    gripper_target=gripper_target if index == len(waypoints) - 1 else None,
                )
            except TimeoutError as stage_exc:
                carb.log_warn(
                    "A1Z Isaac staged move recovery failed "
                    f"stage={index} target_deg={np.round(np.rad2deg(waypoint), 2).tolist()} "
                    f"error={stage_exc}"
                )
                return False
        return True

    def _needs_wrist_recovery(self, arm_target: np.ndarray) -> bool:
        current_arm = self.get_joint_state()["pos"]
        joint_err = np.abs(np.asarray(current_arm, dtype=np.float64) - np.asarray(arm_target, dtype=np.float64))
        if joint_err.shape[0] <= 4:
            return False
        wrist_max_err = float(np.max(joint_err[4:]))
        lead_max_err = float(np.max(joint_err[:4])) if joint_err.shape[0] >= 4 else wrist_max_err
        return lead_max_err <= self._ARM_LEAD_JOINT_SNAP_TOL_RAD and wrist_max_err >= self._ARM_POST_MOVE_WRIST_RECOVERY_TOL_RAD

    def _should_prefer_staged_move(
        self,
        *,
        current_arm: np.ndarray,
        arm_target: np.ndarray,
        speed: float,
    ) -> bool:
        if speed < 0.20:
            return False
        joint_delta = np.abs(np.asarray(arm_target, dtype=np.float64) - np.asarray(current_arm, dtype=np.float64))
        wrist_delta = float(np.max(joint_delta[4:])) if joint_delta.shape[0] > 4 else 0.0
        return wrist_delta >= self._ARM_STAGE_WRIST_DELTA_RAD

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

        self._resolve_arm_joint_paths()
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
        self._resolve_gripper_joint_paths()

    def _resolve_arm_joint_paths(self) -> None:
        self._arm_joint_paths = []
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return

        articulation_path = Sdf.Path(self._articulation_root_prim)
        parent_path = articulation_path.GetParentPath()
        grandparent_path = parent_path.GetParentPath() if parent_path != Sdf.Path.absoluteRootPath else parent_path

        candidate_roots: list[str] = []
        for base in (
            self._articulation_root_prim,
            str(parent_path),
            str(grandparent_path),
            "/World/A1Z_G1Z",
            "/A1Z_G1Z",
        ):
            if not base or base == "/":
                continue
            candidate_roots.extend(
                (
                    f"{base}/Physics",
                    f"{base}/joints",
                    f"{base}/root_joint/joints",
                )
            )

        seen: set[str] = set()
        unique_roots: list[str] = []
        for root in candidate_roots:
            if root in seen:
                continue
            seen.add(root)
            unique_roots.append(root)

        for joint_name in self._arm_joint_names:
            resolved = ""
            for root in unique_roots:
                candidate = f"{root}/{joint_name}"
                if stage.GetPrimAtPath(candidate).IsValid():
                    resolved = candidate
                    break
            self._arm_joint_paths.append(resolved)

    def _resolve_gripper_joint_paths(self) -> None:
        self._gripper_joint_paths = []
        if not self._with_gripper:
            return

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return

        articulation_path = Sdf.Path(self._articulation_root_prim)
        parent_path = articulation_path.GetParentPath()
        grandparent_path = parent_path.GetParentPath() if parent_path != Sdf.Path.absoluteRootPath else parent_path

        candidate_roots: list[str] = []
        for base in (
            self._articulation_root_prim,
            str(parent_path),
            str(grandparent_path),
            "/World/A1Z_G1Z",
            "/A1Z_G1Z",
        ):
            if not base or base == "/":
                continue
            candidate_roots.extend(
                (
                    f"{base}/Physics",
                    f"{base}/joints",
                    f"{base}/root_joint/joints",
                )
            )

        seen: set[str] = set()
        unique_roots: list[str] = []
        for root in candidate_roots:
            if root in seen:
                continue
            seen.add(root)
            unique_roots.append(root)

        for joint_name in self._gripper_joint_names:
            resolved = ""
            for root in unique_roots:
                candidate = f"{root}/{joint_name}"
                if stage.GetPrimAtPath(candidate).IsValid():
                    resolved = candidate
                    break
            self._gripper_joint_paths.append(resolved)

    def _resolve_named_descendant_path(self, root_path: str, prim_name: str) -> str:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return ""
        root_prim = stage.GetPrimAtPath(root_path)
        if not root_prim.IsValid():
            return ""
        for prim in Usd.PrimRange(root_prim):
            if prim.GetName() == prim_name:
                return str(prim.GetPath())
        return ""

    def _find_rigid_body_ancestor_path(self, prim_path: str) -> str:
        stage = omni.usd.get_context().get_stage()
        if stage is None or not prim_path:
            return ""
        current = Sdf.Path(prim_path)
        while current and current != Sdf.Path.absoluteRootPath:
            prim = stage.GetPrimAtPath(current)
            if prim.IsValid():
                enabled_attr = prim.GetAttribute("physics:rigidBodyEnabled")
                if enabled_attr.IsValid():
                    if bool(enabled_attr.Get()):
                        return str(current)
                elif prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    return str(current)
            current = current.GetParentPath()
        return ""

    def _ensure_gripper_structure_paths(self) -> None:
        if self._left_finger_body_path and self._right_finger_body_path and self._gripper_carrier_body_path:
            return
        left_link_path = self._resolve_named_descendant_path(self._articulation_root_prim, "gripper_finger_left_link")
        right_link_path = self._resolve_named_descendant_path(self._articulation_root_prim, "gripper_finger_rIght_link")
        carrier_link_path = self._resolve_named_descendant_path(self._articulation_root_prim, "arm_link6")
        self._left_finger_body_path = self._find_rigid_body_ancestor_path(left_link_path)
        self._right_finger_body_path = self._find_rigid_body_ancestor_path(right_link_path)
        self._gripper_carrier_body_path = self._find_rigid_body_ancestor_path(carrier_link_path)

    def _contact_sensor_local_offset(self, sensor_name: str) -> np.ndarray:
        if sensor_name == "a1z_left_contact_sensor":
            return self._left_contact_sensor_local_offset.copy()
        if sensor_name == "a1z_right_contact_sensor":
            return self._right_contact_sensor_local_offset.copy()
        return np.zeros(3, dtype=np.float64)

    def _set_sensor_local_translation(self, sensor_path: str, translation: np.ndarray) -> None:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        prim = stage.GetPrimAtPath(sensor_path)
        if not prim.IsValid() or not prim.IsA(UsdGeom.Xformable):
            return
        xformable = UsdGeom.Xformable(prim)
        translate_op = None
        for op in xformable.GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                translate_op = op
                break
        if translate_op is None:
            translate_op = xformable.AddTranslateOp()
        translate_op.Set(Gf.Vec3d(*np.asarray(translation, dtype=np.float64).reshape(3).tolist()))

    def _ensure_contact_sensor_for_body(
        self,
        body_path: str,
        sensor_name: str,
        *,
        local_translation: Optional[np.ndarray] = None,
    ) -> str:
        if not body_path:
            return ""
        sensor_path = f"{body_path}/{sensor_name}"
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return ""
        translation = (
            np.asarray(local_translation, dtype=np.float64).reshape(3)
            if local_translation is not None
            else self._contact_sensor_local_offset(sensor_name)
        )
        prim = stage.GetPrimAtPath(sensor_path)
        if not prim.IsValid():
            try:
                backend = self._detect_contact_sensor_backend()
                if backend == "experimental":
                    from isaacsim.sensors.experimental.physics import Contact

                    Contact.create(sensor_path, min_threshold=0.0, max_threshold=1.0e9)
                elif backend == "physics":
                    from isaacsim.sensors.physics import ContactSensor

                    sensor = ContactSensor(
                        sensor_path,
                        name=sensor_name,
                        translation=translation,
                        min_threshold=0.0,
                        max_threshold=1.0e9,
                        radius=-1,
                    )
                    sensor.add_raw_contact_data_to_frame()
                    self._contact_sensor_handles[sensor_path] = sensor
                else:
                    raise RuntimeError("No supported Isaac contact sensor backend is available.")
            except Exception as exc:
                carb.log_warn(f"A1Z Isaac could not create contact sensor at {sensor_path}: {exc}")
                return ""
        self._set_sensor_local_translation(sensor_path, translation)
        if sensor_path not in self._contact_sensor_handles and self._detect_contact_sensor_backend() == "physics":
            try:
                from isaacsim.sensors.physics import ContactSensor

                sensor = ContactSensor(
                    sensor_path,
                    name=sensor_name,
                    translation=translation,
                )
                sensor.add_raw_contact_data_to_frame()
                self._contact_sensor_handles[sensor_path] = sensor
            except Exception as exc:
                carb.log_warn(f"A1Z Isaac could not initialize contact sensor handle at {sensor_path}: {exc}")
                return ""
        return sensor_path

    def _ensure_gripper_contact_sensors(self) -> None:
        self._ensure_gripper_structure_paths()
        self._ensure_contact_sensor_for_body(
            self._left_finger_body_path,
            "a1z_left_contact_sensor",
            local_translation=self._left_contact_sensor_local_offset,
        )
        self._ensure_contact_sensor_for_body(
            self._right_finger_body_path,
            "a1z_right_contact_sensor",
            local_translation=self._right_contact_sensor_local_offset,
        )

    def _detect_contact_sensor_backend(self) -> str:
        if self._contact_sensor_backend is not None:
            return self._contact_sensor_backend
        try:
            from isaacsim.sensors.experimental.physics import ContactSensor as _ExperimentalContactSensor

            del _ExperimentalContactSensor
            self._contact_sensor_backend = "experimental"
            return self._contact_sensor_backend
        except Exception:
            pass
        try:
            from isaacsim.sensors.physics import ContactSensor as _PhysicsContactSensor

            del _PhysicsContactSensor
            self._contact_sensor_backend = "physics"
            return self._contact_sensor_backend
        except Exception:
            pass
        self._contact_sensor_backend = "unavailable"
        return self._contact_sensor_backend

    def _get_world_transform(self, prim_path: str) -> Gf.Matrix4d:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is unavailable.")
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid prim path: {prim_path}")
        return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())

    @staticmethod
    def _matrix_to_pose_components(transform: Gf.Matrix4d) -> tuple[Gf.Vec3f, Gf.Quatf]:
        translation = transform.ExtractTranslation()
        rotation = transform.ExtractRotation().GetQuat()
        return (
            Gf.Vec3f(float(translation[0]), float(translation[1]), float(translation[2])),
            Gf.Quatf(float(rotation.GetReal()), float(rotation.GetImaginary()[0]), float(rotation.GetImaginary()[1]), float(rotation.GetImaginary()[2])),
        )

    def _resolve_target_rigid_body_path(self, target_prim_path: str) -> str:
        if not target_prim_path:
            return ""
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return ""
        target_prim = stage.GetPrimAtPath(target_prim_path)
        if not target_prim.IsValid():
            return ""
        current = target_prim
        while current and current.IsValid():
            enabled_attr = current.GetAttribute("physics:rigidBodyEnabled")
            if enabled_attr.IsValid():
                if bool(enabled_attr.Get()):
                    return str(current.GetPath())
            elif current.HasAPI(UsdPhysics.RigidBodyAPI):
                return str(current.GetPath())
            current = current.GetParent()
        for prim in Usd.PrimRange(target_prim):
            enabled_attr = prim.GetAttribute("physics:rigidBodyEnabled")
            if enabled_attr.IsValid():
                if bool(enabled_attr.Get()):
                    return str(prim.GetPath())
            elif prim.HasAPI(UsdPhysics.RigidBodyAPI):
                return str(prim.GetPath())
        return ""

    def _resolve_contact_body_path(self, prim_path: str) -> str:
        resolved = self._resolve_target_rigid_body_path(str(prim_path or ""))
        return resolved or str(prim_path or "")

    def _cleanup_stale_attachment_joints(self) -> None:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        root = stage.GetPrimAtPath("/World/SimulationGraspAttachments")
        if not root.IsValid():
            return
        for prim in list(root.GetChildren()):
            try:
                stage.RemovePrim(prim.GetPath())
            except Exception as exc:
                carb.log_warn(f"A1Z Isaac failed to remove stale attachment joint {prim.GetPath()}: {exc}")

    def _set_gripper_drive_profile(self, *, kp: np.ndarray, kd: np.ndarray, max_effort: np.ndarray) -> None:
        if not self._with_gripper or self._gripper_joint_indices.size != 2:
            return
        kp = np.asarray(kp, dtype=np.float64).reshape(-1)[:2]
        kd = np.asarray(kd, dtype=np.float64).reshape(-1)[:2]
        max_effort = np.asarray(max_effort, dtype=np.float64).reshape(-1)[:2]
        self._set_subset_gains(self._gripper_joint_indices, kp, kd)
        self._set_subset_max_efforts(self._gripper_joint_indices, max_effort)
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        for local_idx, joint_path in enumerate(self._gripper_joint_paths[:2]):
            if not joint_path:
                continue
            prim = stage.GetPrimAtPath(joint_path)
            if not prim.IsValid():
                continue
            drive = UsdPhysics.DriveAPI.Get(prim, "linear")
            if not drive:
                drive = UsdPhysics.DriveAPI.Apply(prim, "linear")
            drive.GetStiffnessAttr().Set(float(kp[local_idx]))
            drive.GetDampingAttr().Set(float(kd[local_idx]))
            drive.GetMaxForceAttr().Set(float(max_effort[local_idx]))

    def _set_gripper_soft_grasp_gains(self) -> None:
        self._set_gripper_drive_profile(
            kp=self._gripper_soft_kp,
            kd=self._gripper_soft_kd,
            max_effort=self._gripper_soft_max_effort,
        )

    def _set_gripper_hold_gains(self) -> None:
        self._set_gripper_drive_profile(
            kp=self._gripper_hold_kp,
            kd=self._gripper_hold_kd,
            max_effort=self._gripper_hold_max_effort,
        )

    def _set_gripper_default_gains(self) -> None:
        self._set_gripper_drive_profile(
            kp=self._gripper_kp,
            kd=self._gripper_kd,
            max_effort=self._gripper_max_effort,
        )

    def _read_contact_sensor_records(self, sensor_path: str) -> list[dict[str, object]]:
        if not sensor_path:
            return []
        try:
            backend = self._detect_contact_sensor_backend()
            if backend == "experimental":
                from isaacsim.sensors.experimental.physics import ContactSensor

                sensor = ContactSensor(sensor_path)
                return list(sensor.get_raw_data())
            if backend == "physics":
                sensor = self._contact_sensor_handles.get(sensor_path)
                if sensor is None:
                    from isaacsim.sensors.physics import ContactSensor

                    sensor = ContactSensor(sensor_path)
                    sensor.add_raw_contact_data_to_frame()
                    self._contact_sensor_handles[sensor_path] = sensor
                frame = sensor.get_current_frame() or {}
                contacts = frame.get("contacts", []) or []
                return list(contacts)
            raise RuntimeError("No supported Isaac contact sensor backend is available.")
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac failed reading contact sensor {sensor_path}: {exc}")
            return []

    def _normalize_contact_records(self, raw_records: list[dict[str, object]]) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for record in raw_records:
            body0 = str(record.get("body0", "") or "")
            body1 = str(record.get("body1", "") or "")
            normalized.append(
                {
                    "body0": body0,
                    "body1": body1,
                    "position": record.get("position"),
                    "normal": record.get("normal"),
                    "impulse": record.get("impulse"),
                    "dt": float(record.get("dt", 0.0) or 0.0),
                }
            )
        return normalized

    def _read_body_contact_report_records(self) -> list[dict[str, object]]:
        try:
            contact_headers, contact_data = get_physx_simulation_interface().get_contact_report()
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac failed reading PhysX contact report: {exc}")
            return []

        records: list[dict[str, object]] = []
        try:
            from pxr import PhysicsSchemaTools
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac failed importing PhysicsSchemaTools for contact report: {exc}")
            return records

        for header in contact_headers:
            event_type = int(getattr(header, "type", 0))
            if event_type not in (int(ContactEventType.CONTACT_FOUND), int(ContactEventType.CONTACT_PERSIST)):
                continue
            actor0 = str(PhysicsSchemaTools.intToSdfPath(header.actor0))
            actor1 = str(PhysicsSchemaTools.intToSdfPath(header.actor1))
            collider0 = str(PhysicsSchemaTools.intToSdfPath(header.collider0))
            collider1 = str(PhysicsSchemaTools.intToSdfPath(header.collider1))
            contact_data_offset = int(getattr(header, "contact_data_offset", 0))
            num_contact_data = int(getattr(header, "num_contact_data", 0))
            for index in range(contact_data_offset, contact_data_offset + num_contact_data):
                datum = contact_data[index]
                records.append(
                    {
                        "body0": actor0,
                        "body1": actor1,
                        "collider0": collider0,
                        "collider1": collider1,
                        "position": getattr(datum, "position", None),
                        "normal": getattr(datum, "normal", None),
                        "impulse": getattr(datum, "impulse", None),
                        "separation": float(getattr(datum, "separation", 0.0) or 0.0),
                        "face_index0": int(getattr(datum, "face_index0", -1)),
                        "face_index1": int(getattr(datum, "face_index1", -1)),
                    }
                )
        return records

    def _poll_grasp_body_contacts(self) -> dict[str, list[dict[str, object]]]:
        self._ensure_gripper_structure_paths()
        raw_records = self._read_body_contact_report_records()
        left_records: list[dict[str, object]] = []
        right_records: list[dict[str, object]] = []
        for record in raw_records:
            body0 = str(record.get("body0", "") or "")
            body1 = str(record.get("body1", "") or "")
            if body0 == self._left_finger_body_path or body1 == self._left_finger_body_path:
                left_records.append(record)
            if body0 == self._right_finger_body_path or body1 == self._right_finger_body_path:
                right_records.append(record)
        return {
            "left": left_records,
            "right": right_records,
        }

    def _poll_grasp_contacts(self) -> dict[str, list[dict[str, object]]]:
        self._ensure_gripper_structure_paths()
        left_sensor = self._ensure_contact_sensor_for_body(
            self._left_finger_body_path,
            "a1z_left_contact_sensor",
            local_translation=self._left_contact_sensor_local_offset,
        )
        right_sensor = self._ensure_contact_sensor_for_body(
            self._right_finger_body_path,
            "a1z_right_contact_sensor",
            local_translation=self._right_contact_sensor_local_offset,
        )
        return {
            "left": self._normalize_contact_records(self._read_contact_sensor_records(left_sensor)),
            "right": self._normalize_contact_records(self._read_contact_sensor_records(right_sensor)),
        }

    def _contact_body_counterpart(self, record: dict[str, object], sensor_body_path: str) -> str:
        body0 = str(record.get("body0", "") or "")
        body1 = str(record.get("body1", "") or "")
        if body0 == sensor_body_path:
            return body1
        if body1 == sensor_body_path:
            return body0
        if sensor_body_path.endswith(body0):
            return body1
        if sensor_body_path.endswith(body1):
            return body0
        return body1 or body0

    def _collect_contact_candidates(
        self,
        records: list[dict[str, object]],
        *,
        sensor_body_path: str,
        other_finger_body_path: str,
    ) -> tuple[list[str], list[str], list[dict[str, object]]]:
        raw_candidates: list[str] = []
        rigid_body_candidates: list[str] = []
        raw_details: list[dict[str, object]] = []
        for record in records:
            candidate = self._contact_body_counterpart(record, sensor_body_path)
            if not candidate:
                continue
            rigid_body_candidate = self._resolve_contact_body_path(candidate)
            if rigid_body_candidate == other_finger_body_path or rigid_body_candidate == self._gripper_carrier_body_path:
                continue
            raw_candidates.append(candidate)
            rigid_body_candidates.append(rigid_body_candidate)
            raw_details.append(
                {
                    "candidate": candidate,
                    "rigid_body_candidate": rigid_body_candidate,
                    "body0": str(record.get("body0", "") or ""),
                    "body1": str(record.get("body1", "") or ""),
                    "collider0": str(record.get("collider0", "") or ""),
                    "collider1": str(record.get("collider1", "") or ""),
                }
            )
        return raw_candidates, rigid_body_candidates, raw_details

    def _contact_satisfies_attach(
        self,
        contacts: dict[str, list[dict[str, object]]],
        *,
        target_body_path: str,
        require_bilateral_contact: bool,
    ) -> tuple[bool, str, dict[str, object]]:
        left_raw_candidates, left_candidates, left_contact_details = self._collect_contact_candidates(
            contacts.get("left", []),
            sensor_body_path=self._left_finger_body_path,
            other_finger_body_path=self._right_finger_body_path,
        )
        right_raw_candidates, right_candidates, right_contact_details = self._collect_contact_candidates(
            contacts.get("right", []),
            sensor_body_path=self._right_finger_body_path,
            other_finger_body_path=self._left_finger_body_path,
        )

        chosen = ""
        if target_body_path:
            left_has_target = target_body_path in left_candidates
            right_has_target = target_body_path in right_candidates
            if require_bilateral_contact:
                if left_has_target and right_has_target:
                    chosen = target_body_path
            else:
                if left_has_target or right_has_target:
                    chosen = target_body_path
        else:
            for candidate in left_candidates:
                if require_bilateral_contact:
                    if candidate in right_candidates:
                        chosen = candidate
                        break
                else:
                    chosen = candidate
                    break
            if not chosen and not require_bilateral_contact and right_candidates:
                    chosen = right_candidates[0]

        summary = {
            "left_raw_contacts": left_raw_candidates,
            "right_raw_contacts": right_raw_candidates,
            "left_contacts": left_candidates,
            "right_contacts": right_candidates,
            "left_contact_details": left_contact_details,
            "right_contact_details": right_contact_details,
            "target_body_path": target_body_path or None,
            "require_bilateral_contact": bool(require_bilateral_contact),
        }
        return bool(chosen), chosen, summary

    def _create_attachment_joint(self, *, joint_path: str, body0_path: str, body1_path: str) -> str:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is unavailable.")
        root = stage.GetPrimAtPath("/World/SimulationGraspAttachments")
        if not root.IsValid():
            stage.DefinePrim("/World/SimulationGraspAttachments", "Xform")
        carrier_world = self._get_world_transform(body0_path)
        target_world = self._get_world_transform(body1_path)
        carrier_translation, carrier_rotation = self._matrix_to_pose_components(carrier_world)
        target_translation, target_rotation = self._matrix_to_pose_components(target_world)
        joint = UsdPhysics.FixedJoint.Define(stage, joint_path)
        joint.CreateBody0Rel().SetTargets([Sdf.Path(body0_path)])
        joint.CreateBody1Rel().SetTargets([Sdf.Path(body1_path)])
        joint.CreateLocalPos0Attr().Set(carrier_translation)
        joint.CreateLocalPos1Attr().Set(target_translation)
        joint.CreateLocalRot0Attr().Set(carrier_rotation)
        joint.CreateLocalRot1Attr().Set(target_rotation)
        return joint_path

    def _remove_attachment_joint(self, joint_path: str) -> None:
        if not joint_path:
            return
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        if stage.GetPrimAtPath(joint_path).IsValid():
            stage.RemovePrim(joint_path)

    def _grasp_close_and_attach_impl(
        self,
        *,
        target_prim_path: str,
        timeout_s: float,
        contact_window_s: float,
        require_bilateral_contact: bool,
    ) -> Dict[str, Any]:
        self._ensure_gripper_structure_paths()
        self._cleanup_stale_attachment_joints()
        self._sim_grasp_state = _SimGraspState(
            grasp_state="closing_for_grasp",
            target_prim_path=target_prim_path or None,
            target_body_path=self._resolve_target_rigid_body_path(target_prim_path) or None,
        )
        self._set_gripper_soft_grasp_gains()
        self._set_gripper_target(0.0)
        attach_summary: dict[str, object] = {}
        chosen_body_path = ""
        soft_close_timeout_s = max(0.1, float(timeout_s))
        start_time = time.monotonic()
        soft_close_deadline = start_time + soft_close_timeout_s
        full_close_timeout_s = max(
            soft_close_timeout_s + self._GRASP_ATTACH_FULL_CLOSE_EXTRA_TIMEOUT_S,
            self._GRASP_ATTACH_FULL_CLOSE_MIN_TIMEOUT_S,
        )
        full_close_deadline = start_time + full_close_timeout_s
        stable_count = 0
        required_count = self._GRASP_ATTACH_REQUIRED_CONTACT_COUNT
        last_body = ""
        close_phase = "soft_close"
        failure_reason = "grasp_contact_not_found"
        while time.monotonic() < full_close_deadline:
            self._apply_control_action()
            self._step_simulation_once(contact_window_s=contact_window_s, required_count=required_count)
            self._update_state_cache()
            current_open_value = float(self._gripper_open_value)
            body_contacts = self._poll_grasp_body_contacts()
            ok, body_path, summary = self._contact_satisfies_attach(
                body_contacts,
                target_body_path=str(self._sim_grasp_state.target_body_path or ""),
                require_bilateral_contact=require_bilateral_contact,
            )
            attach_summary = summary
            sensor_contacts = self._poll_grasp_contacts()
            sensor_ok, sensor_body_path, sensor_summary = self._contact_satisfies_attach(
                sensor_contacts,
                target_body_path=str(self._sim_grasp_state.target_body_path or ""),
                require_bilateral_contact=require_bilateral_contact,
            )
            attach_summary["sensor_contact_summary"] = sensor_summary
            attach_summary["sensor_contact_match"] = bool(sensor_ok)
            attach_summary["sensor_contact_body_path"] = sensor_body_path or None
            attach_summary["gripper_open_value"] = current_open_value
            attach_summary["close_phase"] = close_phase
            if ok:
                if body_path == last_body:
                    stable_count += 1
                else:
                    stable_count = 1
                    last_body = body_path
                self._sim_grasp_state.grasp_state = "contact_candidate"
                self._sim_grasp_state.last_contact_time = time.time()
                if stable_count >= required_count:
                    chosen_body_path = body_path
                    break
            else:
                stable_count = 0
                last_body = ""
            if self._is_gripper_near_closed(current_open_value):
                failure_reason = "fully_closed_without_contact"
                break
            if close_phase == "soft_close" and time.monotonic() >= soft_close_deadline:
                self._set_gripper_default_gains()
                close_phase = "default_close"
                self._sim_grasp_state.grasp_state = "closing_for_grasp_default"

        if not chosen_body_path:
            if failure_reason == "grasp_contact_not_found":
                current_open_value = float(self._gripper_open_value)
                if self._is_gripper_near_closed(current_open_value):
                    failure_reason = "fully_closed_without_contact"
                elif close_phase == "default_close":
                    failure_reason = "grasp_close_timeout_before_full_close"
            self._sim_grasp_state.grasp_state = "failed"
            self._sim_grasp_state.last_failure_reason = failure_reason
            self._set_gripper_default_gains()
            return {
                "success": False,
                "target_prim_path": target_prim_path or "",
                "attached_object_path": None,
                "attachment_joint_path": None,
                "contact_summary": attach_summary,
                "failure_reason": failure_reason,
                "timing": {
                    "soft_close_timeout_s": soft_close_timeout_s,
                    "full_close_timeout_s": full_close_timeout_s,
                },
            }

        joint_path = f"/World/SimulationGraspAttachments/{self._sim_grasp_state.target_prim_path or self._sim_grasp_state.target_body_path or 'auto'}".replace("//", "/")
        joint_path = joint_path.replace(":", "_").replace(".", "_")
        try:
            attachment_joint_path = self._create_attachment_joint(
                joint_path=joint_path,
                body0_path=self._gripper_carrier_body_path,
                body1_path=chosen_body_path,
            )
        except Exception as exc:
            self._sim_grasp_state.grasp_state = "failed"
            self._sim_grasp_state.last_failure_reason = "attach_creation_failed"
            self._set_gripper_default_gains()
            return {
                "success": False,
                "target_prim_path": target_prim_path or "",
                "attached_object_path": chosen_body_path,
                "attachment_joint_path": None,
                "contact_summary": attach_summary,
                "failure_reason": f"attach_creation_failed: {exc}",
                "timing": {},
            }

        current_gripper = float(self._gripper_open_value)
        self._set_gripper_target(current_gripper)
        self._set_gripper_hold_gains()
        self._step_simulation_once(contact_window_s=contact_window_s, required_count=required_count)
        self._update_state_cache()
        self._sim_grasp_state.grasp_state = "attached"
        self._sim_grasp_state.attached_object_path = chosen_body_path
        self._sim_grasp_state.attachment_joint_path = attachment_joint_path
        return {
            "success": True,
            "target_prim_path": target_prim_path or "",
            "attached_object_path": chosen_body_path,
            "attachment_joint_path": attachment_joint_path,
            "contact_summary": attach_summary,
            "failure_reason": None,
            "timing": {
                "soft_close_timeout_s": soft_close_timeout_s,
                "full_close_timeout_s": full_close_timeout_s,
            },
        }

    def _release_attached_object_impl(
        self,
        *,
        open_gripper: bool,
        timeout_s: float,
    ) -> Dict[str, Any]:
        del timeout_s
        joint_path = str(self._sim_grasp_state.attachment_joint_path or "")
        attached_object_path = self._sim_grasp_state.attached_object_path
        if joint_path:
            self._remove_attachment_joint(joint_path)
        self._sim_grasp_state = _SimGraspState(grasp_state="releasing")
        self._set_gripper_default_gains()
        if open_gripper and self._with_gripper:
            self._set_gripper_target(1.0)
        self._sim_grasp_state.grasp_state = "idle"
        return {
            "success": True,
            "released": True,
            "attached_object_path": attached_object_path,
            "attachment_joint_path": joint_path or None,
            "failure_reason": None,
        }

    def _step_simulation_once(self, *, contact_window_s: float, required_count: int) -> None:
        fallback_sleep_s = min(max(contact_window_s / max(required_count, 1), 0.01), 0.05)
        try:
            SimulationManager.step(render=False)
            return
        except Exception:
            pass
        try:
            if self._world is not None:
                self._world.step(render=False)
                return
        except Exception:
            pass
        time.sleep(fallback_sleep_s)

    def _is_gripper_near_closed(self, open_value: Optional[float] = None) -> bool:
        if open_value is None:
            open_value = float(self._gripper_open_value)
        return float(open_value) <= max(self._GRIPPER_SETTLE_TOL, self._GRASP_ATTACH_CLOSED_TOL)

    def _configure_gripper_drive_targets(self) -> None:
        if not self._with_gripper or len(self._gripper_joint_paths) != 2:
            return
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return

        for local_idx, joint_path in enumerate(self._gripper_joint_paths):
            if not joint_path:
                continue
            prim = stage.GetPrimAtPath(joint_path)
            if not prim.IsValid():
                continue
            drive = UsdPhysics.DriveAPI.Get(prim, "linear")
            if not drive:
                drive = UsdPhysics.DriveAPI.Apply(prim, "linear")

            if prim.HasAttribute("drive:linear:physics:type"):
                drive.GetTypeAttr().Set("acceleration")
            else:
                drive.CreateTypeAttr().Set("acceleration")
            if prim.HasAttribute("drive:linear:physics:stiffness"):
                drive.GetStiffnessAttr().Set(float(self._gripper_kp[local_idx]))
            else:
                drive.CreateStiffnessAttr().Set(float(self._gripper_kp[local_idx]))
            if prim.HasAttribute("drive:linear:physics:damping"):
                drive.GetDampingAttr().Set(float(self._gripper_kd[local_idx]))
            else:
                drive.CreateDampingAttr().Set(float(self._gripper_kd[local_idx]))
            if prim.HasAttribute("drive:linear:physics:maxForce"):
                drive.GetMaxForceAttr().Set(float(self._gripper_max_effort[local_idx]))
            else:
                drive.CreateMaxForceAttr().Set(float(self._gripper_max_effort[local_idx]))
            if prim.HasAttribute("drive:linear:physics:targetVelocity"):
                drive.GetTargetVelocityAttr().Set(0.0)
            else:
                drive.CreateTargetVelocityAttr().Set(0.0)
            if not prim.HasAttribute("drive:linear:physics:targetPosition"):
                drive.CreateTargetPositionAttr().Set(0.0)

    def _configure_arm_drive_params(
        self,
        arm_kp: np.ndarray,
        arm_kd: np.ndarray,
        arm_max_effort: np.ndarray,
    ) -> None:
        if len(self._arm_joint_paths) != self._num_joints:
            return
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return

        arm_kp = np.asarray(arm_kp, dtype=np.float64).reshape(-1)
        arm_kd = np.asarray(arm_kd, dtype=np.float64).reshape(-1)
        arm_max_effort = np.asarray(arm_max_effort, dtype=np.float64).reshape(-1)
        for local_idx, joint_path in enumerate(self._arm_joint_paths):
            if local_idx >= arm_kp.shape[0] or not joint_path:
                continue
            prim = stage.GetPrimAtPath(joint_path)
            if not prim.IsValid():
                continue
            drive = UsdPhysics.DriveAPI.Get(prim, "angular")
            if not drive:
                drive = UsdPhysics.DriveAPI.Apply(prim, "angular")

            if prim.HasAttribute("drive:angular:physics:type"):
                drive.GetTypeAttr().Set("acceleration")
            else:
                drive.CreateTypeAttr().Set("acceleration")
            if prim.HasAttribute("drive:angular:physics:stiffness"):
                drive.GetStiffnessAttr().Set(float(arm_kp[local_idx]))
            else:
                drive.CreateStiffnessAttr().Set(float(arm_kp[local_idx]))
            if prim.HasAttribute("drive:angular:physics:damping"):
                drive.GetDampingAttr().Set(float(arm_kd[local_idx]))
            else:
                drive.CreateDampingAttr().Set(float(arm_kd[local_idx]))
            if local_idx < arm_max_effort.shape[0]:
                if prim.HasAttribute("drive:angular:physics:maxForce"):
                    drive.GetMaxForceAttr().Set(float(arm_max_effort[local_idx]))
                else:
                    drive.CreateMaxForceAttr().Set(float(arm_max_effort[local_idx]))
            if prim.HasAttribute("drive:angular:physics:targetVelocity"):
                drive.GetTargetVelocityAttr().Set(0.0)
            else:
                drive.CreateTargetVelocityAttr().Set(0.0)
            if not prim.HasAttribute("drive:angular:physics:targetPosition"):
                drive.CreateTargetPositionAttr().Set(0.0)

    def _set_arm_drive_targets(self, target_arm: np.ndarray) -> None:
        if len(self._arm_joint_paths) != self._num_joints:
            return
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return

        target_arm = np.asarray(target_arm, dtype=np.float64).reshape(-1)
        for local_idx, joint_path in enumerate(self._arm_joint_paths):
            if local_idx >= target_arm.shape[0] or not joint_path:
                continue
            prim = stage.GetPrimAtPath(joint_path)
            if not prim.IsValid():
                continue
            drive = UsdPhysics.DriveAPI.Get(prim, "angular")
            if not drive:
                drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
            target_deg = float(np.rad2deg(target_arm[local_idx]))
            if prim.HasAttribute("drive:angular:physics:targetPosition"):
                drive.GetTargetPositionAttr().Set(target_deg)
            else:
                drive.CreateTargetPositionAttr().Set(target_deg)
            if prim.HasAttribute("drive:angular:physics:targetVelocity"):
                drive.GetTargetVelocityAttr().Set(0.0)
            else:
                drive.CreateTargetVelocityAttr().Set(0.0)

    def _set_gripper_drive_targets(self, target_dofs: np.ndarray) -> None:
        if not self._with_gripper or len(self._gripper_joint_paths) != 2:
            return
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return

        target_dofs = np.asarray(target_dofs, dtype=np.float64).reshape(-1)
        for local_idx, joint_path in enumerate(self._gripper_joint_paths):
            if local_idx >= target_dofs.shape[0] or not joint_path:
                continue
            prim = stage.GetPrimAtPath(joint_path)
            if not prim.IsValid():
                continue
            drive = UsdPhysics.DriveAPI.Get(prim, "linear")
            if not drive:
                drive = UsdPhysics.DriveAPI.Apply(prim, "linear")
            if prim.HasAttribute("drive:linear:physics:targetPosition"):
                drive.GetTargetPositionAttr().Set(float(target_dofs[local_idx]))
            else:
                drive.CreateTargetPositionAttr().Set(float(target_dofs[local_idx]))
            if prim.HasAttribute("drive:linear:physics:targetVelocity"):
                drive.GetTargetVelocityAttr().Set(0.0)
            else:
                drive.CreateTargetVelocityAttr().Set(0.0)

    def _force_gripper_positions(self, target_dofs: np.ndarray) -> None:
        if self._articulation is None or self._gripper_joint_indices.size != 2:
            return
        target_dofs = np.asarray(target_dofs, dtype=np.float64).reshape(-1)[:2]
        self._articulation.set_joint_positions(
            target_dofs.astype(np.float32),
            joint_indices=self._gripper_joint_indices.astype(np.int64),
        )
        self._articulation.set_joint_velocities(
            np.zeros(2, dtype=np.float32),
            joint_indices=self._gripper_joint_indices.astype(np.int64),
        )
        self._set_gripper_drive_targets(target_dofs)
        self._update_state_cache()

    def _force_arm_positions(self, target_arm: np.ndarray) -> None:
        if self._articulation is None or self._arm_joint_indices.size != self._num_joints:
            return
        target_arm = self._clip_arm_pos(np.asarray(target_arm, dtype=np.float64).reshape(-1)[: self._num_joints])
        with self._command_lock:
            self._command.pos = target_arm.copy()
            self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)
        self._trajectory = None
        self._articulation.set_joint_positions(
            target_arm.astype(np.float32),
            joint_indices=self._arm_joint_indices.astype(np.int64),
        )
        self._articulation.set_joint_velocities(
            np.zeros(self._num_joints, dtype=np.float32),
            joint_indices=self._arm_joint_indices.astype(np.int64),
        )
        if hasattr(self._articulation, "set_joint_efforts"):
            self._articulation.set_joint_efforts(
                np.zeros(self._num_joints, dtype=np.float32),
                joint_indices=self._arm_joint_indices.astype(np.int64),
            )
        self._set_arm_drive_targets(target_arm)
        self._update_state_cache()

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
        self._set_subset_effort_mode(
            "force" if self.zero_gravity_mode else "acceleration",
            self._arm_joint_indices,
        )
        self._set_subset_gains(self._arm_joint_indices, arm_kp, arm_kd)
        self._set_subset_max_efforts(self._arm_joint_indices, self._arm_max_effort)
        self._configure_arm_drive_params(self._hold_kp if not self.zero_gravity_mode else arm_kp, arm_kd, self._arm_max_effort)
        for dof_index in self._arm_joint_indices.tolist():
            self._switch_dof_control_mode(
                "effort" if self.zero_gravity_mode else "position",
                int(dof_index),
            )

        if self._with_gripper and self._gripper_joint_indices.size == 2:
            self._set_subset_gains(self._gripper_joint_indices, self._gripper_kp, self._gripper_kd)
            self._set_subset_max_efforts(self._gripper_joint_indices, self._gripper_max_effort)
            for dof_index in self._gripper_joint_indices.tolist():
                self._switch_dof_control_mode("position", int(dof_index))
            self._configure_gripper_drive_targets()

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
            self._set_arm_drive_targets(pos_target)
            self._controller().apply_action(
                ArticulationAction(
                    joint_positions=pos_target.astype(np.float32),
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
            self._set_gripper_drive_targets(grip)

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
            self._gripper_left_closed = float(limits[left_idx, 0])
            self._gripper_left_open = float(limits[left_idx, 1])
            self._gripper_right_open = float(limits[right_idx, 0])
            self._gripper_right_closed = float(limits[right_idx, 1])

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
        if self._gripper_joint_indices.size == 2:
            left = full_pos[self._gripper_joint_indices[0]]
            right = full_pos[self._gripper_joint_indices[1]]
            left_span = self._gripper_left_closed - self._gripper_left_open
            right_span = self._gripper_right_closed - self._gripper_right_open
            open_estimates: list[float] = []
            if abs(left_span) >= 1e-6:
                left_closed_fraction = (left - self._gripper_left_open) / left_span
                open_estimates.append(float(np.clip(1.0 - left_closed_fraction, 0.0, 1.0)))
            if abs(right_span) >= 1e-6:
                right_closed_fraction = (right - self._gripper_right_open) / right_span
                open_estimates.append(float(np.clip(1.0 - right_closed_fraction, 0.0, 1.0)))
            if open_estimates:
                # Use the more-open finger so one finger reaching the closed limit does not
                # falsely report the entire gripper as fully closed while the other side is blocked.
                gripper_open_value = float(max(open_estimates))
        elif self._gripper_joint_indices.size >= 1:
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
        joint_err = np.abs(current_arm - target_arm)
        max_err = float(np.max(joint_err))
        lead_max_err = float(np.max(joint_err[:4])) if joint_err.shape[0] >= 4 else max_err
        wrist_max_err = float(np.max(joint_err[4:])) if joint_err.shape[0] > 4 else 0.0
        allow_snap = (
            max_err <= self._ARM_FORCE_SNAP_TOL_RAD
            or (
                lead_max_err <= self._ARM_LEAD_JOINT_SNAP_TOL_RAD
                and wrist_max_err <= self._ARM_WRIST_JOINT_SNAP_TOL_RAD
            )
        )
        if allow_snap:
            carb.log_warn(
                "A1Z Isaac arm target nearly settled but remained outside tolerance; "
                f"keeping drive hold without final position snap max_err_rad={max_err:.4f} "
                f"lead_max_err_rad={lead_max_err:.4f} wrist_max_err_rad={wrist_max_err:.4f}"
            )
            return
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
