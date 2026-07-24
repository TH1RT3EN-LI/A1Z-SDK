from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class GraspPhase(str, Enum):
    IDLE = "idle"
    PRECHECK = "precheck"
    SOFT_CLOSE = "soft_close"
    SEARCH = "search"
    PRELOAD = "preload"
    HOLDING = "holding"
    RELEASING = "releasing"
    RELEASED = "released"
    FAILED = "failed"
    ABORTED = "aborted"


class DriveProfile(str, Enum):
    FREE = "free"
    SOFT_CLOSE = "soft_close"
    SEARCH = "search"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class ContactSnapshot:
    left_body_paths: tuple[str, ...] = ()
    right_body_paths: tuple[str, ...] = ()
    left_normal_force_n: float | None = None
    right_normal_force_n: float | None = None
    left_force_by_body_n: tuple[tuple[str, float], ...] = ()
    right_force_by_body_n: tuple[tuple[str, float], ...] = ()
    support_body_paths: tuple[str, ...] = ()
    left_blocked: bool = False
    right_blocked: bool = False
    blocking_reason: str | None = None

    def normal_force_for(self, body_path: str) -> tuple[float | None, float | None]:
        left = dict(self.left_force_by_body_n).get(body_path)
        right = dict(self.right_force_by_body_n).get(body_path)
        if left is None and body_path in self.left_body_paths:
            left = self.left_normal_force_n
        if right is None and body_path in self.right_body_paths:
            right = self.right_normal_force_n
        return left, right

    def bilateral_for(self, target_body_path: str, minimum_normal_force_n: float | None) -> bool:
        if target_body_path in self.support_body_paths:
            return False
        if target_body_path not in self.left_body_paths or target_body_path not in self.right_body_paths:
            return False
        if minimum_normal_force_n is None:
            return True
        left_force, right_force = self.normal_force_for(target_body_path)
        if left_force is None or right_force is None:
            return False
        return (
            float(left_force) >= minimum_normal_force_n
            and float(right_force) >= minimum_normal_force_n
        )

    def strongest_bilateral_body(
        self,
        minimum_normal_force_n: float | None,
    ) -> str | None:
        """Choose the common finger contact with the strongest weaker-side force."""
        common = set(self.left_body_paths).intersection(self.right_body_paths)
        common.difference_update(self.support_body_paths)
        ranked: list[tuple[float, float, str]] = []
        for body_path in common:
            left_force, right_force = self.normal_force_for(body_path)
            if minimum_normal_force_n is not None:
                if left_force is None or right_force is None:
                    continue
                if (
                    float(left_force) < minimum_normal_force_n
                    or float(right_force) < minimum_normal_force_n
                ):
                    continue
            left_value = 0.0 if left_force is None else float(left_force)
            right_value = 0.0 if right_force is None else float(right_force)
            ranked.append((min(left_value, right_value), left_value + right_value, body_path))
        if not ranked:
            return None
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return ranked[0][2]

    @property
    def has_blocking_contact(self) -> bool:
        return self.left_blocked or self.right_blocked

    @property
    def left_support_body_paths(self) -> tuple[str, ...]:
        supports = set(self.support_body_paths)
        return tuple(path for path in self.left_body_paths if path in supports)

    @property
    def right_support_body_paths(self) -> tuple[str, ...]:
        supports = set(self.support_body_paths)
        return tuple(path for path in self.right_body_paths if path in supports)


