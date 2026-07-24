"""Runtime RGB-D capture session for the Isaac-hosted D405 camera."""

from __future__ import annotations

import base64
import copy
from concurrent.futures import Executor, ThreadPoolExecutor
import os
import threading
import time
import zlib
from dataclasses import dataclass
from typing import Any

import numpy as np

from a1z_ext.interfaces.observation import RGBDObservation
from a1z_ext.runtime.d405.pose import camera_to_target_matrix_from_usd
from a1z_ext.runtime.frame_sources.base import RGBDFrameCapture
from a1z_ext.robots.isaac6_backend import configured_isaac_api_profile


@dataclass(slots=True)
class D405CaptureSettings:
    width: int = 320
    height: int = 240
    frequency_hz: int = 10
    annotator_device: str = "cuda"
    warmup_updates: int = 45
    capture_attempts: int = 60
    camera_frame_id: str = "d405_color_optical_frame"
    depth_frame_id: str = "d405_depth_optical_frame"
    target_frame_id: str = "robot_base_frame"
    source_backend: str = "isaacsim_d405"
    calibration_version: str = "isaac_d405_runtime_v1"
    sensor_model: str = "simulated_realsense_d405"
    request_timeout_s: float = 5.0
    annotator_idle_timeout_s: float = 1.0
    zlib_level: int = 1
    encode_workers: int = 2


def _extract_intrinsics(camera) -> dict[str, float]:
    intrinsics = np.asarray(camera.get_intrinsics_matrix(), dtype=np.float64)
    return {
        "fx": float(intrinsics[0, 0]),
        "fy": float(intrinsics[1, 1]),
        "cx": float(intrinsics[0, 2]),
        "cy": float(intrinsics[1, 2]),
    }


def _encode_array(arr: np.ndarray, *, compression_level: int = 1) -> dict[str, Any]:
    compression_level = int(compression_level)
    if not 0 <= compression_level <= 9:
        raise ValueError(f"zlib compression_level must be in [0, 9], got {compression_level}")
    contiguous = np.ascontiguousarray(arr)
    raw_view = memoryview(contiguous).cast("B")
    payload = zlib.compress(raw_view, level=compression_level)
    return {
        "shape": [int(v) for v in contiguous.shape],
        "dtype": str(contiguous.dtype),
        "compression": "zlib",
        "compression_level": compression_level,
        "uncompressed_nbytes": int(contiguous.nbytes),
        "compressed_nbytes": len(payload),
        "data_b64": base64.b64encode(payload).decode("ascii"),
    }


def capture_to_payload(
    capture: RGBDFrameCapture,
    *,
    compression_level: int = 1,
    executor: Executor | None = None,
) -> dict[str, Any]:
    rgb = np.asarray(capture.rgb, dtype=np.uint8)
    depth = np.asarray(capture.depth_m, dtype=np.float32)
    observation = capture.observation
    if executor is None:
        rgb_payload = _encode_array(rgb[:, :, :3], compression_level=compression_level)
        depth_payload = _encode_array(depth, compression_level=compression_level)
    else:
        rgb_future = executor.submit(
            _encode_array,
            rgb[:, :, :3],
            compression_level=compression_level,
        )
        depth_future = executor.submit(
            _encode_array,
            depth,
            compression_level=compression_level,
        )
        rgb_payload = rgb_future.result()
        depth_payload = depth_future.result()
    return {
        "timestamp_ns": int(observation.timestamp_ns),
        "source_backend": observation.source_backend,
        "width": int(observation.width),
        "height": int(observation.height),
        "camera_frame_id": observation.camera_frame_id,
        "depth_frame_id": str(capture.source_info.get("depth_frame_id", observation.camera_frame_id)),
        "target_frame_id": observation.target_frame_id,
        "calibration_version": observation.calibration_version,
        "sensor_model": observation.sensor_model,
        "intrinsics": observation.intrinsics_dict(),
        "extrinsic_camera_to_target": observation.extrinsic_camera_to_target,
        "rgb_encoding": observation.rgb_encoding,
        "depth_encoding": observation.depth_encoding,
        "rgb": rgb_payload,
        "depth": depth_payload,
        "source_info": dict(capture.source_info),
        "scene_context": dict(observation.scene_context),
    }


def _stabilize_camera_local_pose(prim_path: str) -> None:
    try:
        import omni.usd
        from pxr import Gf, UsdGeom
    except Exception:
        return

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return

    identity_matrix = Gf.Matrix4d(1.0)
    xformable = UsdGeom.Xformable(prim)
    for op in xformable.GetOrderedXformOps():
        op_name = op.GetOpName()
        value = op.Get()
        if op_name == "xformOp:translate":
            if isinstance(value, Gf.Vec3d):
                op.Set(Gf.Vec3d(0.0, 0.0, 0.0))
            else:
                op.Set(Gf.Vec3f(0.0, 0.0, 0.0))
        elif op_name == "xformOp:rotateXYZ":
            if isinstance(value, Gf.Vec3d):
                op.Set(Gf.Vec3d(0.0, 0.0, 0.0))
            else:
                op.Set(Gf.Vec3f(0.0, 0.0, 0.0))
        elif op_name == "xformOp:orient":
            if isinstance(value, Gf.Quatd):
                op.Set(Gf.Quatd(1.0, Gf.Vec3d(0.0, 0.0, 0.0)))
            else:
                op.Set(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))
        elif op_name == "xformOp:transform":
            op.Set(identity_matrix)

    fabric_local_matrix = prim.GetAttribute("omni:fabric:localMatrix")
    if fabric_local_matrix.IsValid():
        fabric_local_matrix.Set(identity_matrix)


