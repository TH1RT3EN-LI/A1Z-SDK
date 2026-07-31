from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _wait_until(app, predicate, *, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.002)
    app.processEvents()
    assert predicate()


def test_controller_facade_does_not_own_camera_session_lifecycle() -> None:
    controller_source = (
        ROOT / "console" / "a1z_console" / "controller.py"
    ).read_text(encoding="utf-8")
    coordinator_source = (
        ROOT / "console" / "a1z_console" / "camera_coordinator.py"
    ).read_text(encoding="utf-8")

    for implementation_detail in (
        "CameraProtocolClient",
        "_camera_executor",
        "_camera_timer",
        "_camera_pending",
        "_camera_poll_counter",
    ):
        assert implementation_detail not in controller_source
    assert "CameraCoordinator(self._profile, self)" in controller_source
    assert "class CameraCoordinator(QObject):" in coordinator_source
    assert "a1z-console-camera" in coordinator_source


def test_camera_coordinator_projects_status_capture_and_manual_results() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.camera_coordinator import (
        CameraCoordinator,
        CameraManualResult,
    )
    from a1z_console.profiles import RuntimeProfile

    app = QGuiApplication.instance() or QGuiApplication([])
    calls: list[tuple[str, dict[str, object], float]] = []
    profile = RuntimeProfile(
        name="sim",
        label="仿真",
        expected_backend="isaacsim",
        host="127.0.0.1",
        port=37103,
        socket_path="",
        environment={},
        camera_port=37203,
    )

    class FakeClient:
        def __init__(self, selected_profile: RuntimeProfile) -> None:
            assert selected_profile is profile

        def request(self, command, args, *, timeout_s):
            calls.append((command, dict(args), float(timeout_s)))
            base = {
                "ready": True,
                "width": 640,
                "height": 480,
                "camera_source": "realsense",
            }
            if command == "camera_capture":
                return {
                    **base,
                    "preview_png_b64": "cG5n",
                    "preview_mime": "image/png",
                    "rgb_encoding": "rgb8",
                    "depth_encoding": "16UC1",
                    "sync_delta_ms": 1.25,
                    "depth_range_m": [0.1, 1.5],
                }
            return {
                **base,
                "color_topic": "/camera/color",
                "depth_topic": "/camera/depth",
                "synchronized": True,
                "extrinsic_ready": True,
            }

    coordinator = CameraCoordinator(
        profile,
        client_factory=FakeClient,
    )
    results: list[CameraManualResult] = []
    previews: list[None] = []
    coordinator.manualFinished.connect(results.append)
    coordinator.previewChanged.connect(lambda: previews.append(None))

    assert coordinator.request_manual("camera_status") == ""
    assert coordinator.busy is True
    _wait_until(app, lambda: len(results) == 1)

    assert results[0].success is True
    assert coordinator.bridge_online is True
    assert coordinator.ready is True
    assert coordinator.summary == "640×480 · realsense · 在线"
    assert "/camera/color + /camera/depth" in coordinator.details

    assert coordinator.request_manual("camera_capture") == ""
    _wait_until(app, lambda: len(results) == 2)

    assert coordinator.preview_source == "data:image/png;base64,cG5n"
    assert len(previews) == 1
    assert "同步差 1.2 ms" in coordinator.details
    assert "深度 0.100–1.500 m" in coordinator.details
    assert calls == [
        ("camera_status", {}, 3.0),
        ("camera_capture", {"preview_max_width": 960}, 5.0),
    ]
    coordinator.shutdown()


def test_camera_coordinator_rejects_overlap_and_ignores_stale_profile_result() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.camera_coordinator import CameraCoordinator
    from a1z_console.profiles import RuntimeProfile

    app = QGuiApplication.instance() or QGuiApplication([])
    started = threading.Event()
    release = threading.Event()
    sim = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 1, "", {}, camera_port=2
    )
    real = RuntimeProfile(
        "real", "真机", "socketcan", "127.0.0.1", 3, "", {}, camera_port=4
    )

    class BlockingClient:
        def __init__(self, _profile: RuntimeProfile) -> None:
            pass

        def request(self, _command, _args, *, timeout_s):
            assert timeout_s == 3.0
            started.set()
            assert release.wait(1.0)
            return {"ready": True, "camera_source": "old-profile"}

    coordinator = CameraCoordinator(sim, client_factory=BlockingClient)
    results: list[object] = []
    coordinator.manualFinished.connect(results.append)

    assert coordinator.request_manual("camera_status") == ""
    assert started.wait(1.0)
    assert coordinator.request_manual("camera_capture") == "已有相机请求正在执行"

    coordinator.select_profile(real)
    assert coordinator.busy is False
    assert coordinator.summary == "离线"
    assert coordinator.details == "检查中…"
    release.set()
    _wait_until(app, lambda: coordinator._inflight_count == 0)

    assert results == []
    assert coordinator.bridge_online is False
    assert coordinator.summary == "离线"
    coordinator.shutdown()


