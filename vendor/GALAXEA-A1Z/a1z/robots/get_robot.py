"""Factory functions for creating A1Z robot backends."""

from __future__ import annotations

from typing import Optional

import numpy as np

from a1z.config import get_control_defaults, get_default_backend, get_default_can_channel
from a1z.robots.mock_robot import MockArmRobot
from a1z.robots.robot import Robot

_CONTROL_DEFAULTS = get_control_defaults()
_DEFAULT_URDF_PATH = _CONTROL_DEFAULTS["default_control_urdf_path"]
_NUM_JOINTS = int(_CONTROL_DEFAULTS["num_joints"])
_MOTOR_A_JOINT_INDICES = _CONTROL_DEFAULTS["motor_a_joint_indices"]
_MOTOR_B_JOINT_INDICES = _CONTROL_DEFAULTS["motor_b_joint_indices"]
_MOTOR_A_IDS = _CONTROL_DEFAULTS["motor_a_ids"]
_MOTOR_B_IDS = _CONTROL_DEFAULTS["motor_b_ids"]

_DEFAULT_KP = np.array(_CONTROL_DEFAULTS["default_kp"], dtype=np.float64)
_DEFAULT_KD = np.array(_CONTROL_DEFAULTS["default_kd"], dtype=np.float64)
_JOINT_SIGN = np.array(_CONTROL_DEFAULTS["joint_sign"], dtype=np.float64)
_GRAVITY_TORQUE_SCALE = np.array(_CONTROL_DEFAULTS["gravity_torque_scale"], dtype=np.float64)
_MAX_GRAVITY_TORQUE = np.array(_CONTROL_DEFAULTS["max_gravity_torque"], dtype=np.float64)
_TORQUE_CLIP = np.array(_CONTROL_DEFAULTS["torque_clip"], dtype=np.float64)
_MOTOR_A_KT = float(_CONTROL_DEFAULTS["motor_a_kt"])


def _load_control_model(urdf: str):
    from a1z.dynamics.gravity_model import GravityModel

    gravity_model = GravityModel(urdf)
    if gravity_model.nq != _NUM_JOINTS or gravity_model.nv != _NUM_JOINTS:
        raise ValueError(
            f"Control URDF must expose exactly {_NUM_JOINTS} movable arm joints; "
            f"got nq={gravity_model.nq}, nv={gravity_model.nv} from {urdf}. "
            "Use the control model with fixed gripper joints, such as A1Z_G1Z_control.urdf."
        )
    return gravity_model, gravity_model.get_joint_limits()


def get_a1z_robot(
    can_channel: str = get_default_can_channel(),
    gravity_comp_factor: float = 1.0,
    zero_gravity_mode: bool = True,
    control_freq_hz: int = 250,
    min_freq_hz: float = 80.0,
    urdf_path: Optional[str] = None,
    default_kp: Optional[np.ndarray] = None,
    default_kd: Optional[np.ndarray] = None,
    with_gripper: bool = False,
    gripper_max_torque: float = 2.0,
):
    """Create and return a configured SocketCAN-backed A1Z ArmRobot."""
    import can

    from a1z.motor_drivers.motor_a_driver import MotorA, MotorARanges
    from a1z.motor_drivers.motor_b_driver import MotorB, MotorBRanges, MixedMotorChain
    from a1z.robots.arm_robot import ArmRobot
    from a1z.robots.gripper import GRIPPER_CAN_ID, GRIPPER_MOTOR_RANGES, Gripper

    urdf = urdf_path or _DEFAULT_URDF_PATH
    motor_a_ranges = MotorARanges(**_CONTROL_DEFAULTS["motor_a_ranges"])
    motor_b_ranges_default = MotorBRanges(**_CONTROL_DEFAULTS["motor_b_default_ranges"])
    motor_b_ranges_overrides = {
        int(joint_idx): MotorBRanges(**ranges)
        for joint_idx, ranges in _CONTROL_DEFAULTS["motor_b_joint_overrides"].items()
    }

    bus = can.interface.Bus(
        channel=can_channel,
        bustype="socketcan",
        bitrate=1_000_000,
    )

    motor_a_list = [
        MotorA(motor_id=mid, bus=bus, ranges=motor_a_ranges)
        for mid in _MOTOR_A_IDS
    ]

    motor_b_list = []
    for i, mid in enumerate(_MOTOR_B_IDS):
        joint_idx = _MOTOR_B_JOINT_INDICES[i]
        ranges = motor_b_ranges_overrides.get(joint_idx, motor_b_ranges_default)
        motor_b_list.append(MotorB(motor_id=mid, bus=bus, ranges=ranges))

    motor_chain = MixedMotorChain(
        motor_a_list=motor_a_list,
        motor_b_list=motor_b_list,
        motor_a_joint_indices=_MOTOR_A_JOINT_INDICES,
        motor_b_joint_indices=_MOTOR_B_JOINT_INDICES,
        motor_a_kt=_MOTOR_A_KT,
    )

    gravity_model, joint_limits = _load_control_model(urdf)

    gripper = None
    if with_gripper:
        gripper_motor = MotorB(motor_id=GRIPPER_CAN_ID, bus=bus, ranges=GRIPPER_MOTOR_RANGES)
        gripper = Gripper(gripper_motor, max_torque=gripper_max_torque)

    return ArmRobot(
        motor_chain=motor_chain,
        bus=bus,
        gravity_model=gravity_model,
        num_joints=_NUM_JOINTS,
        gravity_comp_factor=gravity_comp_factor,
        zero_gravity_mode=zero_gravity_mode,
        joint_sign=_JOINT_SIGN,
        gravity_torque_scale=_GRAVITY_TORQUE_SCALE,
        max_gravity_torque=_MAX_GRAVITY_TORQUE,
        torque_clip=_TORQUE_CLIP,
        default_kp=default_kp if default_kp is not None else _DEFAULT_KP,
        default_kd=default_kd if default_kd is not None else _DEFAULT_KD,
        joint_limits=joint_limits,
        gripper=gripper,
        control_freq_hz=control_freq_hz,
        min_freq_hz=min_freq_hz,
        motor_a_kt=_MOTOR_A_KT,
    )


