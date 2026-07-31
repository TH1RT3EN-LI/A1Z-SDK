from __future__ import annotations

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


def test_controller_facade_does_not_own_qprocess_lifecycle() -> None:
    controller_source = (
        ROOT / "console" / "a1z_console" / "controller.py"
    ).read_text(encoding="utf-8")
    runner_source = (
        ROOT / "console" / "a1z_console" / "process_task_runner.py"
    ).read_text(encoding="utf-8")

    assert "QProcess" not in controller_source
    assert "ProcessTaskRunner(self)" in controller_source
    assert "class ProcessTaskRunner(QObject):" in runner_source
    assert "os.killpg" in runner_source


def test_process_task_runner_owns_state_environment_and_output() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.interaction_policy import (
        ProcessAccess,
        ProcessTaskContract,
    )
    from a1z_console.process_task_runner import (
        ProcessTaskRequest,
        ProcessTaskResult,
        ProcessTaskRunner,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    runner = ProcessTaskRunner()
    states: list[bool] = []
    streamed: list[str] = []
    results: list[ProcessTaskResult] = []
    runner.stateChanged.connect(lambda: states.append(runner.busy))
    runner.outputAvailable.connect(streamed.append)
    runner.finished.connect(results.append)
    request = ProcessTaskRequest.create(
        kind="test_task",
        label="测试任务",
        program="/bin/sh",
        arguments=[
            "-c",
            'printf "%s" "$A1Z_RUNNER_TEST"; printf ":stderr" >&2',
        ],
        working_directory=ROOT,
        environment={"A1Z_RUNNER_TEST": "isolated"},
        contract=ProcessTaskContract(ProcessAccess.TASK_SLOT),
    )

    assert runner.start(request) is True
    assert runner.busy is True
    assert runner.cancelable is False
    assert runner.kind == "test_task"
    assert runner.label == "测试任务"
    _wait_until(app, lambda: bool(results))

    assert runner.busy is False
    assert states[0] is True
    assert states[-1] is False
    assert results[0].exit_code == 0
    assert results[0].output == "isolated:stderr"
    assert "isolated:stderr" in "".join(streamed)
    runner.shutdown()


def test_process_task_runner_rejects_overlapping_tasks() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.interaction_policy import (
        ProcessAccess,
        ProcessTaskContract,
    )
    from a1z_console.process_task_runner import (
        ProcessTaskRequest,
        ProcessTaskRunner,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    runner = ProcessTaskRunner()
    contract = ProcessTaskContract(ProcessAccess.TASK_SLOT)
    first = ProcessTaskRequest.create(
        kind="first",
        label="第一个任务",
        program="/bin/sh",
        arguments=["-c", "sleep 0.05"],
        working_directory=ROOT,
        environment={},
        contract=contract,
    )
    second = ProcessTaskRequest.create(
        kind="second",
        label="第二个任务",
        program="/bin/true",
        arguments=[],
        working_directory=ROOT,
        environment={},
        contract=contract,
    )

    assert runner.start(first) is True
    assert runner.start(second) is False
    _wait_until(app, lambda: not runner.busy)
    runner.shutdown()


def test_process_task_runner_cancels_the_owned_process_group() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.interaction_policy import (
        ProcessAccess,
        ProcessTaskContract,
    )
    from a1z_console.process_task_runner import (
        ProcessTaskRequest,
        ProcessTaskResult,
        ProcessTaskRunner,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    runner = ProcessTaskRunner()
    streamed: list[str] = []
    results: list[ProcessTaskResult] = []
    runner.outputAvailable.connect(streamed.append)
    runner.finished.connect(results.append)
    request = ProcessTaskRequest.create(
        kind="plan_execute",
        label="可取消任务",
        program="/bin/sh",
        arguments=["-c", 'printf "ready\\n"; exec sleep 10'],
        working_directory=ROOT,
        environment={},
        contract=ProcessTaskContract(
            ProcessAccess.TASK_SLOT,
            cancelable=True,
        ),
    )

    assert runner.start(request) is True
    assert runner.cancelable is True
    _wait_until(app, lambda: "ready" in "".join(streamed))

    assert runner.cancel() is True
    _wait_until(app, lambda: bool(results))

    assert runner.busy is False
    assert results[0].request is request
    assert results[0].exit_code != 0
    runner.shutdown()


def test_late_cancel_timer_cannot_kill_the_next_task() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QProcess
    from PySide6.QtGui import QGuiApplication

    from a1z_console.interaction_policy import (
        ProcessAccess,
        ProcessTaskContract,
    )
    from a1z_console.process_task_runner import (
        ProcessTaskRequest,
        ProcessTaskRunner,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    runner = ProcessTaskRunner()
    contract = ProcessTaskContract(ProcessAccess.TASK_SLOT, cancelable=True)

    def request(kind: str, script: str) -> ProcessTaskRequest:
        return ProcessTaskRequest.create(
            kind=kind,
            label=kind,
            program="/bin/sh",
            arguments=["-c", script],
            working_directory=ROOT,
            environment={},
            contract=contract,
        )

    try:
        assert runner.start(request("first", "exit 0")) is True
        first_process = runner._process
        assert first_process is not None
        _wait_until(app, lambda: not runner.busy)

        assert runner.start(request("second", "exec sleep 10")) is True
        second_process = runner._process
        assert second_process is not None
        _wait_until(app, lambda: second_process.processId() > 0)

        runner._kill_if_running(first_process)
        app.processEvents()
        assert runner._process is second_process
        assert runner.busy is True
        assert second_process.state() != QProcess.NotRunning

    finally:
        runner.shutdown()


def test_process_task_runner_bounds_captured_output() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.interaction_policy import ProcessAccess, ProcessTaskContract
    from a1z_console.process_task_runner import (
        ProcessTaskRequest,
        ProcessTaskResult,
        ProcessTaskRunner,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    runner = ProcessTaskRunner()
    runner._CAPTURE_LIMIT_BYTES = 32
    results: list[ProcessTaskResult] = []
    runner.finished.connect(results.append)
    request = ProcessTaskRequest.create(
        kind="bounded",
        label="bounded",
        program="/bin/sh",
        arguments=["-c", "printf '%0100d' 0"],
        working_directory=ROOT,
        environment={},
        contract=ProcessTaskContract(ProcessAccess.TASK_SLOT),
        log_stdout=False,
    )

    assert runner.start(request) is True
    _wait_until(app, lambda: bool(results))

    assert results[0].output_truncated is True
    assert len(results[0].output.encode()) <= 32
    runner.shutdown()


def test_controller_facade_tracks_runner_completion() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.interaction_policy import (
        ProcessAccess,
        ProcessTaskContract,
    )

    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT)
    completions: list[tuple[int, str]] = []
    try:
        controller._start_process_task(
            "facade_test",
            "Facade 测试",
            "/bin/sh",
            ["-c", 'printf "done"'],
            contract=ProcessTaskContract(ProcessAccess.TASK_SLOT),
            completion=lambda code, output: completions.append((code, output)),
        )
        assert controller.taskBusy is True
        assert controller.taskKind == "facade_test"
        assert controller.taskLabel == "Facade 测试"

        _wait_until(app, lambda: bool(completions))

        assert controller.taskBusy is False
        assert controller.taskKind == ""
        assert controller.taskLabel == ""
        assert completions == [(0, "done")]
        assert controller.operationFeedbackState == "success"
    finally:
        controller.shutdown()


@pytest.mark.parametrize(
    ("semantic_success", "feedback_state", "expected_success"),
    [
        (True, "warning", True),
        (False, "error", False),
    ],
)
def test_domain_result_is_projected_once_after_process_success(
    semantic_success: bool,
    feedback_state: str,
    expected_success: bool,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.interaction_policy import (
        ProcessAccess,
        ProcessTaskContract,
    )
    from a1z_console.process_task_runner import ProcessTaskSemanticResult

    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT)
    events: list[tuple[str, bool, str]] = []
    callback_count = 0

    def completion(_code: int, _output: str) -> ProcessTaskSemanticResult:
        nonlocal callback_count
        callback_count += 1
        return ProcessTaskSemanticResult(
            success=semantic_success,
            feedback_state=feedback_state,
            status_text="领域结果已审阅",
            error="产物解析失败" if not semantic_success else "",
        )

    controller.operationFinished.connect(
        lambda label, success, message: events.append(
            (label, success, message)
        )
    )
    try:
        assert controller._start_process_task(
            "semantic_test",
            "领域结果测试",
            "/bin/true",
            [],
            contract=ProcessTaskContract(ProcessAccess.TASK_SLOT),
            completion=completion,
        )
        _wait_until(app, lambda: bool(events))

        assert callback_count == 1
        assert events == [
            ("领域结果测试", expected_success, "领域结果已审阅")
        ]
        assert controller.operationFeedbackState == feedback_state
        assert controller.operationFeedbackTitle == "领域结果测试"
        assert "领域结果已审阅" in controller.operationFeedbackMessage
        if not semantic_success:
            assert "产物解析失败" in controller.operationFeedbackMessage
    finally:
        controller.shutdown()