def test_profile_switch_cancels_camera_client_created_in_claim_window() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.camera_coordinator import CameraCoordinator
    from a1z_console.profiles import RuntimeProfile

    app = QGuiApplication.instance() or QGuiApplication([])
    factory_started = threading.Event()
    release_factory = threading.Event()
    cancelled = threading.Event()
    calls: list[tuple[str, str]] = []
    sim = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 1, "", {}, camera_port=2
    )
    real = RuntimeProfile(
        "real", "真机", "socketcan", "127.0.0.1", 3, "", {}, camera_port=4
    )

    class DelayedFactoryClient:
        def __init__(self, profile: RuntimeProfile) -> None:
            self.profile = profile
            factory_started.set()
            assert release_factory.wait(1.0)

        def request(self, command, _args, *, timeout_s):
            calls.append((self.profile.name, command))
            return {}

        def cancel_pending_requests(self) -> None:
            cancelled.set()

    coordinator = CameraCoordinator(sim, client_factory=DelayedFactoryClient)
    assert coordinator.request_manual("camera_status") == ""
    assert factory_started.wait(1.0)

    coordinator.select_profile(real)
    release_factory.set()
    _wait_until(app, lambda: coordinator._inflight_count == 0)

    assert calls == []
    assert cancelled.is_set()
    coordinator.shutdown()


def test_camera_coordinator_turns_malformed_response_into_visible_failure() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.camera_coordinator import (
        CameraCoordinator,
        CameraManualResult,
    )
    from a1z_console.profiles import RuntimeProfile

    app = QGuiApplication.instance() or QGuiApplication([])
    profile = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 1, "", {}, camera_port=2
    )

    class MalformedClient:
        def __init__(self, _profile: RuntimeProfile) -> None:
            pass

        def request(self, _command, _args, *, timeout_s):
            return {"ready": True, "width": "not-an-integer"}

    coordinator = CameraCoordinator(profile, client_factory=MalformedClient)
    results: list[CameraManualResult] = []
    coordinator.manualFinished.connect(results.append)

    assert coordinator.request_manual("camera_status") == ""
    _wait_until(app, lambda: bool(results))

    assert results[0].success is False
    assert "响应字段无效" in results[0].error
    assert coordinator.summary == "相机桥离线"
    assert coordinator.bridge_online is False
    coordinator.shutdown()


def test_camera_coordinator_shutdown_cancels_active_client() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.camera_coordinator import CameraCoordinator
    from a1z_console.profiles import RuntimeProfile

    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    started = threading.Event()
    cancelled = threading.Event()
    finished = threading.Event()
    profile = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 1, "", {}, camera_port=2
    )

    class CancelableClient:
        def __init__(self, _profile: RuntimeProfile) -> None:
            pass

        def request(self, _command, _args, *, timeout_s):
            started.set()
            try:
                assert cancelled.wait(timeout_s)
                raise RuntimeError("相机请求已取消")
            finally:
                finished.set()

        def cancel_pending_requests(self) -> None:
            cancelled.set()

    coordinator = CameraCoordinator(profile, client_factory=CancelableClient)
    assert coordinator.request_manual("camera_status") == ""
    assert started.wait(1.0)

    coordinator.shutdown()

    assert cancelled.is_set()
    assert finished.wait(0.5)


def test_controller_camera_facade_preserves_global_operation_feedback() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController

    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT)

    class FakeClient:
        def __init__(self, _profile) -> None:
            pass

        def request(self, _command, _args, *, timeout_s):
            return {
                "ready": True,
                "width": 320,
                "height": 240,
                "camera_source": "test-camera",
                "synchronized": True,
                "extrinsic_ready": False,
            }

    controller._camera._client_factory = FakeClient
    camera_events: list[None] = []
    global_events: list[None] = []
    controller.cameraStateChanged.connect(lambda: camera_events.append(None))
    controller.stateChanged.connect(lambda: global_events.append(None))
    try:
        controller.queryCamera("camera_status")
        assert controller.operationFeedbackState == "running"
        assert controller.cameraBusy is True
        _wait_until(app, lambda: controller.operationFeedbackState == "success")

        assert controller.cameraBusy is False
        assert controller.cameraReady is True
        assert controller.cameraSummary == "320×240 · test-camera · 在线"
        assert controller.lastError == ""
        assert len(camera_events) >= 2
        assert len(global_events) == 2

        camera_event_count = len(camera_events)
        global_event_count = len(global_events)
        controller.setProfile("real")

        assert controller.profile == "real"
        assert controller.cameraSummary == "离线"
        assert len(camera_events) == camera_event_count + 1
        assert len(global_events) == global_event_count + 1
    finally:
        controller.shutdown()
