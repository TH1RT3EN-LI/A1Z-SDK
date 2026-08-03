"""Stable feedback-aware client API shared by CLI and GUI adapters."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from ._transport import JsonLineTransport
from .models import CommandResult, ControlMode, Endpoint, JointState


class _Transport(Protocol):
    def request(
        self,
        command: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, Any]: ...


def _six_finite(values: Sequence[float], *, name: str) -> list[float]:
    if isinstance(values, (str, bytes)) or len(values) != 6:
        raise ValueError(f"{name} must contain exactly 6 values")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _positive_finite(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return result


class A1ZClient:
    """Client for the process that exclusively owns the real robot hardware.

    ``move_joints`` and ``set_gripper_opening`` wait for feedback verification.
    ``set_joint_target`` submits asynchronously. Every newer valid target
    atomically supersedes the previous target in the control service.
    """

    def __init__(
        self,
        endpoint: Endpoint | None = None,
        *,
        transport: _Transport | None = None,
    ) -> None:
        self.endpoint = endpoint or Endpoint.from_env()
        self._transport = transport or JsonLineTransport(self.endpoint)

    def request(
        self,
        command: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> CommandResult:
        data = self._transport.request(command, arguments, timeout_s=timeout_s)
        return CommandResult.from_mapping(command, data)

    def status(self) -> JointState:
        data = self._transport.request("status")
        return JointState.from_mapping(data)

    def info(self) -> dict[str, Any]:
        return dict(self._transport.request("info"))

    def move_joints(
        self,
        position_deg: Sequence[float],
        *,
        speed_rad_s: float = 0.5,
        timeout_s: float = 120.0,
    ) -> CommandResult:
        joints = _six_finite(position_deg, name="position_deg")
        speed = _positive_finite(speed_rad_s, name="speed_rad_s")
        timeout = _positive_finite(timeout_s, name="timeout_s")
        return self.request(
            "move",
            {"joints": joints, "speed": speed, "timeout_s": timeout},
            timeout_s=timeout + 2.0,
        )

    def set_joint_target(
        self,
        position_deg: Sequence[float],
        *,
        speed_rad_s: float = 0.5,
        timeout_s: float = 120.0,
    ) -> CommandResult:
        joints = _six_finite(position_deg, name="position_deg")
        speed = _positive_finite(speed_rad_s, name="speed_rad_s")
        timeout = _positive_finite(timeout_s, name="timeout_s")
        return self.request(
            "command",
            {"joints": joints, "speed": speed, "timeout_s": timeout},
        )

    def jog_joint(
        self,
        joint: int,
        delta_deg: float,
        *,
        speed_rad_s: float = 0.5,
        timeout_s: float = 30.0,
    ) -> CommandResult:
        joint_index = int(joint)
        delta = float(delta_deg)
        if joint_index != joint or not 1 <= joint_index <= 6:
            raise ValueError("joint must be an integer from 1 to 6")
        if not math.isfinite(delta) or delta == 0:
            raise ValueError("delta_deg must be a finite non-zero number")
        speed = _positive_finite(speed_rad_s, name="speed_rad_s")
        timeout = _positive_finite(timeout_s, name="timeout_s")
        return self.request(
            "joint_jog",
            {
                "joint_index": joint_index,
                "delta_deg": delta,
                "speed": speed,
                "timeout_s": timeout,
            },
            timeout_s=timeout + 2.0,
        )

    def set_control_mode(self, mode: ControlMode | str) -> CommandResult:
        aliases = {
            "hold": ControlMode.POSITION_HOLD,
            "position_hold": ControlMode.POSITION_HOLD,
            "zero-force": ControlMode.ZERO_FORCE,
            "zero_force": ControlMode.ZERO_FORCE,
            "gravity_comp_effort": ControlMode.ZERO_FORCE,
        }
        if isinstance(mode, ControlMode):
            resolved = mode
        else:
            try:
                resolved = aliases[str(mode).strip().lower()]
            except KeyError as exc:
                raise ValueError("mode must be 'hold' or 'zero-force'") from exc
        return self.request(
            "gravity_mode", {"enabled": resolved is ControlMode.ZERO_FORCE}
        )

    def set_gripper_opening(
        self, opening: float, *, timeout_s: float = 10.0
    ) -> CommandResult:
        value = float(opening)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("opening must be in [0.0, 1.0]")
        timeout = _positive_finite(timeout_s, name="timeout_s")
        return self.request("gripper", {"value": value}, timeout_s=timeout)

    def close_grasp(self, *, timeout_s: float = 15.0) -> CommandResult:
        timeout = _positive_finite(timeout_s, name="timeout_s")
        return self.request(
            "grasp_close", {"timeout_s": timeout}, timeout_s=timeout + 2.0
        )

    def grasp_status(self) -> CommandResult:
        return self.request("grasp_status")

    def release_grasp(self, *, timeout_s: float = 3.0) -> CommandResult:
        timeout = _positive_finite(timeout_s, name="timeout_s")
        return self.request(
            "grasp_release", {"timeout_s": timeout}, timeout_s=timeout + 2.0
        )

    def emergency_stop(self) -> CommandResult:
        return self.request("estop")

    def release_emergency_stop(self) -> CommandResult:
        return self.request("estop_release")

    def stop_service(self) -> CommandResult:
        return self.request("stop")