@dataclass(frozen=True, slots=True)
class GripperSnapshot:
    width_m: float
    motion_stable: bool
    fully_closed: bool = False
    joint_positions_m: tuple[float, float] | None = None
    joint_velocities_m_s: tuple[float, float] | None = None
    projected_joint_forces_n: tuple[float, float] | None = None
    residual_joint_forces_n: tuple[float, float] | None = None
    command_lag_m: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class PhysicalGraspConfig:
    open_width_m: float
    closed_width_m: float
    preload_delta_m: float
    maximum_preload_delta_m: float
    minimum_stable_frames: int
    minimum_normal_force_n: float | None
    precheck_timeout_s: float
    soft_close_timeout_s: float
    search_timeout_s: float
    hold_confirm_timeout_s: float
    release_width_tolerance_m: float = 0.001
    force_window_frames: int = 5
    target_normal_force_n: float | None = None
    maximum_normal_force_n: float | None = None
    force_hysteresis_n: float = 0.1
    force_confirm_frames: int = 5
    preload_step_m: float = 0.0001
    preload_timeout_s: float = 2.0
    contact_loss_grace_frames: int = 0
    force_loss_grace_frames: int = 6
    minimum_effort_residual_n: float = 0.1
    minimum_position_lag_m: float = 0.0005
    unilateral_recovery_timeout_s: float = 1.0

    def __post_init__(self) -> None:
        if self.open_width_m <= self.closed_width_m:
            raise ValueError("open_width_m must be greater than closed_width_m")
        if not 0.0 <= self.preload_delta_m <= self.maximum_preload_delta_m:
            raise ValueError("preload_delta_m must be within [0, maximum_preload_delta_m]")
        if self.minimum_stable_frames <= 0:
            raise ValueError("minimum_stable_frames must be positive")
        if self.minimum_normal_force_n is not None and self.minimum_normal_force_n < 0.0:
            raise ValueError("minimum_normal_force_n cannot be negative")
        if self.force_window_frames <= 0:
            raise ValueError("force_window_frames must be positive")
        if self.force_confirm_frames <= 0:
            raise ValueError("force_confirm_frames must be positive")
        if self.target_normal_force_n is not None and self.target_normal_force_n <= 0.0:
            raise ValueError("target_normal_force_n must be positive when configured")
        if self.maximum_normal_force_n is not None and self.maximum_normal_force_n <= 0.0:
            raise ValueError("maximum_normal_force_n must be positive when configured")
        if (
            self.target_normal_force_n is not None
            and self.maximum_normal_force_n is not None
            and self.maximum_normal_force_n < self.target_normal_force_n
        ):
            raise ValueError("maximum_normal_force_n cannot be below target_normal_force_n")
        if self.force_hysteresis_n < 0.0:
            raise ValueError("force_hysteresis_n cannot be negative")
        if (
            self.target_normal_force_n is not None
            and self.force_hysteresis_n >= self.target_normal_force_n
        ):
            raise ValueError("force_hysteresis_n must be below target_normal_force_n")
        if self.preload_step_m <= 0.0:
            raise ValueError("preload_step_m must be positive")
        if self.preload_step_m > self.maximum_preload_delta_m:
            raise ValueError("preload_step_m cannot exceed maximum_preload_delta_m")
        if self.contact_loss_grace_frames < 0:
            raise ValueError("contact_loss_grace_frames cannot be negative")
        if self.force_loss_grace_frames <= 0:
            raise ValueError("force_loss_grace_frames must be positive")
        if self.minimum_effort_residual_n < 0.0:
            raise ValueError("minimum_effort_residual_n cannot be negative")
        if self.minimum_position_lag_m < 0.0:
            raise ValueError("minimum_position_lag_m cannot be negative")
        if self.unilateral_recovery_timeout_s <= 0.0:
            raise ValueError("unilateral_recovery_timeout_s must be positive")
        for name, value in (
            ("precheck_timeout_s", self.precheck_timeout_s),
            ("soft_close_timeout_s", self.soft_close_timeout_s),
            ("search_timeout_s", self.search_timeout_s),
            ("hold_confirm_timeout_s", self.hold_confirm_timeout_s),
            ("preload_timeout_s", self.preload_timeout_s),
        ):
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")

    @classmethod
    def from_controller_profile(cls, payload: Mapping[str, Any]) -> "PhysicalGraspConfig":
        open_dofs = [float(value) for value in payload["open_dofs_m"]]
        closed_dofs = [float(value) for value in payload["closed_dofs_m"]]
        if len(open_dofs) != 2 or len(closed_dofs) != 2:
            raise ValueError("parallel-jaw controller profile must define exactly two DOFs")
        open_width = abs(open_dofs[0] - open_dofs[1])
        closed_width = abs(closed_dofs[0] - closed_dofs[1])
        contact = payload["contact"]
        preload = payload["preload"]
        timeouts = payload["timeouts_s"]
        force_control = payload.get("force_control", {})
        return cls(
            open_width_m=open_width,
            closed_width_m=closed_width,
            preload_delta_m=float(preload["delta_m"]),
            maximum_preload_delta_m=float(preload["maximum_delta_m"]),
            minimum_stable_frames=int(contact["minimum_stable_frames"]),
            minimum_normal_force_n=(
                None
                if contact.get("minimum_normal_force_n") is None
                else float(contact["minimum_normal_force_n"])
            ),
            precheck_timeout_s=float(timeouts["precheck"]),
            soft_close_timeout_s=float(timeouts["soft_close"]),
            search_timeout_s=float(timeouts["search"]),
            hold_confirm_timeout_s=float(timeouts["hold_confirm"]),
            force_window_frames=int(contact.get("force_window_frames", 5)),
            target_normal_force_n=(
                None
                if force_control.get("target_normal_force_n") is None
                else float(force_control["target_normal_force_n"])
            ),
            maximum_normal_force_n=(
                None
                if force_control.get("maximum_normal_force_n") is None
                else float(force_control["maximum_normal_force_n"])
            ),
            force_hysteresis_n=float(force_control.get("force_hysteresis_n", 0.1)),
            force_confirm_frames=int(force_control.get("confirm_frames", 5)),
            preload_step_m=float(force_control.get("preload_step_m", 0.0001)),
            preload_timeout_s=float(timeouts.get("preload", 2.0)),
            contact_loss_grace_frames=int(
                force_control.get("contact_loss_grace_frames", 0)
            ),
            force_loss_grace_frames=int(
                force_control.get("force_loss_grace_frames", 6)
            ),
            minimum_effort_residual_n=float(
                force_control.get("minimum_effort_residual_n", 0.1)
            ),
            minimum_position_lag_m=float(
                force_control.get("minimum_position_lag_m", 0.0005)
            ),
            unilateral_recovery_timeout_s=float(
                force_control.get("unilateral_recovery_timeout_s", 1.0)
            ),
        )


