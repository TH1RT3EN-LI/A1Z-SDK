"""Independent lifecycle and state owner for the RGB-D console bridge."""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from queue import Empty, SimpleQueue
from threading import Lock
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from .camera_protocol import CameraProtocolClient
from .profiles import RuntimeProfile


CameraClientFactory = Callable[[RuntimeProfile], CameraProtocolClient]


@dataclass(frozen=True)
class CameraManualResult:
    """Result projected into the console's global operation feedback."""

    label: str
    success: bool
    error: str = ""
    details: str = ""


class CameraCoordinator(QObject):
    """Own camera polling, requests, preview state, and worker teardown."""

    stateChanged = Signal()
    previewChanged = Signal()
    logAvailable = Signal(str)
    manualStarted = Signal(str)
    manualFinished = Signal(object)

    _LABELS = {
        "camera_status": "读取 RGB-D 状态",
        "camera_capture": "采集 RGB-D 预览",
        "camera_extrinsic": "读取相机外参",
    }

    def __init__(
        self,
        profile: RuntimeProfile,
        parent: QObject | None = None,
        *,
        client_factory: CameraClientFactory = CameraProtocolClient,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._client_factory = client_factory
        self._generation = 0
        self._summary = "离线"
        self._details = ""
        self._preview_source = ""
        self._bridge_online = False
        self._ready = False
        self._pending = False
        self._preview_enabled = False
        self._poll_counter = 0
        self._last_state = ""
        self._monitoring = False
        self._shutting_down = False
        self._inflight_count = 0
        self._active_client_lock = Lock()
        self._active_client: object | None = None
        self._results: SimpleQueue[dict[str, Any]] = SimpleQueue()
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="a1z-console-camera",
        )

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self.poll)

        # Workers only write a Python queue. This GUI-thread timer prevents a
        # late worker from emitting into a QObject while Qt is tearing down.
        self._result_timer = QTimer(self)
        self._result_timer.setInterval(10)
        self._result_timer.timeout.connect(self._drain_results)

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def details(self) -> str:
        return self._details

    @property
    def preview_source(self) -> str:
        return self._preview_source

    @property
    def bridge_online(self) -> bool:
        return self._bridge_online

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def busy(self) -> bool:
        return self._pending

    @property
    def monitoring(self) -> bool:
        return self._monitoring

    @property
    def timer_active(self) -> bool:
        return self._poll_timer.isActive()

    @property
    def state_fingerprint(self) -> tuple[Any, ...]:
        return (
            self._summary,
            self._details,
            self._bridge_online,
            self._ready,
            self._pending,
        )

    def select_profile(
        self,
        profile: RuntimeProfile,
        *,
        notify: bool = True,
    ) -> None:
        """Invalidate all state and late results from the previous profile."""

        if self._shutting_down:
            return
        self._profile = profile
        self._generation += 1
        self._cancel_active_request()
        self._summary = "离线"
        self._details = "检查中…"
        preview_changed = bool(self._preview_source)
        self._preview_source = ""
        self._bridge_online = False
        self._ready = False
        self._pending = False
        self._poll_counter = 0
        self._last_state = ""
        if preview_changed:
            self.previewChanged.emit()
        if notify:
            self.stateChanged.emit()
        if self._monitoring:
            QTimer.singleShot(100, self.poll)

    def start_monitoring(self) -> None:
        if self._monitoring or self._shutting_down:
            return
        self._monitoring = True
        self._poll_timer.start()
        QTimer.singleShot(100, self.poll)

    def set_preview_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._preview_enabled == enabled or self._shutting_down:
            return
        self._preview_enabled = enabled
        self._poll_counter = 0
        if enabled and self._monitoring:
            self.poll()

    def request_manual(self, command: str) -> str:
        """Start one explicit operator request, returning an error if rejected."""

        if command not in self._LABELS:
            return "相机命令不在允许列表中"
        if self._shutting_down:
            return "相机会话正在关闭"
        if self._pending:
            return "已有相机请求正在执行"
        self._request(command, manual=True)
        return ""

    def poll(self) -> None:
        if self._shutting_down or not self._monitoring or self._pending:
            return
        self._poll_counter += 1
        if self._preview_enabled:
            command = "camera_capture" if self._ready else "camera_status"
            self._request(command, manual=False)
        elif self._poll_counter == 1 or self._poll_counter >= 3:
            self._poll_counter = 0
            self._request("camera_status", manual=False)

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._monitoring = False
        self._generation += 1
        self._pending = False
        self._poll_timer.stop()
        self._result_timer.stop()
        self._cancel_active_request()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _request(self, command: str, *, manual: bool) -> None:
        label = self._LABELS[command]
        args = {"preview_max_width": 960} if command == "camera_capture" else {}
        profile = self._profile
        generation = self._generation
        result_queue = self._results
        client_factory = self._client_factory
        self._pending = True
        self._inflight_count += 1
        if manual:
            self.manualStarted.emit(label)
        self.stateChanged.emit()

        def operation() -> dict[str, Any]:
            client = client_factory(profile)
            if not self._claim_client(client, generation):
                raise RuntimeError("相机会话已关闭")
            try:
                data = client.request(
                    command,
                    args,
                    timeout_s=(
                        5.0 if command == "camera_capture" else 3.0
                    ),
                )
            finally:
                self._release_client(client)
            return {
                "generation": generation,
                "command": command,
                "label": label,
                "manual": manual,
                "data": data,
            }

        future = self._executor.submit(operation)

        def done(completed: Future[dict[str, Any]]) -> None:
            try:
                payload = {"ok": True, **completed.result()}
            except Exception as exc:
                payload = {
                    "ok": False,
                    "generation": generation,
                    "command": command,
                    "label": label,
                    "manual": manual,
                    "error": str(exc),
                }
            result_queue.put(payload)

        future.add_done_callback(done)
        if not self._result_timer.isActive():
            self._result_timer.start()

    def _claim_client(self, client: object, generation: int) -> bool:
        with self._active_client_lock:
            if self._shutting_down or generation != self._generation:
                should_cancel = True
            else:
                if self._active_client is not None:
                    raise RuntimeError("相机请求生命周期发生重叠")
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
                result = self._results.get_nowait()
            except Empty:
                break
            self._inflight_count = max(0, self._inflight_count - 1)
            self._handle_result(result)
        if self._inflight_count == 0:
            self._result_timer.stop()

    def _handle_result(self, result: dict[str, Any]) -> None:
        if int(result.get("generation", -1)) != self._generation:
            return
        self._pending = False
        manual = bool(result.get("manual", False))
        label = str(result.get("label", "相机请求"))
        if not result.get("ok"):
            self._apply_failure(
                label,
                str(result.get("error", "相机桥请求失败")),
                manual=manual,
            )
            return

        try:
            self._apply_success(
                str(result.get("command", "")),
                dict(result.get("data", {}) or {}),
            )
        except (TypeError, ValueError) as exc:
            self._apply_failure(
                label,
                f"相机桥响应字段无效：{exc}",
                manual=manual,
            )
            return

        if manual:
            self.manualFinished.emit(
                CameraManualResult(
                    label=label,
                    success=True,
                    details=self._details,
                )
            )
        self.stateChanged.emit()

    def _apply_failure(self, label: str, message: str, *, manual: bool) -> None:
        self._bridge_online = False
        self._ready = False
        self._summary = "相机桥离线"
        self._details = message
        state = f"error:{message}"
        if manual:
            self.manualFinished.emit(
                CameraManualResult(
                    label=label,
                    success=False,
                    error=message,
                    details=message,
                )
            )
        elif state != self._last_state:
            self.logAvailable.emit(f"相机链路离线：{message}")
        self._last_state = state
        self.stateChanged.emit()

    def _apply_success(self, command: str, data: dict[str, Any]) -> None:
        self._bridge_online = True
        ready = bool(data.get("ready", True))
        self._ready = ready
        width = int(data.get("width", 0) or 0)
        height = int(data.get("height", 0) or 0)
        source = str(data.get("camera_source", "ROS"))
        if width > 0 and height > 0:
            self._summary = (
                f"{width}×{height} · {source} · "
                f"{'在线' if ready else '等待帧'}"
            )
        else:
            self._summary = (
                f"{source} · {'在线' if ready else '等待 RGB-D 帧'}"
            )

        if command == "camera_capture":
            preview_b64 = str(data.get("preview_png_b64", ""))
            preview_mime = str(data.get("preview_mime", "image/png"))
            if preview_b64:
                self._set_preview_source(
                    f"data:{preview_mime};base64,{preview_b64}"
                )
            depth_range = data.get("depth_range_m")
            depth_text = ""
            if isinstance(depth_range, list) and len(depth_range) == 2:
                depth_text = (
                    f" · 深度 {float(depth_range[0]):.3f}–"
                    f"{float(depth_range[1]):.3f} m"
                )
            self._details = (
                f"RGB {data.get('rgb_encoding', '—')} · "
                f"Depth {data.get('depth_encoding', '—')} · "
                f"同步差 {float(data.get('sync_delta_ms', 0.0)):.1f} ms"
                f"{depth_text}"
            )
        elif command == "camera_extrinsic":
            self._details = (
                f"{data.get('camera_frame_id', 'camera')} → "
                f"{data.get('target_frame_id', 'target')} · "
                f"{data.get('lookup_mode', 'unknown')} · "
                "T="
                f"{json.dumps(data.get('extrinsic_camera_to_target'), ensure_ascii=False)}"
            )
        else:
            self._details = (
                f"{data.get('color_topic', '—')} + "
                f"{data.get('depth_topic', '—')} · "
                f"同步={'是' if data.get('synchronized') else '否'} · "
                f"外参={'就绪' if data.get('extrinsic_ready') else '等待'}"
            )

        state = f"ready:{ready}:{width}x{height}:{source}"
        if state != self._last_state:
            self.logAvailable.emit(f"相机链路：{self._summary}")
        self._last_state = state

    def _set_preview_source(self, source: str) -> None:
        source = str(source)
        if source == self._preview_source:
            return
        self._preview_source = source
        self.previewChanged.emit()
