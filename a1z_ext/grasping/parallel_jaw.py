from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


def rate_limit_parallel_jaw_setpoint(
    *,
    previous_dofs_m: Sequence[float],
    measured_dofs_m: Sequence[float],
    target_dofs_m: Sequence[float],
    max_velocity_m_s: Sequence[float],
    dt_s: float,
    max_lead_m: float,
) -> tuple[float, float]:
    """Advance a two-DOF jaw setpoint without rebasing it on every measurement."""

    vectors = {
        "previous_dofs_m": previous_dofs_m,
        "measured_dofs_m": measured_dofs_m,
        "target_dofs_m": target_dofs_m,
        "max_velocity_m_s": max_velocity_m_s,
    }
    for name, values in vectors.items():
        if len(values) != 2:
            raise ValueError(f"{name} must contain exactly two values")
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError(f"{name} values must be finite")
    dt = float(dt_s)
    lead = float(max_lead_m)
    if not math.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt_s must be finite and positive")
    if not math.isfinite(lead) or lead <= 0.0:
        raise ValueError("max_lead_m must be finite and positive")
    if any(float(value) <= 0.0 for value in max_velocity_m_s):
        raise ValueError("max_velocity_m_s values must be positive")

    result: list[float] = []
    for index in range(2):
        previous = float(previous_dofs_m[index])
        measured = float(measured_dofs_m[index])
        target = float(target_dofs_m[index])
        max_step = float(max_velocity_m_s[index]) * dt
        target_delta = min(max(target - previous, -max_step), max_step)
        ramped = previous + target_delta
        tracking_delta = min(max(ramped - measured, -lead), lead)
        result.append(measured + tracking_delta)
    return (result[0], result[1])


@dataclass(frozen=True, slots=True)
class ParallelJawMapping:
    """Map one jaw-width coordinate to two independently driven prismatic DOFs."""

    open_dofs_m: tuple[float, float]
    closed_dofs_m: tuple[float, float]

    def __post_init__(self) -> None:
        values = (*self.open_dofs_m, *self.closed_dofs_m)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("parallel-jaw DOF limits must be finite")
        if self.open_width_m <= self.closed_width_m:
            raise ValueError("parallel-jaw open width must exceed closed width")

    @classmethod
    def from_sequences(
        cls,
        *,
        open_dofs_m: Sequence[float],
        closed_dofs_m: Sequence[float],
    ) -> "ParallelJawMapping":
        if len(open_dofs_m) != 2 or len(closed_dofs_m) != 2:
            raise ValueError("parallel-jaw mapping requires exactly two open and closed DOF values")
        return cls(
            open_dofs_m=(float(open_dofs_m[0]), float(open_dofs_m[1])),
            closed_dofs_m=(float(closed_dofs_m[0]), float(closed_dofs_m[1])),
        )

    @property
    def open_width_m(self) -> float:
        return abs(self.open_dofs_m[0] - self.open_dofs_m[1])

    @property
    def closed_width_m(self) -> float:
        return abs(self.closed_dofs_m[0] - self.closed_dofs_m[1])

    def clamp_width(self, width_m: float) -> float:
        return min(max(float(width_m), self.closed_width_m), self.open_width_m)

    def width_to_dofs(self, width_m: float) -> tuple[float, float]:
        width = self.clamp_width(width_m)
        alpha = (width - self.closed_width_m) / (self.open_width_m - self.closed_width_m)
        return tuple(
            self.closed_dofs_m[index]
            + alpha * (self.open_dofs_m[index] - self.closed_dofs_m[index])
            for index in range(2)
        )  # type: ignore[return-value]

    def dofs_to_width(self, dofs_m: Sequence[float]) -> float:
        if len(dofs_m) != 2:
            raise ValueError("parallel-jaw width requires exactly two measured DOFs")
        return self.clamp_width(abs(float(dofs_m[0]) - float(dofs_m[1])))
