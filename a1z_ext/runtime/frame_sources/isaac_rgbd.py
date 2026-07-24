"""Isaac D405 frame source for the non-grasping pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from typing import Any, Callable

import numpy as np

from a1z_ext.interfaces.observation import RGBDObservation
from a1z_ext.robots.get_robot import get_a1z_isaacsim_robot
from a1z_ext.runtime.d405 import attach_d405_wrist_camera
from a1z_ext.runtime.d405.pose import camera_to_target_matrix_from_usd
from a1z_ext.runtime.frame_sources.base import FrameSource, RGBDFrameCapture


ProgressCallback = Callable[[str, dict[str, object] | None], None]


@dataclass(slots=True)
class IsaacD405FrameSourceConfig:
    root_dir: str
    stage_path: str
    reuse_existing_stage: bool = False
    width: int = 1280
    height: int = 720
    warmup_frames: int = 30
    capture_frames: int = 8
    post_camera_warmup_frames: int = 45
    control_freq_hz: int = 60
    with_gripper: bool = True
    articulation_root_prim: str | None = None
    camera_frame_id: str = "d405_color_optical_frame"
    target_frame_id: str = "robot_base_frame"
    source_backend: str = "isaacsim_d405"
    calibration_version: str = "isaac_d405_runtime_v1"
    sensor_model: str = "simulated_realsense_d405"


class IsaacD405FrameSource(FrameSource):
    """Capture a single RGB-D frame from the project D405 Isaac runtime asset."""

    def __init__(
        self,
        *,
        simulation_app: Any,
        config: IsaacD405FrameSourceConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self._simulation_app = simulation_app
        self._config = config
        self._progress_callback = progress_callback
        self._stage = None
        self._attachment = None
        self._color_camera = None
        self._color_path = ""
        self._depth_path = ""
        self._opened = False
        self._robot = None

    def _progress(self, step: str, extra: dict[str, object] | None = None) -> None:
        if self._progress_callback is not None:
            self._progress_callback(step, extra)

    async def _step_app_async(self, frames: int) -> None:
        for _ in range(max(0, int(frames))):
            await self._simulation_app.next_update_async()

    def _step_app(self, frames: int) -> None:
        for _ in range(max(0, int(frames))):
            self._simulation_app.update()

    async def _wait_updates(self, frames: int) -> None:
        if asyncio.get_running_loop().is_running():
            await self._step_app_async(frames)
            return
        self._step_app(frames)

    def _open_stage(self):
        import omni.usd

        usd_context = omni.usd.get_context()
        usd_context.open_stage(self._config.stage_path)
        self._step_app(20)
        stage = usd_context.get_stage()
        if stage is None:
            raise RuntimeError(f"Failed to open stage: {self._config.stage_path}")
        return stage

    async def _open_stage_async(self):
        import omni.usd

        usd_context = omni.usd.get_context()
        success, error = await usd_context.open_stage_async(self._config.stage_path)
        if not success:
            raise RuntimeError(f"Failed to open stage: {self._config.stage_path}: {error}")
        await self._step_app_async(20)
        stage = usd_context.get_stage()
        if stage is None:
            raise RuntimeError(f"Failed to open stage: {self._config.stage_path}")
        return stage

    def _get_current_stage(self):
        import omni.usd

        usd_context = omni.usd.get_context()
        max_wait_frames = max(180, int(self._config.warmup_frames) * 12)
        last_identifier = ""
        for _ in range(max_wait_frames):
            stage = usd_context.get_stage()
            if stage is not None:
                root_layer = stage.GetRootLayer()
                identifier = str(getattr(root_layer, "realPath", "") or root_layer.identifier)
                last_identifier = identifier
                if not self._config.stage_path or self._config.stage_path in identifier:
                    return stage
            self._simulation_app.update()
        raise TimeoutError(
            "Timed out waiting for current Isaac stage to match requested world: "
            f"requested={self._config.stage_path} current={last_identifier or '<none>'}"
        )

    async def _get_current_stage_async(self):
        import omni.usd

        usd_context = omni.usd.get_context()
        max_wait_frames = max(180, int(self._config.warmup_frames) * 12)
        last_identifier = ""
        for _ in range(max_wait_frames):
            stage = usd_context.get_stage()
            if stage is not None:
                root_layer = stage.GetRootLayer()
                identifier = str(getattr(root_layer, "realPath", "") or root_layer.identifier)
                last_identifier = identifier
                if not self._config.stage_path or self._config.stage_path in identifier:
                    return stage
            await self._step_app_async(1)
        raise TimeoutError(
            "Timed out waiting for current Isaac stage to match requested world: "
            f"requested={self._config.stage_path} current={last_identifier or '<none>'}"
        )

    def _camera_from_prim(self, prim_path: str):
        from isaacsim.sensors.camera import Camera

        camera = Camera(
            prim_path=prim_path,
            resolution=(int(self._config.width), int(self._config.height)),
        )
        self._progress("camera_object_created", {"camera_prim_path": prim_path})
        camera.initialize(attach_rgb_annotator=True)
        self._progress("camera_rgb_initialized", {"camera_prim_path": prim_path})
        camera.add_distance_to_image_plane_to_frame()
        self._progress("camera_depth_annotator_attached", {"camera_prim_path": prim_path})
        return camera

    def _extract_intrinsics(self, camera) -> dict[str, float]:
        intrinsics = np.asarray(camera.get_intrinsics_matrix(), dtype=np.float64)
        return {
            "fx": float(intrinsics[0, 0]),
            "fy": float(intrinsics[1, 1]),
            "cx": float(intrinsics[0, 2]),
            "cy": float(intrinsics[1, 2]),
        }

    def _ensure_robot_ready(self) -> None:
        if self._robot is None:
            self._robot = get_a1z_isaacsim_robot(
                control_freq_hz=int(self._config.control_freq_hz),
                with_gripper=bool(self._config.with_gripper),
                articulation_root_prim=self._config.articulation_root_prim,
                zero_gravity_mode=False,
            )
            self._robot.start()
        self._robot.process_pending()
        if self._attachment is not None:
            self._attachment.update(self._robot.get_joint_state()["pos"])

    async def _ensure_robot_ready_async(self) -> None:
        if self._robot is None:
            self._robot = get_a1z_isaacsim_robot(
                control_freq_hz=int(self._config.control_freq_hz),
                with_gripper=bool(self._config.with_gripper),
                articulation_root_prim=self._config.articulation_root_prim,
                zero_gravity_mode=False,
            )
            self._robot.start()
            await self._step_app_async(2)
        self._robot.process_pending()
        if self._attachment is not None:
            self._attachment.update(self._robot.get_joint_state()["pos"])
        await self._step_app_async(2)

    def open(self) -> None:
        if self._opened:
            return

        self._progress("extension_enabled")

        if self._config.reuse_existing_stage:
            self._progress("stage_reuse_start", {"stage_path": self._config.stage_path})
            self._stage = self._get_current_stage()
            self._progress("stage_reused")
        else:
            self._progress("stage_open_start", {"stage_path": self._config.stage_path})
            self._stage = self._open_stage()
            self._progress("stage_opened")
        self._step_app(self._config.warmup_frames)
        self._progress("stage_warmup_done")

        self._attachment = attach_d405_wrist_camera(self._stage)
        if self._attachment is None:
            raise RuntimeError("D405 attachment was not created")
        self._progress("d405_attached", {"camera_paths": self._attachment.camera_paths})
        self._color_path = str(self._attachment.camera_paths.get("color") or "")
        self._depth_path = str(self._attachment.camera_paths.get("depth") or "")
        if not self._color_path:
            raise RuntimeError(f"Missing D405 camera prims: {self._attachment.camera_paths}")

        from isaacsim.core.api import World

        self._progress("world_create_start")
        world = World(stage_units_in_meters=1.0)
        self._progress("world_created")
        self._progress("world_reset_start")
        world.reset()
        self._step_app(5)
        self._progress("world_ready")
        self._progress("robot_ready_start")
        self._ensure_robot_ready()
        self._progress("robot_ready")

        self._progress("color_camera_init_start")
        self._color_camera = self._camera_from_prim(self._color_path)
        self._progress("color_camera_init_done")
        # Use the color camera render product for both RGB and distance-to-image-plane depth.
        self._progress("depth_camera_shared_with_color", {"depth_camera_path": self._depth_path or self._color_path})
        self._progress("post_camera_warmup_start", {"frames": int(self._config.post_camera_warmup_frames)})
        self._step_app(int(self._config.post_camera_warmup_frames))
        self._progress("post_camera_warmup_done")
        self._progress(
            "cameras_initialized",
            {
                "color_camera_path": self._color_path,
                "depth_camera_path": self._depth_path or self._color_path,
                "resolution": [int(self._config.width), int(self._config.height)],
            },
        )
        self._opened = True

    async def open_async(self) -> None:
        if self._opened:
            return

        self._progress("extension_enabled")

        if self._config.reuse_existing_stage:
            self._progress("stage_reuse_start", {"stage_path": self._config.stage_path})
            self._stage = await self._get_current_stage_async()
            self._progress("stage_reused")
        else:
            self._progress("stage_open_start", {"stage_path": self._config.stage_path})
            self._stage = await self._open_stage_async()
            self._progress("stage_opened")
        await self._step_app_async(self._config.warmup_frames)
        self._progress("stage_warmup_done")

        self._attachment = attach_d405_wrist_camera(self._stage)
        if self._attachment is None:
            raise RuntimeError("D405 attachment was not created")
        self._progress("d405_attached", {"camera_paths": self._attachment.camera_paths})
        self._color_path = str(self._attachment.camera_paths.get("color") or "")
        self._depth_path = str(self._attachment.camera_paths.get("depth") or "")
        if not self._color_path:
            raise RuntimeError(f"Missing D405 camera prims: {self._attachment.camera_paths}")

        from isaacsim.core.api import World

        self._progress("world_create_start")
        world = World(stage_units_in_meters=1.0)
        self._progress("world_created")
        self._progress("world_reset_start")
        world.reset()
        await self._step_app_async(5)
        self._progress("world_ready")
        self._progress("robot_ready_start")
        await self._ensure_robot_ready_async()
        self._progress("robot_ready")

        self._progress("color_camera_init_start")
        self._color_camera = self._camera_from_prim(self._color_path)
        self._progress("color_camera_init_done")
        # Use the color camera render product for both RGB and distance-to-image-plane depth.
        self._progress("depth_camera_shared_with_color", {"depth_camera_path": self._depth_path or self._color_path})
        self._progress("post_camera_warmup_start", {"frames": int(self._config.post_camera_warmup_frames)})
        await self._step_app_async(int(self._config.post_camera_warmup_frames))
        self._progress("post_camera_warmup_done")
        self._progress(
            "cameras_initialized",
            {
                "color_camera_path": self._color_path,
                "depth_camera_path": self._depth_path or self._color_path,
                "resolution": [int(self._config.width), int(self._config.height)],
            },
        )
        self._opened = True

    def capture(self) -> RGBDFrameCapture:
        if not self._opened:
            self.open()

        if self._color_camera is None:
            raise RuntimeError("Isaac color camera is not initialized")

        rgb = None
        depth_m = None
        max_attempts = max(60, int(self._config.capture_frames) * 30)
        for attempt in range(max_attempts):
            self._ensure_robot_ready()
            self._step_app(1)
            rgb_frame = self._color_camera.get_rgb()
            depth_frame = self._color_camera.get_depth()
            if rgb_frame is not None and depth_frame is not None:
                rgb = np.asarray(rgb_frame, dtype=np.uint8)
                depth_m = np.asarray(depth_frame, dtype=np.float64)
                if depth_m.ndim == 3 and depth_m.shape[2] == 1:
                    depth_m = depth_m[:, :, 0]
                if rgb.size > 0 and depth_m.size > 0:
                    self._progress(
                        "capture_ready",
                        {
                            "attempt": attempt + 1,
                            "rgb_shape": list(rgb.shape),
                            "depth_shape": list(depth_m.shape),
                        },
                    )
                    break

        if rgb is None or depth_m is None:
            raise RuntimeError("Isaac cameras did not produce RGB-D frames within the capture window")
        if rgb.size == 0:
            raise RuntimeError("Isaac color camera returned empty RGB frame")
        if depth_m.size == 0:
            raise RuntimeError("Isaac depth camera returned empty depth frame")

        observation = RGBDObservation.create(
            source_backend=self._config.source_backend,
            width=int(rgb.shape[1]),
            height=int(rgb.shape[0]),
            camera_frame_id=self._config.camera_frame_id,
            target_frame_id=self._config.target_frame_id,
            intrinsics=self._extract_intrinsics(self._color_camera),
            extrinsic_camera_to_target=camera_to_target_matrix_from_usd(
                camera_prim_path=self._color_path,
                target_frame_id=self._config.target_frame_id,
                joint_pos_rad=np.asarray(self._robot.get_joint_state()["pos"], dtype=np.float64),
            ),
            calibration_version=self._config.calibration_version,
            sensor_model=self._config.sensor_model,
            scene_context={"stage_path": self._config.stage_path},
        )
        capture = RGBDFrameCapture(
            observation=observation,
            rgb=rgb,
            depth_m=depth_m,
            source_info={
                "source_backend": self._config.source_backend,
                "camera_frame_id": self._config.camera_frame_id,
                "target_frame_id": self._config.target_frame_id,
                "stage_path": self._config.stage_path,
                "color_camera_path": self._color_path,
                "depth_camera_path": self._depth_path or self._color_path,
                "render_product_path": self._color_camera.get_render_product_path(),
                "depth_render_product_path": self._color_camera.get_render_product_path(),
            },
        )
        capture.validate()
        return capture

    async def capture_async(self) -> RGBDFrameCapture:
        if not self._opened:
            await self.open_async()

        if self._color_camera is None:
            raise RuntimeError("Isaac color camera is not initialized")

        rgb = None
        depth_m = None
        max_attempts = max(60, int(self._config.capture_frames) * 30)
        for attempt in range(max_attempts):
            await self._ensure_robot_ready_async()
            await self._step_app_async(1)
            rgb_frame = self._color_camera.get_rgb()
            depth_frame = self._color_camera.get_depth()
            if rgb_frame is not None and depth_frame is not None:
                rgb = np.asarray(rgb_frame, dtype=np.uint8)
                depth_m = np.asarray(depth_frame, dtype=np.float64)
                if depth_m.ndim == 3 and depth_m.shape[2] == 1:
                    depth_m = depth_m[:, :, 0]
                if rgb.size > 0 and depth_m.size > 0:
                    self._progress(
                        "capture_ready",
                        {
                            "attempt": attempt + 1,
                            "rgb_shape": list(rgb.shape),
                            "depth_shape": list(depth_m.shape),
                        },
                    )
                    break

        if rgb is None or depth_m is None:
            raise RuntimeError("Isaac cameras did not produce RGB-D frames within the capture window")
        if rgb.size == 0:
            raise RuntimeError("Isaac color camera returned empty RGB frame")
        if depth_m.size == 0:
            raise RuntimeError("Isaac depth camera returned empty depth frame")

        observation = RGBDObservation.create(
            source_backend=self._config.source_backend,
            width=int(rgb.shape[1]),
            height=int(rgb.shape[0]),
            camera_frame_id=self._config.camera_frame_id,
            target_frame_id=self._config.target_frame_id,
            intrinsics=self._extract_intrinsics(self._color_camera),
            extrinsic_camera_to_target=camera_to_target_matrix_from_usd(
                camera_prim_path=self._color_path,
                target_frame_id=self._config.target_frame_id,
                joint_pos_rad=np.asarray(self._robot.get_joint_state()["pos"], dtype=np.float64),
            ),
            calibration_version=self._config.calibration_version,
            sensor_model=self._config.sensor_model,
            scene_context={"stage_path": self._config.stage_path},
        )
        capture = RGBDFrameCapture(
            observation=observation,
            rgb=rgb,
            depth_m=depth_m,
            source_info={
                "source_backend": self._config.source_backend,
                "camera_frame_id": self._config.camera_frame_id,
                "target_frame_id": self._config.target_frame_id,
                "stage_path": self._config.stage_path,
                "color_camera_path": self._color_path,
                "depth_camera_path": self._depth_path or self._color_path,
                "render_product_path": self._color_camera.get_render_product_path(),
                "depth_render_product_path": self._color_camera.get_render_product_path(),
            },
        )
        capture.validate()
        return capture

    def health(self) -> dict[str, Any]:
        return {
            "ready": self._opened,
            "stage_path": self._config.stage_path,
            "color_camera_path": self._color_path,
            "depth_camera_path": self._depth_path,
        }

    def close(self) -> None:
        if self._robot is not None:
            try:
                self._robot.stop()
            finally:
                self._robot = None
        if self._color_camera is not None:
            try:
                self._color_camera.destroy()
            finally:
                self._color_camera = None
        self._opened = False
