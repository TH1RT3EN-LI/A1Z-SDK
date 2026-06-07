from __future__ import annotations

import time

import numpy as np
import pytest

from a1z.robots.arm_robot import ArmRobot
from a1z.robots.get_robot import create_a1z_robot


def test_mock_backend_requires_start_before_control() -> None:
    robot = create_a1z_robot(backend="mock", with_gripper=True)

    with pytest.raises(RuntimeError, match="Robot not running"):
        robot.command_joint_pos(np.zeros(7))

    with pytest.raises(RuntimeError, match="Robot not running"):
        robot.command_gripper(0.5)

    with pytest.raises(RuntimeError, match="Robot not running"):
        robot.start_recording()


def test_mock_backend_record_and_playback_contract() -> None:
    robot = create_a1z_robot(backend="mock", with_gripper=True, zero_gravity_mode=True, control_freq_hz=100)
    robot.start()
    try:
        robot.start_recording(sample_hz=50)
        robot.command_joint_pos(np.array([0.1, -0.2, 0.15, 0.05, -0.1, 0.2, 0.4], dtype=np.float64))
        time.sleep(0.08)
        robot.command_joint_pos(np.array([0.2, -0.1, 0.1, 0.0, -0.05, 0.25, 0.7], dtype=np.float64))
        time.sleep(0.08)
        trajectory = robot.stop_recording()

        assert len(trajectory) >= 2
        assert trajectory[0][0] == pytest.approx(0.0, abs=0.03)
        assert trajectory[-1][0] > trajectory[0][0]

        robot.set_gravity_mode(True)
        robot.play_trajectory(trajectory, speed_factor=1.5)
        assert robot.zero_gravity_mode is True

        pos = robot.get_joint_pos()
        np.testing.assert_allclose(pos[:6], trajectory[-1][1], atol=1e-6)
        assert pos[6] == pytest.approx(0.7, abs=1e-6)
    finally:
        robot.stop()


def test_recording_file_roundtrip_is_backend_agnostic(tmp_path) -> None:
    trajectory = [
        (0.0, np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float64)),
        (0.2, np.array([0.5, 0.4, 0.3, 0.2, 0.1, 0.0], dtype=np.float64)),
    ]
    out = tmp_path / "teach.json"

    ArmRobot.save_recording(trajectory, str(out))
    loaded = ArmRobot.load_recording(str(out))

    assert len(loaded) == len(trajectory)
    for (t_expected, pos_expected), (t_actual, pos_actual) in zip(trajectory, loaded):
        assert t_actual == pytest.approx(t_expected)
        np.testing.assert_allclose(pos_actual, pos_expected)
