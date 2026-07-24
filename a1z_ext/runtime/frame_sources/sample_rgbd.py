"""Sample RGB-D frame source for the non-grasping pipeline skeleton."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from a1z_ext.interfaces.observation import RGBDObservation
from a1z_ext.runtime.frame_sources.base import FrameSource, RGBDFrameCapture


@dataclass(slots=True)
class SampleRGBDFrameSource(FrameSource):
    width: int = 640
    height: int = 480
    camera_frame_id: str = "camera_color_frame"
    target_frame_id: str = "robot_base_frame"

    def _sample_intrinsics(self) -> dict[str, float]:
        return {
            "fx": 620.0,
            "fy": 620.0,
            "cx": float(self.width) / 2.0,
            "cy": float(self.height) / 2.0,
        }

    def _sample_extrinsic(self) -> np.ndarray:
        transform = np.eye(4, dtype=np.float64)
        transform[:3, 3] = np.array([0.32, 0.0, 0.42], dtype=np.float64)
        return transform

    def _sample_depth(self) -> np.ndarray:
        depth = np.full((self.height, self.width), 0.72, dtype=np.float64)
        center_y = self.height // 2
        center_x = self.width // 2
        depth[
            center_y - self.height // 10 : center_y + self.height // 10,
            center_x - self.width // 10 : center_x + self.width // 10,
        ] = 0.48
        return depth

    def capture(self) -> RGBDFrameCapture:
        rgb = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        rgb[:, :, 0] = 64
        rgb[:, :, 1] = 32
        rgb[:, :, 2] = 16

        center_y = self.height // 2
        center_x = self.width // 2
        rgb[
            center_y - self.height // 10 : center_y + self.height // 10,
            center_x - self.width // 10 : center_x + self.width // 10,
            :,
        ] = np.array([180, 30, 30], dtype=np.uint8)

        observation = RGBDObservation.create(
            source_backend="sample",
            width=self.width,
            height=self.height,
            camera_frame_id=self.camera_frame_id,
            target_frame_id=self.target_frame_id,
            intrinsics=self._sample_intrinsics(),
            extrinsic_camera_to_target=self._sample_extrinsic(),
            calibration_version="sample_v1",
            sensor_model="sample_rgbd",
            scene_context={"generator": "sample_rgbd"},
        )
        capture = RGBDFrameCapture(
            observation=observation,
            rgb=rgb,
            depth_m=self._sample_depth(),
            source_info={
                "source_backend": "sample",
                "camera_frame_id": self.camera_frame_id,
                "target_frame_id": self.target_frame_id,
                "generator": "sample_rgbd",
            },
        )
        capture.validate()
        return capture
