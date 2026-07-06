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
import omni.physx
import omni.usd
from isaacsim.core.api import World
from isaacsim.core.prims import RigidPrim, SingleArticulation
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.utils.types import ArticulationAction
from omni.physx import get_physx_simulation_interface
from omni.physx.bindings._physx import ContactEventType
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics
from a1z_ext.config import get_control_defaults
from a1z_ext.robots.grasp_attach_policy import summarize_attach_contacts
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
    filtered_pairs: list[tuple[str, str]] = field(default_factory=list)
    rigid_body_restore: dict[str, object] = field(default_factory=dict)


@dataclass
class _ContactViewCacheEntry:
    sensors: tuple[str, ...]
    filters: tuple[str, ...]
    max_contact_count: int
    view: Any
    sensor_collider_paths: dict[str, str] = field(default_factory=dict)
    filter_collider_paths: dict[str, str] = field(default_factory=dict)


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
    _GRASP_ATTACH_SETTLE_STEPS = 4
    _GRASP_ATTACH_VERIFY_STEPS = 5
    _GRASP_ATTACH_VERIFY_OPEN_TOL = 0.035
    _GRASP_ATTACH_VERIFY_REOPEN_TOL = 0.02
    _GRASP_ATTACH_MAX_OPEN_VALUE_FOR_ATTACH = 0.95
    _GRASP_ATTACH_MIN_CLOSURE_DELTA = 0.04
    _GRASP_CLOSE_MAX_VELOCITY_M_S = 0.06
    _GRASP_CONTACT_HOLD_MAX_VELOCITY_M_S = 0.015
    _GRASP_ATTACH_COMPLIANT_LINEAR_DAMPING = 8.0
    _GRASP_ATTACH_COMPLIANT_ANGULAR_DAMPING = 3.0
    _GRASP_ATTACH_COMPLIANT_MAX_DEPENETRATION_VELOCITY = 0.05
    _GRASP_ATTACH_COMPLIANT_MAX_CONTACT_IMPULSE = 2.5
    _GRASP_ATTACH_COMPLIANT_SOLVER_POSITION_ITERS = 32
    _GRASP_ATTACH_COMPLIANT_SOLVER_VELOCITY_ITERS = 8
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
        self._gripper_soft_kp = self._gripper_kp.copy() * 0.05
        self._gripper_soft_kd = self._gripper_kd.copy() * 0.20
        self._gripper_soft_max_effort = np.maximum(self._gripper_max_effort.copy() * 0.08, np.array([6.0, 6.0], dtype=np.float64))
        self._gripper_hold_kp = self._gripper_kp.copy() * 0.04
        self._gripper_hold_kd = self._gripper_kd.copy() * 0.16
        self._gripper_hold_max_effort = np.maximum(self._gripper_max_effort.copy() * 0.05, np.array([4.0, 4.0], dtype=np.float64))

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
        self._sim_grasp_state = _SimGraspState()
        self._contact_view_cache: dict[tuple[tuple[str, ...], tuple[str, ...], int], _ContactViewCacheEntry] = {}

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
        self._contact_view_cache.clear()
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
        self._contact_view_cache.clear()

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

    def get_sim_grasp_contacts(
        self,
        *,
        target_prim_path: str = "",
        require_bilateral_contact: bool = True,
    ) -> Dict[str, Any]:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        return self._run_on_main_thread(
            lambda: self._get_sim_grasp_contacts_impl(
                target_prim_path=str(target_prim_path or ""),
                require_bilateral_contact=bool(require_bilateral_contact),
            )
        )

    def get_sim_contact_report(
        self,
        *,
        prim_path: str = "",
        limit: int = 200,
    ) -> Dict[str, Any]:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        return self._run_on_main_thread(
            lambda: self._get_sim_contact_report_impl(
                prim_path=str(prim_path or ""),
                limit=int(limit),
            )
        )

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

    @staticmethod
    def _stage_prim_is_rigid_body(prim: Usd.Prim) -> bool:
        if not prim.IsValid():
            return False
        enabled_attr = prim.GetAttribute("physics:rigidBodyEnabled")
        if enabled_attr.IsValid():
            return bool(enabled_attr.Get())
        return bool(prim.HasAPI(UsdPhysics.RigidBodyAPI))

    @staticmethod
    def _stage_prim_has_collision(prim: Usd.Prim) -> bool:
        if not prim.IsValid():
            return False
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            return True
        enabled_attr = prim.GetAttribute("physics:collisionEnabled")
        if enabled_attr.IsValid():
            value = enabled_attr.Get()
            return True if value is None else bool(value)
        return False

    def _resolve_first_collision_descendant_path(self, prim_path: str) -> str:
        stage = omni.usd.get_context().get_stage()
        if stage is None or not prim_path:
            return ""
        root = stage.GetPrimAtPath(prim_path)
        if not root.IsValid():
            return ""
        if self._stage_prim_has_collision(root):
            return str(root.GetPath())
        for prim in Usd.PrimRange(root):
            if self._stage_prim_has_collision(prim):
                return str(prim.GetPath())
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

    def _prepare_contact_tracking_prim(self, prim_path: str) -> None:
        stage = omni.usd.get_context().get_stage()
        if stage is None or not prim_path:
            return
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            return
        if self._stage_prim_has_collision(prim) or self._stage_prim_is_rigid_body(prim):
            report_api = PhysxSchema.PhysxContactReportAPI.Apply(prim)
            if report_api:
                report_api.CreateThresholdAttr().Set(0.0)
        if self._stage_prim_is_rigid_body(prim):
            rigid_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
            if rigid_api:
                rigid_api.CreateSleepThresholdAttr().Set(0.0)

    def _candidate_contact_body_paths(
        self,
        *,
        include_robot_bodies: bool,
        extra_paths: Optional[list[str]] = None,
    ) -> list[str]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return []
        candidates: list[str] = []
        if stage.GetPrimAtPath("/World/GroundPlane").IsValid():
            candidates.append("/World/GroundPlane")
        trash_root = stage.GetPrimAtPath("/World/TrashSet")
        if trash_root.IsValid():
            for prim in trash_root.GetChildren():
                resolved = self._resolve_target_rigid_body_path(str(prim.GetPath()))
                if resolved:
                    candidates.append(resolved)
                elif self._stage_prim_has_collision(prim):
                    candidates.append(str(prim.GetPath()))
        if include_robot_bodies:
            self._ensure_gripper_structure_paths()
            candidates.extend(
                [
                    self._left_finger_body_path,
                    self._right_finger_body_path,
                    self._gripper_carrier_body_path,
                ]
            )
        for path in extra_paths or []:
            resolved = self._resolve_contact_body_path(path)
            if resolved:
                candidates.append(resolved)
            elif path:
                candidates.append(str(path))
        seen: set[str] = set()
        unique: list[str] = []
        for path in candidates:
            path = str(path or "")
            if not path or path in seen:
                continue
            if not stage.GetPrimAtPath(path).IsValid():
                continue
            seen.add(path)
            unique.append(path)
        return unique

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

    @staticmethod
    def _vec3_to_tuple(value: object) -> Optional[tuple[float, float, float]]:
        if value is None:
            return None
        try:
            arr = np.asarray(value, dtype=np.float64).reshape(-1)
        except Exception:
            return None
        if arr.size < 3:
            return None
        return (float(arr[0]), float(arr[1]), float(arr[2]))

    @staticmethod
    def _to_numpy_array(value: object) -> np.ndarray:
        if isinstance(value, np.ndarray):
            return value
        cpu_value = getattr(value, "cpu", None)
        if callable(cpu_value):
            try:
                value = cpu_value()
            except Exception:
                pass
        numpy_value = getattr(value, "numpy", None)
        if callable(numpy_value):
            try:
                return np.asarray(numpy_value())
            except Exception:
                pass
        to_numpy_value = getattr(value, "to_numpy", None)
        if callable(to_numpy_value):
            try:
                return np.asarray(to_numpy_value())
            except Exception:
                pass
        return np.asarray(value)

    def _get_contact_view(
        self,
        *,
        sensor_paths: list[str],
        filter_paths: list[str],
        max_contact_count: int,
    ) -> Optional[_ContactViewCacheEntry]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return None
        valid_sensors = [path for path in sensor_paths if path and stage.GetPrimAtPath(path).IsValid()]
        valid_filters = [path for path in filter_paths if path and stage.GetPrimAtPath(path).IsValid()]
        if not valid_sensors or not valid_filters:
            return None
        key = (tuple(valid_sensors), tuple(valid_filters), int(max_contact_count))
        entry = self._contact_view_cache.get(key)
        if entry is None:
            for path in [*valid_sensors, *valid_filters]:
                self._prepare_contact_tracking_prim(path)
            contact_filter_expr: Any
            if len(valid_sensors) > 1:
                contact_filter_expr = [list(valid_filters) for _ in valid_sensors]
            else:
                contact_filter_expr = list(valid_filters)
            view = RigidPrim(
                prim_paths_expr=valid_sensors,
                name=f"a1z_contact_view_{len(self._contact_view_cache)}",
                contact_filter_prim_paths_expr=contact_filter_expr,
                prepare_contact_sensors=True,
                disable_stablization=False,
                max_contact_count=max_contact_count,
            )
            entry = _ContactViewCacheEntry(
                sensors=tuple(valid_sensors),
                filters=tuple(valid_filters),
                max_contact_count=int(max_contact_count),
                view=view,
                sensor_collider_paths={
                    path: self._resolve_first_collision_descendant_path(path) or path
                    for path in valid_sensors
                },
                filter_collider_paths={
                    path: self._resolve_first_collision_descendant_path(path) or path
                    for path in valid_filters
                },
            )
            self._contact_view_cache[key] = entry
        try:
            if not entry.view.is_physics_handle_valid():
                entry.view.initialize(SimulationManager.get_physics_sim_view())
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac failed to initialize contact-force view: {exc}")
            self._contact_view_cache.pop(key, None)
            return None
        return entry

    def _read_contact_records_from_view(
        self,
        *,
        sensor_paths: list[str],
        filter_paths: list[str],
        max_contact_count: int,
    ) -> list[dict[str, object]]:
        entry = self._get_contact_view(
            sensor_paths=sensor_paths,
            filter_paths=filter_paths,
            max_contact_count=max_contact_count,
        )
        if entry is None:
            return []
        try:
            contact_data = entry.view.get_contact_force_data(dt=1.0)
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac failed reading contact-force data: {exc}")
            return []
        if not contact_data or len(contact_data) != 6:
            return []
        try:
            normal_forces = self._to_numpy_array(contact_data[0]).reshape(-1, 1)
            points = self._to_numpy_array(contact_data[1]).reshape(-1, 3)
            normals = self._to_numpy_array(contact_data[2]).reshape(-1, 3)
            distances = self._to_numpy_array(contact_data[3]).reshape(-1, 1)
            pair_contacts_count = self._to_numpy_array(contact_data[4]).reshape(len(entry.sensors), len(entry.filters))
            pair_contacts_start_indices = self._to_numpy_array(contact_data[5]).reshape(
                len(entry.sensors), len(entry.filters)
            )
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac failed unpacking contact-force data: {exc}")
            return []

        records: list[dict[str, object]] = []
        for sensor_index, sensor_path in enumerate(entry.sensors):
            for filter_index, filter_path in enumerate(entry.filters):
                count = int(pair_contacts_count[sensor_index, filter_index])
                start = int(pair_contacts_start_indices[sensor_index, filter_index])
                if count <= 0:
                    continue
                for data_index in range(start, start + count):
                    normal_vec = normals[data_index][:3].astype(np.float64, copy=False)
                    scalar_force = float(normal_forces[data_index].reshape(-1)[0])
                    impulse_vec = tuple((scalar_force * normal_vec).tolist())
                    point_vec = tuple(points[data_index][:3].astype(np.float64, copy=False).tolist())
                    normal_tuple = tuple(normal_vec.tolist())
                    separation = float(distances[data_index].reshape(-1)[0])
                    records.append(
                        {
                            "body0": sensor_path,
                            "body1": filter_path,
                            "collider0": entry.sensor_collider_paths.get(sensor_path, sensor_path),
                            "collider1": entry.filter_collider_paths.get(filter_path, filter_path),
                            "position": point_vec,
                            "normal": normal_tuple,
                            "impulse": impulse_vec,
                            "separation": separation,
                            "face_index0": -1,
                            "face_index1": -1,
                        }
                    )
        return records

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
        filter_paths = self._candidate_contact_body_paths(
            include_robot_bodies=False,
            extra_paths=[self._sim_grasp_state.target_body_path or ""],
        )
        filter_paths = [
            path
            for path in filter_paths
            if path not in {self._left_finger_body_path, self._right_finger_body_path, self._gripper_carrier_body_path}
        ]
        raw_records = self._read_contact_records_from_view(
            sensor_paths=[self._left_finger_body_path, self._right_finger_body_path],
            filter_paths=filter_paths,
            max_contact_count=max(128, max(1, len(filter_paths)) * 16),
        )
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

    def _record_matches_prim_path(self, record: dict[str, object], prim_path: str) -> bool:
        query = str(prim_path or "")
        if not query:
            return True
        for key in ("body0", "body1", "collider0", "collider1"):
            value = str(record.get(key, "") or "")
            if value == query or value.startswith(query + "/"):
                return True
        return False

    def _record_counterpart_path(self, record: dict[str, object], prim_path: str) -> str:
        query = str(prim_path or "")
        body0 = str(record.get("body0", "") or "")
        body1 = str(record.get("body1", "") or "")
        collider0 = str(record.get("collider0", "") or "")
        collider1 = str(record.get("collider1", "") or "")
        left_hit = any(value == query or value.startswith(query + "/") for value in (body0, collider0))
        right_hit = any(value == query or value.startswith(query + "/") for value in (body1, collider1))
        if left_hit and not right_hit:
            return body1 or collider1
        if right_hit and not left_hit:
            return body0 or collider0
        return ""

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
                    "position": self._vec3_to_tuple(record.get("position")),
                    "normal": self._vec3_to_tuple(record.get("normal")),
                    "impulse": self._vec3_to_tuple(record.get("impulse")),
                    "separation": float(record.get("separation", 0.0) or 0.0),
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

        return summarize_attach_contacts(
            left_raw_candidates=left_raw_candidates,
            left_candidates=left_candidates,
            left_contact_details=left_contact_details,
            right_raw_candidates=right_raw_candidates,
            right_candidates=right_candidates,
            right_contact_details=right_contact_details,
            target_body_path=target_body_path,
            require_bilateral_contact=require_bilateral_contact,
        )

    def _get_sim_grasp_contacts_impl(
        self,
        *,
        target_prim_path: str,
        require_bilateral_contact: bool,
    ) -> Dict[str, Any]:
        self._ensure_gripper_structure_paths()
        self._update_state_cache()
        target_body_path = self._resolve_target_rigid_body_path(target_prim_path) or str(
            self._sim_grasp_state.target_body_path or ""
        )
        contacts = self._poll_grasp_body_contacts()
        ok, body_path, summary = self._contact_satisfies_attach(
            contacts,
            target_body_path=target_body_path,
            require_bilateral_contact=require_bilateral_contact,
        )
        summary["snapshot_ok"] = bool(ok)
        summary["snapshot_body_path"] = body_path or None
        summary["target_prim_path"] = target_prim_path or None
        summary["gripper_open_value"] = float(self._gripper_open_value)
        summary["grasp_state"] = str(self._sim_grasp_state.grasp_state or "")
        summary["attached_object_path"] = self._sim_grasp_state.attached_object_path
        summary["attachment_joint_path"] = self._sim_grasp_state.attachment_joint_path
        return summary

    def _get_sim_contact_report_impl(
        self,
        *,
        prim_path: str,
        limit: int,
    ) -> Dict[str, Any]:
        self._ensure_gripper_structure_paths()
        self._update_state_cache()
        query_path = str(prim_path or "")
        resolved_body_path = self._resolve_target_rigid_body_path(query_path) or query_path
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return {
                "prim_path": query_path or None,
                "resolved_body_path": resolved_body_path or None,
                "match_count": 0,
                "returned_count": 0,
                "counterpart_body_paths": [],
                "records": [],
                "left_finger_body_path": self._left_finger_body_path or None,
                "right_finger_body_path": self._right_finger_body_path or None,
                "grasp_state": str(self._sim_grasp_state.grasp_state or ""),
            }
        query_prim = stage.GetPrimAtPath(query_path) if query_path else Usd.Prim()
        sensor_paths: list[str]
        filter_paths: list[str]
        if resolved_body_path and stage.GetPrimAtPath(resolved_body_path).IsValid() and self._stage_prim_is_rigid_body(
            stage.GetPrimAtPath(resolved_body_path)
        ):
            sensor_paths = [resolved_body_path]
            filter_paths = [
                path
                for path in self._candidate_contact_body_paths(
                    include_robot_bodies=True,
                    extra_paths=[query_path, resolved_body_path],
                )
                if path != resolved_body_path
            ]
        else:
            sensor_paths = [
                path
                for path in self._candidate_contact_body_paths(
                    include_robot_bodies=True,
                    extra_paths=[],
                )
                if path != query_path
            ]
            filter_paths = [query_path] if query_prim.IsValid() else []
        raw_records = self._read_contact_records_from_view(
            sensor_paths=sensor_paths,
            filter_paths=filter_paths,
            max_contact_count=max(128, max(1, len(sensor_paths) * max(1, len(filter_paths))) * 12),
        )
        matched_records = [
            record for record in raw_records
            if self._record_matches_prim_path(record, query_path)
            or (resolved_body_path != query_path and self._record_matches_prim_path(record, resolved_body_path))
        ]
        max_items = max(1, min(int(limit), 1000))
        items: list[dict[str, object]] = []
        counterpart_bodies: list[str] = []
        for record in matched_records[:max_items]:
            counterpart = (
                self._record_counterpart_path(record, query_path)
                or self._record_counterpart_path(record, resolved_body_path)
            )
            counterpart_body = self._resolve_contact_body_path(counterpart)
            if counterpart_body:
                counterpart_bodies.append(counterpart_body)
            items.append(
                {
                    "body0": str(record.get("body0", "") or ""),
                    "body1": str(record.get("body1", "") or ""),
                    "collider0": str(record.get("collider0", "") or ""),
                    "collider1": str(record.get("collider1", "") or ""),
                    "position": self._vec3_to_tuple(record.get("position")),
                    "normal": self._vec3_to_tuple(record.get("normal")),
                    "impulse": self._vec3_to_tuple(record.get("impulse")),
                    "separation": float(record.get("separation", 0.0) or 0.0),
                    "counterpart_path": counterpart or None,
                    "counterpart_body_path": counterpart_body or None,
                }
            )
        return {
            "prim_path": query_path or None,
            "resolved_body_path": resolved_body_path or None,
            "match_count": len(matched_records),
            "returned_count": len(items),
            "counterpart_body_paths": sorted(set(path for path in counterpart_bodies if path)),
            "records": items,
            "left_finger_body_path": self._left_finger_body_path or None,
            "right_finger_body_path": self._right_finger_body_path or None,
            "grasp_state": str(self._sim_grasp_state.grasp_state or ""),
        }

    def _set_filtered_pair(self, source_path: str, target_path: str) -> None:
        stage = omni.usd.get_context().get_stage()
        if stage is None or not source_path or not target_path:
            return
        source_prim = stage.GetPrimAtPath(source_path)
        target_prim = stage.GetPrimAtPath(target_path)
        if not source_prim.IsValid() or not target_prim.IsValid():
            return
        api = UsdPhysics.FilteredPairsAPI.Apply(source_prim)
        existing = list(api.GetFilteredPairsRel().GetTargets() or [])
        target = Sdf.Path(target_path)
        if target not in existing:
            existing.append(target)
            api.GetFilteredPairsRel().SetTargets(sorted(existing, key=str))

    def _clear_filtered_pair(self, source_path: str, target_path: str) -> None:
        stage = omni.usd.get_context().get_stage()
        if stage is None or not source_path or not target_path:
            return
        source_prim = stage.GetPrimAtPath(source_path)
        if not source_prim.IsValid() or not source_prim.HasAPI(UsdPhysics.FilteredPairsAPI):
            return
        api = UsdPhysics.FilteredPairsAPI(source_prim)
        existing = list(api.GetFilteredPairsRel().GetTargets() or [])
        target = Sdf.Path(target_path)
        if target not in existing:
            return
        remaining = [path for path in existing if path != target]
        api.GetFilteredPairsRel().SetTargets(sorted(remaining, key=str))

    def _clear_filtered_pairs(self, filtered_pairs: list[tuple[str, str]]) -> None:
        for source_path, target_path in filtered_pairs:
            self._clear_filtered_pair(source_path, target_path)

    def _filter_attached_collisions(self, attached_body_path: str) -> list[tuple[str, str]]:
        applied_pairs: list[tuple[str, str]] = []
        for source_path in (
            self._left_finger_body_path,
            self._right_finger_body_path,
            self._gripper_carrier_body_path,
        ):
            if not source_path:
                continue
            self._set_filtered_pair(source_path, attached_body_path)
            self._set_filtered_pair(attached_body_path, source_path)
            applied_pairs.append((source_path, attached_body_path))
            applied_pairs.append((attached_body_path, source_path))
        return applied_pairs

    def _apply_attach_compliance_profile(self, body_path: str) -> dict[str, object]:
        stage = omni.usd.get_context().get_stage()
        if stage is None or not body_path:
            return {}
        prim = stage.GetPrimAtPath(body_path)
        if not prim.IsValid():
            return {}
        rigid_body_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        restore = {
            "linear_damping": rigid_body_api.GetLinearDampingAttr().Get(),
            "angular_damping": rigid_body_api.GetAngularDampingAttr().Get(),
            "max_depenetration_velocity": rigid_body_api.GetMaxDepenetrationVelocityAttr().Get(),
            "max_contact_impulse": rigid_body_api.GetMaxContactImpulseAttr().Get(),
            "solver_position_iteration_count": rigid_body_api.GetSolverPositionIterationCountAttr().Get(),
            "solver_velocity_iteration_count": rigid_body_api.GetSolverVelocityIterationCountAttr().Get(),
        }
        rigid_body_api.CreateLinearDampingAttr().Set(float(self._GRASP_ATTACH_COMPLIANT_LINEAR_DAMPING))
        rigid_body_api.CreateAngularDampingAttr().Set(float(self._GRASP_ATTACH_COMPLIANT_ANGULAR_DAMPING))
        rigid_body_api.CreateMaxDepenetrationVelocityAttr().Set(
            float(self._GRASP_ATTACH_COMPLIANT_MAX_DEPENETRATION_VELOCITY)
        )
        rigid_body_api.CreateMaxContactImpulseAttr().Set(float(self._GRASP_ATTACH_COMPLIANT_MAX_CONTACT_IMPULSE))
        rigid_body_api.CreateSolverPositionIterationCountAttr().Set(
            int(self._GRASP_ATTACH_COMPLIANT_SOLVER_POSITION_ITERS)
        )
        rigid_body_api.CreateSolverVelocityIterationCountAttr().Set(
            int(self._GRASP_ATTACH_COMPLIANT_SOLVER_VELOCITY_ITERS)
        )
        return restore

    def _restore_attach_compliance_profile(self, body_path: str, restore: dict[str, object]) -> None:
        stage = omni.usd.get_context().get_stage()
        if stage is None or not body_path or not restore:
            return
        prim = stage.GetPrimAtPath(body_path)
        if not prim.IsValid():
            return
        rigid_body_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        if "linear_damping" in restore and restore["linear_damping"] is not None:
            rigid_body_api.CreateLinearDampingAttr().Set(float(restore["linear_damping"]))
        if "angular_damping" in restore and restore["angular_damping"] is not None:
            rigid_body_api.CreateAngularDampingAttr().Set(float(restore["angular_damping"]))
        if "max_depenetration_velocity" in restore and restore["max_depenetration_velocity"] is not None:
            rigid_body_api.CreateMaxDepenetrationVelocityAttr().Set(float(restore["max_depenetration_velocity"]))
        if "max_contact_impulse" in restore and restore["max_contact_impulse"] is not None:
            rigid_body_api.CreateMaxContactImpulseAttr().Set(float(restore["max_contact_impulse"]))
        if "solver_position_iteration_count" in restore and restore["solver_position_iteration_count"] is not None:
            rigid_body_api.CreateSolverPositionIterationCountAttr().Set(int(restore["solver_position_iteration_count"]))
        if "solver_velocity_iteration_count" in restore and restore["solver_velocity_iteration_count"] is not None:
            rigid_body_api.CreateSolverVelocityIterationCountAttr().Set(int(restore["solver_velocity_iteration_count"]))

    def _restore_grasp_phase_gains(self, close_phase: str) -> None:
        self._set_gripper_target(0.0)
        if close_phase == "soft_close":
            self._set_gripper_soft_grasp_gains()
        else:
            self._set_gripper_default_gains()

    def _verify_attach_candidate(
        self,
        *,
        chosen_body_path: str,
        contact_window_s: float,
        require_bilateral_contact: bool,
        attach_open_upper_bound: float,
        min_required_closure_delta: float,
    ) -> tuple[bool, dict[str, object]]:
        open_values = [float(self._gripper_open_value)]
        final_summary: dict[str, object] = {}
        for _ in range(self._GRASP_ATTACH_VERIFY_STEPS):
            self._apply_control_action()
            self._step_simulation_once(contact_window_s=contact_window_s, required_count=self._GRASP_ATTACH_REQUIRED_CONTACT_COUNT)
            self._update_state_cache()
            open_values.append(float(self._gripper_open_value))
            body_contacts = self._poll_grasp_body_contacts()
            ok, body_path, summary = self._contact_satisfies_attach(
                body_contacts,
                target_body_path=chosen_body_path,
                require_bilateral_contact=require_bilateral_contact,
            )
            final_summary = summary
            if not ok or body_path != chosen_body_path:
                return False, {
                    "reason": "contact_lost_during_verify",
                    "open_values": open_values,
                    "contact_summary": summary,
                }

        initial_open = open_values[0]
        min_open = min(open_values)
        reopen_delta = max(open_values) - initial_open
        open_span = max(open_values) - min(open_values)
        closure_delta = initial_open - min_open
        if initial_open > float(attach_open_upper_bound) + 1e-6:
            return False, {
                "reason": "gripper_too_open_for_attach",
                "open_values": open_values,
                "contact_summary": final_summary,
                "attach_open_upper_bound": float(attach_open_upper_bound),
                "min_required_closure_delta": float(min_required_closure_delta),
                "closure_delta": closure_delta,
            }
        if closure_delta < float(min_required_closure_delta) - 1e-6:
            return False, {
                "reason": "insufficient_gripper_closure_before_attach",
                "open_values": open_values,
                "contact_summary": final_summary,
                "attach_open_upper_bound": float(attach_open_upper_bound),
                "min_required_closure_delta": float(min_required_closure_delta),
                "closure_delta": closure_delta,
            }
        if reopen_delta > float(self._GRASP_ATTACH_VERIFY_REOPEN_TOL):
            return False, {
                "reason": "gripper_reopened_during_verify",
                "open_values": open_values,
                "contact_summary": final_summary,
                "reopen_delta": reopen_delta,
                "open_span": open_span,
                "closure_delta": closure_delta,
            }
        if open_span > float(self._GRASP_ATTACH_VERIFY_OPEN_TOL):
            return False, {
                "reason": "gripper_not_settled_during_verify",
                "open_values": open_values,
                "contact_summary": final_summary,
                "reopen_delta": reopen_delta,
                "open_span": open_span,
                "closure_delta": closure_delta,
            }
        return True, {
            "reason": "verified",
            "open_values": open_values,
            "contact_summary": final_summary,
            "reopen_delta": reopen_delta,
            "open_span": open_span,
            "closure_delta": closure_delta,
        }

    @staticmethod
    def _average_contact_point(
        contact_details: list[dict[str, object]],
        *,
        chosen_body_path: str,
    ) -> Optional[np.ndarray]:
        points: list[np.ndarray] = []
        for detail in contact_details:
            if str(detail.get("rigid_body_candidate", "") or "") != chosen_body_path:
                continue
            position = detail.get("position")
            if position is None:
                continue
            try:
                point = np.asarray(position, dtype=np.float64).reshape(-1)
            except Exception:
                continue
            if point.size < 3:
                continue
            points.append(point[:3].copy())
        if not points:
            return None
        return np.mean(np.stack(points, axis=0), axis=0)

    def _compute_attach_world(
        self,
        *,
        chosen_body_path: str,
        attach_summary: dict[str, object],
    ) -> tuple[Gf.Matrix4d, dict[str, object]]:
        target_world = self._get_world_transform(chosen_body_path)
        source_summary = attach_summary
        verification = attach_summary.get("candidate_verification")
        if isinstance(verification, dict):
            verification_summary = verification.get("contact_summary")
            if isinstance(verification_summary, dict):
                source_summary = verification_summary

        left_point = self._average_contact_point(
            list(source_summary.get("left_contact_details", []) or []),
            chosen_body_path=chosen_body_path,
        )
        right_point = self._average_contact_point(
            list(source_summary.get("right_contact_details", []) or []),
            chosen_body_path=chosen_body_path,
        )
        attach_point = None
        source = "body_origin"
        if left_point is not None and right_point is not None:
            attach_point = 0.5 * (left_point + right_point)
            source = "bilateral_contact_midpoint"
        elif left_point is not None:
            attach_point = left_point
            source = "left_contact_point"
        elif right_point is not None:
            attach_point = right_point
            source = "right_contact_point"

        attach_world = Gf.Matrix4d(target_world)
        meta: dict[str, object] = {
            "attach_anchor_source": source,
            "left_contact_point_world_m": left_point.tolist() if left_point is not None else None,
            "right_contact_point_world_m": right_point.tolist() if right_point is not None else None,
        }
        if attach_point is not None:
            attach_world.SetTranslateOnly(Gf.Vec3d(*attach_point.tolist()))
            meta["attach_anchor_world_m"] = attach_point.tolist()
        else:
            origin = target_world.ExtractTranslation()
            meta["attach_anchor_world_m"] = [float(origin[0]), float(origin[1]), float(origin[2])]
        return attach_world, meta

    def _create_attachment_joint(
        self,
        *,
        joint_path: str,
        body0_path: str,
        body1_path: str,
        attach_world: Gf.Matrix4d,
    ) -> str:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is unavailable.")
        root = stage.GetPrimAtPath("/World/SimulationGraspAttachments")
        if not root.IsValid():
            stage.DefinePrim("/World/SimulationGraspAttachments", "Xform")
        carrier_world = self._get_world_transform(body0_path)
        target_world = self._get_world_transform(body1_path)
        local0 = carrier_world.GetInverse() * attach_world
        local1 = target_world.GetInverse() * attach_world
        carrier_translation, carrier_rotation = self._matrix_to_pose_components(local0)
        target_translation, target_rotation = self._matrix_to_pose_components(local1)
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
        chosen_rigid_body_restore: dict[str, object] = {}
        bilateral_hold_active = False
        initial_open_value = float(self._gripper_open_value)
        attach_open_upper_bound = min(
            float(self._GRASP_ATTACH_MAX_OPEN_VALUE_FOR_ATTACH),
            max(0.0, initial_open_value - float(self._GRASP_ATTACH_MIN_CLOSURE_DELTA)),
        )
        min_required_closure_delta = min(
            float(self._GRASP_ATTACH_MIN_CLOSURE_DELTA),
            max(0.0, initial_open_value),
        )
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
            attach_summary["gripper_open_value"] = current_open_value
            attach_summary["close_phase"] = close_phase
            attach_summary["initial_gripper_open_value"] = initial_open_value
            attach_summary["attach_open_upper_bound"] = attach_open_upper_bound
            attach_summary["min_required_closure_delta"] = min_required_closure_delta
            attach_summary["gripper_closure_delta"] = max(0.0, initial_open_value - current_open_value)
            ground_contact_present = bool(summary.get("left_has_ground_contact")) or bool(summary.get("right_has_ground_contact"))
            attach_summary["ground_contact_present"] = ground_contact_present
            bilateral_effective_ready = bool(summary.get("left_has_selected_body_contact")) and bool(
                summary.get("right_has_selected_body_contact")
            )
            attach_summary["bilateral_effective_ready"] = bilateral_effective_ready
            if ok:
                if bilateral_effective_ready and not ground_contact_present and not bilateral_hold_active:
                    held_open_value = current_open_value
                    self._set_gripper_target(held_open_value)
                    self._set_gripper_hold_gains()
                    bilateral_hold_active = True
                    attach_summary["bilateral_hold_triggered"] = True
                    attach_summary["bilateral_hold_open_value"] = held_open_value
                if body_path == last_body:
                    stable_count += 1
                else:
                    stable_count = 1
                    last_body = body_path
                self._sim_grasp_state.grasp_state = "contact_candidate"
                self._sim_grasp_state.last_contact_time = time.time()
                if stable_count >= required_count and not ground_contact_present:
                    held_open_value = current_open_value
                    self._set_gripper_target(held_open_value)
                    self._set_gripper_hold_gains()
                    candidate_rigid_body_restore = self._apply_attach_compliance_profile(body_path)
                    verified, verification = self._verify_attach_candidate(
                        chosen_body_path=body_path,
                        contact_window_s=contact_window_s,
                        require_bilateral_contact=require_bilateral_contact,
                        attach_open_upper_bound=attach_open_upper_bound,
                        min_required_closure_delta=min_required_closure_delta,
                    )
                    attach_summary["candidate_verification"] = verification
                    if verified:
                        chosen_body_path = body_path
                        chosen_rigid_body_restore = candidate_rigid_body_restore
                        break
                    self._restore_attach_compliance_profile(body_path, candidate_rigid_body_restore)
                    stable_count = 0
                    last_body = ""
                    bilateral_hold_active = False
                    self._restore_grasp_phase_gains(close_phase)
                    continue
            else:
                stable_count = 0
                last_body = ""
                if bilateral_hold_active:
                    bilateral_hold_active = False
                    self._restore_grasp_phase_gains(close_phase)
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
                "target_body_path": str(self._sim_grasp_state.target_body_path or "") or None,
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
        current_gripper = float(self._gripper_open_value)
        self._set_gripper_target(current_gripper)
        self._set_gripper_hold_gains()
        filtered_pairs = self._filter_attached_collisions(chosen_body_path)
        rigid_body_restore = chosen_rigid_body_restore or self._apply_attach_compliance_profile(chosen_body_path)
        for _ in range(self._GRASP_ATTACH_SETTLE_STEPS):
            self._apply_control_action()
            self._step_simulation_once(contact_window_s=contact_window_s, required_count=required_count)
            self._update_state_cache()
        attach_world, attach_anchor_meta = self._compute_attach_world(
            chosen_body_path=chosen_body_path,
            attach_summary=attach_summary,
        )
        attach_summary.update(attach_anchor_meta)
        try:
            attachment_joint_path = self._create_attachment_joint(
                joint_path=joint_path,
                body0_path=self._gripper_carrier_body_path,
                body1_path=chosen_body_path,
                attach_world=attach_world,
            )
        except Exception as exc:
            self._clear_filtered_pairs(filtered_pairs)
            self._restore_attach_compliance_profile(chosen_body_path, rigid_body_restore)
            self._sim_grasp_state.grasp_state = "failed"
            self._sim_grasp_state.last_failure_reason = "attach_creation_failed"
            self._set_gripper_default_gains()
            return {
                "success": False,
                "target_prim_path": target_prim_path or "",
                "target_body_path": str(self._sim_grasp_state.target_body_path or "") or None,
                "attached_object_path": chosen_body_path,
                "attachment_joint_path": None,
                "contact_summary": attach_summary,
                "failure_reason": f"attach_creation_failed: {exc}",
                "timing": {},
            }

        self._step_simulation_once(contact_window_s=contact_window_s, required_count=required_count)
        self._update_state_cache()
        self._sim_grasp_state.grasp_state = "attached"
        self._sim_grasp_state.attached_object_path = chosen_body_path
        self._sim_grasp_state.attachment_joint_path = attachment_joint_path
        self._sim_grasp_state.filtered_pairs = filtered_pairs
        self._sim_grasp_state.rigid_body_restore = rigid_body_restore
        return {
            "success": True,
            "target_prim_path": target_prim_path or "",
            "target_body_path": str(self._sim_grasp_state.target_body_path or "") or None,
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
        filtered_pairs = list(self._sim_grasp_state.filtered_pairs)
        rigid_body_restore = dict(self._sim_grasp_state.rigid_body_restore)
        if joint_path:
            self._remove_attachment_joint(joint_path)
        for source_path, target_path in filtered_pairs:
            self._clear_filtered_pair(source_path, target_path)
        if attached_object_path:
            self._restore_attach_compliance_profile(attached_object_path, rigid_body_restore)
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

    def _active_gripper_velocity_limits(self) -> np.ndarray:
        limits = self._gripper_max_velocity[:2].copy()
        if self._sim_grasp_state.grasp_state == "contact_candidate":
            limits[:] = np.minimum(limits, self._GRASP_CONTACT_HOLD_MAX_VELOCITY_M_S)
        elif self._sim_grasp_state.grasp_state in {
            "closing_for_grasp",
            "closing_for_grasp_default",
        }:
            limits[:] = np.minimum(limits, self._GRASP_CLOSE_MAX_VELOCITY_M_S)
        return limits

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
        max_step = self._active_gripper_velocity_limits() * dt
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
