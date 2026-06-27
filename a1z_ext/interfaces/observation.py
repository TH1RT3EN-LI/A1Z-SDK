"""Observation contracts for the non-grasping open-vocabulary pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any
from uuid import uuid4

import numpy as np


def _uuid() -> str:
    return str(uuid4())


@dataclass(slots=True)
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    distortion_model: str = "none"
    distortion_coeffs: list[float] = field(default_factory=list)
    schema_name: str = "CameraIntrinsics"
    schema_version: str = "v1"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CameraIntrinsics":
        return cls(
            fx=float(value["fx"]),
            fy=float(value["fy"]),
            cx=float(value["cx"]),
            cy=float(value["cy"]),
            distortion_model=str(value.get("distortion_model", "none")),
            distortion_coeffs=[float(v) for v in value.get("distortion_coeffs", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fx": float(self.fx),
            "fy": float(self.fy),
            "cx": float(self.cx),
            "cy": float(self.cy),
            "distortion_model": self.distortion_model,
            "distortion_coeffs": [float(v) for v in self.distortion_coeffs],
        }


@dataclass(slots=True)
class RGBDObservation:
    observation_id: str
    timestamp_ns: int
    source_backend: str
    width: int
    height: int
    camera_frame_id: str
    target_frame_id: str
    intrinsics: CameraIntrinsics
    extrinsic_camera_to_target: list[list[float]]
    rgb_encoding: str = "rgb8"
    depth_encoding: str = "32fc1_m"
    rgb_path: str | None = None
    depth_path: str | None = None
    calibration_version: str = "unknown"
    sensor_model: str = "unknown"
    scene_context: dict[str, Any] = field(default_factory=dict)
    schema_name: str = "RGBDObservation"
    schema_version: str = "v1"

    @classmethod
    def create(
        cls,
        *,
        source_backend: str,
        width: int,
        height: int,
        camera_frame_id: str,
        target_frame_id: str,
        intrinsics: CameraIntrinsics | dict[str, Any],
        extrinsic_camera_to_target: np.ndarray | list[list[float]],
        rgb_encoding: str = "rgb8",
        depth_encoding: str = "32fc1_m",
        rgb_path: str | None = None,
        depth_path: str | None = None,
        calibration_version: str = "unknown",
        sensor_model: str = "unknown",
        scene_context: dict[str, Any] | None = None,
        timestamp_ns: int | None = None,
    ) -> "RGBDObservation":
        intrinsics_obj = (
            intrinsics if isinstance(intrinsics, CameraIntrinsics) else CameraIntrinsics.from_dict(intrinsics)
        )
        transform = np.asarray(extrinsic_camera_to_target, dtype=np.float64)
        if transform.shape != (4, 4):
            raise ValueError("extrinsic_camera_to_target must be 4x4")
        return cls(
            observation_id=_uuid(),
            timestamp_ns=int(timestamp_ns or time.time_ns()),
            source_backend=source_backend,
            width=int(width),
            height=int(height),
            camera_frame_id=camera_frame_id,
            target_frame_id=target_frame_id,
            intrinsics=intrinsics_obj,
            extrinsic_camera_to_target=transform.astype(float).tolist(),
            rgb_encoding=rgb_encoding,
            depth_encoding=depth_encoding,
            rgb_path=rgb_path,
            depth_path=depth_path,
            calibration_version=calibration_version,
            sensor_model=sensor_model,
            scene_context=dict(scene_context or {}),
        )

    def intrinsics_dict(self) -> dict[str, Any]:
        return self.intrinsics.to_dict()

    def extrinsic_matrix(self) -> np.ndarray:
        transform = np.asarray(self.extrinsic_camera_to_target, dtype=np.float64)
        if transform.shape != (4, 4):
            raise ValueError("extrinsic_camera_to_target must be 4x4")
        return transform
