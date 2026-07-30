"""Isaac Sim-backed A1Z robot backend."""

from __future__ import annotations

import os
import queue
import threading
import time
import warnings
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Mapping, Optional

import carb
import numpy as np
import omni.physx
import omni.usd
from isaacsim.core.simulation_manager import SimulationManager
from omni.physx import get_physx_simulation_interface
from omni.physx.bindings._physx import ContactEventType
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade
from a1z_ext.config import get_arm_motion_speed_limits, get_control_defaults
from a1z_ext.grasping.contact_reducer import reduce_contact_impulses
from a1z_ext.grasping.parallel_jaw import (
    ParallelJawMapping,
    rate_limit_parallel_jaw_setpoint,
)
from a1z_ext.grasping.physical_fsm import PhysicalGraspFSM
from a1z_ext.grasping.physical_types import (
    ContactSnapshot,
    DriveProfile,
    GraspPhase,
    GripperSnapshot,
    PhysicalGraspConfig,
    PhysicalGraspStatus,
)
from a1z_ext.robots.grasp_attach_policy import select_contact_candidate, summarize_attach_contacts
from a1z_ext.robots.position_hold import bounded_position_hold_feedforward
from a1z_ext.robots.trajectory import RecordingSession, Trajectory, play_trajectory_blocking


from a1z_ext.robots.isaac6_backend import configured_isaac_api_profile


_NATIVE_ISAAC6 = configured_isaac_api_profile() == "native_6_0"
if _NATIVE_ISAAC6:
    from a1z_ext.robots.isaac6_backend import (
        A1ZArticulationCommand as ArticulationCommand,
        Isaac6ArticulationAdapter as ArticulationAdapter,
        Isaac6RigidPrimAdapter as RigidPrim,
    )

    World = Any
else:
    from isaacsim.core.api import World
    from isaacsim.core.prims import RigidPrim, SingleArticulation as ArticulationAdapter
    from isaacsim.core.utils.types import ArticulationAction as ArticulationCommand


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
    post_attach_closing_active: bool = False
    post_attach_stable_count: int = 0
    post_attach_required_count: int = 0
    post_attach_target_value: float = 0.0


@dataclass
class _ContactViewCacheEntry:
    sensors: tuple[str, ...]
    filters: tuple[str, ...]
    max_contact_count: int
    view: Any
    sensor_collider_paths: dict[str, str] = field(default_factory=dict)
    filter_collider_paths: dict[str, str] = field(default_factory=dict)


@dataclass
class _PendingGraspAttach:
    target_prim_path: str
    timeout_s: float
    contact_window_s: float
    require_bilateral_contact: bool
    done_event: threading.Event = field(default_factory=threading.Event)
    result: Optional[Dict[str, Any]] = None
    error: Optional[BaseException] = None
    attach_summary: dict[str, object] = field(default_factory=dict)
    soft_close_timeout_s: float = 0.0
    full_close_timeout_s: float = 0.0
    start_time: float = 0.0
    soft_close_deadline: float = 0.0
    full_close_deadline: float = 0.0
    stable_count: int = 0
    required_count: int = 0
    last_body: str = ""
    close_phase: str = "soft_close"
    failure_reason: str = "grasp_contact_not_found"
    initial_open_value: float = 0.0
    filtered_pairs: list[tuple[str, str]] = field(default_factory=list)
    rigid_body_restore: dict[str, object] = field(default_factory=dict)
    attachment_joint_path: Optional[str] = None
    stage: str = "precheck"
    max_frame_open_delta: float = 0.0
    max_frame_dt_s: float = 0.0
    sample_count: int = 0
    last_progress_time: float = 0.0
    last_progress_open_value: Optional[float] = None
    stage_counts: dict[str, int] = field(default_factory=dict)
    progress_samples: list[dict[str, object]] = field(default_factory=list)
    ground_block_hold_active: bool = False
    ground_block_hold_started_at: Optional[float] = None
    ground_block_hold_open_value: float = 0.0
    precheck_clear_count: int = 0
    contact_filter_paths: list[str] = field(default_factory=list)
    precheck_last_arm_pos: Optional[np.ndarray] = None


@dataclass
class _PhysicalGraspOperation:
    fsm: PhysicalGraspFSM
    mapping: ParallelJawMapping
    target_body_path: str
    initial_constraint_paths: frozenset[str]
    initial_target_physics_state: Mapping[str, bool]
    initial_target_world_translation_m: Optional[tuple[float, float, float]]
    max_close_velocity_m_s: float
    max_command_lead_m: float
    controller_profile: Optional[Mapping[str, Any]] = None
    last_applied_command_signature: Optional[tuple[Any, ...]] = None
    close_done_event: threading.Event = field(default_factory=threading.Event)
    release_done_event: threading.Event = field(default_factory=threading.Event)
    close_result: Optional[Dict[str, Any]] = None
    release_result: Optional[Dict[str, Any]] = None
    error: Optional[BaseException] = None
    latest_contacts: ContactSnapshot = field(default_factory=ContactSnapshot)
    latest_gripper: Optional[GripperSnapshot] = None
    started_at_s: float = 0.0
    holding_confirmed: bool = False
    minimum_effort_residual_n: float = 0.1
    minimum_position_lag_m: float = 0.0005
    gripper_effort_baseline_n: Optional[tuple[float, float]] = None
    gripper_effort_baseline_samples: int = 0
    latest_effort_residual_n: Optional[tuple[float, float]] = None