def get_a1z_mock_robot(
    gravity_comp_factor: float = 1.0,
    zero_gravity_mode: bool = True,
    control_freq_hz: int = 250,
    urdf_path: Optional[str] = None,
    default_kp: Optional[np.ndarray] = None,
    default_kd: Optional[np.ndarray] = None,
    with_gripper: bool = False,
) -> MockArmRobot:
    """Create and return a mock A1Z robot for offline validation."""
    urdf = urdf_path or _DEFAULT_URDF_PATH
    _gravity_model, joint_limits = _load_control_model(urdf)
    return MockArmRobot(
        num_joints=_NUM_JOINTS,
        gravity_comp_factor=gravity_comp_factor,
        zero_gravity_mode=zero_gravity_mode,
        default_kp=default_kp if default_kp is not None else _DEFAULT_KP,
        default_kd=default_kd if default_kd is not None else _DEFAULT_KD,
        joint_limits=joint_limits,
        with_gripper=with_gripper,
        control_freq_hz=control_freq_hz,
    )


def get_a1z_isaacsim_robot(
    control_freq_hz: int = 60,
    with_gripper: bool = False,
    articulation_root_prim: Optional[str] = None,
    urdf_path: Optional[str] = None,
    default_kp: Optional[np.ndarray] = None,
    default_kd: Optional[np.ndarray] = None,
    gravity_comp_factor: float = 1.0,
    zero_gravity_mode: bool = False,
):
    """Create and return an Isaac Sim-backed A1Z robot."""
    from a1z.robots.isaacsim_robot import IsaacSimArmRobot

    return IsaacSimArmRobot(
        num_joints=_NUM_JOINTS,
        with_gripper=with_gripper,
        control_freq_hz=control_freq_hz,
        articulation_root_prim=articulation_root_prim,
        default_kp=default_kp if default_kp is not None else _DEFAULT_KP,
        default_kd=default_kd if default_kd is not None else _DEFAULT_KD,
        urdf_path=urdf_path or _DEFAULT_URDF_PATH,
        gravity_comp_factor=gravity_comp_factor,
        zero_gravity_mode=zero_gravity_mode,
        gravity_torque_scale=_GRAVITY_TORQUE_SCALE,
        max_gravity_torque=_MAX_GRAVITY_TORQUE,
        torque_clip=_TORQUE_CLIP,
    )


def create_a1z_robot(
    backend: str = get_default_backend(),
    can_channel: str = get_default_can_channel(),
    gravity_comp_factor: float = 1.0,
    zero_gravity_mode: bool = True,
    control_freq_hz: int = 250,
    min_freq_hz: float = 80.0,
    urdf_path: Optional[str] = None,
    default_kp: Optional[np.ndarray] = None,
    default_kd: Optional[np.ndarray] = None,
    with_gripper: bool = False,
    gripper_max_torque: float = 2.0,
    articulation_root_prim: Optional[str] = None,
) -> Robot:
    """Create the requested A1Z backend."""
    if backend == "socketcan":
        return get_a1z_robot(
            can_channel=can_channel,
            gravity_comp_factor=gravity_comp_factor,
            zero_gravity_mode=zero_gravity_mode,
            control_freq_hz=control_freq_hz,
            min_freq_hz=min_freq_hz,
            urdf_path=urdf_path,
            default_kp=default_kp,
            default_kd=default_kd,
            with_gripper=with_gripper,
            gripper_max_torque=gripper_max_torque,
        )
    if backend == "mock":
        return get_a1z_mock_robot(
            gravity_comp_factor=gravity_comp_factor,
            zero_gravity_mode=zero_gravity_mode,
            control_freq_hz=control_freq_hz,
            urdf_path=urdf_path,
            default_kp=default_kp,
            default_kd=default_kd,
            with_gripper=with_gripper,
        )
    if backend == "isaacsim":
        return get_a1z_isaacsim_robot(
            control_freq_hz=control_freq_hz,
            with_gripper=with_gripper,
            articulation_root_prim=articulation_root_prim,
            urdf_path=urdf_path,
            default_kp=default_kp,
            default_kd=default_kd,
            gravity_comp_factor=gravity_comp_factor,
            zero_gravity_mode=zero_gravity_mode,
        )
    raise ValueError(
        f"Unsupported A1Z backend '{backend}'. Expected one of: socketcan, mock, isaacsim"
    )
