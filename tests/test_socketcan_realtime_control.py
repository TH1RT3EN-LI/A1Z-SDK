from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest


np = pytest.importorskip("numpy")
pytest.importorskip("can")
pytest.importorskip("pinocchio")

ROOT = Path(__file__).resolve().parents[1]
SDK_PATH = str(ROOT / "vendor" / "GALAXEA-A1Z")
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

from a1z.robots.arm_robot import JointCommand, JointState
from a1z_ext.robots.realtime_joint_controller import JointReference, JointTorqueShaper
from a1z_ext.robots.socketcan_robot import SocketCANArmRobot


class InactiveStartupGate:
    active = False


class FixedReferenceGenerator:
    def advance(self, _measured_position, _measured_velocity):
        return JointReference(
            position=np.array([0.1, -0.2, 0.3, 0.0, 0.0, 0.0]),
            velocity=np.array([0.2, -0.1, 0.0, 0.0, 0.0, 0.0]),
            acceleration=np.array([0.4, -0.3, 0.0, 0.0, 0.0, 0.0]),
            target=np.array([0.5, -0.4, 0.3, 0.0, 0.0, 0.0]),
            generation=7,
            finished=False,
        )


class RecordingDynamics:
    def __init__(self) -> None:
        self.calls = []

    def compute_inverse_dynamics(self, position, velocity, acceleration):
        self.calls.append((position.copy(), velocity.copy(), acceleration.copy()))
        return np.ones(6, dtype=np.float64)


class RecordingMotorChain:
    def __init__(self) -> None:
        self.calls = []

    def send_commands(self, **command) -> None:
        self.calls.append(command)


def test_socketcan_update_uses_one_reference_for_rnea_and_mit_frame() -> None:
    robot = SocketCANArmRobot.__new__(SocketCANArmRobot)
    robot._num_joints = 6
    robot._running = False
    robot._control_period_s = 0.004
    robot._arm_feedback_startup_lock = threading.Lock()
    robot._arm_feedback_startup_gate = InactiveStartupGate()
    robot._recording = False
    robot._state_lock = threading.Lock()
    robot._state = JointState(
        pos=np.array([-0.3, 0.2, -0.1, 0.0, 0.0, 0.0]),
        vel=np.zeros(6),
    )
    robot._command_lock = threading.Lock()
    robot._command = JointCommand(
        pos=np.zeros(6),
        vel=np.zeros(6),
        acc=np.zeros(6),
        kp=np.zeros(6),
        kd=np.zeros(6),
        torque_ff=np.zeros(6),
    )
    robot._default_kp = np.array([30.0, 30.0, 30.0, 20.0, 5.0, 5.0])
    robot._default_kd = np.array([1.0, 1.0, 1.0, 0.5, 0.5, 0.5])
    robot._native_reference_lock = threading.Lock()
    robot._native_trajectory_lock = threading.Lock()
    robot._torque_shaper_lock = threading.Lock()
    robot._native_trajectory_mode = "active"
    robot._native_integral_gain_s_inv = 0.6
    robot._native_correction_rate_limit_rad_s = np.deg2rad(0.5)
    robot._native_max_correction_rad = np.deg2rad(3.0)
    robot._joint_reference_generator = FixedReferenceGenerator()
    robot._joint_torque_shaper = JointTorqueShaper(
        6,
        0.004,
        [250.0, 250.0, 250.0, 100.0, 40.0, 40.0],
    )
    robot._joint_trajectory_status = {"generation": 0}
    robot._gravity_model = RecordingDynamics()
    robot._max_gravity_torque = np.full(6, 50.0)
    robot._gravity_torque_scale = np.ones(6)
    robot.gravity_comp_factor = 1.0
    robot._torque_clip = np.full(6, 10.0)
    robot._joint_sign = np.array([1.0, 1.0, -1.0, 1.0, -1.0, 1.0])
    robot._motor_chain = RecordingMotorChain()
    robot.gripper = None
    robot.zero_gravity_mode = False
    robot._runtime_fault_lock = threading.Lock()
    robot._runtime_fault = ""
    robot._read_state = lambda: None
    robot._check_runtime_safety = lambda: None

    robot._update()

    assert len(robot._gravity_model.calls) == 1
    dynamics_position, dynamics_velocity, dynamics_acceleration = (
        robot._gravity_model.calls[0]
    )
    reference = robot._joint_reference_generator.advance(None, None)
    assert dynamics_position == pytest.approx(reference.position)
    assert dynamics_velocity == pytest.approx(reference.velocity)
    assert dynamics_acceleration == pytest.approx(reference.acceleration)
    assert len(robot._motor_chain.calls) == 1
    sent = robot._motor_chain.calls[0]
    assert sent["pos"] == pytest.approx(reference.position * robot._joint_sign)
    assert sent["vel"] == pytest.approx(reference.velocity * robot._joint_sign)
    assert sent["kp"] == pytest.approx(robot._default_kp)
    assert sent["kd"] == pytest.approx(robot._default_kd)
    assert sent["torque"] == pytest.approx(np.ones(6) * robot._joint_sign)
    status = robot.get_joint_trajectory_status()
    assert status["generation"] == 7
    assert status["finished"] is False


