from __future__ import annotations

from typing import Protocol, runtime_checkable

from .physical_types import ContactSnapshot, GraspCommand, GripperSnapshot


@runtime_checkable
class ParallelJawActuator(Protocol):
    """Low-level parallel-jaw boundary implemented by the A1Z Isaac adapter."""

    def snapshot(self) -> GripperSnapshot:
        """Return the measured jaw state without changing simulation state."""

    def apply(self, command: GraspCommand) -> None:
        """Apply a finite-drive command; implementations must not teleport joint state."""


@runtime_checkable
class PhysicalContactObserver(Protocol):
    """Contact boundary for explicit-target or automatically discovered grasping."""

    def observe(self, *, target_body_path: str = "", physics_dt_s: float) -> ContactSnapshot:
        """Return contact forces converted using the actual physics time step."""