class IsaacSimArmRobot:
    """Drive the imported A1Z articulation from inside the Isaac Kit thread."""

    _REQUEST_TIMEOUT_S = 120.0
    _ARM_SETTLE_TOL_RAD = np.deg2rad(0.50)
    _ARM_SETTLE_REQUIRED_SAMPLES = 3
    _ARM_FORCE_SNAP_TOL_RAD = np.deg2rad(0.75)
    _ARM_LEAD_JOINT_SNAP_TOL_RAD = np.deg2rad(0.75)
    _ARM_WRIST_JOINT_SNAP_TOL_RAD = np.deg2rad(3.0)
    _ARM_POST_MOVE_WRIST_RECOVERY_TOL_RAD = np.deg2rad(10.0)
    _ARM_STAGE_WRIST_DELTA_RAD = np.deg2rad(12.0)
    _ARM_STAGE_SPEED_RAD_S = 0.30
    _GRIPPER_SETTLE_TOL = 0.03
    _GRASP_ATTACH_REQUIRED_CONTACT_COUNT = 3
    _GRASP_ATTACH_PRECHECK_CLEAR_STEPS = 3
    _GRASP_ATTACH_PRECHECK_MAX_ARM_VEL_RAD_S = 0.12
    _GRASP_ATTACH_PRECHECK_MAX_WRIST_VEL_RAD_S = 0.20
    _GRASP_ATTACH_PRECHECK_MAX_ARM_COMMAND_ERR_RAD = np.deg2rad(2.0)
    _GRASP_ATTACH_PRECHECK_MAX_ARM_FRAME_DELTA_RAD = np.deg2rad(0.10)
    _GRASP_ATTACH_CLOSED_TOL = 0.05
    _GRASP_ATTACH_FULL_CLOSE_EXTRA_TIMEOUT_S = 4.0
    _GRASP_ATTACH_FULL_CLOSE_MIN_TIMEOUT_S = 6.0
    _GRASP_ATTACH_SETTLE_STEPS = 4
    _GRASP_ATTACH_VERIFY_STEPS = 5
    _GRASP_ATTACH_VERIFY_OPEN_TOL = 0.035
    _GRASP_ATTACH_VERIFY_REOPEN_TOL = 0.02
    _GRASP_ATTACH_MAX_OPEN_VALUE_FOR_ATTACH = 0.95
    _GRASP_ATTACH_MIN_CLOSURE_DELTA = 0.04
    _GRASP_ATTACH_UNILATERAL_HOLD_TIMEOUT_S = 0.75
    _GRASP_ATTACH_GROUND_BLOCK_TIMEOUT_S = 0.20
    _GRASP_ATTACH_PROVISIONAL_CLOSE_TIMEOUT_S = 0.60
    _GRASP_ATTACH_PROVISIONAL_MAX_OPEN_VALUE = 0.92
    _GRASP_CLOSE_MAX_VELOCITY_M_S = 0.06
    _GRASP_CONTACT_HOLD_MAX_VELOCITY_M_S = 0.015
    _GRASP_ATTACH_RATE_LIMIT_DT_CAP_S = 0.03
    _GRASP_ATTACH_PROGRESS_SAMPLE_LIMIT = 80
    _GRASP_ATTACH_CONTACT_FILTER_RADIUS_M = 0.20
    _GRASP_ATTACH_CONTACT_FILTER_MAX_BODIES = 6
    _GRASP_ATTACH_COMPLIANT_LINEAR_DAMPING = 8.0
    _GRASP_ATTACH_COMPLIANT_ANGULAR_DAMPING = 3.0
    _GRASP_ATTACH_COMPLIANT_MAX_DEPENETRATION_VELOCITY = 0.05
    _GRASP_ATTACH_COMPLIANT_MAX_CONTACT_IMPULSE = 2.5
    _GRASP_ATTACH_COMPLIANT_SOLVER_POSITION_ITERS = 32
    _GRASP_ATTACH_COMPLIANT_SOLVER_VELOCITY_ITERS = 8
    _POST_ATTACH_CLOSE_REQUIRED_CONTACT_COUNT = 2
    _PHYSICAL_GRASP_MOTION_STABLE_VEL_M_S = 0.002
    _PHYSICAL_GRASP_FULLY_CLOSED_TOL_M = 0.001
    _PHYSICAL_GRASP_MAX_COMMAND_LEAD_M = 0.005
    _GRIPPER_PAD_MATERIAL_PATH = "/World/PhysicsMaterials/A1ZGripperPad"
    _GRIPPER_PAD_STATIC_FRICTION = 2.0
    _GRIPPER_PAD_DYNAMIC_FRICTION = 1.5

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
        self._control_elapsed_s = 0.0
        # ArticulationController is the authoritative live command path.  The
        # old USD mirror is retained only for version-specific compatibility
        # experiments because writing both paths every control tick produces
        # redundant USD/Fabric notices in Isaac Sim 6.
        self._mirror_drive_targets_to_usd = os.environ.get(
            "A1Z_ISAAC_MIRROR_DRIVE_TARGETS_TO_USD", "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._articulation_root_prim = articulation_root_prim or isaac_cfg["articulation_root_prim"]
        self._arm_drive_type = str(isaac_cfg.get("arm_drive_type", "force")).strip().lower()
        if self._arm_drive_type not in {"force", "acceleration"}:
            raise ValueError(
                "isaacsim.arm_drive_type must be 'force' or 'acceleration', "
                f"got {self._arm_drive_type!r}"
            )
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
        self._position_hold_gravity_compensation = bool(
            isaac_cfg.get("position_hold_gravity_compensation", True)
        )
        self._position_hold_feedforward_limit = np.asarray(
            isaac_cfg.get(
                "position_hold_feedforward_limit_nm",
                control_defaults["arm_rated_torque_nm"],
            ),
            dtype=np.float64,
        ).reshape(-1)[: self._num_joints]
        if (
            self._position_hold_feedforward_limit.size != self._num_joints
            or not np.all(np.isfinite(self._position_hold_feedforward_limit))
            or np.any(self._position_hold_feedforward_limit <= 0.0)
        ):
            raise ValueError(
                "isaacsim.position_hold_feedforward_limit_nm must contain "
                f"{self._num_joints} finite positive values"
            )
        self._arm_max_effort = np.asarray(isaac_cfg["arm_max_effort"], dtype=np.float64).reshape(-1)
        self._arm_max_velocity = np.asarray(isaac_cfg["arm_max_velocity"], dtype=np.float64).reshape(-1)
        self._arm_peak_velocity = np.asarray(control_defaults["arm_peak_velocity_rad_s"], dtype=np.float64).reshape(-1)
        self._arm_motion_speed_limits = get_arm_motion_speed_limits()
        self._gravity_mode_kd_scale = float(isaac_cfg["gravity_mode_kd_scale"])
        self._gripper_kp = np.asarray(isaac_cfg["gripper_kp"], dtype=np.float64).reshape(-1)
        self._gripper_kd = np.asarray(isaac_cfg["gripper_kd"], dtype=np.float64).reshape(-1)
        self._gripper_max_effort = np.asarray(isaac_cfg["gripper_max_effort"], dtype=np.float64).reshape(-1)
        self._gripper_max_velocity = np.asarray(isaac_cfg["gripper_max_velocity"], dtype=np.float64).reshape(-1)
        self._gripper_soft_kp = np.minimum(
            self._gripper_kp.copy(), np.array([4000.0, 4000.0], dtype=np.float64)
        )
        self._gripper_soft_kd = np.minimum(
            self._gripper_kd.copy(), np.array([140.0, 140.0], dtype=np.float64)
        )
        self._gripper_soft_max_effort = np.minimum(
            self._gripper_max_effort.copy(), np.array([50.0, 50.0], dtype=np.float64)
        )
        self._gripper_search_kp = np.minimum(
            self._gripper_kp.copy(), np.array([6000.0, 6000.0], dtype=np.float64)
        )
        self._gripper_search_kd = np.minimum(
            self._gripper_kd.copy(), np.array([180.0, 180.0], dtype=np.float64)
        )
        self._gripper_search_max_effort = np.minimum(
            self._gripper_max_effort.copy(), np.array([80.0, 80.0], dtype=np.float64)
        )
        self._gripper_hold_kp = np.minimum(
            self._gripper_kp.copy(), np.array([7000.0, 7000.0], dtype=np.float64)
        )
        self._gripper_hold_kd = np.minimum(
            self._gripper_kd.copy(), np.array([220.0, 220.0], dtype=np.float64)
        )
        self._gripper_hold_max_effort = np.minimum(
            self._gripper_max_effort.copy(), np.array([100.0, 100.0], dtype=np.float64)
        )

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
        self._articulation: Optional[ArticulationAdapter] = None
        self._running = False
        self._estopped = False

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
        self._gripper_command_dofs: Optional[np.ndarray] = None
        self._gripper_target_dofs_override: Optional[np.ndarray] = None
        self._gripper_free_drive = False
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
        self._rigid_body_view_cache: dict[str, RigidPrim] = {}
        self._nested_rigid_body_reset_repaired: set[str] = set()
        self._nested_rigid_body_reset_flip_logged: set[str] = set()
        self._pending_grasp_attach: Optional[_PendingGraspAttach] = None
        self._physical_grasp_operation: Optional[_PhysicalGraspOperation] = None
        self._active_gripper_drive_profile = ""
        self._gripper_pad_material_status: dict[str, Any] = {}

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

    def _resolve_articulation(self) -> tuple[str, ArticulationAdapter]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is not available while resolving articulation root.")
        prim = stage.GetPrimAtPath(self._articulation_root_prim)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid articulation root prim: {self._articulation_root_prim}")

        articulation = ArticulationAdapter(prim_path=self._articulation_root_prim, name="a1z")
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
        existing_world=None,
        reset_world: bool = True,
    ) -> None:
        self._run_on_main_thread(
            lambda: self._start_impl(
                initial_kp=initial_kp,
                initial_kd=initial_kd,
                existing_world=existing_world,
                reset_world=reset_world,
            )
        )

    def _start_impl(
        self,
        initial_kp: Optional[np.ndarray] = None,
        initial_kd: Optional[np.ndarray] = None,
        existing_world=None,
        reset_world: bool = True,
    ) -> None:
        self._contact_view_cache.clear()
        self._rigid_body_view_cache.clear()
        self._active_gripper_drive_profile = ""
        self._gripper_free_drive = False
        if existing_world is None:
            if _NATIVE_ISAAC6:
                raise RuntimeError("Isaac 6 A1Z backend requires the A1Z public-API world adapter.")
            self._world = World(stage_units_in_meters=1.0)
            if reset_world:
                self._world.reset()
        else:
            self._world = existing_world
            if reset_world and hasattr(self._world, "reset"):
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
        self._estopped = False
        self._control_elapsed_s = 0.0
        if self._with_gripper:
            try:
                self._gripper_pad_material_status = self._ensure_gripper_pad_physics_material()
            except Exception as exc:
                self._gripper_pad_material_status = {"ready": False, "error": str(exc)}
                carb.log_warn(f"A1Z Isaac could not configure high-friction gripper pads: {exc}")

        self._update_state_cache()
        if self._with_gripper and self._gripper_joint_indices.size == 2:
            self._gripper_command_dofs = self._full_pos[self._gripper_joint_indices].copy()
            self._gripper_target_dofs_override = None
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
        self._gripper_command_dofs = None
        self._gripper_target_dofs_override = None
        self._gripper_free_drive = False
        self._contact_view_cache.clear()
        self._rigid_body_view_cache.clear()
        self._active_gripper_drive_profile = ""
        pending = self._pending_grasp_attach
        self._pending_grasp_attach = None
        if pending is not None and not pending.done_event.is_set():
            pending.error = RuntimeError("Isaac Sim robot stopped while grasp_attach was running.")
            pending.done_event.set()
        physical = self._physical_grasp_operation
        self._physical_grasp_operation = None
        if physical is not None:
            physical.error = RuntimeError("Isaac Sim robot stopped while physical grasp was running.")
            physical.close_done_event.set()
            physical.release_done_event.set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_estopped(self) -> bool:
        return self._estopped

    def _require_motion_enabled(self) -> None:
        if self._estopped:
            raise RuntimeError("Robot is in estop.")

    def estop(self) -> None:
        """Cancel the active trajectory and hold the measured simulated pose."""
        if self._estopped:
            return
        # Latch before entering Kit's main thread so every concurrent public
        # command is rejected immediately.
        self._estopped = True
        self._run_on_main_thread(self._estop_impl)

    def _estop_impl(self) -> None:
        self._ensure_main_thread()
        interrupted = self._trajectory
        self._trajectory = None
        with self._state_lock:
            current = self._full_pos[self._arm_joint_indices].copy()
        self.zero_gravity_mode = False
        with self._command_lock:
            self._command.pos = self._clip_arm_pos(current)
            self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.kp = self._hold_kp.copy()
            self._command.kd = self._hold_kd.copy()
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)
        self._configure_actuators()
        self._apply_control_action()
        if interrupted is not None and interrupted.done_event is not None:
            interrupted.done_event.set()

    def release(self) -> None:
        """Release the latch while retaining position hold at the current pose."""
        if not self._estopped:
            return
        self._run_on_main_thread(self._release_estop_impl)

    def _release_estop_impl(self) -> None:
        self._ensure_main_thread()
        with self._state_lock:
            current = self._full_pos[self._arm_joint_indices].copy()
        with self._command_lock:
            self._command.pos = self._clip_arm_pos(current)
            self._command.vel = np.zeros(self._num_joints, dtype=np.float64)
            self._command.acc = np.zeros(self._num_joints, dtype=np.float64)
            self._command.kp = self._hold_kp.copy()
            self._command.kd = self._hold_kd.copy()
            self._command.torque_ff = np.zeros(self._num_joints, dtype=np.float64)
        self._estopped = False
        self._configure_actuators()
        self._apply_control_action()

    def process_pending(self, step_size: Optional[float] = None) -> bool:
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
            return False

        if step_size is not None:
            self._control_elapsed_s += max(0.0, float(step_size))
            if self._control_elapsed_s + 1.0e-12 < self._control_period_s:
                return False
            self._control_elapsed_s %= self._control_period_s

        self._update_state_cache()
        self._check_arm_hard_limits()
        self._recording.maybe_sample(
            now_s=time.time(),
            pos=self._full_pos[self._arm_joint_indices].copy(),
        )
        self._advance_trajectory()
        self._apply_control_action()
        self._advance_physical_grasp()
        self._advance_pending_grasp_attach()
        self._advance_post_attach_close()
        return True

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
        # RobotServer calls this method on a socket thread, but articulation
        # property reads enter PhysX. Serialize the complete read on Kit's main
        # thread just like the other Isaac-backed operations.
        return self._run_on_main_thread(self._get_robot_info_impl)

    def _get_robot_info_impl(self) -> Dict[str, Any]:
        self._ensure_main_thread()
        with self._state_lock:
            articulation_joint_limits = None if self._joint_limits is None else self._joint_limits.copy()
        actual_kp = None
        actual_kd = None
        actual_max_effort = None
        actual_position_targets = None
        effort_modes = None
        active_physics_engine = None
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
            try:
                actual_max_effort = np.asarray(
                    self._controller().get_max_efforts(), dtype=np.float64
                ).reshape(-1).copy()
            except Exception:
                pass
            try:
                actual_position_targets = np.asarray(
                    self._articulation.get_joint_position_targets(), dtype=np.float64
                ).reshape(-1).copy()
            except Exception:
                pass
            try:
                active_physics_engine = str(SimulationManager.get_active_physics_engine())
            except Exception:
                pass
        with self._command_lock:
            command_pos = self._command.pos.copy()
            command_vel = self._command.vel.copy()
        gripper_target_value = float(self._gripper_target_value)
        gripper_target_dofs = None
        gripper_current_dofs = None
        gripper_command_dofs = None
        if self._with_gripper and self._gripper_joint_indices.size == 2:
            gripper_target_dofs = (
                self._normalized_to_gripper_dofs(gripper_target_value).copy()
                if self._gripper_target_dofs_override is None
                else self._gripper_target_dofs_override.copy()
            )
            if self._gripper_command_dofs is not None:
                gripper_command_dofs = self._gripper_command_dofs.copy()
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
            "arm_motion_speed_rad_s": {
                "minimum": self._arm_motion_speed_limits.minimum,
                "default": self._arm_motion_speed_limits.default,
                "maximum": self._arm_motion_speed_limits.maximum,
            },
            "articulation_root_prim": self._articulation_root_prim,
            "dof_names": list(self._dof_names),
            "arm_joint_indices": self._arm_joint_indices.copy(),
            "gripper_joint_indices": self._gripper_joint_indices.copy(),
            "gripper_joint_paths": list(self._gripper_joint_paths),
            "gravity_comp_factor": self._gravity_comp_factor,
            "zero_gravity_mode": self.zero_gravity_mode,
            "gravity_model_available": self._gravity_model is not None,
            "position_hold_gravity_compensation_enabled": (
                self._position_hold_gravity_compensation
            ),
            "position_hold_gravity_compensation_active": (
                not self.zero_gravity_mode
                and self._position_hold_gravity_compensation
                and self._gravity_model is not None
            ),
            "position_hold_feedforward_limit_nm": (
                self._position_hold_feedforward_limit.copy()
            ),
            "gravity_torque_scale": self._gravity_torque_scale.copy(),
            "max_gravity_torque": self._max_gravity_torque.copy(),
            "torque_clip": self._torque_clip.copy(),
            "actual_kp": actual_kp,
            "actual_kd": actual_kd,
            "actual_max_effort": actual_max_effort,
            "actual_position_targets": actual_position_targets,
            "active_physics_engine": active_physics_engine,
            "configured_arm_drive_type": self._arm_drive_type,
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
            "gripper_command_dofs": gripper_command_dofs,
            "gripper_current_dofs": gripper_current_dofs,
            "gripper_free_drive": self._gripper_free_drive,
            "gripper_carrier_body_path": self._gripper_carrier_body_path,
            "left_finger_body_path": self._left_finger_body_path,
            "right_finger_body_path": self._right_finger_body_path,
            "gripper_pad_material": dict(self._gripper_pad_material_status),
            "sim_grasp_state": self.get_sim_grasp_status(),
            "control_mode": "gravity_comp_effort" if self.zero_gravity_mode else "position_hold",
            "is_estopped": self._estopped,
            "command_path": (
                "articulation_controller_with_usd_mirror"
                if self._mirror_drive_targets_to_usd
                else "articulation_controller"
            ),
        }

    def command_gripper(self, value: float) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        self._require_motion_enabled()
        if not self._with_gripper:
            raise RuntimeError("No gripper attached. Start the backend with gripper enabled.")
        if self._gripper_free_drive:
            raise RuntimeError("Gripper is in free-drive mode.")
        value = float(np.clip(value, 0.0, 1.0))
        self._run_on_main_thread(lambda: self._abort_physical_grasp_impl("manual_gripper_override"))
        if self._sim_grasp_state.attached_object_path and value > float(self._gripper_open_value) + 1e-3:
            self._run_on_main_thread(lambda: self._release_attached_object_impl(open_gripper=False, timeout_s=2.0))
        else:
            self._run_on_main_thread(self._cancel_post_attach_close)
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

    def set_gripper_free_drive(self, enabled: bool) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        self._require_motion_enabled()
        if not self._with_gripper or self._gripper_joint_indices.size != 2:
            raise RuntimeError("No gripper attached. Start the backend with gripper enabled.")
        self._run_on_main_thread(lambda: self._set_gripper_free_drive_impl(bool(enabled)))

    def _set_gripper_free_drive_impl(self, enabled: bool) -> None:
        self._ensure_main_thread()
        if enabled == self._gripper_free_drive:
            return
        if enabled and self._sim_grasp_state.attached_object_path:
            raise RuntimeError("Release the attached object before enabling gripper free-drive.")
        if enabled:
            self._abort_physical_grasp_impl("gripper_free_drive")
        with self._state_lock:
            current = self._full_pos[self._gripper_joint_indices].copy()
        self._gripper_free_drive = enabled
        self._gripper_command_dofs = current.copy()
        self._gripper_target_dofs_override = current.copy()
        if enabled:
            zeros = np.zeros(2, dtype=np.float64)
            self._set_gripper_drive_profile(
                profile_name="free_drive",
                kp=zeros,
                kd=zeros,
                max_effort=zeros,
                drive_type="force",
            )
            for dof_index in self._gripper_joint_indices.tolist():
                self._switch_dof_control_mode("effort", int(dof_index))
        else:
            self._set_gripper_default_gains()
            for dof_index in self._gripper_joint_indices.tolist():
                self._switch_dof_control_mode("position", int(dof_index))
            self._set_gripper_drive_targets(current)
        self._apply_control_action()

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

    def grasp_close_physical(
        self,
        *,
        timeout_s: float = 15.0,
        minimum_normal_force_n: Optional[float] = None,
        preload_delta_m: Optional[float] = None,
        controller_profile: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Close slowly and lock the rigid body contacted by both fingers."""

        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if not self._with_gripper:
            raise RuntimeError("Physical grasp requires the gripper-enabled backend.")
        timeout = float(timeout_s)
        if timeout <= 0.0:
            raise ValueError("timeout_s must be positive")
        operation = self._run_on_main_thread(
            lambda: self._start_physical_grasp_impl(
                timeout_s=timeout,
                minimum_normal_force_n=minimum_normal_force_n,
                preload_delta_m=preload_delta_m,
                controller_profile=controller_profile,
            )
        )
        if not operation.close_done_event.wait(timeout=timeout + self._control_period_s * 4.0):
            self._run_on_main_thread(lambda: self._abort_physical_grasp_impl("client_timeout"))
            raise TimeoutError(f"Physical grasp timed out after {timeout:.3f}s")
        if operation.error is not None:
            raise RuntimeError(str(operation.error)) from operation.error
        return dict(operation.close_result or self._physical_grasp_status_payload(operation))

    def release_physical_grasp(self, *, timeout_s: float = 3.0) -> Dict[str, Any]:
        """Open the jaws and wait for the physical grasp FSM to report released."""

        timeout = float(timeout_s)
        if timeout <= 0.0:
            raise ValueError("timeout_s must be positive")
        operation = self._run_on_main_thread(self._start_physical_release_impl)
        if not operation.release_done_event.wait(timeout=timeout + self._control_period_s * 4.0):
            self._run_on_main_thread(lambda: self._abort_physical_grasp_impl("release_timeout"))
            raise TimeoutError(f"Physical grasp release timed out after {timeout:.3f}s")
        if operation.error is not None:
            raise RuntimeError(str(operation.error)) from operation.error
        return dict(operation.release_result or self._physical_grasp_status_payload(operation))

    def get_physical_grasp_status(self) -> Dict[str, Any]:
        operation = self._physical_grasp_operation
        if operation is None:
            return {
                "contract_version": 2,
                "mode": "physical",
                "success": False,
                "phase": GraspPhase.IDLE.value,
                "target_body_path": None,
                "bilateral_contact": False,
                "stable_contact_frames": 0,
                "contact_loss_frames": 0,
                "force_control_active": False,
                "force_target_reached": False,
                "force_stable_frames": 0,
                "force_loss_frames": 0,
                "resistance_confirmed": False,
                "support_body_paths": [],
                "left_support_body_paths": [],
                "right_support_body_paths": [],
                "support_contact_present": False,
                "constraint_count_delta": 0,
                "failure_reason": None,
            }
        return self._run_on_main_thread(lambda: self._physical_grasp_status_payload(operation))

    def grasp_close(self, *, timeout_s: float = 15.0) -> Dict[str, Any]:
        """Backend-neutral grasp entry point used by task execution."""
        data = dict(self.grasp_close_physical(timeout_s=timeout_s))
        data.update(
            {
                "backend": "isaacsim",
                "object_detected": bool(data.get("success")),
            }
        )
        return data

    def grasp_release(self, *, timeout_s: float = 3.0) -> Dict[str, Any]:
        """Backend-neutral release entry point used by task execution."""
        data = dict(self.release_physical_grasp(timeout_s=timeout_s))
        data.update(
            {
                "backend": "isaacsim",
                "object_detected": False,
            }
        )
        return data

    def get_grasp_status(self) -> Dict[str, Any]:
        """Return the common grasp status without exposing a simulator command."""
        data = dict(self.get_physical_grasp_status())
        data.update(
            {
                "backend": "isaacsim",
                "object_detected": bool(data.get("success")) and data.get("phase") == "holding",
            }
        )
        return data

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

    def get_sim_prim_debug(
        self,
        *,
        prim_path: str,
    ) -> Dict[str, Any]:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        return self._run_on_main_thread(
            lambda: self._get_sim_prim_debug_impl(
                prim_path=str(prim_path or ""),
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
        attached_object_path = str(self._sim_grasp_state.attached_object_path or "")
        requested_target_path = str(target_prim_path or "")
        if attached_object_path:
            current_target_path = str(self._sim_grasp_state.target_body_path or "")
            if not requested_target_path or requested_target_path == attached_object_path or requested_target_path == current_target_path:
                return {
                    "success": True,
                    "target_prim_path": requested_target_path,
                    "target_body_path": current_target_path or attached_object_path or None,
                    "attached_object_path": attached_object_path,
                    "attachment_joint_path": self._sim_grasp_state.attachment_joint_path,
                    "contact_summary": {
                        "mode": "already_attached",
                        "target_body_path": current_target_path or attached_object_path or None,
                        "chosen_body_path": attached_object_path,
                        "selected_body_contact_ready": True,
                        "ground_contact_present": False,
                    },
                    "failure_reason": None,
                    "timing": {},
                }
            raise RuntimeError(
                f"Already attached to {attached_object_path}; release before attaching a different target."
            )
        operation = self._run_on_main_thread(
            lambda: self._start_grasp_close_and_attach_impl(
                target_prim_path=str(target_prim_path or ""),
                timeout_s=float(timeout_s),
                contact_window_s=float(contact_window_s),
                require_bilateral_contact=bool(require_bilateral_contact),
            )
        )
        wait_timeout_s = max(10.0, float(operation.full_close_timeout_s) + 10.0)
        if not operation.done_event.wait(timeout=wait_timeout_s):
            raise TimeoutError("Timed out waiting for Isaac Sim grasp_attach operation to finish.")
        if operation.error is not None:
            raise RuntimeError(str(operation.error)) from operation.error
        return dict(operation.result or {})

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

    def grasp_link_current_contact(
        self,
        target_prim_path: str = "",
        *,
        require_bilateral_contact: bool = True,
    ) -> Dict[str, Any]:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        if not self._with_gripper:
            raise RuntimeError("No gripper attached. Start the backend with gripper enabled.")
        attached_object_path = str(self._sim_grasp_state.attached_object_path or "")
        requested_target_path = str(target_prim_path or "")
        if attached_object_path:
            current_target_path = str(self._sim_grasp_state.target_body_path or "")
            if not requested_target_path or requested_target_path == attached_object_path or requested_target_path == current_target_path:
                return {
                    "success": True,
                    "target_prim_path": requested_target_path,
                    "target_body_path": current_target_path or attached_object_path or None,
                    "attached_object_path": attached_object_path,
                    "attachment_joint_path": self._sim_grasp_state.attachment_joint_path,
                    "contact_summary": {
                        "mode": "already_attached",
                        "target_body_path": current_target_path or attached_object_path or None,
                        "chosen_body_path": attached_object_path,
                        "selected_body_contact_ready": True,
                        "ground_contact_present": False,
                    },
                    "failure_reason": None,
                    "timing": {},
                }
            raise RuntimeError(
                f"Already attached to {attached_object_path}; release before attaching a different target."
            )
        return self._run_on_main_thread(
            lambda: self._grasp_link_current_contact_impl(
                target_prim_path=str(target_prim_path or ""),
                require_bilateral_contact=bool(require_bilateral_contact),
            )
        )

    def command_joint_pos(self, pos: np.ndarray) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        self._require_motion_enabled()
        pos = np.asarray(pos, dtype=np.float64).reshape(-1)
        arm_target = self._clip_arm_pos(pos[: self._num_joints])
        gripper_target = None
        if self._with_gripper and pos.shape[0] == self._num_joints + 1:
            if self._gripper_free_drive:
                raise RuntimeError("Gripper is in free-drive mode.")
            gripper_target = float(np.clip(pos[self._num_joints], 0.0, 1.0))
        self._run_on_main_thread(lambda: self._set_command_now(arm_target, gripper_target))

    def command_joint_state(self, joint_state: Dict[str, np.ndarray]) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        self._require_motion_enabled()
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
        self._require_motion_enabled()
        speed = self._arm_motion_speed_limits.validate(speed)

        target_pos = np.asarray(target_pos, dtype=np.float64).reshape(-1)
        arm_target = self._clip_arm_pos(target_pos[: self._num_joints])
        gripper_target = None
        if self._with_gripper and target_pos.shape[0] == self._num_joints + 1:
            if self._gripper_free_drive:
                raise RuntimeError("Gripper is in free-drive mode.")
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
        self._require_motion_enabled()
        self._run_on_main_thread(lambda: self._set_gravity_mode_impl(enabled))

    def start_recording(self, sample_hz: int = 50) -> None:
        if not self._running:
            raise RuntimeError("Robot not running. Call start() first.")
        self._require_motion_enabled()
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
        self._require_motion_enabled()
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
        self._gripper_target_dofs_override = None
        self._apply_control_action()

    def _set_gripper_dof_target(self, target_dofs: np.ndarray) -> None:
        target = self._clip_gripper_dofs(
            np.asarray(target_dofs, dtype=np.float64).reshape(-1)[:2]
        )
        if target.shape[0] != 2 or not np.all(np.isfinite(target)):
            raise ValueError("gripper DOF target must contain two finite values")
        self._gripper_target_dofs_override = target.copy()
        width = abs(float(target[0] - target[1]))
        width_range = max(
            1e-9,
            abs(self._gripper_left_open - self._gripper_right_open)
            - abs(self._gripper_left_closed - self._gripper_right_closed),
        )
        closed_width = abs(self._gripper_left_closed - self._gripper_right_closed)
        self._gripper_target_value = float(
            np.clip((width - closed_width) / width_range, 0.0, 1.0)
        )
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
            self._gripper_target_dofs_override = None
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
        self._require_motion_enabled()
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
        self._require_motion_enabled()
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
        candidates: list[Usd.Prim] = []
        for prim in Usd.PrimRange(root_prim):
            if prim.GetName() == prim_name:
                candidates.append(prim)
        if not candidates:
            return ""

        def _candidate_key(prim: Usd.Prim) -> tuple[int, int, int]:
            # Imported links such as gripper fingers contain an outer rigid-body
            # link prim plus inner same-name visual instances. Prefer the actual
            # rigid/collision-bearing link prim and fall back to the shallowest
            # match if no physics-bearing candidate exists.
            physics_score = 0
            if self._stage_prim_is_rigid_body(prim):
                physics_score += 2
            if self._stage_prim_has_collision(prim):
                physics_score += 1
            return (-physics_score, prim.GetPath().pathElementCount, len(str(prim.GetPath())))

        return str(min(candidates, key=_candidate_key).GetPath())

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

    def _ensure_gripper_pad_physics_material(self) -> dict[str, Any]:
        self._ensure_gripper_structure_paths()
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is unavailable while configuring gripper friction.")

        UsdGeom.Scope.Define(stage, "/World/PhysicsMaterials")
        material = UsdShade.Material.Define(stage, self._GRIPPER_PAD_MATERIAL_PATH)
        material_api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        material_api.CreateStaticFrictionAttr().Set(self._GRIPPER_PAD_STATIC_FRICTION)
        material_api.CreateDynamicFrictionAttr().Set(self._GRIPPER_PAD_DYNAMIC_FRICTION)
        material_api.CreateRestitutionAttr().Set(0.0)
        physx_material_api = PhysxSchema.PhysxMaterialAPI.Apply(material.GetPrim())
        physx_material_api.CreateFrictionCombineModeAttr().Set("max")
        physx_material_api.CreateRestitutionCombineModeAttr().Set("min")

        collision_paths: list[str] = []
        for body_path in (self._left_finger_body_path, self._right_finger_body_path):
            collision_path = self._resolve_first_collision_descendant_path(body_path)
            if not collision_path:
                continue
            collision_prim = stage.GetPrimAtPath(collision_path)
            if not collision_prim.IsValid():
                continue
            UsdShade.MaterialBindingAPI.Apply(collision_prim)
            collision_prim.CreateRelationship(
                "material:binding:physics", custom=False
            ).SetTargets([Sdf.Path(self._GRIPPER_PAD_MATERIAL_PATH)])
            collision_paths.append(collision_path)

        status = {
            "ready": len(collision_paths) == 2,
            "material_path": self._GRIPPER_PAD_MATERIAL_PATH,
            "static_friction": self._GRIPPER_PAD_STATIC_FRICTION,
            "dynamic_friction": self._GRIPPER_PAD_DYNAMIC_FRICTION,
            "friction_combine_mode": "max",
            "collision_paths": collision_paths,
        }
        self._gripper_pad_material_status = status
        return status

    def _nested_rigid_body_paths(self) -> list[str]:
        self._ensure_gripper_structure_paths()
        paths = [
            self._gripper_carrier_body_path,
            self._left_finger_body_path,
            self._right_finger_body_path,
        ]
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return [path for path in paths if path]
        d405_link_path = self._resolve_named_descendant_path(self._articulation_root_prim, "d405_link")
        d405_body_path = self._find_rigid_body_ancestor_path(d405_link_path)
        if d405_body_path:
            paths.append(d405_body_path)
        unique: list[str] = []
        seen: set[str] = set()
        for path in paths:
            path = str(path or "")
            if not path or path in seen:
                continue
            if not stage.GetPrimAtPath(path).IsValid():
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _preserve_world_transform_with_reset(self, prim: Usd.Prim, world_transform: Gf.Matrix4d) -> None:
        xformable = UsdGeom.Xformable(prim)
        if not xformable:
            return
        for op in list(xformable.GetOrderedXformOps()):
            prim.RemoveProperty(op.GetOpName())
        xformable.ClearXformOpOrder()
        xformable.AddTransformOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Matrix4d(world_transform))
        xformable.SetResetXformStack(True)

    def _repair_nested_rigid_body_reset_xforms(self, *, reason: str) -> list[str]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return []
        repaired: list[str] = []
        for prim_path in self._nested_rigid_body_paths():
            prim = stage.GetPrimAtPath(prim_path)
            if not prim.IsValid() or not self._stage_prim_is_rigid_body(prim):
                continue
            xformable = UsdGeom.Xformable(prim)
            if not xformable:
                continue
            if xformable.GetResetXformStack():
                continue
            world_transform = Gf.Matrix4d(xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
            self._preserve_world_transform_with_reset(prim, world_transform)
            repaired.append(prim_path)
            if prim_path not in self._nested_rigid_body_reset_flip_logged:
                carb.log_warn(
                    "A1Z Isaac repaired nested rigid-body resetXformStack at runtime: "
                    f"path={prim_path} reason={reason}"
                )
                self._nested_rigid_body_reset_flip_logged.add(prim_path)
        self._nested_rigid_body_reset_repaired.update(repaired)
        return repaired

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

    def _build_grasp_attach_contact_filter_paths(
        self,
        *,
        target_body_path: str,
        seed_paths: Optional[list[str]] = None,
    ) -> list[str]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return []
        self._ensure_gripper_structure_paths()

        candidates: list[str] = []
        ground_path = "/World/GroundPlane"
        if stage.GetPrimAtPath(ground_path).IsValid():
            candidates.append(ground_path)

        for path in seed_paths or []:
            resolved = self._resolve_contact_body_path(path)
            if resolved:
                candidates.append(resolved)

        if target_body_path:
            resolved_target = self._resolve_contact_body_path(target_body_path)
            if resolved_target:
                candidates.append(resolved_target)

        anchor_path = self._gripper_carrier_body_path or self._left_finger_body_path or self._right_finger_body_path
        anchor_translation: Optional[np.ndarray] = None
        if anchor_path and stage.GetPrimAtPath(anchor_path).IsValid():
            try:
                anchor_translation = np.asarray(
                    self._get_world_transform(anchor_path).ExtractTranslation(),
                    dtype=np.float64,
                ).reshape(-1)[:3]
            except Exception:
                anchor_translation = None

        nearby: list[tuple[float, str]] = []
        trash_root = stage.GetPrimAtPath("/World/TrashSet")
        if trash_root.IsValid():
            for prim in trash_root.GetChildren():
                resolved = self._resolve_target_rigid_body_path(str(prim.GetPath()))
                if not resolved:
                    if self._stage_prim_has_collision(prim):
                        resolved = str(prim.GetPath())
                    else:
                        continue
                if resolved in {
                    self._left_finger_body_path,
                    self._right_finger_body_path,
                    self._gripper_carrier_body_path,
                }:
                    continue
                distance = float("inf")
                if anchor_translation is not None:
                    try:
                        body_translation = np.asarray(
                            self._get_world_transform(resolved).ExtractTranslation(),
                            dtype=np.float64,
                        ).reshape(-1)[:3]
                        distance = float(np.linalg.norm(body_translation - anchor_translation))
                    except Exception:
                        distance = float("inf")
                nearby.append((distance, resolved))

        nearby.sort(key=lambda item: (item[0], item[1]))
        within_radius = [
            path
            for distance, path in nearby
            if np.isfinite(distance) and distance <= float(self._GRASP_ATTACH_CONTACT_FILTER_RADIUS_M)
        ]
        if within_radius:
            candidates.extend(within_radius[: self._GRASP_ATTACH_CONTACT_FILTER_MAX_BODIES])
        else:
            candidates.extend([path for _, path in nearby[: self._GRASP_ATTACH_CONTACT_FILTER_MAX_BODIES]])

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

    def _get_rigid_body_world_transform(self, prim_path: str) -> Gf.Matrix4d:
        body_path = self._resolve_target_rigid_body_path(prim_path) or str(prim_path or "")
        if not body_path:
            raise RuntimeError("Rigid body path is empty.")
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is unavailable.")
        prim = stage.GetPrimAtPath(body_path)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid rigid body prim path: {body_path}")
        view = self._rigid_body_view_cache.get(body_path)
        if view is None:
            view = RigidPrim(
                prim_paths_expr=body_path,
                name=f"a1z_rigid_body_pose_{len(self._rigid_body_view_cache)}",
                reset_xform_properties=False,
            )
            self._rigid_body_view_cache[body_path] = view
        if not view.is_physics_handle_valid():
            view.initialize(SimulationManager.get_physics_sim_view())
        positions, orientations = view.get_world_poses(clone=True)
        position = self._to_numpy_array(positions).reshape(-1, 3)[0]
        orientation = self._to_numpy_array(orientations).reshape(-1, 4)[0]
        transform = Gf.Matrix4d(1.0)
        transform.SetRotateOnly(
            Gf.Rotation(
                Gf.Quatd(
                    float(orientation[0]),
                    float(orientation[1]),
                    float(orientation[2]),
                    float(orientation[3]),
                )
            )
        )
        transform.SetTranslateOnly(
            Gf.Vec3d(
                float(position[0]),
                float(position[1]),
                float(position[2]),
            )
        )
        return transform

    @staticmethod
    def _matrix_to_pose_components(transform: Gf.Matrix4d) -> tuple[Gf.Vec3f, Gf.Quatf]:
        translation = transform.ExtractTranslation()
        rotation = transform.ExtractRotation().GetQuat()
        return (
            Gf.Vec3f(float(translation[0]), float(translation[1]), float(translation[2])),
            Gf.Quatf(float(rotation.GetReal()), float(rotation.GetImaginary()[0]), float(rotation.GetImaginary()[1]), float(rotation.GetImaginary()[2])),
        )

    @staticmethod
    def _rigidize_transform(transform: Gf.Matrix4d) -> Gf.Matrix4d:
        rigid = Gf.Matrix4d(1.0)
        rigid.SetRotateOnly(transform.ExtractRotation())
        rigid.SetTranslateOnly(transform.ExtractTranslation())
        return rigid

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

    def _cleanup_active_attachment_state(self) -> None:
        joint_path = str(self._sim_grasp_state.attachment_joint_path or "")
        if joint_path:
            self._remove_attachment_joint(joint_path)
        self._clear_filtered_pairs(list(self._sim_grasp_state.filtered_pairs))
        attached_object_path = str(self._sim_grasp_state.attached_object_path or "")
        if attached_object_path:
            self._restore_attach_compliance_profile(
                attached_object_path,
                dict(self._sim_grasp_state.rigid_body_restore),
            )
        self._sim_grasp_state.filtered_pairs = []
        self._sim_grasp_state.rigid_body_restore = {}
        self._sim_grasp_state.attached_object_path = None
        self._sim_grasp_state.attachment_joint_path = None
        self._cancel_post_attach_close()

    def _set_gripper_drive_profile(
        self,
        *,
        profile_name: str,
        kp: np.ndarray,
        kd: np.ndarray,
        max_effort: np.ndarray,
        drive_type: str = "acceleration",
    ) -> None:
        if not self._with_gripper or self._gripper_joint_indices.size != 2:
            return
        drive_type = str(drive_type).strip().lower()
        if drive_type not in {"force", "acceleration"}:
            raise ValueError(
                "gripper drive_type must be 'force' or 'acceleration', "
                f"got {drive_type!r}"
            )
        profile_key = f"{profile_name}:{drive_type}"
        if profile_key == self._active_gripper_drive_profile:
            return
        kp = np.asarray(kp, dtype=np.float64).reshape(-1)[:2]
        kd = np.asarray(kd, dtype=np.float64).reshape(-1)[:2]
        max_effort = np.asarray(max_effort, dtype=np.float64).reshape(-1)[:2]
        self._set_subset_effort_mode(drive_type, self._gripper_joint_indices)
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
            if prim.HasAttribute("drive:linear:physics:type"):
                drive.GetTypeAttr().Set(drive_type)
            else:
                drive.CreateTypeAttr().Set(drive_type)
            drive.GetStiffnessAttr().Set(float(kp[local_idx]))
            drive.GetDampingAttr().Set(float(kd[local_idx]))
            drive.GetMaxForceAttr().Set(float(max_effort[local_idx]))
        self._active_gripper_drive_profile = profile_key

    def _set_gripper_soft_grasp_gains(self) -> None:
        self._set_gripper_drive_profile(
            profile_name="soft_grasp",
            kp=self._gripper_soft_kp,
            kd=self._gripper_soft_kd,
            max_effort=self._gripper_soft_max_effort,
        )

    def _set_gripper_hold_gains(self) -> None:
        self._set_gripper_drive_profile(
            profile_name="hold",
            kp=self._gripper_hold_kp,
            kd=self._gripper_hold_kd,
            max_effort=self._gripper_hold_max_effort,
        )

    def _set_gripper_search_gains(self) -> None:
        self._set_gripper_drive_profile(
            profile_name="search",
            kp=self._gripper_search_kp,
            kd=self._gripper_search_kd,
            max_effort=self._gripper_search_max_effort,
        )

    def _set_gripper_default_gains(self) -> None:
        self._set_gripper_drive_profile(
            profile_name="default",
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
            self._repair_nested_rigid_body_reset_xforms(reason="before_contact_view_create")
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
                reset_xform_properties=False,
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
            repaired = self._repair_nested_rigid_body_reset_xforms(reason="after_contact_view_create")
            if repaired:
                carb.log_warn(
                    "A1Z Isaac preserved nested rigid-body resetXformStack after contact view creation: "
                    + ", ".join(repaired)
                )
        try:
            if not entry.view.is_physics_handle_valid():
                entry.view.initialize(SimulationManager.get_physics_sim_view())
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac failed to initialize contact-force view: {exc}")
            self._contact_view_cache.pop(key, None)
            return None
        self._repair_nested_rigid_body_reset_xforms(reason="after_contact_view_init")
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

    def _poll_grasp_body_contacts(
        self,
        *,
        filter_paths: Optional[list[str]] = None,
    ) -> dict[str, list[dict[str, object]]]:
        self._ensure_gripper_structure_paths()
        if filter_paths is None:
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

    @staticmethod
    def _preferred_unilateral_contact_candidate(summary: dict[str, object]) -> str:
        target_body_path = str(summary.get("target_body_path", "") or "")
        if target_body_path and (
            bool(summary.get("left_has_target_contact")) or bool(summary.get("right_has_target_contact"))
        ):
            return target_body_path
        left_candidates = list(summary.get("left_contacts", []) or [])
        right_candidates = list(summary.get("right_contacts", []) or [])
        left_contact_details = list(summary.get("left_contact_details", []) or [])
        right_contact_details = list(summary.get("right_contact_details", []) or [])
        return str(
            select_contact_candidate(
                left_candidates=left_candidates,
                right_candidates=right_candidates,
                left_contact_details=left_contact_details,
                right_contact_details=right_contact_details,
                require_bilateral_contact=False,
            )
            or ""
        )

    def _attachment_body0_path(self) -> str:
        return (
            self._gripper_carrier_body_path
            or self._left_finger_body_path
            or self._right_finger_body_path
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

    def _get_sim_prim_debug_impl(
        self,
        *,
        prim_path: str,
    ) -> Dict[str, Any]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is unavailable.")
        query_path = str(prim_path or "")
        prim = stage.GetPrimAtPath(query_path)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid prim path: {query_path}")

        parent = prim.GetParent()
        world = self._get_world_transform(query_path)
        xformable = UsdGeom.Xformable(prim)
        local_result = xformable.GetLocalTransformation(Usd.TimeCode.Default())
        if isinstance(local_result, tuple):
            local_matrix = local_result[0]
        else:
            local_matrix = local_result
        resets_stack = bool(xformable.GetResetXformStack())

        result: Dict[str, Any] = {
            "prim_path": query_path,
            "prim_type": prim.GetTypeName(),
            "parent_path": str(parent.GetPath()) if parent and parent.IsValid() else None,
            "child_paths": [str(child.GetPath()) for child in prim.GetChildren()],
            "is_rigid_body": self._stage_prim_is_rigid_body(prim),
            "has_collision": self._stage_prim_has_collision(prim),
            "world_matrix": [[float(value) for value in row] for row in np.asarray(world, dtype=np.float64).tolist()],
            "world_translation": self._vec3_to_tuple(world.ExtractTranslation()),
            "local_translation": self._vec3_to_tuple(local_matrix.ExtractTranslation()),
            "resets_xform_stack": bool(resets_stack),
            "resolved_rigid_body_path": self._resolve_target_rigid_body_path(query_path) or None,
            "first_collision_descendant_path": self._resolve_first_collision_descendant_path(query_path) or None,
        }
        if result["is_rigid_body"]:
            try:
                physics_world = self._get_rigid_body_world_transform(query_path)
                result["physics_world_translation"] = self._vec3_to_tuple(physics_world.ExtractTranslation())
            except Exception as exc:
                result["physics_world_translation_error"] = str(exc)

        if prim.IsA(UsdPhysics.Joint):
            joint = UsdPhysics.Joint(prim)
            body0 = [str(path) for path in (joint.GetBody0Rel().GetTargets() or [])]
            body1 = [str(path) for path in (joint.GetBody1Rel().GetTargets() or [])]
            result["joint"] = {
                "body0": body0,
                "body1": body1,
                "local_pos0": self._vec3_to_tuple(joint.GetLocalPos0Attr().Get()),
                "local_pos1": self._vec3_to_tuple(joint.GetLocalPos1Attr().Get()),
            }
            if prim.IsA(UsdPhysics.PrismaticJoint):
                prismatic = UsdPhysics.PrismaticJoint(prim)
                result["joint"]["axis"] = str(prismatic.GetAxisAttr().Get() or "")
                lower = prim.GetAttribute("physics:lowerLimit")
                upper = prim.GetAttribute("physics:upperLimit")
                result["joint"]["lower_limit"] = float(lower.Get()) if lower.IsValid() and lower.Get() is not None else None
                result["joint"]["upper_limit"] = float(upper.Get()) if upper.IsValid() and upper.Get() is not None else None
        return result

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
        source_path = self._gripper_carrier_body_path
        if source_path:
            self._set_filtered_pair(source_path, attached_body_path)
            self._set_filtered_pair(attached_body_path, source_path)
            applied_pairs.append((source_path, attached_body_path))
            applied_pairs.append((attached_body_path, source_path))
        return applied_pairs

    def _start_post_attach_close(self, body_path: str) -> None:
        if not body_path or not self._with_gripper:
            return
        current_gripper = float(self._gripper_open_value)
        target_value = 0.0
        if current_gripper <= target_value + 1e-4:
            self._sim_grasp_state.post_attach_closing_active = False
            self._sim_grasp_state.post_attach_stable_count = 0
            self._sim_grasp_state.post_attach_required_count = 0
            self._sim_grasp_state.post_attach_target_value = current_gripper
            self._set_gripper_target(current_gripper)
            self._set_gripper_hold_gains()
            return
        self._sim_grasp_state.grasp_state = "attached_closing"
        self._sim_grasp_state.post_attach_closing_active = True
        self._sim_grasp_state.post_attach_stable_count = 0
        self._sim_grasp_state.post_attach_required_count = self._POST_ATTACH_CLOSE_REQUIRED_CONTACT_COUNT
        self._sim_grasp_state.post_attach_target_value = target_value
        self._set_gripper_soft_grasp_gains()
        self._set_gripper_target(target_value)

    def _cancel_post_attach_close(self) -> None:
        self._sim_grasp_state.post_attach_closing_active = False
        self._sim_grasp_state.post_attach_stable_count = 0
        self._sim_grasp_state.post_attach_required_count = 0
        self._sim_grasp_state.post_attach_target_value = float(self._gripper_target_value)
        if self._sim_grasp_state.attached_object_path:
            self._sim_grasp_state.grasp_state = "attached"

    def _advance_post_attach_close(self) -> None:
        if not self._sim_grasp_state.post_attach_closing_active:
            return
        attached_body_path = str(self._sim_grasp_state.attached_object_path or "")
        if not attached_body_path:
            self._cancel_post_attach_close()
            return
        contacts = self._poll_grasp_body_contacts(filter_paths=[attached_body_path])
        _, _, summary = self._contact_satisfies_attach(
            contacts,
            target_body_path=attached_body_path,
            require_bilateral_contact=False,
        )
        if bool(summary.get("ground_contact_present")):
            return
        if bool(summary.get("selected_body_contact_ready")):
            self._sim_grasp_state.post_attach_stable_count += 1
        else:
            self._sim_grasp_state.post_attach_stable_count = 0
        current_open = float(self._gripper_open_value)
        if (
            self._sim_grasp_state.post_attach_stable_count
            >= max(1, int(self._sim_grasp_state.post_attach_required_count))
            or self._is_gripper_near_closed(current_open)
        ):
            self._cancel_post_attach_close()
            self._sim_grasp_state.post_attach_target_value = current_open
            self._set_gripper_target(current_open)
            self._set_gripper_hold_gains()

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
        elif close_phase == "search_close":
            self._set_gripper_search_gains()
        else:
            self._set_gripper_default_gains()


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
        body0_path: str,
        chosen_body_path: str,
        attach_summary: dict[str, object],
    ) -> tuple[Gf.Matrix4d, dict[str, object]]:
        body0_world = self._rigidize_transform(self._get_rigid_body_world_transform(body0_path))
        chosen_body_world = self._rigidize_transform(self._get_rigid_body_world_transform(chosen_body_path))
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
        source = "body0_physics_world_pose"
        if left_point is not None and right_point is not None:
            attach_point = 0.5 * (left_point + right_point)
            source = "body0_physics_world_pose_with_bilateral_contact_reference"
        elif left_point is not None:
            attach_point = left_point
            source = "body0_physics_world_pose_with_left_contact_reference"
        elif right_point is not None:
            attach_point = right_point
            source = "body0_physics_world_pose_with_right_contact_reference"

        attach_world = Gf.Matrix4d(body0_world)
        meta: dict[str, object] = {
            "attach_anchor_source": source,
            "left_contact_point_world_m": left_point.tolist() if left_point is not None else None,
            "right_contact_point_world_m": right_point.tolist() if right_point is not None else None,
            "attach_anchor_rotation_source": "body0_physics_world_rotation",
            "attach_body0_path": body0_path or None,
            "attach_body0_world_m": self._vec3_to_tuple(body0_world.ExtractTranslation()),
            "attach_body1_path": chosen_body_path or None,
            "attach_body1_world_m": self._vec3_to_tuple(chosen_body_world.ExtractTranslation()),
        }
        if attach_point is not None:
            attach_world.SetTranslateOnly(Gf.Vec3d(*attach_point.tolist()))
            meta["attach_anchor_world_m"] = attach_point.tolist()
        else:
            origin = body0_world.ExtractTranslation()
            meta["attach_anchor_world_m"] = [float(origin[0]), float(origin[1]), float(origin[2])]
        meta["attach_contact_reference_world_m"] = attach_point.tolist() if attach_point is not None else None
        return attach_world, meta

    def _create_link6_relative_attachment(
        self,
        *,
        body_path: str,
        summary: dict[str, object],
        target_prim_path: str,
    ) -> Dict[str, Any]:
        body0_path = self._attachment_body0_path()
        if not body0_path:
            self._sim_grasp_state.grasp_state = "failed"
            self._sim_grasp_state.last_failure_reason = "grasp_attach_body0_unavailable"
            return {
                "success": False,
                "target_prim_path": target_prim_path or "",
                "target_body_path": str(self._sim_grasp_state.target_body_path or "") or None,
                "attached_object_path": None,
                "attachment_joint_path": None,
                "contact_summary": dict(summary),
                "failure_reason": "grasp_attach_body0_unavailable",
                "timing": {},
            }
        attach_world, attach_anchor_meta = self._compute_attach_world(
            body0_path=body0_path,
            chosen_body_path=body_path,
            attach_summary=summary,
        )
        result_summary = dict(summary)
        result_summary.update(attach_anchor_meta)
        joint_path = (
            f"/World/SimulationGraspAttachments/{body_path or 'auto'}"
            .replace("//", "/")
            .replace(":", "_")
            .replace(".", "_")
        )
        attachment_joint_path = self._create_attachment_joint(
            joint_path=joint_path,
            body0_path=body0_path,
            body1_path=body_path,
            attach_world=attach_world,
        )
        filtered_pairs = self._filter_attached_collisions(body_path)
        rigid_body_restore = self._apply_attach_compliance_profile(body_path)
        self._sim_grasp_state.grasp_state = "attached"
        self._sim_grasp_state.attached_object_path = body_path
        self._sim_grasp_state.attachment_joint_path = attachment_joint_path
        self._sim_grasp_state.target_prim_path = target_prim_path or None
        self._sim_grasp_state.target_body_path = body_path
        self._sim_grasp_state.last_contact_time = time.time()
        self._sim_grasp_state.last_failure_reason = None
        self._sim_grasp_state.filtered_pairs = list(filtered_pairs)
        self._sim_grasp_state.rigid_body_restore = dict(rigid_body_restore)
        self._start_post_attach_close(body_path)
        return {
            "success": True,
            "target_prim_path": target_prim_path or "",
            "target_body_path": body_path,
            "attached_object_path": body_path,
            "attachment_joint_path": attachment_joint_path,
            "contact_summary": result_summary,
            "failure_reason": None,
            "timing": {},
        }

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
        carrier_world = self._rigidize_transform(self._get_rigid_body_world_transform(body0_path))
        target_world = self._rigidize_transform(self._get_rigid_body_world_transform(body1_path))
        attach_world = self._rigidize_transform(attach_world)
        # USD/Gf joint local frames compose in the same direction used by Isaac's
        # fixed-joint assembler helpers: local * body_world = anchor_world.
        local0 = attach_world * carrier_world.GetInverse()
        local1 = attach_world * target_world.GetInverse()
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

    def _physics_constraint_paths(self) -> frozenset[str]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return frozenset()
        return frozenset(
            str(prim.GetPath())
            for prim in stage.Traverse()
            if prim.IsValid() and prim.IsA(UsdPhysics.Joint)
        )

    def _target_physics_state(self, body_path: str) -> Dict[str, bool]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Isaac stage is unavailable while auditing target physics state.")
        prim = stage.GetPrimAtPath(body_path)
        if not prim.IsValid():
            raise RuntimeError(f"Target rigid body disappeared during physical grasp: {body_path}")

        def read_bool(name: str, default: bool) -> bool:
            attribute = prim.GetAttribute(name)
            if not attribute.IsValid():
                return default
            value = attribute.Get()
            return default if value is None else bool(value)

        return {
            "rigid_body_enabled": read_bool(
                "physics:rigidBodyEnabled", prim.HasAPI(UsdPhysics.RigidBodyAPI)
            ),
            "kinematic_enabled": read_bool("physics:kinematicEnabled", False),
            "gravity_disabled": read_bool("physxRigidBody:disableGravity", False),
        }

    def _validate_physical_grasp_target(
        self,
        body_path: str,
    ) -> tuple[str, Dict[str, bool], tuple[float, float, float]]:
        requested_path = str(body_path or "")
        if not requested_path.startswith("/"):
            raise ValueError("discovered physical grasp body path must be absolute")
        resolved_path = self._resolve_target_rigid_body_path(requested_path)
        if not resolved_path:
            raise ValueError(
                f"physical grasp contact does not resolve to an enabled rigid body: {requested_path}"
            )
        state = self._target_physics_state(resolved_path)
        if not bool(state.get("rigid_body_enabled")):
            raise ValueError(f"physical grasp body is not dynamic: {resolved_path}")
        if bool(state.get("kinematic_enabled")):
            raise ValueError(f"physical grasp body must not be kinematic: {resolved_path}")
        if bool(state.get("gravity_disabled")):
            raise ValueError(f"physical grasp body must remain gravity-enabled: {resolved_path}")
        if not self._resolve_first_collision_descendant_path(resolved_path):
            raise ValueError(f"physical grasp body has no enabled collision shape: {resolved_path}")
        transform = self._get_rigid_body_world_transform(resolved_path)
        translation = self._vec3_to_tuple(transform.ExtractTranslation())
        if translation is None:
            raise RuntimeError(
                f"physical grasp body world translation is unavailable: {resolved_path}"
            )
        return resolved_path, state, translation

    def _physics_dt_s(self) -> float:
        world = self._world
        getter = getattr(world, "get_physics_dt", None)
        if not callable(getter):
            raise RuntimeError("Isaac World does not expose get_physics_dt(); physical forces are unavailable.")
        physics_dt_s = float(getter())
        if not np.isfinite(physics_dt_s) or physics_dt_s <= 0.0 or physics_dt_s > 1.0:
            raise RuntimeError(f"Invalid Isaac physics dt for physical grasp: {physics_dt_s!r}")
        return physics_dt_s

    def _physical_jaw_mapping(self) -> ParallelJawMapping:
        if self._gripper_joint_indices.size != 2:
            raise RuntimeError("Physical grasp requires two resolved gripper DOFs.")
        return ParallelJawMapping.from_sequences(
            open_dofs_m=(self._gripper_left_open, self._gripper_right_open),
            closed_dofs_m=(self._gripper_left_closed, self._gripper_right_closed),
        )

    def _start_physical_grasp_impl(
        self,
        *,
        timeout_s: float,
        minimum_normal_force_n: Optional[float],
        preload_delta_m: Optional[float],
        controller_profile: Optional[Mapping[str, Any]],
    ) -> _PhysicalGraspOperation:
        self._ensure_main_thread()
        if self._pending_grasp_attach is not None or self._sim_grasp_state.attached_object_path:
            raise RuntimeError("Release the legacy grasp attachment before starting physical grasp v2.")
        existing = self._physical_grasp_operation
        if existing is not None and existing.fsm.phase not in {
            GraspPhase.RELEASED,
            GraspPhase.FAILED,
            GraspPhase.ABORTED,
        }:
            raise RuntimeError(f"Physical grasp is already active in phase {existing.fsm.phase.value}.")
        self._ensure_gripper_structure_paths()
        pad_status = self._ensure_gripper_pad_physics_material()
        if not pad_status["ready"]:
            raise RuntimeError(
                "Physical grasp requires high-friction material bindings on both finger "
                f"colliders; resolved={pad_status['collision_paths']}"
            )
        mapping = self._physical_jaw_mapping()
        profile = None if controller_profile is None else dict(controller_profile)
        if profile is None:
            max_close_velocity_m_s = min(
                self._GRASP_CLOSE_MAX_VELOCITY_M_S,
                0.008,
            )
            max_command_lead_m = self._PHYSICAL_GRASP_MAX_COMMAND_LEAD_M
            preload = 0.0005 if preload_delta_m is None else float(preload_delta_m)
            maximum_preload = min(0.006, 0.25 * (mapping.open_width_m - mapping.closed_width_m))
            config = PhysicalGraspConfig(
                open_width_m=mapping.open_width_m,
                closed_width_m=mapping.closed_width_m,
                preload_delta_m=preload,
                maximum_preload_delta_m=maximum_preload,
                minimum_stable_frames=5,
                minimum_normal_force_n=(
                    None if minimum_normal_force_n is None else float(minimum_normal_force_n)
                ),
                precheck_timeout_s=timeout_s * 0.15,
                soft_close_timeout_s=timeout_s * 0.25,
                search_timeout_s=timeout_s * 0.35,
                hold_confirm_timeout_s=timeout_s * 0.10,
                target_normal_force_n=0.75,
                maximum_normal_force_n=3.0,
                force_hysteresis_n=0.12,
                force_confirm_frames=5,
                preload_step_m=0.0001,
                preload_timeout_s=timeout_s * 0.15,
                contact_loss_grace_frames=3,
                force_loss_grace_frames=6,
                unilateral_recovery_timeout_s=1.0,
            )
        else:
            max_close_velocity_m_s = float(profile["max_close_velocity_m_s"])
            if not np.isfinite(max_close_velocity_m_s) or max_close_velocity_m_s <= 0.0:
                raise ValueError("controller profile max_close_velocity_m_s must be positive")
            max_command_lead_m = float(
                profile.get("max_command_lead_m", self._PHYSICAL_GRASP_MAX_COMMAND_LEAD_M)
            )
            if not np.isfinite(max_command_lead_m) or max_command_lead_m <= 0.0:
                raise ValueError("controller profile max_command_lead_m must be positive")
            config = PhysicalGraspConfig.from_controller_profile(profile)
            if not np.isclose(config.open_width_m, mapping.open_width_m, atol=1e-4) or not np.isclose(
                config.closed_width_m, mapping.closed_width_m, atol=1e-4
            ):
                raise ValueError(
                    "controller profile jaw widths do not match the active Isaac articulation: "
                    f"profile=[{config.closed_width_m}, {config.open_width_m}] "
                    f"articulation=[{mapping.closed_width_m}, {mapping.open_width_m}]"
                )
            config = PhysicalGraspConfig(
                open_width_m=config.open_width_m,
                closed_width_m=config.closed_width_m,
                preload_delta_m=(
                    config.preload_delta_m if preload_delta_m is None else float(preload_delta_m)
                ),
                maximum_preload_delta_m=config.maximum_preload_delta_m,
                minimum_stable_frames=config.minimum_stable_frames,
                minimum_normal_force_n=(
                    config.minimum_normal_force_n
                    if minimum_normal_force_n is None
                    else float(minimum_normal_force_n)
                ),
                precheck_timeout_s=config.precheck_timeout_s,
                soft_close_timeout_s=config.soft_close_timeout_s,
                search_timeout_s=config.search_timeout_s,
                hold_confirm_timeout_s=config.hold_confirm_timeout_s,
                force_window_frames=config.force_window_frames,
                target_normal_force_n=config.target_normal_force_n,
                maximum_normal_force_n=config.maximum_normal_force_n,
                force_hysteresis_n=config.force_hysteresis_n,
                force_confirm_frames=config.force_confirm_frames,
                preload_step_m=config.preload_step_m,
                preload_timeout_s=config.preload_timeout_s,
                contact_loss_grace_frames=config.contact_loss_grace_frames,
                force_loss_grace_frames=config.force_loss_grace_frames,
                minimum_effort_residual_n=config.minimum_effort_residual_n,
                minimum_position_lag_m=config.minimum_position_lag_m,
                unilateral_recovery_timeout_s=config.unilateral_recovery_timeout_s,
            )
            configured_duration_s = (
                config.precheck_timeout_s
                + config.soft_close_timeout_s
                + config.search_timeout_s
                + config.preload_timeout_s
                + config.hold_confirm_timeout_s
            )
            if configured_duration_s > timeout_s:
                raise ValueError(
                    f"timeout_s={timeout_s} is shorter than controller profile budget "
                    f"{configured_duration_s:.3f}s"
                )
        fsm = PhysicalGraspFSM(config)
        operation = _PhysicalGraspOperation(
            fsm=fsm,
            mapping=mapping,
            target_body_path="",
            initial_constraint_paths=self._physics_constraint_paths(),
            initial_target_physics_state={},
            initial_target_world_translation_m=None,
            max_close_velocity_m_s=max_close_velocity_m_s,
            max_command_lead_m=max_command_lead_m,
            controller_profile=profile,
            started_at_s=time.monotonic(),
            minimum_effort_residual_n=config.minimum_effort_residual_n,
            minimum_position_lag_m=config.minimum_position_lag_m,
        )
        self._physical_grasp_operation = operation
        initial_width_m = mapping.dofs_to_width(
            self._full_pos[self._gripper_joint_indices].copy()
        )
        status = fsm.begin(
            now_s=operation.started_at_s,
            initial_width_m=initial_width_m,
        )
        self._apply_physical_grasp_command(operation, status)
        return operation

    def _start_physical_release_impl(self) -> _PhysicalGraspOperation:
        self._ensure_main_thread()
        operation = self._physical_grasp_operation
        if operation is None:
            raise RuntimeError("No physical grasp v2 operation is available to release.")
        phase = operation.fsm.phase
        if phase == GraspPhase.RELEASED:
            operation.release_result = self._physical_grasp_status_payload(operation)
            operation.release_done_event.set()
            return operation
        if phase in {GraspPhase.PRECHECK, GraspPhase.SOFT_CLOSE, GraspPhase.SEARCH}:
            operation.fsm.abort(reason="release_requested_during_close")
        status = operation.fsm.release(now_s=time.monotonic())
        operation.release_done_event.clear()
        self._apply_physical_grasp_command(operation, status)
        return operation

    def _abort_physical_grasp_impl(self, reason: str) -> None:
        operation = self._physical_grasp_operation
        if operation is None or operation.fsm.phase in {
            GraspPhase.IDLE,
            GraspPhase.RELEASED,
            GraspPhase.FAILED,
            GraspPhase.ABORTED,
        }:
            return
        status = operation.fsm.abort(reason=reason)
        self._apply_physical_grasp_command(operation, status)
        payload = self._physical_grasp_status_payload(operation)
        operation.close_result = operation.close_result or payload
        operation.release_result = operation.release_result or payload
        operation.close_done_event.set()
        operation.release_done_event.set()

    def _physical_gripper_snapshot(self, mapping: ParallelJawMapping) -> GripperSnapshot:
        measured_dofs = self._full_pos[self._gripper_joint_indices].copy()
        measured_velocity = self._full_vel[self._gripper_joint_indices].copy()
        measured_effort = self._full_eff[self._gripper_joint_indices].copy()
        command_dofs = (
            measured_dofs
            if self._gripper_command_dofs is None
            else self._gripper_command_dofs.copy()
        )
        width_m = mapping.dofs_to_width(measured_dofs)
        stable = bool(
            measured_velocity.size == 2
            and float(np.max(np.abs(measured_velocity))) <= self._PHYSICAL_GRASP_MOTION_STABLE_VEL_M_S
        )
        return GripperSnapshot(
            width_m=width_m,
            motion_stable=stable,
            fully_closed=(
                width_m <= mapping.closed_width_m + self._PHYSICAL_GRASP_FULLY_CLOSED_TOL_M
            ),
            joint_positions_m=tuple(float(value) for value in measured_dofs),
            joint_velocities_m_s=tuple(float(value) for value in measured_velocity),
            projected_joint_forces_n=(
                tuple(float(value) for value in measured_effort)
                if np.all(np.isfinite(measured_effort))
                else None
            ),
            command_lag_m=(
                tuple(float(value) for value in np.abs(command_dofs - measured_dofs))
                if np.all(np.isfinite(command_dofs))
                else None
            ),
        )

    def _update_physical_resistance_diagnostics(
        self,
        operation: _PhysicalGraspOperation,
    ) -> None:
        gripper = operation.latest_gripper
        if gripper is None or gripper.projected_joint_forces_n is None:
            operation.latest_effort_residual_n = None
            return
        raw = np.asarray(gripper.projected_joint_forces_n, dtype=np.float64)
        contacts = operation.latest_contacts
        support_paths = set(contacts.support_body_paths)
        object_contact_paths = (
            set(contacts.left_body_paths).union(contacts.right_body_paths)
            - support_paths
        )
        if (
            not object_contact_paths
            and operation.fsm.phase
            in {GraspPhase.PRECHECK, GraspPhase.SOFT_CLOSE, GraspPhase.SEARCH}
        ):
            if operation.gripper_effort_baseline_n is None:
                baseline = raw
            else:
                previous = np.asarray(
                    operation.gripper_effort_baseline_n,
                    dtype=np.float64,
                )
                alpha = 1.0 / min(operation.gripper_effort_baseline_samples + 1, 20)
                baseline = previous + alpha * (raw - previous)
            operation.gripper_effort_baseline_n = tuple(
                float(value) for value in baseline
            )
            operation.gripper_effort_baseline_samples += 1
        if operation.gripper_effort_baseline_n is None:
            operation.latest_effort_residual_n = None
            return
        baseline = np.asarray(operation.gripper_effort_baseline_n, dtype=np.float64)
        operation.latest_effort_residual_n = tuple(
            float(value) for value in np.abs(raw - baseline)
        )

    def _physical_arm_is_stable(self) -> bool:
        arm_pos = self._full_pos[self._arm_joint_indices].copy()
        arm_vel = self._full_vel[self._arm_joint_indices].copy()
        with self._command_lock:
            command_pos = self._command.pos.copy()
        lead_velocity = (
            float(np.max(np.abs(arm_vel[:4]))) if arm_vel.size else 0.0
        )
        wrist_velocity = (
            float(np.max(np.abs(arm_vel[4:6]))) if arm_vel.size > 4 else lead_velocity
        )
        max_error = (
            float(np.max(np.abs(arm_pos - command_pos[: arm_pos.size])))
            if arm_pos.size and command_pos.size
            else 0.0
        )
        return bool(
            lead_velocity <= self._GRASP_ATTACH_PRECHECK_MAX_ARM_VEL_RAD_S
            and wrist_velocity <= self._GRASP_ATTACH_PRECHECK_MAX_WRIST_VEL_RAD_S
            and max_error <= self._GRASP_ATTACH_PRECHECK_MAX_ARM_COMMAND_ERR_RAD
        )

    def _physical_contact_snapshot(self, operation: _PhysicalGraspOperation) -> ContactSnapshot:
        stage = omni.usd.get_context().get_stage()
        blocker_seeds = [self._gripper_carrier_body_path]
        support_seeds: list[str] = []
        if stage is not None:
            for path in (
                "/World/GroundPlane",
                "/World/defaultGroundPlane",
                "/World/groundPlane",
                "/World/Table",
                "/World/table",
                "/World/Workbench",
            ):
                if stage.GetPrimAtPath(path).IsValid():
                    support_seeds.append(path)
        support_seeds.extend(
            path.strip()
            for path in os.environ.get(
                "A1Z_PHYSICAL_GRASP_SUPPORT_BODY_PATHS", ""
            ).split(",")
            if path.strip()
        )
        blocker_seeds.extend(
            path.strip()
            for path in os.environ.get(
                "A1Z_PHYSICAL_GRASP_BLOCKING_BODY_PATHS", ""
            ).split(",")
            if path.strip()
        )
        filter_paths = self._build_grasp_attach_contact_filter_paths(
            target_body_path=operation.target_body_path,
            seed_paths=[*blocker_seeds, *support_seeds],
        )
        blocking_paths = []
        for path in blocker_seeds:
            resolved = self._resolve_contact_body_path(path)
            if resolved and resolved not in blocking_paths:
                blocking_paths.append(resolved)
        support_paths = []
        for path in support_seeds:
            resolved = self._resolve_contact_body_path(path)
            if resolved and resolved not in support_paths:
                support_paths.append(resolved)
        records = self._poll_grasp_body_contacts(filter_paths=filter_paths)
        return reduce_contact_impulses(
            left_records=records.get("left", []),
            right_records=records.get("right", []),
            left_finger_body_path=self._left_finger_body_path,
            right_finger_body_path=self._right_finger_body_path,
            target_body_path=operation.target_body_path,
            physics_dt_s=self._physics_dt_s(),
            blocking_body_paths=blocking_paths,
            support_body_paths=support_paths,
        )

    def _apply_physical_grasp_command(
        self,
        operation: _PhysicalGraspOperation,
        status: PhysicalGraspStatus,
    ) -> None:
        command = status.command
        if command is None:
            return
        width = operation.mapping.clamp_width(command.target_width_m)
        target_dofs = np.asarray(
            operation.mapping.width_to_dofs(width),
            dtype=np.float64,
        )
        measured_dofs = (
            None
            if operation.latest_gripper is None
            or operation.latest_gripper.joint_positions_m is None
            else np.asarray(
                operation.latest_gripper.joint_positions_m,
                dtype=np.float64,
            )
        )
        if measured_dofs is not None:
            if command.freeze_contact_finger is not None:
                frozen_index = 0 if command.freeze_contact_finger == "left" else 1
                # Shift the symmetric width target without changing its width,
                # pinning the contacting jaw while the free jaw catches up.
                target_dofs += measured_dofs[frozen_index] - target_dofs[frozen_index]
            else:
                coupling = (
                    operation.controller_profile.get("virtual_coupling", {})
                    if operation.controller_profile is not None
                    else {}
                )
                center_gain = float(coupling.get("center_error_gain", 1.0))
                maximum_center_correction_m = float(
                    coupling.get("maximum_center_correction_m", 0.0015)
                )
                reference_center = float(np.mean(target_dofs))
                measured_center = float(np.mean(measured_dofs))
                center_correction = float(
                    np.clip(
                        -center_gain * (measured_center - reference_center),
                        -maximum_center_correction_m,
                        maximum_center_correction_m,
                    )
                )
                target_dofs += center_correction
        target_dofs = self._clip_gripper_dofs(target_dofs)
        signature = (
            command.drive_profile.value,
            round(float(command.target_width_m), 9),
            command.reason,
            command.freeze_contact_finger,
            round(float(target_dofs[0]), 9),
            round(float(target_dofs[1]), 9),
        )
        if signature == operation.last_applied_command_signature:
            return
        configured_profiles = (
            operation.controller_profile.get("profiles")
            if operation.controller_profile is not None
            else None
        )
        profile_payload = (
            configured_profiles.get(command.drive_profile.value)
            if isinstance(configured_profiles, Mapping)
            else None
        )
        if isinstance(profile_payload, Mapping):
            self._set_gripper_drive_profile(
                profile_name=f"physical_v2_{command.drive_profile.value}",
                kp=np.asarray(profile_payload["stiffness"], dtype=np.float64),
                kd=np.asarray(profile_payload["damping"], dtype=np.float64),
                max_effort=np.asarray(profile_payload["max_effort"], dtype=np.float64),
                drive_type=str(
                    operation.controller_profile.get("drive_type", "acceleration")
                ),
            )
        elif command.drive_profile == DriveProfile.SOFT_CLOSE:
            self._set_gripper_soft_grasp_gains()
        elif command.drive_profile == DriveProfile.SEARCH:
            self._set_gripper_search_gains()
        elif command.drive_profile == DriveProfile.HOLD:
            self._set_gripper_hold_gains()
        else:
            self._set_gripper_default_gains()
        self._set_gripper_dof_target(target_dofs)
        operation.last_applied_command_signature = signature

    def _physical_grasp_status_payload(
        self,
        operation: _PhysicalGraspOperation,
    ) -> Dict[str, Any]:
        status = operation.fsm.status()
        contacts = operation.latest_contacts
        gripper = operation.latest_gripper
        new_constraints = sorted(self._physics_constraint_paths() - operation.initial_constraint_paths)
        command = status.command
        target_path = str(operation.target_body_path or "")
        target_physics_state = (
            self._target_physics_state(target_path) if target_path else {}
        )
        target_world = (
            self._get_rigid_body_world_transform(target_path) if target_path else None
        )
        carrier_path = self._gripper_carrier_body_path
        carrier_world = (
            self._get_rigid_body_world_transform(carrier_path) if carrier_path else None
        )
        target_translation = (
            None
            if target_world is None
            else self._vec3_to_tuple(target_world.ExtractTranslation())
        )
        left_force, right_force = (
            contacts.normal_force_for(target_path)
            if target_path
            else (contacts.left_normal_force_n, contacts.right_normal_force_n)
        )
        carrier_translation = (
            None if carrier_world is None else self._vec3_to_tuple(carrier_world.ExtractTranslation())
        )
        relative_translation = (
            None
            if target_translation is None or carrier_translation is None
            else tuple(
                float(target_translation[index] - carrier_translation[index])
                for index in range(3)
            )
        )
        effort_residual = operation.latest_effort_residual_n
        command_lag = None if gripper is None else gripper.command_lag_m
        joint_load_resistance = bool(
            effort_residual is not None
            and command_lag is not None
            and min(effort_residual) >= operation.minimum_effort_residual_n
            and min(command_lag) >= operation.minimum_position_lag_m
        )
        contact_force_resistance = bool(
            status.bilateral_contact
            and status.filtered_weak_normal_force_n is not None
            and status.filtered_weak_normal_force_n > 0.0
        )
        force_target_reached = bool(
            status.target_normal_force_n is not None
            and status.effective_grip_force_n is not None
            and status.effective_grip_force_n >= status.target_normal_force_n
        )
        return {
            "contract_version": 2,
            "mode": "physical",
            "controller_profile_id": (
                None
                if operation.controller_profile is None
                else operation.controller_profile.get("controller_profile_id")
            ),
            "calibration_status": (
                "runtime_default"
                if operation.controller_profile is None
                else operation.controller_profile.get("calibration_status")
            ),
            "gripper_drive_type": (
                "acceleration"
                if operation.controller_profile is None
                else operation.controller_profile.get("drive_type", "acceleration")
            ),
            "active_gripper_drive_profile": self._active_gripper_drive_profile,
            "success": bool(
                operation.holding_confirmed
                and status.phase in {GraspPhase.HOLDING, GraspPhase.RELEASED}
            ),
            "phase": status.phase.value,
            "target_body_path": status.target_body_path,
            "target_discovery_mode": True,
            "candidate_body_path": status.candidate_body_path,
            "carrier_body_path": carrier_path or None,
            "target_world_translation_m": target_translation,
            "initial_target_world_translation_m": operation.initial_target_world_translation_m,
            "carrier_world_translation_m": carrier_translation,
            "target_to_carrier_translation_m": relative_translation,
            "target_physics_state": target_physics_state,
            "initial_target_physics_state": dict(operation.initial_target_physics_state),
            "target_physics_state_mutated": (
                bool(target_path)
                and target_physics_state != dict(operation.initial_target_physics_state)
            ),
            "bilateral_contact": bool(status.bilateral_contact),
            "stable_contact_frames": int(status.stable_contact_frames),
            "contact_loss_frames": int(status.contact_loss_frames),
            "contact_width_m": status.contact_width_m,
            "hold_width_m": status.hold_width_m,
            "applied_preload_delta_m": (
                None
                if status.contact_width_m is None or status.hold_width_m is None
                else max(0.0, float(status.contact_width_m - status.hold_width_m))
            ),
            "gripper_pad_material": dict(self._gripper_pad_material_status),
            "measured_width_m": None if gripper is None else float(gripper.width_m),
            "measured_jaw_dofs_m": (
                None if gripper is None else gripper.joint_positions_m
            ),
            "left_normal_force_n": left_force,
            "right_normal_force_n": right_force,
            "filtered_left_normal_force_n": status.filtered_left_normal_force_n,
            "filtered_right_normal_force_n": status.filtered_right_normal_force_n,
            "filtered_weak_normal_force_n": status.filtered_weak_normal_force_n,
            "effective_grip_force_n": status.effective_grip_force_n,
            "grip_force_source": status.grip_force_source,
            "target_normal_force_n": status.target_normal_force_n,
            "maximum_normal_force_n": status.maximum_normal_force_n,
            "force_control_active": bool(status.force_control_active),
            "force_target_reached": force_target_reached,
            "force_stable_frames": int(status.force_stable_frames),
            "force_loss_frames": int(status.force_loss_frames),
            "unilateral_recovery_active": bool(status.unilateral_recovery_active),
            "unilateral_contact_side": status.unilateral_contact_side,
            "resistance_confirmed": bool(
                status.bilateral_contact
                and (contact_force_resistance or joint_load_resistance)
            ),
            "resistance_signals": {
                "contact_force_resistance": contact_force_resistance,
                "joint_load_resistance": joint_load_resistance,
                "projected_joint_force_n": (
                    None
                    if gripper is None
                    else gripper.projected_joint_forces_n
                ),
                "free_motion_baseline_n": operation.gripper_effort_baseline_n,
                "effort_residual_n": effort_residual,
                "command_lag_m": command_lag,
                "minimum_effort_residual_n": operation.minimum_effort_residual_n,
                "minimum_position_lag_m": operation.minimum_position_lag_m,
                "semantics": (
                    "bilateral filtered contact force is primary; bilateral "
                    "baseline-subtracted joint resistance is a guarded fallback"
                ),
            },
            "left_body_paths": list(contacts.left_body_paths),
            "right_body_paths": list(contacts.right_body_paths),
            "support_body_paths": list(contacts.support_body_paths),
            "left_support_body_paths": list(contacts.left_support_body_paths),
            "right_support_body_paths": list(contacts.right_support_body_paths),
            "support_contact_present": bool(
                contacts.left_support_body_paths or contacts.right_support_body_paths
            ),
            "constraint_count_delta": len(new_constraints),
            "new_constraint_paths": new_constraints,
            "attachment_joint_path": None,
            "attached_object_path": None,
            "failure_reason": status.failure_reason,
            "command": None
            if command is None
            else {
                "drive_profile": command.drive_profile.value,
                "target_width_m": float(command.target_width_m),
                "target_dofs_m": (
                    None
                    if self._gripper_target_dofs_override is None
                    else self._gripper_target_dofs_override.tolist()
                ),
                "freeze_contact_finger": command.freeze_contact_finger,
                "reason": command.reason,
            },
            "elapsed_s": max(0.0, time.monotonic() - operation.started_at_s),
        }

    def _advance_physical_grasp(self) -> None:
        operation = self._physical_grasp_operation
        if operation is None or operation.fsm.phase in {
            GraspPhase.IDLE,
            GraspPhase.RELEASED,
            GraspPhase.FAILED,
            GraspPhase.ABORTED,
        }:
            return
        try:
            new_constraints = self._physics_constraint_paths() - operation.initial_constraint_paths
            target_physics_mutated = (
                bool(operation.target_body_path)
                and self._target_physics_state(operation.target_body_path)
                != dict(operation.initial_target_physics_state)
            )
            if new_constraints:
                status = operation.fsm.abort(reason="constraint_created_during_physical_grasp")
            elif target_physics_mutated:
                status = operation.fsm.abort(reason="target_physics_state_mutated")
            else:
                operation.latest_gripper = self._physical_gripper_snapshot(operation.mapping)
                operation.latest_contacts = self._physical_contact_snapshot(operation)
                self._update_physical_resistance_diagnostics(operation)
                operation.latest_gripper = replace(
                    operation.latest_gripper,
                    residual_joint_forces_n=operation.latest_effort_residual_n,
                )
                status = operation.fsm.step(
                    now_s=time.monotonic(),
                    arm_stable=self._physical_arm_is_stable(),
                    gripper=operation.latest_gripper,
                    contacts=operation.latest_contacts,
                )
                discovered_path = str(status.target_body_path or "")
                if discovered_path and not operation.target_body_path:
                    (
                        resolved_path,
                        initial_state,
                        initial_translation,
                    ) = self._validate_physical_grasp_target(discovered_path)
                    if resolved_path != discovered_path:
                        raise RuntimeError(
                            "physical grasp contact path was not a canonical rigid body: "
                            f"{discovered_path} -> {resolved_path}"
                        )
                    operation.target_body_path = resolved_path
                    operation.initial_target_physics_state = initial_state
                    operation.initial_target_world_translation_m = initial_translation
            self._apply_physical_grasp_command(operation, status)
            if status.phase == GraspPhase.HOLDING:
                operation.holding_confirmed = True
            payload = self._physical_grasp_status_payload(operation)
            if status.phase == GraspPhase.HOLDING and not operation.close_done_event.is_set():
                operation.close_result = payload
                operation.close_done_event.set()
            elif status.phase in {GraspPhase.FAILED, GraspPhase.ABORTED}:
                operation.close_result = operation.close_result or payload
                operation.release_result = operation.release_result or payload
                operation.close_done_event.set()
                operation.release_done_event.set()
            elif status.phase == GraspPhase.RELEASED:
                operation.close_result = operation.close_result or payload
                operation.release_result = payload
                operation.close_done_event.set()
                operation.release_done_event.set()
        except BaseException as exc:
            operation.error = exc
            operation.fsm.abort(reason=f"runtime_error:{type(exc).__name__}")
            operation.close_done_event.set()
            operation.release_done_event.set()

    def _start_grasp_close_and_attach_impl(
        self,
        *,
        target_prim_path: str,
        timeout_s: float,
        contact_window_s: float,
        require_bilateral_contact: bool,
    ) -> _PendingGraspAttach:
        del require_bilateral_contact
        if self._pending_grasp_attach is not None:
            raise RuntimeError("A grasp_attach operation is already running.")
        self._ensure_gripper_structure_paths()
        self._cleanup_active_attachment_state()
        self._cleanup_stale_attachment_joints()
        resolved_target_body_path = self._resolve_target_rigid_body_path(target_prim_path) or None
        self._sim_grasp_state = _SimGraspState(
            grasp_state="closing_for_grasp",
            target_prim_path=target_prim_path or None,
            target_body_path=resolved_target_body_path,
        )
        soft_close_timeout_s = max(0.1, float(timeout_s))
        start_time = time.monotonic()
        full_close_timeout_s = max(
            soft_close_timeout_s + self._GRASP_ATTACH_FULL_CLOSE_EXTRA_TIMEOUT_S,
            self._GRASP_ATTACH_FULL_CLOSE_MIN_TIMEOUT_S,
        )
        initial_open_value = float(self._gripper_open_value)
        operation = _PendingGraspAttach(
            target_prim_path=target_prim_path or "",
            timeout_s=float(timeout_s),
            contact_window_s=float(contact_window_s),
            require_bilateral_contact=False,
            soft_close_timeout_s=soft_close_timeout_s,
            full_close_timeout_s=full_close_timeout_s,
            start_time=start_time,
            soft_close_deadline=start_time + soft_close_timeout_s,
            full_close_deadline=start_time + full_close_timeout_s,
            required_count=self._GRASP_ATTACH_REQUIRED_CONTACT_COUNT,
            initial_open_value=initial_open_value,
            stage="precheck",
            contact_filter_paths=self._build_grasp_attach_contact_filter_paths(
                target_body_path=str(resolved_target_body_path or ""),
                seed_paths=[resolved_target_body_path] if resolved_target_body_path else [],
            ),
        )
        self._set_gripper_target(initial_open_value)
        self._set_gripper_hold_gains()
        self._pending_grasp_attach = operation
        return operation

    def _finish_pending_grasp_attach(self, operation: _PendingGraspAttach, result: Dict[str, Any]) -> None:
        contact_summary = result.get("contact_summary")
        if isinstance(contact_summary, dict) and "control_progress" not in contact_summary:
            contact_summary["control_progress"] = self._summarize_pending_grasp_attach_progress(operation)
        operation.result = dict(result)
        operation.done_event.set()
        if self._pending_grasp_attach is operation:
            self._pending_grasp_attach = None

    def _record_pending_grasp_attach_progress(self, operation: _PendingGraspAttach) -> None:
        now = time.monotonic()
        current_open_value = float(self._gripper_open_value)
        operation.sample_count += 1
        operation.stage_counts[operation.stage] = int(operation.stage_counts.get(operation.stage, 0)) + 1
        if operation.last_progress_time > 0.0:
            frame_dt_s = max(0.0, now - operation.last_progress_time)
            operation.max_frame_dt_s = max(operation.max_frame_dt_s, frame_dt_s)
        else:
            frame_dt_s = 0.0
        if operation.last_progress_open_value is not None:
            frame_open_delta = abs(current_open_value - operation.last_progress_open_value)
            operation.max_frame_open_delta = max(operation.max_frame_open_delta, frame_open_delta)
        else:
            frame_open_delta = 0.0
        operation.last_progress_time = now
        operation.last_progress_open_value = current_open_value
        if len(operation.progress_samples) < self._GRASP_ATTACH_PROGRESS_SAMPLE_LIMIT:
            operation.progress_samples.append(
                {
                    "t_s": round(max(0.0, now - operation.start_time), 4),
                    "stage": operation.stage,
                    "gripper_open_value": round(current_open_value, 6),
                    "frame_dt_s": round(frame_dt_s, 4),
                    "frame_open_delta": round(frame_open_delta, 6),
                }
            )

    def _summarize_pending_grasp_attach_progress(self, operation: _PendingGraspAttach) -> dict[str, object]:
        return {
            "sample_count": int(operation.sample_count),
            "max_frame_open_delta": float(operation.max_frame_open_delta),
            "max_frame_dt_s": float(operation.max_frame_dt_s),
            "dt_cap_s": float(self._GRASP_ATTACH_RATE_LIMIT_DT_CAP_S),
            "stage_counts": {str(key): int(value) for key, value in operation.stage_counts.items()},
            "samples": list(operation.progress_samples),
        }

    def _fail_pending_grasp_attach(self, operation: _PendingGraspAttach, failure_reason: str) -> None:
        current_open_value = float(self._gripper_open_value)
        if failure_reason == "grasp_contact_not_found":
            if self._is_gripper_near_closed(current_open_value):
                failure_reason = "fully_closed_without_contact"
            elif operation.close_phase == "default_close":
                failure_reason = "grasp_close_timeout_before_full_close"
        self._sim_grasp_state.grasp_state = "failed"
        self._sim_grasp_state.last_failure_reason = failure_reason
        self._set_gripper_default_gains()
        self._finish_pending_grasp_attach(
            operation,
            {
                "success": False,
                "target_prim_path": operation.target_prim_path or "",
                "target_body_path": str(self._sim_grasp_state.target_body_path or "") or None,
                "attached_object_path": None,
                "attachment_joint_path": None,
                "contact_summary": dict(operation.attach_summary),
                "failure_reason": failure_reason,
                "timing": {
                    "soft_close_timeout_s": operation.soft_close_timeout_s,
                    "full_close_timeout_s": operation.full_close_timeout_s,
                },
            },
        )

    def _grasp_link_current_contact_impl(
        self,
        *,
        target_prim_path: str,
        require_bilateral_contact: bool,
    ) -> Dict[str, Any]:
        del require_bilateral_contact
        self._ensure_gripper_structure_paths()
        self._cleanup_active_attachment_state()
        self._cleanup_stale_attachment_joints()
        resolved_target_body_path = self._resolve_target_rigid_body_path(target_prim_path) or ""
        contact_filter_paths = self._build_grasp_attach_contact_filter_paths(
            target_body_path=resolved_target_body_path,
            seed_paths=[resolved_target_body_path] if resolved_target_body_path else [],
        )
        body_contacts = self._poll_grasp_body_contacts(filter_paths=contact_filter_paths)
        ok, body_path, summary = self._contact_satisfies_attach(
            body_contacts,
            target_body_path=resolved_target_body_path,
            require_bilateral_contact=False,
        )
        current_open_value = float(self._gripper_open_value)
        summary = dict(summary)
        summary["gripper_open_value"] = current_open_value
        summary["target_prim_path"] = target_prim_path or None
        if not ok or not body_path:
            self._sim_grasp_state.grasp_state = "failed"
            self._sim_grasp_state.last_failure_reason = "grasp_contact_not_found"
            return {
                "success": False,
                "target_prim_path": target_prim_path or "",
                "target_body_path": resolved_target_body_path or None,
                "attached_object_path": None,
                "attachment_joint_path": None,
                "contact_summary": summary,
                "failure_reason": "grasp_contact_not_found",
                "timing": {},
            }
        return self._create_link6_relative_attachment(
            body_path=body_path,
            summary=summary,
            target_prim_path=target_prim_path,
        )

    def _advance_pending_grasp_attach(self) -> None:
        operation = self._pending_grasp_attach
        if operation is None or operation.done_event.is_set():
            return
        try:
            self._record_pending_grasp_attach_progress(operation)
            if time.monotonic() >= operation.full_close_deadline:
                self._fail_pending_grasp_attach(operation, operation.failure_reason)
                return
            if operation.stage == "precheck":
                current_open_value = float(self._gripper_open_value)
                current_arm = self._full_pos[self._arm_joint_indices].copy()
                arm_vel = self._full_vel[self._arm_joint_indices].copy()
                arm_speed_max = float(np.max(np.abs(arm_vel))) if arm_vel.size else 0.0
                with self._command_lock:
                    command_arm = self._command.pos.copy()
                arm_command_error_max = (
                    float(np.max(np.abs(current_arm - command_arm[: current_arm.shape[0]])))
                    if current_arm.size and command_arm.size
                    else 0.0
                )
                if operation.precheck_last_arm_pos is None or operation.precheck_last_arm_pos.shape != current_arm.shape:
                    arm_frame_delta_max = float("inf")
                    pose_stable_enough = False
                else:
                    arm_frame_delta_max = float(
                        np.max(np.abs(current_arm - operation.precheck_last_arm_pos))
                    )
                    pose_stable_enough = (
                        arm_command_error_max <= self._GRASP_ATTACH_PRECHECK_MAX_ARM_COMMAND_ERR_RAD
                        and arm_frame_delta_max <= self._GRASP_ATTACH_PRECHECK_MAX_ARM_FRAME_DELTA_RAD
                    )
                operation.precheck_last_arm_pos = current_arm.copy()
                body_contacts = self._poll_grasp_body_contacts(filter_paths=operation.contact_filter_paths)
                _, body_path, summary = self._contact_satisfies_attach(
                    body_contacts,
                    target_body_path=str(self._sim_grasp_state.target_body_path or ""),
                    require_bilateral_contact=operation.require_bilateral_contact,
                )
                operation.attach_summary = dict(summary)
                operation.attach_summary["gripper_open_value"] = current_open_value
                operation.attach_summary["close_phase"] = operation.close_phase
                operation.attach_summary["initial_gripper_open_value"] = operation.initial_open_value
                operation.attach_summary["gripper_closure_delta"] = 0.0
                operation.attach_summary["arm_speed_max_rad_s"] = arm_speed_max
                operation.attach_summary["arm_command_error_max_rad"] = arm_command_error_max
                operation.attach_summary["arm_frame_delta_max_rad"] = (
                    arm_frame_delta_max if np.isfinite(arm_frame_delta_max) else None
                )
                operation.attach_summary["precheck_pose_stable_enough"] = pose_stable_enough
                operation.attach_summary["contact_filter_count"] = len(operation.contact_filter_paths)
                operation.attach_summary["gripper_drive_profile"] = self._active_gripper_drive_profile or None
                ground_contact_present = bool(summary.get("left_has_ground_contact")) or bool(
                    summary.get("right_has_ground_contact")
                )
                operation.attach_summary["ground_contact_present"] = ground_contact_present
                candidate_body_path = body_path or self._preferred_unilateral_contact_candidate(summary)
                operation.attach_summary["candidate_body_path"] = candidate_body_path or None
                operation.attach_summary["candidate_contact_ready"] = bool(candidate_body_path) and not ground_contact_present
                if ground_contact_present:
                    operation.attach_summary["preclose_ground_blocked"] = True
                    self._sim_grasp_state.grasp_state = "failed"
                    self._sim_grasp_state.last_failure_reason = "ground_contact_blocking_grasp"
                    self._finish_pending_grasp_attach(
                        operation,
                        {
                            "success": False,
                            "target_prim_path": operation.target_prim_path or "",
                            "target_body_path": str(self._sim_grasp_state.target_body_path or "") or None,
                            "attached_object_path": None,
                            "attachment_joint_path": None,
                            "contact_summary": dict(operation.attach_summary),
                            "failure_reason": "ground_contact_blocking_grasp",
                            "timing": {
                                "soft_close_timeout_s": operation.soft_close_timeout_s,
                                "full_close_timeout_s": operation.full_close_timeout_s,
                            },
                        },
                    )
                    return
                if (
                    arm_speed_max > self._GRASP_ATTACH_PRECHECK_MAX_ARM_VEL_RAD_S
                    and not pose_stable_enough
                ):
                    operation.precheck_clear_count = 0
                    return
                operation.precheck_clear_count += 1
                operation.attach_summary["precheck_clear_count"] = operation.precheck_clear_count
                if operation.precheck_clear_count < self._GRASP_ATTACH_PRECHECK_CLEAR_STEPS:
                    return
                self._set_gripper_soft_grasp_gains()
                self._set_gripper_target(0.0)
                operation.stage = "closing"
                self._sim_grasp_state.grasp_state = "closing_for_grasp"
                return
            if operation.stage != "closing":
                return

            current_open_value = float(self._gripper_open_value)
            body_contacts = self._poll_grasp_body_contacts(filter_paths=operation.contact_filter_paths)
            _, body_path, summary = self._contact_satisfies_attach(
                body_contacts,
                target_body_path=str(self._sim_grasp_state.target_body_path or ""),
                require_bilateral_contact=False,
            )
            operation.attach_summary = dict(summary)
            operation.attach_summary["gripper_open_value"] = current_open_value
            operation.attach_summary["close_phase"] = operation.close_phase
            operation.attach_summary["initial_gripper_open_value"] = operation.initial_open_value
            operation.attach_summary["gripper_closure_delta"] = max(
                0.0, operation.initial_open_value - current_open_value
            )
            operation.attach_summary["contact_filter_count"] = len(operation.contact_filter_paths)
            operation.attach_summary["gripper_drive_profile"] = self._active_gripper_drive_profile or None

            ground_contact_present = bool(summary.get("left_has_ground_contact")) or bool(
                summary.get("right_has_ground_contact")
            )
            operation.attach_summary["ground_contact_present"] = ground_contact_present
            candidate_body_path = body_path or self._preferred_unilateral_contact_candidate(summary)
            candidate_contact_ready = bool(candidate_body_path) and not ground_contact_present
            operation.attach_summary["candidate_body_path"] = candidate_body_path or None
            operation.attach_summary["candidate_contact_ready"] = candidate_contact_ready
            if candidate_body_path and candidate_body_path not in operation.contact_filter_paths:
                operation.contact_filter_paths = self._build_grasp_attach_contact_filter_paths(
                    target_body_path=str(self._sim_grasp_state.target_body_path or ""),
                    seed_paths=[candidate_body_path],
                )

            if ground_contact_present:
                self._sim_grasp_state.grasp_state = "ground_contact_blocked"
                if not operation.ground_block_hold_active:
                    held_open_value = current_open_value
                    self._set_gripper_target(held_open_value)
                    self._set_gripper_hold_gains()
                    operation.ground_block_hold_active = True
                    operation.ground_block_hold_started_at = time.monotonic()
                    operation.ground_block_hold_open_value = held_open_value
                    operation.attach_summary["ground_block_hold_triggered"] = True
                    operation.attach_summary["ground_block_hold_open_value"] = held_open_value
                elif (
                    operation.ground_block_hold_started_at is not None
                    and time.monotonic() - operation.ground_block_hold_started_at
                    >= self._GRASP_ATTACH_GROUND_BLOCK_TIMEOUT_S
                ):
                    operation.attach_summary["ground_block_timeout_s"] = float(
                        time.monotonic() - operation.ground_block_hold_started_at
                    )
                    self._fail_pending_grasp_attach(operation, "ground_contact_blocking_grasp")
                    return
                return

            if operation.ground_block_hold_active:
                operation.ground_block_hold_active = False
                operation.ground_block_hold_started_at = None
                operation.ground_block_hold_open_value = 0.0
                self._restore_grasp_phase_gains(operation.close_phase)

            if candidate_contact_ready:
                if candidate_body_path == operation.last_body:
                    operation.stable_count += 1
                else:
                    operation.stable_count = 1
                    operation.last_body = candidate_body_path
                self._sim_grasp_state.grasp_state = "contact_candidate"
                self._sim_grasp_state.last_contact_time = time.time()
                if operation.stable_count >= operation.required_count:
                    result = self._create_link6_relative_attachment(
                        body_path=candidate_body_path,
                        summary=operation.attach_summary,
                        target_prim_path=operation.target_prim_path,
                    )
                    self._finish_pending_grasp_attach(operation, result)
                    return
            else:
                operation.stable_count = 0
                operation.last_body = ""

            if self._is_gripper_near_closed(current_open_value):
                self._fail_pending_grasp_attach(operation, "fully_closed_without_contact")
                return
            if (
                operation.close_phase == "soft_close"
                and time.monotonic() >= operation.soft_close_deadline
            ):
                self._set_gripper_search_gains()
                operation.close_phase = "search_close"
                self._sim_grasp_state.grasp_state = "closing_for_grasp_search"
                operation.failure_reason = "grasp_close_timeout_before_full_close"
        except BaseException as exc:
            operation.error = exc
            operation.done_event.set()
            if self._pending_grasp_attach is operation:
                self._pending_grasp_attach = None

    def _release_attached_object_impl(
        self,
        *,
        open_gripper: bool,
        timeout_s: float,
    ) -> Dict[str, Any]:
        del timeout_s
        joint_path = str(self._sim_grasp_state.attachment_joint_path or "")
        attached_object_path = self._sim_grasp_state.attached_object_path
        self._cleanup_active_attachment_state()
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
        physical = self._physical_grasp_operation
        if physical is not None and physical.fsm.phase in {GraspPhase.PRELOAD, GraspPhase.HOLDING}:
            limits[:] = np.minimum(
                limits,
                min(physical.max_close_velocity_m_s, self._GRASP_CONTACT_HOLD_MAX_VELOCITY_M_S),
            )
        elif physical is not None and physical.fsm.phase in {
            GraspPhase.PRECHECK,
            GraspPhase.SOFT_CLOSE,
            GraspPhase.SEARCH,
            GraspPhase.RELEASING,
            GraspPhase.FAILED,
            GraspPhase.ABORTED,
        }:
            limits[:] = np.minimum(limits, physical.max_close_velocity_m_s)
        elif self._sim_grasp_state.grasp_state == "contact_candidate":
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

            # Isaac's controller API expresses angular drive gains per radian,
            # while the USD angular DriveAPI attributes are per degree. Writing
            # controller gains directly to USD multiplies the live PhysX gain by
            # 180/pi when the stage change is consumed.
            usd_stiffness = float(np.deg2rad(arm_kp[local_idx]))
            usd_damping = float(np.deg2rad(arm_kd[local_idx]))

            if prim.HasAttribute("drive:angular:physics:type"):
                drive.GetTypeAttr().Set(self._arm_drive_type)
            else:
                drive.CreateTypeAttr().Set(self._arm_drive_type)
            if prim.HasAttribute("drive:angular:physics:stiffness"):
                drive.GetStiffnessAttr().Set(usd_stiffness)
            else:
                drive.CreateStiffnessAttr().Set(usd_stiffness)
            if prim.HasAttribute("drive:angular:physics:damping"):
                drive.GetDampingAttr().Set(usd_damping)
            else:
                drive.CreateDampingAttr().Set(usd_damping)
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
        self._gripper_command_dofs = target_dofs.copy()
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
            preserve_authored_gains = os.environ.get(
                "A1Z_ISAAC_PRESERVE_AUTHORED_DRIVE_GAINS", "0"
            ).strip().lower() in {"1", "true", "yes", "on"}
            if preserve_authored_gains:
                dof_props = self._articulation.dof_properties
                authored_kp = np.asarray(dof_props["stiffness"], dtype=np.float64).reshape(-1)[
                    self._arm_joint_indices
                ]
                authored_kd = np.asarray(dof_props["damping"], dtype=np.float64).reshape(-1)[
                    self._arm_joint_indices
                ]
                if (
                    authored_kp.size != self._num_joints
                    or authored_kd.size != self._num_joints
                    or not np.all(np.isfinite(authored_kp))
                    or not np.all(np.isfinite(authored_kd))
                    or np.any(authored_kp <= 0.0)
                    or np.any(authored_kd < 0.0)
                ):
                    raise RuntimeError(
                        "A1Z authored drive gains are invalid for mounted Isaac operation: "
                        f"kp={authored_kp.tolist()} kd={authored_kd.tolist()}"
                    )
                arm_kp = authored_kp.copy()
                arm_kd = authored_kd.copy()
                carb.log_info(
                    "A1Z Isaac preserving authored mounted-arm drive gains: "
                    f"kp={np.round(arm_kp, 2).tolist()} kd={np.round(arm_kd, 2).tolist()}"
                )

        # The compatibility facade exposes the articulation controller for drive
        # configuration. It accepts full gain arrays, while control
        # mode and effort mode can still be set per DOF.
        self._set_subset_effort_mode(
            "force" if self.zero_gravity_mode else self._arm_drive_type,
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
            if self._gripper_free_drive:
                zeros = np.zeros(2, dtype=np.float64)
                self._set_gripper_drive_profile(
                    profile_name="free_drive",
                    kp=zeros,
                    kd=zeros,
                    max_effort=zeros,
                    drive_type="force",
                )
                for dof_index in self._gripper_joint_indices.tolist():
                    self._switch_dof_control_mode("effort", int(dof_index))
            else:
                self._set_subset_gains(self._gripper_joint_indices, self._gripper_kp, self._gripper_kd)
                self._set_subset_max_efforts(self._gripper_joint_indices, self._gripper_max_effort)
                for dof_index in self._gripper_joint_indices.tolist():
                    self._switch_dof_control_mode("position", int(dof_index))
                self._configure_gripper_drive_targets()

        position_hold_gravity_ff_active = bool(
            not self.zero_gravity_mode
            and self._position_hold_gravity_compensation
            and self._gravity_model is not None
        )
        try:
            dof_props = self._articulation.dof_properties
            actual_kp = np.asarray(dof_props["stiffness"], dtype=np.float64).reshape(-1)
            actual_kd = np.asarray(dof_props["damping"], dtype=np.float64).reshape(-1)
            carb.log_info(
                "A1Z Isaac actuator config: "
                f"mode={'gravity_comp_effort' if self.zero_gravity_mode else 'position_hold'} "
                f"position_hold_gravity_ff={position_hold_gravity_ff_active} "
                f"arm_idx={self._arm_joint_indices.tolist()} "
                f"gripper_idx={self._gripper_joint_indices.tolist()} "
                f"actual_arm_kp={np.round(actual_kp[self._arm_joint_indices], 2).tolist()} "
                f"actual_arm_kd={np.round(actual_kd[self._arm_joint_indices], 2).tolist()} "
                f"drive_type={'force' if self.zero_gravity_mode else self._arm_drive_type}"
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
                ArticulationCommand(
                    joint_efforts=arm_effort.astype(np.float32),
                    joint_indices=self._arm_joint_indices.astype(np.int64),
                )
            )
        else:
            q = self._full_pos[self._arm_joint_indices].copy()
            qd = self._full_vel[self._arm_joint_indices].copy()
            pos_err = pos_target - q
            vel_err = vel_target - qd
            gravity_tau = np.zeros(self._num_joints, dtype=np.float64)
            if self._position_hold_gravity_compensation:
                zeros = np.zeros(self._num_joints, dtype=np.float64)
                gravity_tau = self._compute_gravity_feedforward(q, zeros, zeros)
            arm_feedforward = bounded_position_hold_feedforward(
                gravity_tau,
                torque_ff,
                self._position_hold_feedforward_limit,
            )
            self._last_gravity_q = q.copy()
            self._last_gravity_qd = qd.copy()
            self._last_gravity_pos_err = pos_err.copy()
            self._last_gravity_vel_err = vel_err.copy()
            self._last_gravity_tau_id = gravity_tau.copy()
            self._last_gravity_effort = arm_feedforward.copy()
            now = time.monotonic()
            if (
                np.max(np.abs(pos_err)) > self._ARM_SETTLE_TOL_RAD
                and now - self._debug_last_gravity_log >= 1.0
            ):
                carb.log_info(
                    "A1Z position hold gravity feedforward: "
                    f"pos_err_deg={np.round(np.rad2deg(pos_err), 3).tolist()} "
                    f"tau_g={np.round(gravity_tau, 3).tolist()} "
                    f"ff={np.round(arm_feedforward, 3).tolist()}"
                )
                self._debug_last_gravity_log = now
            if self._mirror_drive_targets_to_usd:
                self._set_arm_drive_targets(pos_target)
            self._controller().apply_action(
                ArticulationCommand(
                    joint_positions=pos_target.astype(np.float32),
                    joint_efforts=arm_feedforward.astype(np.float32),
                    joint_indices=self._arm_joint_indices.astype(np.int64),
                )
            )

        if self._with_gripper and self._gripper_joint_indices.size == 2:
            raw_grip_target = (
                self._normalized_to_gripper_dofs(self._gripper_target_value)
                if self._gripper_target_dofs_override is None
                else self._gripper_target_dofs_override.copy()
            )
            grip = self._rate_limit_gripper_dofs(raw_grip_target)
            if self._mirror_drive_targets_to_usd:
                self._set_gripper_drive_targets(grip)
            self._controller().apply_action(
                ArticulationCommand(
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
        pending_grasp_attach = self._pending_grasp_attach
        if pending_grasp_attach is not None and not pending_grasp_attach.done_event.is_set():
            dt = min(dt, self._GRASP_ATTACH_RATE_LIMIT_DT_CAP_S)
        physical_grasp = self._physical_grasp_operation
        if physical_grasp is not None and physical_grasp.fsm.phase not in {
            GraspPhase.IDLE,
            GraspPhase.RELEASED,
            GraspPhase.FAILED,
            GraspPhase.ABORTED,
        }:
            dt = min(dt, self._GRASP_ATTACH_RATE_LIMIT_DT_CAP_S)
        current_pos = self._full_pos[self._gripper_joint_indices].copy()
        max_step = self._active_gripper_velocity_limits() * dt
        previous_pos = (
            current_pos.copy()
            if self._gripper_command_dofs is None
            else self._gripper_command_dofs.copy()
        )
        physical = self._physical_grasp_operation
        max_lead_m = (
            physical.max_command_lead_m
            if physical is not None
            and physical.fsm.phase
            not in {GraspPhase.IDLE, GraspPhase.RELEASED}
            else self._PHYSICAL_GRASP_MAX_COMMAND_LEAD_M
        )
        limited = np.asarray(
            rate_limit_parallel_jaw_setpoint(
                previous_dofs_m=previous_pos,
                measured_dofs_m=current_pos,
                target_dofs_m=target_pos,
                max_velocity_m_s=max_step / dt,
                dt_s=dt,
                max_lead_m=max_lead_m,
            ),
            dtype=np.float64,
        )
        self._gripper_command_dofs = self._clip_gripper_dofs(limited)
        return self._gripper_command_dofs.copy()

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
        stable_samples = 0
        while time.monotonic() < deadline:
            current_arm = self.get_joint_state()["pos"]
            if np.max(np.abs(current_arm - target_arm)) <= self._ARM_SETTLE_TOL_RAD:
                stable_samples += 1
                if stable_samples >= self._ARM_SETTLE_REQUIRED_SAMPLES:
                    return
            else:
                stable_samples = 0
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
