from __future__ import annotations

import pytest


np = pytest.importorskip("numpy")

from a1z_ext.robots.realtime_joint_controller import (
    JointTorqueShaper,
    RuckigJointReferenceGenerator,
)


def test_ruckig_reference_is_generated_at_the_control_period_with_hard_limits() -> None:
    pytest.importorskip("ruckig")
    period_s = 0.004
    generator = RuckigJointReferenceGenerator(6, period_s)
    generator.reset(np.zeros(6))
    generation = generator.set_target(
        [0.4, -0.2, 0.1, 0.0, 0.0, 0.0],
        max_velocity=0.5,
        max_acceleration=2.0,
        max_jerk=12.0,
    )

    positions = []
    velocities = []
    accelerations = []
    for _ in range(5000):
        reference = generator.advance(np.zeros(6), np.zeros(6))
        positions.append(reference.position)
        velocities.append(reference.velocity)
        accelerations.append(reference.acceleration)
        if reference.finished:
            break

    assert reference.finished is True
    assert reference.generation == generation
    assert reference.position == pytest.approx([0.4, -0.2, 0.1, 0, 0, 0], abs=1e-9)
    assert np.max(np.abs(velocities)) <= 0.5 + 1e-9
    assert np.max(np.abs(accelerations)) <= 2.0 + 1e-9
    jerks = np.diff(np.asarray(accelerations), axis=0) / period_s
    assert np.max(np.abs(jerks)) <= 12.0 + 1e-6
    assert np.max(np.abs(np.diff(np.asarray(positions), axis=0))) < 0.003


def test_ruckig_replacement_preserves_reference_continuity() -> None:
    pytest.importorskip("ruckig")
    period_s = 0.004
    generator = RuckigJointReferenceGenerator(6, period_s)
    generator.reset(np.zeros(6))
    generator.set_target(
        [1.0, 0, 0, 0, 0, 0],
        max_velocity=0.6,
        max_acceleration=2.0,
        max_jerk=12.0,
    )
    before = None
    for _ in range(80):
        before = generator.advance(np.zeros(6), np.zeros(6))
    assert before is not None
    generation = generator.set_target(
        [-0.2, 0, 0, 0, 0, 0],
        max_velocity=0.6,
        max_acceleration=2.0,
        max_jerk=12.0,
    )
    after = generator.advance(np.zeros(6), np.zeros(6))

    assert after.generation == generation
    assert abs(after.position[0] - before.position[0]) <= 0.6 * period_s + 1e-9
    assert abs(after.velocity[0] - before.velocity[0]) <= 2.0 * period_s + 1e-9
    assert abs(after.acceleration[0] - before.acceleration[0]) <= 12.0 * period_s + 1e-9


def test_torque_shaper_limits_total_step_and_integral_windup() -> None:
    shaper = JointTorqueShaper(
        2,
        control_period_s=0.01,
        torque_slew_rate_nm_s=[10.0, 20.0],
    )
    assert shaper.shape_total([1.0, -1.0], [5.0, 5.0]) == pytest.approx(
        [1.0, -1.0]
    )
    assert shaper.shape_total([5.0, 5.0], [5.0, 5.0]) == pytest.approx(
        [1.1, -0.8]
    )

    for _ in range(100):
        bias = shaper.update_integral(
            position_error=[1.0, -1.0],
            kp=[10.0, 10.0],
            base_torque=[4.95, -4.95],
            torque_limit=[5.0, 5.0],
            enabled=True,
            integral_gain_s_inv=1.0,
            correction_rate_limit_rad_s=0.2,
            max_correction_rad=0.5,
        )
    assert bias == pytest.approx([0.04, -0.04])
    assert shaper.equivalent_correction == pytest.approx([0.004, -0.004])