@dataclass(frozen=True, slots=True)
class GraspCommand:
    drive_profile: DriveProfile
    target_width_m: float
    reason: str
    freeze_contact_finger: str | None = None

    def __post_init__(self) -> None:
        if self.freeze_contact_finger not in {None, "left", "right"}:
            raise ValueError("freeze_contact_finger must be 'left', 'right', or None")


@dataclass(frozen=True, slots=True)
class PhysicalGraspStatus:
    phase: GraspPhase
    target_body_path: str | None
    bilateral_contact: bool
    stable_contact_frames: int
    contact_width_m: float | None
    hold_width_m: float | None
    failure_reason: str | None
    command: GraspCommand | None
    candidate_body_path: str | None = None
    filtered_left_normal_force_n: float | None = None
    filtered_right_normal_force_n: float | None = None
    filtered_weak_normal_force_n: float | None = None
    target_normal_force_n: float | None = None
    maximum_normal_force_n: float | None = None
    force_stable_frames: int = 0
    contact_loss_frames: int = 0
    force_loss_frames: int = 0
    force_control_active: bool = False
    unilateral_recovery_active: bool = False
    unilateral_contact_side: str | None = None
    effective_grip_force_n: float | None = None
    grip_force_source: str | None = None

    @property
    def contact_ready(self) -> bool:
        return self.phase in {GraspPhase.PRELOAD, GraspPhase.HOLDING}

    @property
    def terminal(self) -> bool:
        return self.phase in {
            GraspPhase.RELEASED,
            GraspPhase.FAILED,
            GraspPhase.ABORTED,
        }
