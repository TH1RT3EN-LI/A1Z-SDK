from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("can")

from a1z_ext.robots.paced_motor_chain import PacedMixedMotorChain


class _FakeMotor:
    def __init__(self, label: str, calls: list[tuple[str, dict[str, float]]]) -> None:
        self._label = label
        self._calls = calls

    def send_mit_command(self, **command: float) -> None:
        self._calls.append((self._label, command))


def test_paced_chain_preserves_sdk_order_and_waits_only_between_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, float]]] = []
    sleeps: list[float] = []
    chain = object.__new__(PacedMixedMotorChain)
    chain._motor_a_list = [_FakeMotor(f"A{i}", calls) for i in range(1, 4)]
    chain._motor_b_list = [_FakeMotor(f"B{i}", calls) for i in range(4, 7)]
    chain._motor_a_joint_indices = [0, 1, 2]
    chain._motor_b_joint_indices = [3, 4, 5]
    chain._inter_command_delay_s = 0.0001
    monkeypatch.setattr(
        "a1z_ext.robots.paced_motor_chain.time.sleep",
        sleeps.append,
    )

    values = np.arange(6, dtype=np.float64)
    chain.send_commands(
        pos=values,
        vel=values + 10.0,
        kp=values + 20.0,
        kd=values + 30.0,
        torque=values + 40.0,
        motor_a_mode=2,
    )

    assert [label for label, _command in calls] == [
        "A1",
        "A2",
        "A3",
        "B4",
        "B5",
        "B6",
    ]
    assert sleeps == [0.0001] * 5
    for joint_index, (_label, command) in enumerate(calls):
        assert command["pos"] == pytest.approx(float(values[joint_index]))
        assert command["vel"] == pytest.approx(float(values[joint_index] + 10.0))
        assert command["kp"] == pytest.approx(float(values[joint_index] + 20.0))
        assert command["kd"] == pytest.approx(float(values[joint_index] + 30.0))
        assert command["torque"] == pytest.approx(float(values[joint_index] + 40.0))
    assert [command.get("mode") for _label, command in calls] == [
        2,
        2,
        2,
        None,
        None,
        None,
    ]


def test_paced_chain_skips_wait_when_compatibility_delay_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, float]]] = []
    chain = object.__new__(PacedMixedMotorChain)
    chain._motor_a_list = [_FakeMotor("A1", calls)]
    chain._motor_b_list = [_FakeMotor("B2", calls)]
    chain._motor_a_joint_indices = [0]
    chain._motor_b_joint_indices = [1]
    chain._inter_command_delay_s = 0.0
    monkeypatch.setattr(
        "a1z_ext.robots.paced_motor_chain.time.sleep",
        lambda _delay: pytest.fail("zero delay must not sleep"),
    )

    zeros = np.zeros(2, dtype=np.float64)
    chain.send_commands(zeros, zeros, zeros, zeros, zeros)

    assert [label for label, _command in calls] == ["A1", "B2"]
