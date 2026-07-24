"""Base types for RGB-D frame sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from a1z_ext.interfaces.observation import RGBDObservation


@dataclass(slots=True)
class RGBDFrameCapture:
    observation: RGBDObservation
    rgb: np.ndarray
    depth_m: np.ndarray
    source_info: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.rgb.ndim != 3 or self.rgb.shape[2] < 3:
            raise ValueError(f"rgb must have shape (H, W, C>=3), got {self.rgb.shape}")
        if self.depth_m.ndim != 2:
            raise ValueError(f"depth_m must have shape (H, W), got {self.depth_m.shape}")
        if self.rgb.shape[:2] != self.depth_m.shape[:2]:
            raise ValueError(
                f"rgb and depth resolution mismatch: rgb={self.rgb.shape[:2]} depth={self.depth_m.shape[:2]}"
            )
        if int(self.observation.height) != int(self.rgb.shape[0]) or int(self.observation.width) != int(
            self.rgb.shape[1]
        ):
            raise ValueError(
                "observation resolution mismatch: "
                f"observation=({self.observation.height}, {self.observation.width}) "
                f"rgb={self.rgb.shape[:2]}"
            )
        self.observation.extrinsic_matrix()


class FrameSource(ABC):
    """Minimal contract for shared RGB-D frame providers."""

    def open(self) -> None:
        """Initialize the source if needed."""

    @abstractmethod
    def capture(self) -> RGBDFrameCapture:
        """Capture a single RGB-D observation."""

    def close(self) -> None:
        """Release source resources if needed."""

    def health(self) -> dict[str, Any]:
        """Return a simple health payload for debugging."""
        return {"ready": True}
