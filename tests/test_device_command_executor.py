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


def test_controller_facade_does_not_own_command_worker_lifecycle() -> None:
    controller_source = (
        ROOT / "console" / "a1z_console" / "controller.py"
    ).read_text(encoding="utf-8")
    executor_source = (
        ROOT / "console" / "a1z_console" / "device_command_executor.py"
    ).read_text(encoding="utf-8")

    for implementation_detail in (
        "ThreadPoolExecutor",
        "_ThreadBridge",
        "_emergency_executor",
        "_operation_sequence",
        "_safety_epoch",
    ):
        assert implementation_detail not in controller_source
    assert "DeviceCommandExecutor(self)" in controller_source
    assert "class DeviceCommandExecutor(QObject):" in executor_source
    assert "a1z-console-command" in executor_source
    assert "a1z-console-estop" in executor_source


def test_device_command_executor_serializes_and_classifies_ambiguity() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.device_command_executor import (
        DeviceCommandExecutor,
        DeviceCommandRequest,
        DeviceCommandResult,
    )
    from a1z_console.interaction_policy import ResourceEffect
    from a1z_console.protocol import AmbiguousCommandError

    app = QGuiApplication.instance() or QGuiApplication([])
    started = threading.Event()
    release = threading.Event()
    executor = DeviceCommandExecutor()
    results: list[DeviceCommandResult] = []
    executor.commandFinished.connect(results.append)

    def blocking_operation() -> dict[str, object]:
        started.set()
        assert release.wait(1.0)
        return {"value": 7}

    first = DeviceCommandRequest(
        label="第一个命令",
        operation=blocking_operation,
        effects=ResourceEffect.ARM,
        result_handler="motion",
    )
    second = DeviceCommandRequest(
        label="第二个命令",
        operation=lambda: {},
        effects=ResourceEffect.NONE,
    )

    assert executor.submit_command(first) == 1
    assert started.wait(1.0)
    assert executor.command_busy is True
    assert executor.submit_command(second) is None
    release.set()
    _wait_until(app, lambda: len(results) == 1)

    assert executor.command_busy is False
    assert results[0].success is True
    assert results[0].sequence == 1
    assert results[0].data == {"value": 7}
    assert results[0].effects is ResourceEffect.ARM
    assert results[0].result_handler == "motion"

    def ambiguous_operation() -> dict[str, object]:
        raise AmbiguousCommandError("响应丢失")

    ambiguous = DeviceCommandRequest(
        label="不确定命令",
        operation=ambiguous_operation,
        effects=ResourceEffect.GRIPPER,
    )
    assert executor.submit_command(ambiguous) == 2
    _wait_until(app, lambda: len(results) == 2)

    assert results[1].success is False
    assert results[1].ambiguous is True
    assert results[1].error == "响应丢失"

    malformed = DeviceCommandRequest(
        label="错误返回类型",
        operation=lambda: "not-an-object",  # type: ignore[return-value]
        effects=ResourceEffect.NONE,
    )
    assert executor.submit_command(malformed) == 3
    _wait_until(app, lambda: len(results) == 3)
    assert results[2].success is False
    assert results[2].error == "设备命令执行函数没有返回对象"
    executor.shutdown()


def test_emergency_lane_preempts_result_projection_without_waiting_for_command() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.device_command_executor import (
        DeviceCommandExecutor,
        DeviceCommandRequest,
        DeviceCommandResult,
        EmergencyCommandRequest,
        EmergencyCommandResult,
    )
    from a1z_console.interaction_policy import ResourceEffect

    app = QGuiApplication.instance() or QGuiApplication([])
    command_started = threading.Event()
    release_command = threading.Event()
    executor = DeviceCommandExecutor()
    command_results: list[DeviceCommandResult] = []
    emergency_results: list[EmergencyCommandResult] = []
    executor.commandFinished.connect(command_results.append)
    executor.emergencyFinished.connect(emergency_results.append)

    def slow_command() -> dict[str, object]:
        command_started.set()
        assert release_command.wait(1.0)
        return {"motion": "finished"}

    assert executor.submit_command(
        DeviceCommandRequest(
            "慢速运动",
            slow_command,
            ResourceEffect.ARM,
            "motion",
        )
    ) == 1
    assert command_started.wait(1.0)
    assert executor.submit_emergency(
        EmergencyCommandRequest("软急停", lambda: {"estopped": True})
    ) is True
    _wait_until(app, lambda: bool(emergency_results))

    assert emergency_results[0].success is True
    assert executor.emergency_busy is False
    assert executor.command_busy is True
    assert command_results == []

    release_command.set()
    _wait_until(app, lambda: bool(command_results))

    assert command_results[0].success is True
    assert command_results[0].superseded_by_emergency is True
    assert executor.command_busy is False
    executor.shutdown()


