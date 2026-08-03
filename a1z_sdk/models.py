"""Small dependency-free data models for the public SDK."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ControlMode(str, Enum):
    """The two mutually exclusive arm control modes."""

    POSITION_HOLD = "position_hold"
    ZERO_FORCE = "gravity_comp_effort"


class Completion(str, Enum):
    """Known completion semantics returned by the control service."""

    FEEDBACK_VERIFIED = "feedback_verified"
    FEEDBACK_SETTLED = "feedback_settled"
    ALREADY_AT_TARGET = "already_at_target"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    NOT_VERIFIED = "not_verified"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Endpoint:
    """Address of the single local or remote control service."""

    socket_path: str = ""
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 37103
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        if not 0 <= int(self.tcp_port) <= 65535:
            raise ValueError("tcp_port must be in [0, 65535]")
        if not math.isfinite(float(self.timeout_s)) or float(self.timeout_s) <= 0:
            raise ValueError("timeout_s must be a positive finite number")
        if not self.socket_path and int(self.tcp_port) == 0:
            raise ValueError("at least one control transport must be enabled")

    @classmethod
    def from_env(cls, *, timeout_s: float | None = None) -> "Endpoint":
        return cls(
            socket_path=os.environ.get("A1Z_SOCKET_PATH", ""),
            tcp_host=os.environ.get("A1Z_TCP_HOST", "127.0.0.1"),
            tcp_port=int(os.environ.get("A1Z_TCP_PORT", "37103")),
            timeout_s=(
                float(timeout_s)
                if timeout_s is not None
                else float(os.environ.get("A1Z_REQUEST_TIMEOUT_S", "10"))
            ),
        )


def _float_tuple(
    data: Mapping[str, Any], key: str, *, length: int | None = None
) -> tuple[float, ...]:
    raw = data.get(key, ())
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError(f"{key} must be a numeric sequence")
    values = tuple(float(value) for value in raw)
    if length is not None and len(values) != length:
        raise ValueError(f"{key} must contain {length} values")
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{key} must contain only finite values")
    return values


@dataclass(frozen=True)
class JointState:
    """One feedback snapshot from the real robot control loop."""

    position_deg: tuple[float, ...]
    velocity_rad_s: tuple[float, ...]
    torque_nm: tuple[float, ...]
    running: bool
    faulted: bool
    fault_message: str = ""
    estopped: bool = False
    control_mode: ControlMode | None = None
    gravity_comp_factor: float | None = None
    motion: Mapping[str, Any] = field(default_factory=dict)
    gripper_measured: float | None = None
    gripper_target: float | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "JointState":
        gripper_measured = data.get("gripper_measured")
        gripper_target = data.get("gripper_target")
        raw_control_mode = data.get("control_mode")
        try:
            control_mode = (
                None
                if raw_control_mode is None
                else ControlMode(str(raw_control_mode))
            )
        except ValueError:
            control_mode = None
        raw_gravity_factor = data.get("gravity_comp_factor")
        gravity_comp_factor = (
            None if raw_gravity_factor is None else float(raw_gravity_factor)
        )
        if gravity_comp_factor is not None and not math.isfinite(
            gravity_comp_factor
        ):
            gravity_comp_factor = None
        return cls(
            position_deg=_float_tuple(data, "pos_deg", length=6),
            velocity_rad_s=_float_tuple(data, "vel_rad_s", length=6),
            torque_nm=_float_tuple(data, "torque_nm", length=6),
            running=bool(data.get("running", False)),
            faulted=bool(data.get("faulted", False)),
            fault_message=str(data.get("fault_message", "") or ""),
            estopped=bool(data.get("estopped", False)),
            control_mode=control_mode,
            gravity_comp_factor=gravity_comp_factor,
            motion=(
                dict(data.get("motion", {}))
                if isinstance(data.get("motion"), Mapping)
                else {}
            ),
            gripper_measured=(
                None if gripper_measured is None else float(gripper_measured)
            ),
            gripper_target=None if gripper_target is None else float(gripper_target),
            raw=dict(data),
        )


@dataclass(frozen=True)
class CommandResult:
    """Successful service response with explicit completion semantics."""

    command: str
    completion: str
    data: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, command: str, data: Mapping[str, Any]) -> "CommandResult":
        return cls(
            command=command,
            completion=str(data.get("completion", Completion.UNKNOWN.value)),
            data=dict(data),
        )

    @property
    def feedback_verified(self) -> bool:
        if self.completion in {
            Completion.FEEDBACK_VERIFIED.value,
            Completion.FEEDBACK_SETTLED.value,
            Completion.ALREADY_AT_TARGET.value,
        }:
            return True
        verification = self.data.get("verification")
        return bool(
            isinstance(verification, Mapping)
            and (verification.get("reached") or verification.get("settled"))
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "command": self.command,
            "completion": self.completion,
            "feedback_verified": self.feedback_verified,
            "data": dict(self.data),
        }
