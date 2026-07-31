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


def test_controller_facade_does_not_own_telemetry_transport_lifecycle() -> None:
    controller_source = (
        ROOT / "console" / "a1z_console" / "controller.py"
    ).read_text(encoding="utf-8")
    coordinator_source = (
        ROOT / "console" / "a1z_console" / "telemetry_coordinator.py"
    ).read_text(encoding="utf-8")

    for implementation_detail in (
        "_telemetry_timer",
        "_age_timer",
        "_telemetry_pending",
        "_info_refresh_counter",
        "_poll_telemetry",
        "_telemetry_future_done",
        "telemetryFinished",
    ):
        assert implementation_detail not in controller_source
    assert "self._telemetry = TelemetryCoordinator(" in controller_source
    assert "class TelemetryCoordinator(QObject):" in coordinator_source
    assert "a1z-console-telemetry" in coordinator_source
    assert 'client.request("status"' in coordinator_source


def test_telemetry_coordinator_owns_info_cadence_and_freshness_clock() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.profiles import RuntimeProfile
    from a1z_console.telemetry_coordinator import (
        TelemetryCoordinator,
        TelemetryResult,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    now = [100.0]
    calls: list[str] = []
    profile = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 37103, "", {}
    )

    class FakeClient:
        def __init__(self, selected_profile: RuntimeProfile) -> None:
            assert selected_profile is profile

        def request(self, command: str, *, timeout_s: float):
            assert timeout_s == 2.5
            calls.append(command)
            if command == "info":
                return {
                    "backend": "isaacsim",
                    "control_mode": "position_hold",
                }
            return {"pos_deg": [0.0] * 6, "running": True}

    coordinator = TelemetryCoordinator(
        profile,
        client_factory=FakeClient,
        clock=lambda: now[0],
    )
    results: list[TelemetryResult] = []
    age_events: list[bool] = []
    coordinator.resultAvailable.connect(results.append)
    coordinator.ageChanged.connect(age_events.append)

    assert coordinator.refresh(force_info=True) is True
    _wait_until(app, lambda: len(results) == 1)

    assert results[0].success is True
    assert results[0].info is not None
    assert results[0].timing_changed is True
    assert results[0].freshness_changed is True
    assert coordinator.age_ms == 0
    assert coordinator.fresh is True

    for expected_count in range(2, 10):
        assert coordinator.refresh() is True
        _wait_until(app, lambda count=expected_count: len(results) == count)

    assert calls.count("status") == 9
    assert calls.count("info") == 2

    now[0] = 102.1
    coordinator._update_age()
    assert 2090 <= coordinator.age_ms <= 2100
    assert coordinator.fresh is False
    assert age_events == [True]

    now[0] = 103.2
    coordinator._update_age()
    assert 3190 <= coordinator.age_ms <= 3200
    assert age_events == [True, False]
    coordinator.shutdown()


def test_telemetry_coordinator_respects_task_block_without_command_coupling() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.profiles import RuntimeProfile
    from a1z_console.telemetry_coordinator import TelemetryCoordinator

    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    profile = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 37103, "", {}
    )
    blocked = [True]
    created: list[None] = []

    class FakeClient:
        def __init__(self, _profile: RuntimeProfile) -> None:
            created.append(None)

    coordinator = TelemetryCoordinator(
        profile,
        poll_blocked=lambda: blocked[0],
        client_factory=FakeClient,
    )

    assert coordinator.refresh(force_info=True) is False
    assert coordinator.pending is False
    assert created == []
    blocked[0] = False
    assert coordinator.refresh(force_info=True) is True
    _wait_until(app, lambda: not coordinator.pending)
    coordinator.shutdown()