def test_socketcan_zero_gravity_matches_official_live_pose_torque_path() -> None:
    robot = SocketCANArmRobot.__new__(SocketCANArmRobot)
    robot._num_joints = 6
    robot._running = False
    robot._control_period_s = 0.004
    robot._arm_feedback_startup_lock = threading.Lock()
    robot._arm_feedback_startup_gate = InactiveStartupGate()
    robot._recording = False
    robot._state_lock = threading.Lock()
    measured_position = np.array([-0.3, 0.2, -0.1, 0.4, -0.5, 0.6])
    frozen_command_position = np.array([0.7, -0.6, 0.5, -0.4, 0.3, -0.2])
    robot._state = JointState(
        pos=measured_position.copy(),
        vel=np.zeros(6),
    )
    robot._command_lock = threading.Lock()
    robot._command = JointCommand(
        pos=frozen_command_position.copy(),
        vel=np.zeros(6),
        acc=np.zeros(6),
        kp=np.zeros(6),
        kd=np.array([0.5, 0.5, 0.5, 0.25, 0.25, 0.25]),
        torque_ff=np.zeros(6),
    )
    robot._default_kp = np.array([30.0, 30.0, 30.0, 20.0, 5.0, 5.0])
    robot._default_kd = np.array([1.0, 1.0, 1.0, 0.5, 0.5, 0.5])
    robot._native_reference_lock = threading.Lock()
    robot._native_trajectory_lock = threading.Lock()
    robot._torque_shaper_lock = threading.Lock()
    robot._native_trajectory_mode = "inactive"
    robot._native_integral_gain_s_inv = 0.6
    robot._native_correction_rate_limit_rad_s = np.deg2rad(0.5)
    robot._native_max_correction_rad = np.deg2rad(3.0)
    robot._joint_reference_generator = FixedReferenceGenerator()
    robot._joint_torque_shaper = JointTorqueShaper(
        6,
        0.004,
        [250.0, 250.0, 250.0, 100.0, 40.0, 40.0],
    )
    # Seed the position-mode shaper so the assertion also proves that floating
    # mode bypasses its slew-rate state, as the official SDK does.
    robot._joint_torque_shaper.shape_total(np.zeros(6), np.full(6, 10.0))
    robot._joint_trajectory_status = {"generation": 0}
    robot._gravity_model = RecordingDynamics()
    robot._max_gravity_torque = np.full(6, 50.0)
    robot._gravity_torque_scale = np.ones(6)
    robot.gravity_comp_factor = 1.0
    robot._torque_clip = np.full(6, 10.0)
    robot._joint_sign = np.array([1.0, 1.0, -1.0, 1.0, -1.0, 1.0])
    robot._motor_chain = RecordingMotorChain()
    robot.gripper = None
    robot.zero_gravity_mode = True
    robot._runtime_fault_lock = threading.Lock()
    robot._runtime_fault = ""
    robot._read_state = lambda: None
    robot._check_runtime_safety = lambda: None

    robot._update()

    assert len(robot._gravity_model.calls) == 1
    dynamics_position, dynamics_velocity, dynamics_acceleration = (
        robot._gravity_model.calls[0]
    )
    assert dynamics_position == pytest.approx(measured_position)
    assert dynamics_position != pytest.approx(frozen_command_position)
    assert dynamics_velocity == pytest.approx(np.zeros(6))
    assert dynamics_acceleration == pytest.approx(np.zeros(6))
    assert len(robot._motor_chain.calls) == 1
    sent = robot._motor_chain.calls[0]
    assert sent["pos"] == pytest.approx(
        frozen_command_position * robot._joint_sign
    )
    assert sent["kp"] == pytest.approx(np.zeros(6))
    assert sent["kd"] == pytest.approx(robot._default_kd * 0.5)
    assert sent["torque"] == pytest.approx(np.ones(6) * robot._joint_sign)