def test_executor_marks_old_profile_results_and_suppresses_shutdown_callbacks() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.device_command_executor import (
        DeviceCommandExecutor,
        EmergencyCommandRequest,
        EmergencyCommandResult,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    started = threading.Event()
    release = threading.Event()
    executor = DeviceCommandExecutor()
    results: list[EmergencyCommandResult] = []
    executor.emergencyFinished.connect(results.append)

    def blocking_emergency() -> dict[str, object]:
        started.set()
        assert release.wait(1.0)
        return {"estopped": True}

    assert executor.submit_emergency(
        EmergencyCommandRequest("旧配置急停", blocking_emergency)
    ) is True
    assert started.wait(1.0)
    executor.select_profile()
    release.set()
    _wait_until(app, lambda: bool(results))

    assert results[0].stale_profile is True

    started.clear()
    release.clear()
    assert executor.submit_emergency(
        EmergencyCommandRequest("关闭中急停", blocking_emergency)
    ) is True
    assert started.wait(1.0)
    delivered_before_shutdown = len(results)
    executor.shutdown()
    release.set()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.002)

    assert len(results) == delivered_before_shutdown


def test_controller_emergency_feedback_preempts_a_late_normal_result() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    import a1z_console.controller as controller_module
    from a1z_console.interaction_policy import ResourceEffect

    app = QGuiApplication.instance() or QGuiApplication([])
    command_started = threading.Event()
    release_command = threading.Event()

    class Endpoint:
        backend = "isaacsim"
        control_mode = "position_hold"

    class FakeProtocolClient:
        def __init__(self, _profile) -> None:
            pass

        def verified_request(self, command: str, **_kwargs):
            assert command == "estop"
            return {"estopped": True}, Endpoint()

    original_client = controller_module.A1ZProtocolClient
    controller_module.A1ZProtocolClient = FakeProtocolClient
    controller = controller_module.ConsoleController(ROOT)
    controller._connected = True
    controller._backend_matched = True
    controller._backend = "isaacsim"
    controller.refreshNow = lambda: None  # type: ignore[method-assign]

    def slow_command() -> dict[str, object]:
        command_started.set()
        assert release_command.wait(1.0)
        return {
            "data": {"control_mode": "gravity_comp_effort"},
            "backend": "late-backend",
            "controlMode": "gravity_comp_effort",
        }

    try:
        controller._submit_operation(
            "慢速运动",
            slow_command,
            effects=ResourceEffect.ARM,
            result_handler="motion",
        )
        assert command_started.wait(1.0)
        controller.emergencyStop()
        _wait_until(app, lambda: controller.estopped)

        assert controller.emergencyBusy is False
        assert controller.commandBusy is True
        assert controller.operationFeedbackTitle == "软急停"
        assert controller.operationFeedbackState == "success"

        release_command.set()
        _wait_until(app, lambda: not controller.commandBusy)

        assert controller.backend == "isaacsim"
        assert controller.controlMode != "gravity_comp_effort"
        assert controller.operationFeedbackTitle == "软急停"
        assert controller.statusText == "软急停已锁定"
    finally:
        release_command.set()
        controller.shutdown()
        controller_module.A1ZProtocolClient = original_client


def test_controller_fails_closed_when_emergency_acknowledgement_is_ambiguous() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.device_command_executor import EmergencyCommandResult

    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    try:
        controller._on_emergency_finished(
            EmergencyCommandResult(
                label="软急停",
                success=False,
                error="响应在发送后丢失",
                ambiguous=True,
            )
        )

        assert controller.estopped is True
        assert controller.commandOutcomeUncertain is True
        assert controller.operationFeedbackState == "uncertain"
        assert "按已急停处理" in controller.statusText
    finally:
        controller.shutdown()
