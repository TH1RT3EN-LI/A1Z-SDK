"""Lifecycle owner for one external console task at a time."""

from __future__ import annotations

import os
import signal
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
)

from .interaction_policy import (
    ProcessAccess,
    ProcessTaskContract,
)


@dataclass(frozen=True)
class ProcessTaskSemanticResult:
    """Optional domain-level interpretation of a finished process."""

    success: bool
    feedback_state: str
    status_text: str
    error: str = ""


CompletionCallback = Callable[
    [int, str],
    ProcessTaskSemanticResult | None,
]


@dataclass(frozen=True)
class ProcessTaskRequest:
    """Everything the runner needs to execute one external task."""

    kind: str
    label: str
    program: str
    arguments: tuple[str, ...]
    working_directory: Path
    environment: Mapping[str, str]
    contract: ProcessTaskContract
    completion: CompletionCallback | None = None
    log_stdout: bool = True

    @classmethod
    def create(
        cls,
        *,
        kind: str,
        label: str,
        program: str,
        arguments: Sequence[str],
        working_directory: Path,
        environment: Mapping[str, str],
        contract: ProcessTaskContract,
        completion: CompletionCallback | None = None,
        log_stdout: bool = True,
    ) -> ProcessTaskRequest:
        return cls(
            kind=str(kind),
            label=str(label),
            program=str(program),
            arguments=tuple(str(value) for value in arguments),
            working_directory=Path(working_directory).resolve(),
            environment={str(key): str(value) for key, value in environment.items()},
            contract=contract,
            completion=completion,
            log_stdout=bool(log_stdout),
        )


@dataclass(frozen=True)
class ProcessTaskResult:
    request: ProcessTaskRequest
    exit_code: int
    output: str
    output_truncated: bool = False


@dataclass(frozen=True)
class ProcessTaskStartFailure:
    request: ProcessTaskRequest
    message: str


class ProcessTaskRunner(QObject):
    """Own QProcess, cancellation, output capture, and teardown."""

    outputAvailable = Signal(str)
    finished = Signal(object)
    failedToStart = Signal(object)
    stateChanged = Signal()
    _CAPTURE_LIMIT_BYTES = 2 * 1024 * 1024

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._request: ProcessTaskRequest | None = None
        self._process: QProcess | None = None
        self._output = bytearray()
        self._output_truncated = False
        self._shutting_down = False

    @property
    def busy(self) -> bool:
        return self._request is not None and self._process is not None

    @property
    def kind(self) -> str:
        return self._request.kind if self._request else ""

    @property
    def label(self) -> str:
        return self._request.label if self._request else ""

    @property
    def contract(self) -> ProcessTaskContract:
        if self._request is None:
            return ProcessTaskContract(ProcessAccess.TASK_SLOT)
        return self._request.contract

    @property
    def cancelable(self) -> bool:
        return self.busy and self.contract.cancelable

    def start(self, request: ProcessTaskRequest) -> bool:
        if self._shutting_down or self.busy:
            return False

        process = QProcess(self)
        process.setWorkingDirectory(str(request.working_directory))
        process.setProcessChannelMode(QProcess.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        for key, value in request.environment.items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)

        self._request = request
        self._process = process
        self._output.clear()
        self._output_truncated = False
        process.readyReadStandardOutput.connect(
            lambda process=process: self._read_output(process)
        )
        process.finished.connect(
            lambda exit_code, _status, process=process: self._finished(
                process,
                int(exit_code),
            )
        )
        process.errorOccurred.connect(
            lambda error, process=process: self._process_error(process, error)
        )
        # One process group covers docker/SSH descendants for cancellation.
        process.start("/usr/bin/setsid", [request.program, *request.arguments])
        self.stateChanged.emit()
        return True

    def cancel(self) -> bool:
        process = self._process
        if process is None or process.state() == QProcess.NotRunning:
            return False
        pid = int(process.processId())
        if pid > 0:
            try:
                os.killpg(pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            except PermissionError:
                process.terminate()
        QTimer.singleShot(
            5000,
            lambda process=process: self._kill_if_running(process),
        )
        return True

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        process = self._process
        if process is None:
            return
        self.cancel()
        process.waitForFinished(1500)
        if process.state() != QProcess.NotRunning:
            self._kill_process(process)
            process.waitForFinished(500)
        if self._process is process:
            self._reset(process)

    def _read_output(self, process: QProcess) -> None:
        if process is not self._process:
            return
        chunk = bytes(process.readAllStandardOutput())
        if not chunk:
            return
        self._output.extend(chunk)
        overflow = len(self._output) - self._CAPTURE_LIMIT_BYTES
        if overflow > 0:
            del self._output[:overflow]
            self._output_truncated = True
        request = self._request
        if request is not None and request.log_stdout:
            self.outputAvailable.emit(
                chunk.decode("utf-8", errors="replace").rstrip()
            )

    def _finished(self, process: QProcess, exit_code: int) -> None:
        if process is not self._process or self._request is None:
            return
        self._read_output(process)
        result = ProcessTaskResult(
            request=self._request,
            exit_code=int(exit_code),
            output=self._output.decode("utf-8", errors="replace").strip(),
            output_truncated=self._output_truncated,
        )
        self._reset(process)
        if not self._shutting_down:
            self.finished.emit(result)

    def _process_error(
        self,
        process: QProcess,
        error: QProcess.ProcessError,
    ) -> None:
        if (
            process is not self._process
            or self._request is None
            or error != QProcess.FailedToStart
        ):
            return
        failure = ProcessTaskStartFailure(
            request=self._request,
            message=f"任务无法启动：{process.errorString() or error}",
        )
        self._reset(process)
        if not self._shutting_down:
            self.failedToStart.emit(failure)

    def _kill_if_running(self, process: QProcess) -> None:
        if (
            process is self._process
            and process.state() != QProcess.NotRunning
        ):
            self._kill_process(process)

    @staticmethod
    def _kill_process(process: QProcess) -> None:
        pid = int(process.processId())
        if pid > 0:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                process.kill()

    def _reset(self, process: QProcess) -> None:
        if process is not self._process:
            return
        self._request = None
        self._process = None
        self._output.clear()
        self._output_truncated = False
        process.deleteLater()
        self.stateChanged.emit()