def _sensor_array_to_numpy(values) -> np.ndarray | None:
    if values is None:
        return None
    numpy_method = getattr(values, "numpy", None)
    if callable(numpy_method):
        device = getattr(values, "device", None)
        if device is not None:
            import warp as wp

            wp.synchronize_device(device)
        return np.array(numpy_method(), copy=True)
    return np.array(values, copy=True)


def _is_transient_camera_warmup_error(exc: BaseException) -> bool:
    message = str(exc)
    return "IHydraTexture::getFrameData" in message


class _Isaac6CameraSensorAdapter:
    """Legacy-shaped facade over Isaac 6 RtxCamera and CameraSensor."""

    def __init__(self, prim_path: str, *, width: int, height: int, frequency_hz: int) -> None:
        import omni.usd
        import warp as wp
        from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path) if stage is not None else None
        if prim is None or not prim.IsValid():
            raise RuntimeError(f"D405 camera prim is unavailable: {prim_path}")
        if "OmniSensorAPI" not in prim.GetAppliedSchemas():
            prim.ApplyAPI("OmniSensorAPI")

        self._prim_path = str(prim_path)
        self._frequency_hz = float(max(1, int(frequency_hz)))
        self._rtx_camera = RtxCamera(
            self._prim_path,
            tick_rate=self._frequency_hz,
            reset_xform_op_properties=False,
        )
        self._sensor = CameraSensor(
            self._rtx_camera,
            resolution=(int(height), int(width)),
            annotators=["rgb", "distance_to_image_plane"],
        )
        self._rgb_out = wp.empty((int(height), int(width), 3), dtype=wp.uint8, device="cuda")
        self._depth_out = wp.empty((int(height), int(width), 1), dtype=wp.float32, device="cuda")
        self._custom_annotators = {
            "rgb": True,
            "distance_to_image_plane": True,
        }

    def get_intrinsics_matrix(self) -> np.ndarray:
        import omni.usd
        from pxr import UsdGeom

        stage = omni.usd.get_context().get_stage()
        camera = UsdGeom.Camera.Get(stage, self._prim_path) if stage is not None else None
        if camera is None or not camera.GetPrim().IsValid():
            raise RuntimeError(f"D405 camera prim is unavailable: {self._prim_path}")
        height, width = self._sensor.resolution
        focal_length = float(camera.GetFocalLengthAttr().Get())
        horizontal_aperture = float(camera.GetHorizontalApertureAttr().Get())
        vertical_aperture = float(camera.GetVerticalApertureAttr().Get())
        horizontal_offset = float(camera.GetHorizontalApertureOffsetAttr().Get() or 0.0)
        vertical_offset = float(camera.GetVerticalApertureOffsetAttr().Get() or 0.0)
        return np.array(
            [
                [
                    focal_length * float(width) / horizontal_aperture,
                    0.0,
                    (float(width) * 0.5) + horizontal_offset * float(width) / horizontal_aperture,
                ],
                [
                    0.0,
                    focal_length * float(height) / vertical_aperture,
                    (float(height) * 0.5) + vertical_offset * float(height) / vertical_aperture,
                ],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

    def _get_data(self, annotator: str, *, out=None) -> np.ndarray | None:
        values, _ = self._sensor.get_data(annotator, out=out)
        return _sensor_array_to_numpy(values)

    def get_rgb(self, device: str = "cpu") -> np.ndarray | None:
        del device
        return self._get_data("rgb", out=self._rgb_out)

    def get_depth(self, device: str = "cpu") -> np.ndarray | None:
        del device
        return self._get_data("distance_to_image_plane", out=self._depth_out)

    def get_rgbd(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Read one stable, completed RGB-D generation from CameraSensor."""

        token_before = self._completed_render_token()
        if token_before is None:
            return None, None
        rgb = self.get_rgb()
        depth = self.get_depth()
        token_after = self._completed_render_token()
        if token_after is None or token_after != token_before:
            # An asynchronous render completed between the two AOV readbacks.
            # Retry on the next Kit update instead of pairing different frames.
            return None, None
        return rgb, depth

    def _completed_render_token(self) -> tuple[object, object] | None:
        render_product = getattr(self._sensor, "_hydra_texture", None)
        hydra_texture = getattr(render_product, "hydra_texture", None)
        if hydra_texture is None:
            return None
        try:
            frame_info = dict(hydra_texture.get_frame_info() or {})
        except RuntimeError as exc:
            if _is_transient_camera_warmup_error(exc):
                return None
            raise
        frame_number = frame_info.get("frame_number")
        swh_frame_number = frame_info.get("swh_frame_number")
        if frame_number is None and swh_frame_number is None:
            return None
        return frame_number, swh_frame_number

    def get_current_frame(self, clone: bool = False) -> dict[str, object]:
        del clone
        token = self._completed_render_token()
        frame_number, swh_frame_number = token if token is not None else (None, None)
        return {
            "rendering_frame": frame_number,
            "rendering_time": swh_frame_number,
        }

    def attach_annotator(self, annotator_name: str) -> None:
        name = str(annotator_name)
        if name not in self._custom_annotators:
            self._sensor.attach_annotators(name)
            self._custom_annotators[name] = True

    def detach_annotator(self, annotator_name: str) -> None:
        name = str(annotator_name)
        if name in self._custom_annotators:
            self._sensor.detach_annotators(name)
            self._custom_annotators.pop(name, None)

    def add_distance_to_image_plane_to_frame(self) -> None:
        self.attach_annotator("distance_to_image_plane")

    def remove_distance_to_image_plane_from_frame(self) -> None:
        self.detach_annotator("distance_to_image_plane")

    def get_render_product_path(self) -> str:
        # CameraSensor creates its render product asynchronously.  Its public
        # property currently dereferences an internal ``None`` during the
        # first Kit updates, so health probes must tolerate the warm-up state.
        try:
            render_product = self._sensor.render_product
        except (AttributeError, RuntimeError):
            return ""
        if render_product is None:
            return ""
        get_path = getattr(render_product, "GetPath", None)
        if not callable(get_path):
            return ""
        return str(get_path())

    def close(self) -> None:
        self._sensor._invalidate_sensor()
        self._custom_annotators.clear()


class _Isaac6SharedViewportCameraAdapter:
    """Capture D405 frames from a caller-owned viewport render product.

    Production passes a hidden D405-only viewport here. This keeps StreamSDK's
    primary viewport/frame context untouched while still using Kit's proven
    viewport render path. The hidden viewport owns its own Hydra tick rate.
    """

    def __init__(
        self,
        prim_path: str,
        *,
        width: int,
        height: int,
        frequency_hz: int,
        viewport,
    ) -> None:
        import omni.replicator.core as rep
        import omni.usd

        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path) if stage is not None else None
        if prim is None or not prim.IsValid():
            raise RuntimeError(f"D405 camera prim is unavailable: {prim_path}")
        if "OmniSensorAPI" not in prim.GetAppliedSchemas():
            prim.ApplyAPI("OmniSensorAPI")
        tick_rate_attr = prim.GetAttribute("omni:sensor:tickRate")
        if not tick_rate_attr.IsValid():
            raise RuntimeError(f"D405 camera does not expose omni:sensor:tickRate: {prim_path}")
        tick_rate_attr.Set(float(max(1, int(frequency_hz))))
        render_product_path = self._viewport_render_product_path(viewport)
        if not render_product_path:
            raise RuntimeError("The active WebRTC viewport has no render product path.")

        self._prim_path = str(prim_path)
        self._width = int(width)
        self._height = int(height)
        self._frequency_hz = float(max(1, int(frequency_hz)))
        self._viewport = viewport
        self._render_product_path = render_product_path
        self._restore_camera_path: str | None = str(getattr(viewport, "camera_path", "") or "")
        self._capture_active = False
        self._continuous_camera = os.environ.get(
            "A1Z_D405_SHARED_VIEWPORT_CONTINUOUS",
            "1",
        ).strip().lower() not in {"0", "false", "no", "off", ""}
        self._rgb_annotator = rep.AnnotatorRegistry.get_annotator(
            "rgb",
            device="cuda",
            do_array_copy=True,
        )
        self._depth_annotator = rep.AnnotatorRegistry.get_annotator(
            "distance_to_image_plane",
            device="cpu",
            do_array_copy=True,
        )
        self._rgb_annotator.attach(self._render_product_path)
        self._depth_annotator.attach(self._render_product_path)
        self._custom_annotators = {
            "rgb": True,
            "distance_to_image_plane": True,
        }
        if self._continuous_camera:
            self._viewport.set_active_camera(self._prim_path)

    @staticmethod
    def _viewport_render_product_path(viewport) -> str:
        getter = getattr(viewport, "get_render_product_path", None)
        if callable(getter):
            try:
                path = str(getter() or "")
                if path:
                    return path
            except Exception:
                pass
        return str(getattr(viewport, "render_product_path", "") or "")

    def get_intrinsics_matrix(self) -> np.ndarray:
        import omni.usd
        from pxr import UsdGeom

        stage = omni.usd.get_context().get_stage()
        camera = UsdGeom.Camera.Get(stage, self._prim_path) if stage is not None else None
        if camera is None or not camera.GetPrim().IsValid():
            raise RuntimeError(f"D405 camera prim is unavailable: {self._prim_path}")
        focal_length = float(camera.GetFocalLengthAttr().Get())
        horizontal_aperture = float(camera.GetHorizontalApertureAttr().Get())
        vertical_aperture = float(camera.GetVerticalApertureAttr().Get())
        horizontal_offset = float(camera.GetHorizontalApertureOffsetAttr().Get() or 0.0)
        vertical_offset = float(camera.GetVerticalApertureOffsetAttr().Get() or 0.0)
        return np.array(
            [
                [
                    focal_length * float(self._width) / horizontal_aperture,
                    0.0,
                    (float(self._width) * 0.5)
                    + horizontal_offset * float(self._width) / horizontal_aperture,
                ],
                [
                    0.0,
                    focal_length * float(self._height) / vertical_aperture,
                    (float(self._height) * 0.5)
                    + vertical_offset * float(self._height) / vertical_aperture,
                ],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

    def _resize_to_capture(self, values: np.ndarray) -> np.ndarray:
        if values.ndim < 2:
            raise RuntimeError(f"D405 viewport annotator returned invalid shape: {values.shape}")
        source_height, source_width = values.shape[:2]
        if source_height == self._height and source_width == self._width:
            return values
        if source_height < 1 or source_width < 1:
            raise RuntimeError(f"D405 viewport annotator returned empty shape: {values.shape}")
        rows = np.minimum(
            (np.arange(self._height, dtype=np.int64) * source_height) // self._height,
            source_height - 1,
        )
        columns = np.minimum(
            (np.arange(self._width, dtype=np.int64) * source_width) // self._width,
            source_width - 1,
        )
        return values[rows[:, None], columns[None, :]]

    @staticmethod
    def _annotator_data(annotator) -> np.ndarray | None:
        values = annotator.get_data(device="cpu")
        if isinstance(values, dict):
            values = values.get("data")
        if values is None:
            return None
        return np.asarray(values)

    def get_rgb(self, device: str = "cpu") -> np.ndarray | None:
        del device
        values = self._annotator_data(self._rgb_annotator)
        if values is None:
            return None
        return self._resize_to_capture(values)

    def get_depth(self, device: str = "cpu") -> np.ndarray | None:
        del device
        values = self._annotator_data(self._depth_annotator)
        if values is None:
            return None
        values = self._resize_to_capture(np.asarray(values, dtype=np.float32))
        if values.ndim == 2:
            values = values[:, :, None]
        return values

    def get_current_frame(self, clone: bool = False) -> dict[str, object]:
        del clone
        frame_info = dict(getattr(self._viewport, "frame_info", {}) or {})
        frame_index = frame_info.get("frame_number")
        if frame_index is None:
            frame_index = frame_info.get("swh_frame_number")
        return {
            "rendering_frame": frame_index,
            "rendering_time": frame_info.get("reference_time"),
        }

    def begin_capture(self) -> None:
        if self._continuous_camera:
            if str(getattr(self._viewport, "camera_path", "") or "") != self._prim_path:
                self._viewport.set_active_camera(self._prim_path)
            return
        if self._capture_active:
            return
        self._restore_camera_path = str(getattr(self._viewport, "camera_path", "") or "")
        self._viewport.set_active_camera(self._prim_path)
        self._capture_active = True

    def end_capture(self) -> None:
        if self._continuous_camera:
            return
        if not self._capture_active:
            return
        restore_path = self._restore_camera_path
        self._restore_camera_path = None
        self._capture_active = False
        if restore_path and restore_path != self._prim_path:
            self._viewport.set_active_camera(restore_path)

    def attach_annotator(self, annotator_name: str) -> None:
        # The shared annotators remain attached for the lifetime of the stream.
        if str(annotator_name) not in self._custom_annotators:
            raise RuntimeError(f"Unsupported shared viewport annotator: {annotator_name}")

    def detach_annotator(self, annotator_name: str) -> None:
        # Detaching and rebuilding annotator graphs while StreamSDK is encoding
        # is itself disruptive. They are detached only by close().
        del annotator_name

    def add_distance_to_image_plane_to_frame(self) -> None:
        self.attach_annotator("distance_to_image_plane")

    def remove_distance_to_image_plane_from_frame(self) -> None:
        return None

    def get_render_product_path(self) -> str:
        return self._render_product_path

    def close(self) -> None:
        if self._continuous_camera:
            restore_path = self._restore_camera_path
            if restore_path and restore_path != self._prim_path:
                self._viewport.set_active_camera(restore_path)
        else:
            self.end_capture()
        if self._rgb_annotator is not None:
            self._rgb_annotator.detach([self._render_product_path])
            self._rgb_annotator = None
        if self._depth_annotator is not None:
            self._depth_annotator.detach([self._render_product_path])
            self._depth_annotator = None
        self._custom_annotators.clear()


class D405FrameSession:
    def __init__(
        self,
        *,
        attachment,
        color_camera_path: str,
        depth_camera_path: str | None = None,
        settings: D405CaptureSettings | None = None,
        stage_path: str = "",
        shared_viewport=None,
    ) -> None:
        self._attachment = attachment
        self._color_camera_path = color_camera_path
        self._depth_camera_path = depth_camera_path or color_camera_path
        self._settings = settings or D405CaptureSettings()
        if not 0 <= int(self._settings.zlib_level) <= 9:
            raise ValueError("D405 zlib_level must be in [0, 9].")
        if int(self._settings.encode_workers) < 0:
            raise ValueError("D405 encode_workers must be non-negative.")
        if float(self._settings.annotator_idle_timeout_s) < 0.0:
            raise ValueError("D405 annotator_idle_timeout_s must be non-negative.")
        self._stage_path = stage_path
        self._shared_viewport = shared_viewport
        self._latest_lock = threading.Lock()
        self._capture_condition = threading.Condition(self._latest_lock)
        self._latest_capture: RGBDFrameCapture | None = None
        self._capture_generation = 0
        self._capture_requested = False
        self._capture_armed = False
        self._capture_armed_render_token = None
        self._capture_last_render_token = None
        self._capture_render_changes_since_arm = 0
        self._closed = False
        self._last_error: str | None = None
        self._update_failure_count = 0
        self._update_count = 0
        self._render_token_change_count = 0
        self._last_render_token = None
        self._capture_timeout_count = 0
        self._annotators_attached = True
        self._annotator_attach_count = 1
        self._annotator_detach_count = 0
        self._last_request_monotonic = time.monotonic()
        self._last_capture_monotonic: float | None = None
        self._payload_executor: ThreadPoolExecutor | None = None
        self._last_payload_encode_ms: float | None = None
        self._last_payload_b64_bytes = 0
        self._camera_prim_paths = tuple(dict.fromkeys((self._color_camera_path, self._depth_camera_path)))
        self._camera = self._camera_from_prim(color_camera_path)
        self._continuous_capture = bool(
            configured_isaac_api_profile() == "native_6_0"
            and isinstance(
                self._camera,
                (_Isaac6CameraSensorAdapter, _Isaac6SharedViewportCameraAdapter),
            )
        )
        self._continuous_render_token = None
        if int(self._settings.encode_workers) > 1:
            self._payload_executor = ThreadPoolExecutor(
                max_workers=int(self._settings.encode_workers),
                thread_name_prefix="d405_payload",
            )
        self._stabilize_all_camera_local_poses()
        self._warmup_complete = False

    def _camera_from_prim(self, prim_path: str):
        if configured_isaac_api_profile() == "native_6_0":
            render_product_mode = os.environ.get(
                "A1Z_D405_RENDER_PRODUCT_MODE", "dedicated"
            ).strip().lower()
            if render_product_mode not in {"auto", "dedicated", "shared_viewport"}:
                raise ValueError(
                    "A1Z_D405_RENDER_PRODUCT_MODE must be auto, dedicated, or shared_viewport."
                )
            if self._shared_viewport is not None and render_product_mode != "dedicated":
                camera = _Isaac6SharedViewportCameraAdapter(
                    prim_path,
                    width=int(self._settings.width),
                    height=int(self._settings.height),
                    frequency_hz=max(1, int(self._settings.frequency_hz)),
                    viewport=self._shared_viewport,
                )
                _stabilize_camera_local_pose(prim_path)
                return camera
            if render_product_mode == "shared_viewport":
                raise RuntimeError("D405 shared_viewport mode requires an active streaming viewport.")
            camera = _Isaac6CameraSensorAdapter(
                prim_path,
                width=int(self._settings.width),
                height=int(self._settings.height),
                frequency_hz=max(1, int(self._settings.frequency_hz)),
            )
            _stabilize_camera_local_pose(prim_path)
            return camera

        from isaacsim.sensors.camera import Camera

        camera = Camera(
            prim_path=prim_path,
            frequency=max(1, int(self._settings.frequency_hz)),
            resolution=(int(self._settings.width), int(self._settings.height)),
            annotator_device=self._settings.annotator_device,
        )
        camera.initialize(attach_rgb_annotator=True)
        camera.add_distance_to_image_plane_to_frame()
        _stabilize_camera_local_pose(prim_path)
        return camera

    def _attach_capture_annotators(self) -> None:
        if self._annotators_attached:
            return
        custom_annotators = getattr(self._camera, "_custom_annotators", {})
        if "rgb" not in custom_annotators:
            self._camera.attach_annotator(annotator_name="rgb")
        if "distance_to_image_plane" not in custom_annotators:
            self._camera.add_distance_to_image_plane_to_frame()
        self._annotators_attached = True
        self._annotator_attach_count += 1

    def _detach_capture_annotators(self) -> None:
        if not self._annotators_attached:
            return
        custom_annotators = getattr(self._camera, "_custom_annotators", {})
        if "rgb" in custom_annotators:
            self._camera.detach_annotator("rgb")
        if "distance_to_image_plane" in custom_annotators:
            self._camera.remove_distance_to_image_plane_from_frame()
        self._annotators_attached = False
        self._annotator_detach_count += 1

    def _current_render_token(self):
        current_frame = self._camera.get_current_frame(clone=False)
        rendering_frame = current_frame.get("rendering_frame")
        rendering_time = current_frame.get("rendering_time")
        return repr(rendering_frame), repr(rendering_time)

    def _stabilize_all_camera_local_poses(self) -> None:
        for prim_path in self._camera_prim_paths:
            _stabilize_camera_local_pose(prim_path)

    def _capture_once(self, joint_pos, *, update_attachment: bool = True) -> bool:
        if update_attachment and self._attachment is not None:
            self._attachment.update(joint_pos)

        get_rgbd = getattr(self._camera, "get_rgbd", None)
        if callable(get_rgbd):
            rgb_frame, depth_frame = get_rgbd()
        else:
            rgb_frame = self._camera.get_rgb(device="cpu")
            depth_frame = self._camera.get_depth(device="cpu")
        if rgb_frame is None or depth_frame is None:
            return False

        rgb = np.asarray(rgb_frame, dtype=np.uint8)
        if rgb.ndim == 3 and rgb.shape[2] > 3:
            rgb = rgb[:, :, :3]
        depth = np.asarray(depth_frame, dtype=np.float32)
        if depth.ndim == 3 and depth.shape[2] == 1:
            depth = depth[:, :, 0]
        if rgb.size == 0 or depth.size == 0:
            return False
        finite_depth = depth[np.isfinite(depth)]
        if finite_depth.size and np.any(finite_depth < 0.0):
            # The CUDA annotator buffer can be observed between RTX production
            # and completion. Negative distance is never a valid D405 return;
            # leave the request armed and retry after a later render update.
            return False

        observation = RGBDObservation.create(
            source_backend=self._settings.source_backend,
            width=int(rgb.shape[1]),
            height=int(rgb.shape[0]),
            camera_frame_id=self._settings.camera_frame_id,
            target_frame_id=self._settings.target_frame_id,
            intrinsics=_extract_intrinsics(self._camera),
            extrinsic_camera_to_target=camera_to_target_matrix_from_usd(
                camera_prim_path=self._color_camera_path,
                target_frame_id=self._settings.target_frame_id,
                joint_pos_rad=np.asarray(joint_pos, dtype=np.float64),
            ),
            calibration_version=self._settings.calibration_version,
            sensor_model=self._settings.sensor_model,
            scene_context={
                "stage_path": self._stage_path,
                "color_camera_path": self._color_camera_path,
                "depth_camera_path": self._depth_camera_path,
                "render_product_path": self._camera.get_render_product_path(),
            },
        )
        capture = RGBDFrameCapture(
            observation=observation,
            rgb=rgb,
            depth_m=depth,
            source_info={
                "source_backend": observation.source_backend,
                "camera_frame_id": observation.camera_frame_id,
                "depth_frame_id": self._settings.depth_frame_id,
                "target_frame_id": observation.target_frame_id,
                "stage_path": self._stage_path,
                "color_camera_path": self._color_camera_path,
                "depth_camera_path": self._depth_camera_path,
                "render_product_path": self._camera.get_render_product_path(),
            },
        )
        capture.validate()
        with self._capture_condition:
            self._latest_capture = capture
            self._capture_generation += 1
            self._last_capture_monotonic = time.monotonic()
            self._last_error = None
            self._capture_condition.notify_all()
        return True

    def warmup(self, joint_pos_provider, *, app=None) -> bool:
        try:
            import omni.kit.app
        except Exception:
            return False

        if callable(joint_pos_provider):
            get_joint_pos = joint_pos_provider
        else:
            def get_joint_pos():
                return joint_pos_provider

        app = app or omni.kit.app.get_app()
        warmup_updates = max(0, int(self._settings.warmup_updates))
        capture_attempts = max(1, int(self._settings.capture_attempts))
        native_isaac6 = configured_isaac_api_profile() == "native_6_0"
        if native_isaac6:
            from isaacsim.core.simulation_manager import SimulationManager

            sensor_period_steps = int(
                np.ceil(
                    1.0
                    / (
                        max(1, int(self._settings.frequency_hz))
                        * float(SimulationManager.get_physics_dt())
                    )
                )
            )
            # The first RTX frame compiles the camera render pipeline. Keep
            # stepping through two scheduled frames plus a completion margin;
            # otherwise a 5 Hz sensor can reach its first trigger just as the
            # startup retry loop ends.
            capture_attempts = max(capture_attempts, (2 * sensor_period_steps) + 90)

        restore_paused_timeline = False
        if native_isaac6:
            import isaacsim.core.experimental.utils.app as app_utils

            if not app_utils.is_playing():
                app_utils.play(commit=True)
                restore_paused_timeline = True

        def advance_sensor_clock() -> None:
            app.update()

        begin_capture = getattr(self._camera, "begin_capture", None)
        end_capture = getattr(self._camera, "end_capture", None)
        if callable(begin_capture):
            begin_capture()
        try:
            for _ in range(warmup_updates):
                joint_pos = np.asarray(get_joint_pos(), dtype=np.float64)
                if self._attachment is not None:
                    self._attachment.update(joint_pos)
                advance_sensor_clock()

            for _ in range(capture_attempts):
                joint_pos = np.asarray(get_joint_pos(), dtype=np.float64)
                advance_sensor_clock()
                if self._capture_once(joint_pos):
                    self._warmup_complete = True
                    return True
            self._detach_capture_annotators()
            return False
        finally:
            if callable(end_capture):
                end_capture()
            if restore_paused_timeline:
                import isaacsim.core.experimental.utils.app as app_utils

                app_utils.pause(commit=True)

    def update(self, joint_pos) -> bool:
        """Track the mount and capture only after a completed render generation.

        Isaac 6 CameraSensor and viewport paths continuously refresh one latest
        RGB-D snapshot for ROS. Other camera paths retain explicit fresh-frame
        requests. Annotator readback never runs at the physics callback rate.
        """
        joint_pos_array = np.asarray(joint_pos, dtype=np.float64)
        self._update_count += 1
        if self._attachment is not None:
            self._attachment.update(joint_pos_array)

        now = time.monotonic()
        with self._capture_condition:
            if self._closed:
                return False
            if not self._capture_requested:
                if self._continuous_capture:
                    should_capture_latest = True
                    should_detach = False
                else:
                    should_capture_latest = False
                idle_timeout = float(self._settings.annotator_idle_timeout_s)
                last_activity = max(
                    self._last_request_monotonic,
                    self._last_capture_monotonic or self._last_request_monotonic,
                )
                should_detach = bool(
                    not should_capture_latest
                    and self._annotators_attached
                    and not self._capture_armed
                    and now - last_activity >= idle_timeout
                )
                if not should_capture_latest and not should_detach:
                    return False
            else:
                should_capture_latest = False
                should_detach = False

        if should_capture_latest:
            try:
                render_token = self._current_render_token()
            except RuntimeError as exc:
                if _is_transient_camera_warmup_error(exc):
                    return False
                raise
            if render_token == ("None", "None") or render_token == self._continuous_render_token:
                return False
            self._continuous_render_token = render_token
            self._last_render_token = render_token
            self._render_token_change_count += 1
            try:
                captured = self._capture_once(joint_pos_array, update_attachment=False)
            except RuntimeError as exc:
                # The full headed App can expose a completed-frame token one
                # update before CameraSensor's CUDA AOV buffers are readable.
                # Keep warming up instead of permanently closing the session.
                if _is_transient_camera_warmup_error(exc):
                    return False
                raise
            if captured:
                self._warmup_complete = True
            return captured

        if should_detach:
            self._detach_capture_annotators()
            return False

        with self._capture_condition:
            if not self._capture_armed:
                self._capture_armed = True
                should_arm = True
            else:
                should_arm = False

        if should_arm:
            try:
                self._attach_capture_annotators()
                begin_capture = getattr(self._camera, "begin_capture", None)
                if callable(begin_capture):
                    begin_capture()
                render_token = self._current_render_token()
            except Exception:
                end_capture = getattr(self._camera, "end_capture", None)
                if callable(end_capture):
                    end_capture()
                with self._capture_condition:
                    self._capture_armed = False
                    self._capture_armed_render_token = None
                raise
            with self._capture_condition:
                self._capture_armed_render_token = render_token
                self._capture_last_render_token = render_token
                self._capture_render_changes_since_arm = 0
            # Require the viewport's actual completed-frame generation rather
            # than assuming a later physics callback implies a render.
            return False

        render_token = self._current_render_token()
        self._last_render_token = render_token
        with self._capture_condition:
            armed_render_token = self._capture_armed_render_token
            last_capture_render_token = self._capture_last_render_token
        if render_token == armed_render_token or render_token == last_capture_render_token:
            return False
        with self._capture_condition:
            self._capture_last_render_token = render_token
            self._capture_render_changes_since_arm += 1
            capture_render_changes = self._capture_render_changes_since_arm
        self._render_token_change_count += 1
        minimum_render_changes = 1
        if capture_render_changes < minimum_render_changes:
            return False

        captured = self._capture_once(joint_pos_array, update_attachment=False)
        if captured:
            end_capture = getattr(self._camera, "end_capture", None)
            if callable(end_capture):
                end_capture()
            with self._capture_condition:
                self._capture_requested = False
                self._capture_armed = False
                self._capture_armed_render_token = None
                self._capture_last_render_token = None
                self._capture_render_changes_since_arm = 0
        else:
            # Annotators can briefly return no data while a render product is
            # settling. Keep the request pending for a later physics update.
            with self._capture_condition:
                if not self._closed:
                    self._capture_requested = True
        return captured

    def request_capture(self, *, timeout_s: float | None = None) -> RGBDFrameCapture:
        """Request and wait for one fresh frame from the Kit main thread."""
        timeout = self._settings.request_timeout_s if timeout_s is None else float(timeout_s)
        deadline = time.monotonic() + max(0.0, timeout)
        with self._capture_condition:
            if self._closed:
                detail = f": {self._last_error}" if self._last_error else "."
                raise RuntimeError("D405 camera session is closed" + detail)
            target_generation = self._capture_generation + 1
            self._capture_requested = True
            self._last_request_monotonic = time.monotonic()
            while self._capture_generation < target_generation:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    self._capture_timeout_count += 1
                    self._last_error = (
                        "Timed out waiting for a fresh D405 frame from the Kit main thread."
                    )
                    raise TimeoutError("Timed out waiting for a fresh D405 frame from the Kit main thread.")
                self._capture_condition.wait(timeout=remaining)
                if self._closed:
                    raise RuntimeError("D405 camera session closed while waiting for a frame.")
            if self._latest_capture is None:
                raise RuntimeError("D405 capture completed without a frame.")
            return copy.deepcopy(self._latest_capture)

    def latest_capture(self) -> RGBDFrameCapture | None:
        with self._latest_lock:
            capture = self._latest_capture
            if capture is None:
                return None
            return copy.deepcopy(capture)

    def latest_payload(self, *, fresh: bool = True) -> dict[str, Any]:
        capture = self.request_capture() if fresh else self.latest_capture()
        if capture is None:
            capture = self.request_capture()
        started = time.perf_counter()
        payload = capture_to_payload(
            capture,
            compression_level=int(self._settings.zlib_level),
            executor=self._payload_executor,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        encoded_bytes = len(payload["rgb"]["data_b64"]) + len(payload["depth"]["data_b64"])
        with self._capture_condition:
            self._last_payload_encode_ms = elapsed_ms
            self._last_payload_b64_bytes = encoded_bytes
        return payload

    def latest_extrinsic_payload(self) -> dict[str, Any]:
        capture = self.latest_capture()
        if capture is None:
            raise RuntimeError("No D405 frame has been captured yet.")
        observation = capture.observation
        return {
            "timestamp_ns": int(observation.timestamp_ns),
            "source_backend": observation.source_backend,
            "camera_frame_id": observation.camera_frame_id,
            "target_frame_id": observation.target_frame_id,
            "extrinsic_camera_to_target": observation.extrinsic_camera_to_target,
            "scene_context": dict(observation.scene_context),
        }

    def health(self) -> dict[str, Any]:
        with self._capture_condition:
            ready = bool(
                self._latest_capture is not None
                and self._warmup_complete
                and not self._closed
                and self._last_error is None
            )
            capture_generation = self._capture_generation
            capture_requested = self._capture_requested
            capture_armed = self._capture_armed
            capture_render_changes_since_arm = self._capture_render_changes_since_arm
            closed = self._closed
            last_error = self._last_error
            update_failure_count = self._update_failure_count
            update_count = self._update_count
            render_token_change_count = self._render_token_change_count
            last_render_token = self._last_render_token
            capture_timeout_count = self._capture_timeout_count
            annotators_attached = self._annotators_attached
            annotator_attach_count = self._annotator_attach_count
            annotator_detach_count = self._annotator_detach_count
            last_capture_monotonic = self._last_capture_monotonic
            last_payload_encode_ms = self._last_payload_encode_ms
            last_payload_b64_bytes = self._last_payload_b64_bytes
        return {
            "ready": ready,
            "closed": bool(closed),
            "last_error": last_error,
            "update_failure_count": int(update_failure_count),
            "update_count": int(update_count),
            "render_token_change_count": int(render_token_change_count),
            "last_render_token": last_render_token,
            "capture_timeout_count": int(capture_timeout_count),
            "warmup_complete": self._warmup_complete,
            "capture_mode": (
                "camera_sensor_continuous_latest"
                if isinstance(self._camera, _Isaac6CameraSensorAdapter)
                and self._continuous_capture
                else "shared_viewport_continuous_latest"
                if isinstance(self._camera, _Isaac6SharedViewportCameraAdapter)
                and self._continuous_capture
                else "shared_viewport_on_demand"
                if isinstance(self._camera, _Isaac6SharedViewportCameraAdapter)
                else "on_demand_readback_continuous_sensor_pipeline"
                if configured_isaac_api_profile() == "native_6_0"
                else "on_demand_render_gated_idle_grace"
            ),
            "capture_generation": int(capture_generation),
            "continuous_capture": bool(self._continuous_capture),
            "capture_requested": bool(capture_requested),
            "capture_armed": bool(capture_armed),
            "capture_render_changes_since_arm": int(capture_render_changes_since_arm),
            "annotators_attached": bool(annotators_attached),
            "annotator_attach_count": int(annotator_attach_count),
            "annotator_detach_count": int(annotator_detach_count),
            "annotator_idle_timeout_s": float(self._settings.annotator_idle_timeout_s),
            "last_capture_monotonic": last_capture_monotonic,
            "last_capture_age_s": (
                None
                if last_capture_monotonic is None
                else max(0.0, time.monotonic() - last_capture_monotonic)
            ),
            "frequency_hz": int(self._settings.frequency_hz),
            "annotator_device": self._settings.annotator_device,
            "payload_compression": "zlib",
            "payload_zlib_level": int(self._settings.zlib_level),
            "payload_encode_workers": int(self._settings.encode_workers),
            "last_payload_encode_ms": last_payload_encode_ms,
            "last_payload_b64_bytes": int(last_payload_b64_bytes),
            "stage_path": self._stage_path,
            "color_camera_path": self._color_camera_path,
            "depth_camera_path": self._depth_camera_path,
            "render_product_path": self._camera.get_render_product_path(),
        }

    def mark_failed(self, exc: BaseException) -> None:
        with self._capture_condition:
            self._last_error = repr(exc)
            self._update_failure_count += 1
        self.close(wait_for_encoder=False)

    def close(self, *, wait_for_encoder: bool = True) -> None:
        with self._capture_condition:
            self._closed = True
            self._capture_requested = False
            self._capture_armed = False
            self._capture_armed_render_token = None
            self._capture_last_render_token = None
            self._capture_render_changes_since_arm = 0
            self._capture_condition.notify_all()
        end_capture = getattr(self._camera, "end_capture", None)
        if callable(end_capture):
            end_capture()
        self._detach_capture_annotators()
        close_camera = getattr(self._camera, "close", None)
        if callable(close_camera):
            close_camera()
        if self._payload_executor is not None:
            self._payload_executor.shutdown(wait=wait_for_encoder, cancel_futures=True)
            self._payload_executor = None
