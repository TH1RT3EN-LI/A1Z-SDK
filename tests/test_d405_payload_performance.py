from __future__ import annotations

import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import numpy as np


A1Z_ROOT = Path(__file__).resolve().parents[1]
ROS_D405_SRC = A1Z_ROOT / "ros2_ws" / "src" / "a1z_d405"
GALAXEA_SDK_SRC = A1Z_ROOT / "vendor" / "GALAXEA-A1Z"
for path in (A1Z_ROOT, ROS_D405_SRC, GALAXEA_SDK_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from a1z_d405.decode import decode_array  # noqa: E402
from a1z_ext.interfaces.observation import RGBDObservation  # noqa: E402
from a1z_ext.robots.server import RobotServer  # noqa: E402
from a1z_ext.runtime.d405.session import (  # noqa: E402
    D405CaptureSettings,
    D405FrameSession,
    _Isaac6CameraSensorAdapter,
    _encode_array,
    _is_transient_camera_warmup_error,
    capture_to_payload,
)
from a1z_ext.runtime.frame_sources.base import RGBDFrameCapture  # noqa: E402


def _capture(width: int = 96, height: int = 54) -> RGBDFrameCapture:
    x = np.arange(width, dtype=np.uint8)[None, :]
    y = np.arange(height, dtype=np.uint8)[:, None]
    rgb = np.stack(
        (
            np.broadcast_to(x, (height, width)),
            np.broadcast_to(y, (height, width)),
            np.bitwise_xor(x, y),
        ),
        axis=2,
    )
    depth = np.linspace(0.2, 2.0, width * height, dtype=np.float32).reshape(height, width)
    observation = RGBDObservation.create(
        source_backend="test",
        width=width,
        height=height,
        camera_frame_id="camera",
        target_frame_id="base",
        intrinsics={"fx": 100.0, "fy": 100.0, "cx": width / 2, "cy": height / 2},
        extrinsic_camera_to_target=np.eye(4),
        timestamp_ns=123,
    )
    return RGBDFrameCapture(
        observation=observation,
        rgb=rgb,
        depth_m=depth,
        source_info={"depth_frame_id": "depth"},
    )


class D405PayloadPerformanceTests(unittest.TestCase):
    @staticmethod
    def _bare_camera_sensor_adapter(*, change_token_during_read: bool = False):
        class FakeHydraTexture:
            def __init__(self):
                self.frame = 7

            def get_frame_info(self):
                return {"frame_number": self.frame, "swh_frame_number": self.frame + 100}

        class FakeSensor:
            def __init__(self):
                self._hydra_texture = mock.Mock(hydra_texture=FakeHydraTexture())

            def get_data(self, annotator, *, out=None):
                del out
                if annotator == "rgb":
                    return np.ones((2, 3, 3), dtype=np.uint8), {}
                if change_token_during_read:
                    self._hydra_texture.hydra_texture.frame += 1
                return np.ones((2, 3, 1), dtype=np.float32), {}

        adapter = object.__new__(_Isaac6CameraSensorAdapter)
        adapter._sensor = FakeSensor()
        adapter._rgb_out = object()
        adapter._depth_out = object()
        return adapter

    @staticmethod
    def _bare_session(*, idle_timeout_s: float = 1.0):
        class FakeCamera:
            def __init__(self):
                self.frame = 10
                self._custom_annotators = {
                    "rgb": object(),
                    "distance_to_image_plane": object(),
                }

            def get_current_frame(self, clone=False):
                return {"rendering_frame": self.frame, "rendering_time": self.frame / 5.0}

            def get_render_product_path(self):
                return "/Render/test"

            def get_rgb(self, device="cpu"):
                del device
                return None

            def get_depth(self, device="cpu"):
                del device
                return None

            def attach_annotator(self, annotator_name):
                self._custom_annotators[annotator_name] = object()

            def add_distance_to_image_plane_to_frame(self):
                self._custom_annotators["distance_to_image_plane"] = object()

            def detach_annotator(self, annotator_name):
                self._custom_annotators.pop(annotator_name, None)

            def remove_distance_to_image_plane_from_frame(self):
                self._custom_annotators.pop("distance_to_image_plane", None)

        session = object.__new__(D405FrameSession)
        session._attachment = None
        session._settings = D405CaptureSettings(annotator_idle_timeout_s=idle_timeout_s)
        session._latest_lock = threading.Lock()
        session._capture_condition = threading.Condition(session._latest_lock)
        session._latest_capture = _capture()
        session._capture_generation = 1
        session._capture_requested = False
        session._capture_armed = False
        session._capture_armed_render_token = None
        session._capture_last_render_token = None
        session._capture_render_changes_since_arm = 0
        session._closed = False
        session._last_error = None
        session._update_failure_count = 0
        session._update_count = 0
        session._render_token_change_count = 0
        session._last_render_token = None
        session._capture_timeout_count = 0
        session._annotators_attached = True
        session._annotator_attach_count = 1
        session._annotator_detach_count = 0
        session._last_request_monotonic = time.monotonic()
        session._last_capture_monotonic = time.monotonic()
        session._last_payload_encode_ms = None
        session._last_payload_b64_bytes = 0
        session._warmup_complete = True
        session._continuous_capture = False
        session._continuous_render_token = None
        session._payload_executor = None
        session._stage_path = "/World/test.usd"
        session._color_camera_path = "/World/color"
        session._depth_camera_path = "/World/depth"
        session._camera = FakeCamera()
        return session

    def test_default_codec_keeps_zlib_protocol_at_low_cpu_level(self) -> None:
        settings = D405CaptureSettings()
        self.assertEqual((settings.width, settings.height), (320, 240))
        self.assertEqual(settings.frequency_hz, 10)
        self.assertEqual(settings.zlib_level, 1)
        self.assertEqual(settings.encode_workers, 2)
        self.assertEqual(settings.annotator_idle_timeout_s, 1.0)

        source = np.arange(128 * 64, dtype=np.float32).reshape(64, 128)
        encoded = _encode_array(source)

        self.assertEqual(encoded["compression"], "zlib")
        self.assertEqual(encoded["compression_level"], 1)
        self.assertEqual(encoded["uncompressed_nbytes"], source.nbytes)
        self.assertGreater(encoded["compressed_nbytes"], 0)
        np.testing.assert_array_equal(decode_array(encoded), source)

    def test_camera_sensor_rgbd_accepts_one_stable_completed_generation(self) -> None:
        adapter = self._bare_camera_sensor_adapter()

        rgb, depth = adapter.get_rgbd()

        self.assertEqual(rgb.shape, (2, 3, 3))
        self.assertEqual(depth.shape, (2, 3, 1))
        self.assertEqual(
            adapter.get_current_frame(),
            {"rendering_frame": 7, "rendering_time": 107},
        )

    def test_camera_sensor_rgbd_rejects_a_generation_change_between_aovs(self) -> None:
        adapter = self._bare_camera_sensor_adapter(change_token_during_read=True)

        self.assertEqual(adapter.get_rgbd(), (None, None))

    def test_camera_sensor_health_tolerates_render_product_warmup(self) -> None:
        adapter = self._bare_camera_sensor_adapter()
        adapter._sensor.render_product = None

        self.assertEqual(adapter.get_render_product_path(), "")

    def test_only_hydra_first_frame_failure_is_treated_as_warmup(self) -> None:
        self.assertTrue(
            _is_transient_camera_warmup_error(
                RuntimeError("IHydraTexture::getFrameData for 0 failed")
            )
        )
        self.assertFalse(_is_transient_camera_warmup_error(RuntimeError("CUDA device lost")))

    def test_rgb_and_depth_parallel_payload_remains_ros_decoder_compatible(self) -> None:
        capture = _capture()
        with ThreadPoolExecutor(max_workers=2) as executor:
            payload = capture_to_payload(capture, compression_level=1, executor=executor)

        self.assertEqual(payload["timestamp_ns"], 123)
        self.assertEqual(payload["rgb"]["compression"], "zlib")
        self.assertEqual(payload["depth"]["compression"], "zlib")
        np.testing.assert_array_equal(decode_array(payload["rgb"]), capture.rgb)
        np.testing.assert_array_equal(decode_array(payload["depth"]), capture.depth_m)

    def test_read_requests_do_not_take_robot_command_lock(self) -> None:
        class CameraSession:
            @staticmethod
            def health():
                return {"ready": True}

        class Robot:
            is_running = True
            is_estopped = False

            @staticmethod
            def get_joint_state():
                return {
                    "pos": np.zeros(6),
                    "vel": np.zeros(6),
                    "eff": np.zeros(6),
                }

            @staticmethod
            def get_robot_info():
                return {"control_mode": "position_hold"}

        class RaisingLock:
            def __enter__(self):
                raise AssertionError("robot command lock was entered")

            def __exit__(self, *_args):
                return False

        server = RobotServer(Robot(), with_gripper=False, camera_session=CameraSession())
        server._lock = RaisingLock()

        result = server._dispatch_request("camera_status", {})

        self.assertEqual(result, {"ok": True, "data": {"ready": True}})
        self.assertTrue(server._dispatch_request("status", {})["ok"])
        # Latest-target commands deliberately bypass the legacy command lock;
        # otherwise a newer target could not supersede a blocking move.
        move_result = server._dispatch_request(
            "command", {"joints": [0.0] * 6, "speed": 0.5}
        )
        self.assertTrue(move_result["ok"])
        # Mutually exclusive control-mode transitions remain serialized.
        with self.assertRaisesRegex(AssertionError, "robot command lock"):
            server._dispatch_request("gravity_mode", {"enabled": True})

    def test_on_demand_capture_waits_for_a_new_render_generation_and_keeps_graph_warm(self) -> None:
        session = self._bare_session()
        session._capture_requested = True
        session._capture_once = mock.Mock(return_value=True)

        self.assertFalse(session.update(np.zeros(7)))
        self.assertTrue(session._capture_armed)
        self.assertFalse(session.update(np.zeros(7)))
        session._capture_once.assert_not_called()

        session._camera.frame += 1
        self.assertTrue(session.update(np.zeros(7)))
        session._capture_once.assert_called_once()
        self.assertFalse(session._capture_armed)
        self.assertFalse(session._capture_requested)
        self.assertTrue(session._annotators_attached)
        self.assertEqual(session._annotator_attach_count, 1)
        self.assertEqual(session._annotator_detach_count, 0)

    def test_capture_does_not_rewrite_camera_pose_each_frame(self) -> None:
        session = self._bare_session()
        session._stabilize_all_camera_local_poses = mock.Mock()

        self.assertFalse(session._capture_once(np.zeros(7)))

        session._stabilize_all_camera_local_poses.assert_not_called()

    def test_on_demand_annotators_detach_only_after_idle_grace(self) -> None:
        session = self._bare_session(idle_timeout_s=1.0)

        self.assertFalse(session.update(np.zeros(7)))
        self.assertTrue(session._annotators_attached)
        session._last_request_monotonic = time.monotonic() - 2.0
        session._last_capture_monotonic = time.monotonic() - 2.0
        self.assertFalse(session.update(np.zeros(7)))
        self.assertFalse(session._annotators_attached)
        self.assertEqual(session._annotator_detach_count, 1)

    def test_continuous_sensor_captures_each_completed_render_without_a_request(self) -> None:
        session = self._bare_session()
        session._continuous_capture = True
        session._continuous_render_token = session._current_render_token()
        session._capture_once = mock.Mock(return_value=True)

        self.assertFalse(session.update(np.zeros(7)))
        session._camera.frame += 1
        self.assertTrue(session.update(np.zeros(7)))
        session._capture_once.assert_called_once_with(
            mock.ANY,
            update_attachment=False,
        )

    def test_latest_payload_can_reuse_the_latest_complete_sensor_frame(self) -> None:
        session = self._bare_session()
        session.request_capture = mock.Mock(side_effect=AssertionError("fresh capture requested"))

        payload = session.latest_payload(fresh=False)

        self.assertEqual(payload["timestamp_ns"], 123)
        session.request_capture.assert_not_called()

    def test_failed_camera_session_cannot_report_stale_ready_health(self) -> None:
        session = self._bare_session()
        self.assertTrue(session.health()["ready"])

        session.mark_failed(RuntimeError("synthetic camera failure"))

        health = session.health()
        self.assertFalse(health["ready"])
        self.assertTrue(health["closed"])
        self.assertIn("synthetic camera failure", health["last_error"])
        self.assertEqual(health["update_failure_count"], 1)

    def test_capture_timeout_marks_health_not_ready_until_a_later_capture_recovers(self) -> None:
        session = self._bare_session()

        with self.assertRaises(TimeoutError):
            session.request_capture(timeout_s=0.0)

        health = session.health()
        self.assertFalse(health["ready"])
        self.assertEqual(health["capture_timeout_count"], 1)
        self.assertIn("Timed out", health["last_error"])

    def test_robot_server_readiness_waits_for_listener_bind(self) -> None:
        with TemporaryDirectory(prefix="a1z_server_ready_") as temp_dir:
            socket_path = str(Path(temp_dir) / "a1z.sock")
            server = RobotServer(object(), with_gripper=False)
            thread = threading.Thread(
                target=server.run,
                kwargs={"socket_path": socket_path, "tcp_port": 0},
                daemon=True,
            )
            thread.start()

            server.wait_until_ready(timeout_s=2.0)

            self.assertTrue(Path(socket_path).exists())
            self.assertTrue(thread.is_alive())
            server._shutdown.set()
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive())

    def test_robot_server_readiness_propagates_listener_bind_failure(self) -> None:
        with TemporaryDirectory(prefix="a1z_server_failure_") as temp_dir:
            socket_path = str(Path(temp_dir) / "missing" / "a1z.sock")
            server = RobotServer(object(), with_gripper=False)
            thread_errors = []

            def run_server():
                try:
                    server.run(socket_path=socket_path, tcp_port=0)
                except BaseException as exc:
                    thread_errors.append(exc)

            thread = threading.Thread(target=run_server, daemon=True)
            thread.start()

            with self.assertRaisesRegex(RuntimeError, "listeners failed to start"):
                server.wait_until_ready(timeout_s=2.0)
            thread.join(timeout=2.0)

            self.assertFalse(thread.is_alive())
            self.assertEqual(len(thread_errors), 1)


if __name__ == "__main__":
    unittest.main()