def test_telemetry_coordinator_ignores_late_old_profile_result() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.profiles import RuntimeProfile
    from a1z_console.telemetry_coordinator import TelemetryCoordinator

    app = QGuiApplication.instance() or QGuiApplication([])
    started = threading.Event()
    release = threading.Event()
    sim = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 1, "", {}
    )
    real = RuntimeProfile(
        "real", "真机", "socketcan", "127.0.0.1", 2, "", {}
    )

    class BlockingClient:
        def __init__(self, _profile: RuntimeProfile) -> None:
            pass

        def request(self, command: str, *, timeout_s: float):
            assert command == "info"
            started.set()
            assert release.wait(timeout_s)
            return {"backend": "isaacsim"}

    coordinator = TelemetryCoordinator(sim, client_factory=BlockingClient)
    results: list[object] = []
    coordinator.resultAvailable.connect(results.append)

    assert coordinator.refresh(force_info=True) is True
    assert started.wait(1.0)
    coordinator.select_profile(real)
    assert coordinator.pending is False
    assert coordinator.age_ms == -1
    release.set()
    _wait_until(app, lambda: coordinator._inflight_count == 0)

    assert results == []
    assert coordinator.age_ms == -1
    coordinator.shutdown()


def test_profile_switch_cancels_client_created_in_claim_window() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.profiles import RuntimeProfile
    from a1z_console.telemetry_coordinator import TelemetryCoordinator

    app = QGuiApplication.instance() or QGuiApplication([])
    factory_started = threading.Event()
    release_factory = threading.Event()
    cancelled = threading.Event()
    calls: list[tuple[str, str]] = []
    sim = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 1, "", {}
    )
    real = RuntimeProfile(
        "real", "真机", "socketcan", "127.0.0.1", 2, "", {}
    )

    class DelayedFactoryClient:
        def __init__(self, profile: RuntimeProfile) -> None:
            self.profile = profile
            factory_started.set()
            assert release_factory.wait(1.0)

        def request(self, command: str, *, timeout_s: float):
            calls.append((self.profile.name, command))
            return {}

        def cancel_pending_requests(self) -> None:
            cancelled.set()

    coordinator = TelemetryCoordinator(
        sim,
        client_factory=DelayedFactoryClient,
    )
    assert coordinator.refresh(force_info=True) is True
    assert factory_started.wait(1.0)

    coordinator.select_profile(real)
    release_factory.set()
    _wait_until(app, lambda: coordinator._inflight_count == 0)

    assert calls == []
    assert cancelled.is_set()
    coordinator.shutdown()


def test_telemetry_coordinator_shutdown_cancels_active_client() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.profiles import RuntimeProfile
    from a1z_console.telemetry_coordinator import TelemetryCoordinator

    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    started = threading.Event()
    cancelled = threading.Event()
    finished = threading.Event()
    profile = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", 37103, "", {}
    )

    class CancelableClient:
        def __init__(self, _profile: RuntimeProfile) -> None:
            pass

        def request(self, _command: str, *, timeout_s: float):
            started.set()
            try:
                assert cancelled.wait(timeout_s)
                raise RuntimeError("遥测请求已取消")
            finally:
                finished.set()

        def cancel_pending_requests(self) -> None:
            cancelled.set()

    coordinator = TelemetryCoordinator(profile, client_factory=CancelableClient)
    assert coordinator.refresh(force_info=True) is True
    assert started.wait(1.0)

    coordinator.shutdown()

    assert cancelled.is_set()
    assert finished.wait(0.5)


def test_controller_keeps_telemetry_responsive_while_command_is_busy() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.device_command_executor import (
        DeviceCommandRequest,
    )
    from a1z_console.interaction_policy import ResourceEffect

    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT)
    calls: list[str] = []
    release_command = threading.Event()

    class FakeClient:
        def __init__(self, _profile) -> None:
            pass

        def request(self, command: str, *, timeout_s: float):
            calls.append(command)
            if command == "info":
                return {
                    "backend": "isaacsim",
                    "control_mode": "position_hold",
                    "running": True,
                    "faulted": False,
                }
            return {
                "pos_deg": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "running": True,
                "faulted": False,
            }

    controller._telemetry._client_factory = FakeClient
    sequence = controller._commands.submit_command(
        DeviceCommandRequest(
            "测试中的长命令",
            lambda: (
                release_command.wait(1.0)
                and {"data": {}}
            ),
            ResourceEffect.NONE,
        )
    )
    assert sequence == 1
    try:
        controller.refreshNow()
        _wait_until(app, lambda: controller.connected)

        assert controller.commandBusy is True
        assert controller.telemetryFresh is True
        assert controller.joints[0]["position"] == pytest.approx(1.0)
        assert calls == ["info", "status"]
    finally:
        release_command.set()
        _wait_until(app, lambda: not controller.commandBusy)
        controller.shutdown()
