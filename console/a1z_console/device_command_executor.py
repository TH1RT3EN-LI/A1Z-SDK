"""Priority-aware lifecycle owner for device commands and emergency stop."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Empty, SimpleQueue
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from .interaction_policy import ResourceEffect
from .protocol import AmbiguousCommandError


DeviceOperation = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class DeviceCommandRequest:
    label: str
    operation: DeviceOperation
    effects: ResourceEffect
    result_handler: str = ""


@dataclass(frozen=True)
class EmergencyCommandRequest:
    label: str
    operation: DeviceOperation


@dataclass(frozen=True)
class DeviceCommandResult:
    label: str
    sequence: int
    effects: ResourceEffect
    result_handler: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    ambiguous: bool = False
    superseded_by_emergency: bool = False
    stale_profile: bool = False


@dataclass(frozen=True)
class EmergencyCommandResult:
    label: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    ambiguous: bool = False
    stale_profile: bool = False


@dataclass(frozen=True)
class _CommandSubmission:
    request: DeviceCommandRequest
    sequence: int
    profile_generation: int
    safety_epoch: int


@dataclass(frozen=True)
class _EmergencySubmission:
    request: EmergencyCommandRequest
    profile_generation: int


class DeviceCommandExecutor(QObject):
    """Own normal serialization and an independent emergency priority lane."""

    commandFinished = Signal(object)
    emergencyFinished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._profile_generation = 0
        self._safety_epoch = 0
        self._sequence = 0
        self._command_submission: _CommandSubmission | None = None
        self._emergency_submission: _EmergencySubmission | None = None
        self._shutting_down = False
        self._inflight_count = 0
        self._results: SimpleQueue[dict[str, Any]] = SimpleQueue()
        self._command_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="a1z-console-command",
        )
        self._emergency_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="a1z-console-estop",
        )
        self._result_timer = QTimer(self)
        self._result_timer.setInterval(10)
        self._result_timer.timeout.connect(self._drain_results)

    @property
    def command_busy(self) -> bool:
        return self._command_submission is not None

    @property
    def emergency_busy(self) -> bool:
        return self._emergency_submission is not None

    @property
    def current_effects(self) -> ResourceEffect:
        submission = self._command_submission
        if submission is None:
            return ResourceEffect.NONE
        return submission.request.effects

    @property
    def current_result_handler(self) -> str:
        submission = self._command_submission
        if submission is None:
            return ""
        return submission.request.result_handler

    def select_profile(self) -> None:
        """Invalidate any result produced for the previous endpoint."""

        if not self._shutting_down:
            self._profile_generation += 1

    def submit_command(self, request: DeviceCommandRequest) -> int | None:
        if self._shutting_down or self.command_busy or self.emergency_busy:
            return None
        self._sequence += 1
        submission = _CommandSubmission(
            request=request,
            sequence=self._sequence,
            profile_generation=self._profile_generation,
            safety_epoch=self._safety_epoch,
        )
        self._command_submission = submission
        self._inflight_count += 1
        self._submit(
            lane="command",
            submission=submission,
            operation=request.operation,
            pool=self._command_pool,
        )
        return submission.sequence

    def submit_emergency(self, request: EmergencyCommandRequest) -> bool:
        if self._shutting_down or self.emergency_busy:
            return False
        self._safety_epoch += 1
        submission = _EmergencySubmission(
            request=request,
            profile_generation=self._profile_generation,
        )
        self._emergency_submission = submission
        self._inflight_count += 1
        self._submit(
            lane="emergency",
            submission=submission,
            operation=request.operation,
            pool=self._emergency_pool,
        )
        return True

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._profile_generation += 1
        self._safety_epoch += 1
        self._command_submission = None
        self._emergency_submission = None
        self._result_timer.stop()
        self._command_pool.shutdown(wait=False, cancel_futures=True)
        self._emergency_pool.shutdown(wait=False, cancel_futures=True)

    def _submit(
        self,
        *,
        lane: str,
        submission: _CommandSubmission | _EmergencySubmission,
        operation: DeviceOperation,
        pool: ThreadPoolExecutor,
    ) -> None:
        result_queue = self._results
        future = pool.submit(operation)

        def done(completed: Future[dict[str, Any]]) -> None:
            try:
                payload = {
                    "lane": lane,
                    "submission": submission,
                    "success": True,
                    "data": completed.result(),
                }
            except Exception as exc:
                payload = {
                    "lane": lane,
                    "submission": submission,
                    "success": False,
                    "error": str(exc),
                    "ambiguous": isinstance(exc, AmbiguousCommandError),
                }
            result_queue.put(payload)

        future.add_done_callback(done)
        if not self._result_timer.isActive():
            self._result_timer.start()

    def _drain_results(self) -> None:
        if self._shutting_down:
            return
        while True:
            try:
                payload = self._results.get_nowait()
            except Empty:
                break
            self._inflight_count = max(0, self._inflight_count - 1)
            if payload.get("lane") == "emergency":
                self._finish_emergency(payload)
            else:
                self._finish_command(payload)
        if self._inflight_count == 0:
            self._result_timer.stop()

    def _finish_command(self, payload: dict[str, Any]) -> None:
        submission = payload.get("submission")
        if not isinstance(submission, _CommandSubmission):
            return
        if self._command_submission is submission:
            self._command_submission = None
        request = submission.request
        success = bool(payload.get("success", False))
        data_value = payload.get("data")
        if success and not isinstance(data_value, dict):
            success = False
            error = "设备命令执行函数没有返回对象"
            data: dict[str, Any] = {}
        else:
            error = str(payload.get("error", ""))
            data = dict(data_value or {})
        self.commandFinished.emit(
            DeviceCommandResult(
                label=request.label,
                sequence=submission.sequence,
                effects=request.effects,
                result_handler=request.result_handler,
                success=success,
                data=data,
                error=error,
                ambiguous=bool(payload.get("ambiguous", False)),
                superseded_by_emergency=(
                    submission.safety_epoch != self._safety_epoch
                ),
                stale_profile=(
                    submission.profile_generation != self._profile_generation
                ),
            )
        )

    def _finish_emergency(self, payload: dict[str, Any]) -> None:
        submission = payload.get("submission")
        if not isinstance(submission, _EmergencySubmission):
            return
        if self._emergency_submission is submission:
            self._emergency_submission = None
        request = submission.request
        success = bool(payload.get("success", False))
        data_value = payload.get("data")
        if success and not isinstance(data_value, dict):
            success = False
            error = "软急停执行函数没有返回对象"
            data: dict[str, Any] = {}
        else:
            error = str(payload.get("error", ""))
            data = dict(data_value or {})
        self.emergencyFinished.emit(
            EmergencyCommandResult(
                label=request.label,
                success=success,
                data=data,
                error=error,
                ambiguous=bool(payload.get("ambiguous", False)),
                stale_profile=(
                    submission.profile_generation != self._profile_generation
                ),
            )
        )
