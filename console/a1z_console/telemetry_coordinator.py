"""Independent polling and freshness lifecycle for robot telemetry."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Empty, SimpleQueue
from threading import Lock
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from .profiles import RuntimeProfile
from .protocol import A1ZProtocolClient, BackendMismatchError


TelemetryClientFactory = Callable[[RuntimeProfile], A1ZProtocolClient]
PollBlocked = Callable[[], bool]
MonotonicClock = Callable[[], float]


@dataclass(frozen=True)
class TelemetryResult:
    """One current-profile read result ready for state projection."""

    success: bool
    profile_name: str
    status: dict[str, Any] = field(default_factory=dict)
    info: dict[str, Any] | None = None
    error: str = ""
    mismatch: bool = False
    timing_changed: bool = False
    freshness_changed: bool = False


class TelemetryCoordinator(QObject):
    """Own read transport, poll cadence, profile epochs, and sample age."""

    resultAvailable = Signal(object)
    ageChanged = Signal(bool)
    stateChanged = Signal()

    def __init__(
        self,
        profile: RuntimeProfile,
        parent: QObject | None = None,
        *,
        poll_blocked: PollBlocked | None = None,
        client_factory: TelemetryClientFactory = A1ZProtocolClient,
        clock: MonotonicClock = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._poll_blocked = poll_blocked or (lambda: False)
        self._client_factory = client_factory
        self._clock = clock
        self._generation = 0
        self._pending = False
        self._monitoring = False
        self._shutting_down = False
        self._has_info = False
        self._info_refresh_counter = 0
        self._age_ms = -1
        self._last_received_monotonic = 0.0
        self._inflight_count = 0
        self._active_client_lock = Lock()
        self._active_client: object | None = None
        self._results: SimpleQueue[dict[str, Any]] = SimpleQueue()
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="a1z-console-telemetry",
        )

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(700)
        self._poll_timer.timeout.connect(self.refresh)

        self._age_timer = QTimer(self)
        self._age_timer.setInterval(200)
        self._age_timer.timeout.connect(self._update_age)

        # Worker callbacks touch only this Python queue. Results are projected
        # on the GUI thread so QObject teardown cannot race a late socket read.
        self._result_timer = QTimer(self)
        self._result_timer.setInterval(10)
        self._result_timer.timeout.connect(self._drain_results)

    @property
    def age_ms(self) -> int:
        return self._age_ms

    @property
    def fresh(self) -> bool:
        return 0 <= self._age_ms <= 2000

    @property
    def pending(self) -> bool:
        return self._pending

    @property
    def monitoring(self) -> bool:
        return self._monitoring

    @property
    def poll_timer_active(self) -> bool:
        return self._poll_timer.isActive()

    @property
    def age_timer_active(self) -> bool:
        return self._age_timer.isActive()

    def select_profile(
        self,
        profile: RuntimeProfile,
        *,
        notify: bool = True,
    ) -> None:
        """Reset freshness and invalidate late reads from the old endpoint."""

        if self._shutting_down:
            return
        previous_age = self._age_ms
        previous_fresh = self.fresh
        self._profile = profile
        self._generation += 1
        self._cancel_active_request()
        self._pending = False
        self._has_info = False
        self._info_refresh_counter = 0
        self._age_ms = -1
        self._last_received_monotonic = 0.0
        if notify and previous_age != self._age_ms:
            self.ageChanged.emit(previous_fresh != self.fresh)
        if self._monitoring:
            QTimer.singleShot(0, lambda: self.refresh(force_info=True))

    def start_monitoring(self) -> None:
        if self._monitoring or self._shutting_down:
            return
        self._monitoring = True
        self._poll_timer.start()
        self._age_timer.start()
        QTimer.singleShot(0, lambda: self.refresh(force_info=True))

    def refresh(self, force_info: bool = False) -> bool:
        """Start one read unless another read or explicit task blocks it."""

        if self._shutting_down or self._pending or self._poll_blocked():
            return False
        self._pending = True
        self.stateChanged.emit()
        generation = self._generation
        profile = self._profile
        result_queue = self._results
        client_factory = self._client_factory
        self._info_refresh_counter += 1
        include_info = (
            bool(force_info)
            or not self._has_info
            or self._info_refresh_counter >= 8
        )
        if include_info:
            self._info_refresh_counter = 0
        self._inflight_count += 1

        def operation() -> dict[str, Any]:
            client = client_factory(profile)
            if not self._claim_client(client, generation):
                raise RuntimeError("遥测会话已关闭")
            try:
                info: dict[str, Any] | None = None
                if include_info:
                    info = client.request("info", timeout_s=2.5)
                    actual = str(info.get("backend", ""))
                    if actual != profile.expected_backend:
                        raise BackendMismatchError(
                            "后端身份不匹配："
                            f"期望 {profile.expected_backend}，"
                            f"实际 {actual or 'unknown'}"
                        )
                status = client.request("status", timeout_s=2.5)
            finally:
                self._release_client(client)
            return {
                "generation": generation,
                "profile_name": profile.name,
                "status": status,
                "info": info,
            }

        future = self._executor.submit(operation)

        def done(completed: Future[dict[str, Any]]) -> None:
            try:
                payload = {"ok": True, **completed.result()}
            except Exception as exc:
                payload = {
                    "ok": False,
                    "generation": generation,
                    "profile_name": profile.name,
                    "error": str(exc),
                    "mismatch": isinstance(exc, BackendMismatchError),
                }
            result_queue.put(payload)

        future.add_done_callback(done)
        if not self._result_timer.isActive():
            self._result_timer.start()
        return True

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._monitoring = False
        self._generation += 1
        self._pending = False
        self.stateChanged.emit()
        self._poll_timer.stop()
        self._age_timer.stop()
        self._result_timer.stop()
        self._cancel_active_request()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _claim_client(self, client: object, generation: int) -> bool:
        with self._active_client_lock:
            if self._shutting_down or generation != self._generation:
                should_cancel = True
            else:
                if self._active_client is not None:
                    raise RuntimeError("遥测请求生命周期发生重叠")
                self._active_client = client
                should_cancel = False
        if should_cancel:
            self._cancel_client(client)
            return False
        return True

    def _release_client(self, client: object) -> None:
        with self._active_client_lock:
            if self._active_client is client:
                self._active_client = None

    def _cancel_active_request(self) -> None:
        with self._active_client_lock:
            client = self._active_client
        if client is not None:
            self._cancel_client(client)

    @staticmethod
    def _cancel_client(client: object) -> None:
        cancel = getattr(client, "cancel_pending_requests", None)
        if callable(cancel):
            cancel()

    def _drain_results(self) -> None:
        if self._shutting_down:
            return
        while True:
            try:
                payload = self._results.get_nowait()
            except Empty:
                break
            self._inflight_count = max(0, self._inflight_count - 1)
            self._handle_result(payload)
        if self._inflight_count == 0:
            self._result_timer.stop()

    def _handle_result(self, payload: dict[str, Any]) -> None:
        if int(payload.get("generation", -1)) != self._generation:
            return
        self._pending = False
        self.stateChanged.emit()
        profile_name = str(payload.get("profile_name", self._profile.name))
        if not payload.get("ok"):
            self.resultAvailable.emit(
                TelemetryResult(
                    success=False,
                    profile_name=profile_name,
                    error=str(payload.get("error", "")),
                    mismatch=bool(payload.get("mismatch", False)),
                )
            )
            return

        info_value = payload.get("info")
        info = dict(info_value) if isinstance(info_value, dict) else None
        self._has_info = self._has_info or info is not None
        previous_age = self._age_ms
        previous_fresh = self.fresh
        self._last_received_monotonic = self._clock()
        self._age_ms = 0
        self.resultAvailable.emit(
            TelemetryResult(
                success=True,
                profile_name=profile_name,
                status=dict(payload.get("status", {}) or {}),
                info=info,
                timing_changed=previous_age != self._age_ms,
                freshness_changed=previous_fresh != self.fresh,
            )
        )

    def _update_age(self) -> None:
        previous_fresh = self.fresh
        if self._last_received_monotonic <= 0.0:
            age = -1
        else:
            age = int(
                (self._clock() - self._last_received_monotonic) * 1000.0
            )
        if age == self._age_ms:
            return
        self._age_ms = age
        self.ageChanged.emit(previous_fresh != self.fresh)
