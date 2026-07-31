"""Qt-facing controller with serialized, fail-closed robot operations."""

from __future__ import annotations

import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QObject,
    Property,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
    Slot,
)

from .camera_protocol import CameraProtocolClient
from .plan_parser import summarize_pipeline
from .profiles import RuntimeProfile, load_profiles
from .protocol import (
    A1ZProtocolClient,
    AmbiguousCommandError,
    BackendMismatchError,
    ProtocolError,
)


class _ThreadBridge(QObject):
    operationFinished = Signal(object)
    telemetryFinished = Signal(object)
    emergencyFinished = Signal(object)
    cameraFinished = Signal(object)


class ConsoleController(QObject):
    stateChanged = Signal()
    logsChanged = Signal()
    planChanged = Signal()
    preflightChanged = Signal()
    operationFinished = Signal(str, bool, str)

    def __init__(self, repo_root: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._repo_root = repo_root.resolve()
        self._profiles = load_profiles(self._repo_root)
        self._profile_name = "sim"
        self._connected = False
        self._backend_matched = False
        self._backend = ""
        self._control_mode = ""
        self._command_busy = False
        self._task_busy = False
        self._task_motion = False
        self._task_kind = ""
        self._task_label = ""
        self._emergency_busy = False
        self._uncertain = False
        self._estopped = False
        self._telemetry_age_ms = -1
        self._last_telemetry_monotonic = 0.0
        self._status_text = "等待连接"
        self._last_error = ""
        self._joint_rows = self._empty_joint_rows()
        self._gripper: float | None = None
        self._gripper_target: float | None = None
        self._info: dict[str, Any] = {}
        self._camera_summary = "相机桥未连接"
        self._camera_details = "等待 ROS RGB-D 链路"
        self._camera_preview_source = ""
        self._camera_bridge_online = False
        self._camera_ready = False
        self._camera_busy = False
        self._camera_pending = False
        self._camera_preview_enabled = False
        self._camera_poll_counter = 0
        self._camera_last_state = ""
        self._recording_summary = "未录制"
        self._gripper_free_drive = False
        self._gravity_comp_factor = 1.0
        self._ee_pose_text = "尚未读取 FK"
        self._ee_axis_text = "读取 FK 后显示 grasp_tcp 三轴在 Base 中的方向"
        self._ee_motion_text = "尚未执行末端点动"
        self._logs = ""
        self._log_lines: list[str] = []
        self._plan_summary: dict[str, Any] = {}
        self._preflight_items: list[dict[str, Any]] = []
        self._pipeline_output_dir = ""
        self._pending_process_output = bytearray()
        self._telemetry_pending = False
        self._info_refresh_counter = 0
        self._profile_generation = 0
        self._process: QProcess | None = None
        self._process_completion: Callable[[int, str], None] | None = None
        self._operation_sequence = 0
        self._state_lock = threading.Lock()

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="a1z-console-command",
        )
        self._emergency_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="a1z-console-estop",
        )
        self._camera_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="a1z-console-camera",
        )
        self._bridge = _ThreadBridge(self)
        self._bridge.operationFinished.connect(self._on_operation_finished)
        self._bridge.telemetryFinished.connect(self._on_telemetry_finished)
        self._bridge.emergencyFinished.connect(self._on_emergency_finished)
        self._bridge.cameraFinished.connect(self._on_camera_finished)

        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.setInterval(700)
        self._telemetry_timer.timeout.connect(self._poll_telemetry)
        self._telemetry_timer.start()

        self._age_timer = QTimer(self)
        self._age_timer.setInterval(200)
        self._age_timer.timeout.connect(self._update_telemetry_age)
        self._age_timer.start()

        self._camera_timer = QTimer(self)
        self._camera_timer.setInterval(1000)
        self._camera_timer.timeout.connect(self._poll_camera)
        self._camera_timer.start()

        self._append_log("A1Z Console 已启动；运动命令自动重发已禁用。")
        QTimer.singleShot(50, self.refreshNow)
        QTimer.singleShot(150, self._poll_camera)

    # ------------------------------------------------------------------
    # Qt properties
    # ------------------------------------------------------------------

    @Property(str, notify=stateChanged)
    def profile(self) -> str:
        return self._profile_name

    @Property(str, notify=stateChanged)
    def profileLabel(self) -> str:
        return self._profile.label

    @Property(str, notify=stateChanged)
    def expectedBackend(self) -> str:
        return self._profile.expected_backend

    @Property(str, notify=stateChanged)
    def endpoint(self) -> str:
        return f"{self._profile.host}:{self._profile.port}"

    @Property(bool, notify=stateChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(bool, notify=stateChanged)
    def backendMatched(self) -> bool:
        return self._backend_matched

    @Property(str, notify=stateChanged)
    def backend(self) -> str:
        return self._backend or "—"

    @Property(str, notify=stateChanged)
    def backendLabel(self) -> str:
        return {
            "isaacsim": "Isaac Sim 仿真",
            "socketcan": "SocketCAN 真机",
            "mock": "Mock 离线",
        }.get(self._backend, self._backend or "—")

    @Property(str, notify=stateChanged)
    def controlMode(self) -> str:
        return self._control_mode or "—"

    @Property(str, notify=stateChanged)
    def controlModeLabel(self) -> str:
        return {
            "gravity_comp_effort": "零力漂浮",
            "position_hold": "位置保持",
        }.get(self._control_mode, self._control_mode or "—")

    @Property(str, notify=stateChanged)
    def sdkDynamicsSummary(self) -> str:
        frequency = self._info.get("control_freq_hz")
        kp = list(self._info.get("default_kp", []) or [])
        kd = list(self._info.get("default_kd", []) or [])
        parts = []
        if frequency is not None:
            parts.append(f"{int(frequency)} Hz")
        if kp:
            parts.append("Kp [" + ", ".join(f"{float(v):g}" for v in kp[:6]) + "]")
        if kd:
            parts.append("Kd [" + ", ".join(f"{float(v):g}" for v in kd[:6]) + "]")
        torque_limit = self._info.get("gripper_torque_limit_nm")
        if torque_limit is not None:
            parts.append(f"G1Z 上限 {float(torque_limit):g} Nm")
        return " · ".join(parts) if parts else "等待 SDK 参数回读"

    @Property(bool, notify=stateChanged)
    def commandBusy(self) -> bool:
        return self._command_busy

    @Property(bool, notify=stateChanged)
    def taskBusy(self) -> bool:
        return self._task_busy

    @Property(bool, notify=stateChanged)
    def taskMotion(self) -> bool:
        return self._task_motion

    @Property(str, notify=stateChanged)
    def taskLabel(self) -> str:
        return self._task_label

    @Property(bool, notify=stateChanged)
    def emergencyBusy(self) -> bool:
        return self._emergency_busy

    @Property(bool, notify=stateChanged)
    def commandOutcomeUncertain(self) -> bool:
        return self._uncertain

    @Property(bool, notify=stateChanged)
    def estopped(self) -> bool:
        return self._estopped

    @Property(int, notify=stateChanged)
    def telemetryAgeMs(self) -> int:
        return self._telemetry_age_ms

    @Property(bool, notify=stateChanged)
    def telemetryFresh(self) -> bool:
        return 0 <= self._telemetry_age_ms <= 2000

    @Property(bool, notify=stateChanged)
    def motionEnabled(self) -> bool:
        return (
            self._connected
            and self._backend_matched
            and self.telemetryFresh
            and not self._command_busy
            and not self._task_busy
            and not self._uncertain
            and not self._estopped
        )

    @Property(str, notify=stateChanged)
    def motionGateText(self) -> str:
        if self._uncertain:
            return "上条命令结果不确定，请先核对现场并解除锁定"
        if self._estopped:
            return "软急停已锁定"
        if self._task_busy:
            return f"{self._task_label or '任务'}进行中"
        if self._command_busy:
            return "单命令事务执行中"
        if not self._connected:
            return "控制服务未连接"
        if not self._backend_matched:
            return "Real / Sim 后端身份不匹配"
        if not self.telemetryFresh:
            return "遥测已过期"
        return "就绪：一次点击只发送一次运动"

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=stateChanged)
    def lastError(self) -> str:
        return self._last_error

    @Property("QVariantList", notify=stateChanged)
    def joints(self) -> list[dict[str, Any]]:
        return self._joint_rows

    @Property(float, notify=stateChanged)
    def gripper(self) -> float:
        return -1.0 if self._gripper is None else self._gripper

    @Property(float, notify=stateChanged)
    def gripperMeasured(self) -> float:
        return -1.0 if self._gripper is None else self._gripper

    @Property(float, notify=stateChanged)
    def gripperTarget(self) -> float:
        return -1.0 if self._gripper_target is None else self._gripper_target

    @Property(str, notify=stateChanged)
    def cameraSummary(self) -> str:
        return self._camera_summary

    @Property(str, notify=stateChanged)
    def cameraDetails(self) -> str:
        return self._camera_details

    @Property(str, notify=stateChanged)
    def cameraPreviewSource(self) -> str:
        return self._camera_preview_source

    @Property(bool, notify=stateChanged)
    def cameraBridgeOnline(self) -> bool:
        return self._camera_bridge_online

    @Property(bool, notify=stateChanged)
    def cameraReady(self) -> bool:
        return self._camera_ready

    @Property(bool, notify=stateChanged)
    def cameraBusy(self) -> bool:
        return self._camera_busy

    @Property(str, notify=stateChanged)
    def recordingSummary(self) -> str:
        return self._recording_summary

    @Property(bool, notify=stateChanged)
    def gripperFreeDrive(self) -> bool:
        return self._gripper_free_drive

    @Property(float, notify=stateChanged)
    def gravityCompFactor(self) -> float:
        return self._gravity_comp_factor

    @Property(str, notify=stateChanged)
    def eePoseText(self) -> str:
        return self._ee_pose_text

    @Property(str, notify=stateChanged)
    def eeAxisText(self) -> str:
        return self._ee_axis_text

    @Property(str, notify=stateChanged)
    def eeMotionText(self) -> str:
        return self._ee_motion_text

    @Property(str, notify=logsChanged)
    def logs(self) -> str:
        return self._logs

    @Property(str, notify=planChanged)
    def latestPlanPath(self) -> str:
        return str(self._plan_summary.get("planPath", ""))

    @Property(str, notify=planChanged)
    def pipelineOutputDir(self) -> str:
        return self._pipeline_output_dir

    @Property(str, notify=planChanged)
    def planId(self) -> str:
        return str(self._plan_summary.get("planId", ""))

    @Property(str, notify=planChanged)
    def planFrame(self) -> str:
        return str(self._plan_summary.get("frameId", ""))

    @Property(str, notify=planChanged)
    def graspSummary(self) -> str:
        grasp = dict(self._plan_summary.get("grasp", {}) or {})
        if not grasp:
            return "尚无已计算抓取位姿"
        xyz = grasp.get("translationMm", [])
        xyz_text = ", ".join(f"{float(value):.1f}" for value in xyz)
        return (
            f"候选 #{grasp.get('rank', '—')} · score {float(grasp.get('score', 0.0)):.4f} · "
            f"宽度 {float(grasp.get('widthMm', 0.0)):.1f} mm · 相机坐标 [{xyz_text}] mm"
        )

    @Property("QVariantList", notify=planChanged)
    def planSegments(self) -> list[dict[str, Any]]:
        return list(self._plan_summary.get("segments", []) or [])

    @Property("QVariantList", notify=planChanged)
    def planSafety(self) -> list[dict[str, Any]]:
        return list(self._plan_summary.get("safety", []) or [])

    @Property(bool, notify=planChanged)
    def planSafetyPassed(self) -> bool:
        return bool(self._plan_summary.get("allSafetyPassed", False))

    @Property("QVariantList", notify=preflightChanged)
    def preflightItems(self) -> list[dict[str, Any]]:
        return self._preflight_items

    @property
    def _profile(self) -> RuntimeProfile:
        return self._profiles[self._profile_name]

    # ------------------------------------------------------------------
    # Profile, telemetry, and logging
    # ------------------------------------------------------------------

    @Slot(str)
    def setProfile(self, name: str) -> None:
        if name not in self._profiles or name == self._profile_name:
            return
        if self._command_busy or self._task_busy:
            self._set_error("命令或任务进行中，不能切换 Real / Sim 配置")
            return
        self._profile_name = name
        self._profile_generation += 1
        self._connected = False
        self._backend_matched = False
        self._backend = ""
        self._control_mode = ""
        self._last_telemetry_monotonic = 0.0
        self._telemetry_age_ms = -1
        self._last_error = ""
        self._status_text = f"已选择{self._profile.label}，正在核验后端"
        self._joint_rows = self._empty_joint_rows()
        self._gripper = None
        self._gripper_target = None
        self._gripper_free_drive = False
        self._gravity_comp_factor = 1.0
        self._ee_pose_text = "尚未读取 FK"
        self._ee_axis_text = "读取 FK 后显示 grasp_tcp 三轴在 Base 中的方向"
        self._ee_motion_text = "尚未执行末端点动"
        self._info = {}
        self._camera_summary = "相机桥未连接"
        self._camera_details = "正在核验所选配置的 ROS RGB-D 链路"
        self._camera_preview_source = ""
        self._camera_bridge_online = False
        self._camera_ready = False
        self._camera_busy = False
        self._camera_pending = False
        self._camera_poll_counter = 0
        self._camera_last_state = ""
        self._append_log(
            f"运行配置切换为 {self._profile.label}："
            f"{self._profile.expected_backend} @ {self.endpoint}"
        )
        self.stateChanged.emit()
        self.refreshNow()
        QTimer.singleShot(100, self._poll_camera)

    @Slot()
    def refreshNow(self) -> None:
        self._poll_telemetry(force_info=True)

    @Slot()
    def acknowledgeUncertain(self) -> None:
        if not self._uncertain:
            return
        self._uncertain = False
        self._status_text = "结果不确定锁已由操作员解除；请先刷新并确认机械臂状态"
        self._append_log("操作员解除“命令结果不确定”互锁。")
        self.stateChanged.emit()
        self.refreshNow()

    @Slot()
    def clearLogs(self) -> None:
        self._log_lines.clear()
        self._logs = ""
        self.logsChanged.emit()

    @Slot()
    def neutralizeUi(self) -> None:
        # Motion is edge-triggered and never held, so there is no zero command to
        # publish.  This hook documents and enforces that window deactivation
        # cannot leave a QML timer or key-repeat producer alive.
        self._append_log("窗口失焦：已确认不存在保持式运动输入。")

    def _poll_telemetry(self, force_info: bool = False) -> None:
        if self._telemetry_pending or self._command_busy:
            return
        if self._task_busy and self._task_motion:
            return
        self._telemetry_pending = True
        generation = self._profile_generation
        profile = self._profile
        self._info_refresh_counter += 1
        include_info = force_info or not self._info or self._info_refresh_counter >= 8
        if include_info:
            self._info_refresh_counter = 0

        def operation() -> dict[str, Any]:
            client = A1ZProtocolClient(profile)
            info: dict[str, Any] | None = None
            if include_info:
                info = client.request("info", timeout_s=2.5)
                actual = str(info.get("backend", ""))
                if actual != profile.expected_backend:
                    raise BackendMismatchError(
                        f"后端身份不匹配：期望 {profile.expected_backend}，实际 {actual or 'unknown'}"
                    )
            status = client.request("status", timeout_s=2.5)
            return {
                "generation": generation,
                "status": status,
                "info": info,
                "profile": profile.name,
            }

        future = self._executor.submit(operation)
        future.add_done_callback(self._telemetry_future_done)

    def _telemetry_future_done(self, future: Future[dict[str, Any]]) -> None:
        try:
            payload = {"ok": True, "data": future.result()}
        except Exception as exc:
            payload = {
                "ok": False,
                "error": str(exc),
                "mismatch": isinstance(exc, BackendMismatchError),
                "generation": self._profile_generation,
            }
        self._bridge.telemetryFinished.emit(payload)

    @Slot(object)
    def _on_telemetry_finished(self, payload: object) -> None:
        self._telemetry_pending = False
        result = dict(payload)
        if not result.get("ok"):
            self._connected = False
            self._backend_matched = False
            self._status_text = "后端身份冲突" if result.get("mismatch") else "控制服务离线"
            self._last_error = str(result.get("error", ""))
            self.stateChanged.emit()
            return

        data = dict(result["data"])
        if int(data.get("generation", -1)) != self._profile_generation:
            return
        info = data.get("info")
        if isinstance(info, dict):
            self._apply_info(info)
        self._apply_status(dict(data.get("status", {})))
        self._connected = True
        self._backend_matched = self._backend == self._profile.expected_backend
        self._last_error = ""
        self._status_text = "遥测在线"
        self._last_telemetry_monotonic = time.monotonic()
        self._telemetry_age_ms = 0
        self.stateChanged.emit()

    def _update_telemetry_age(self) -> None:
        if self._last_telemetry_monotonic <= 0.0:
            age = -1
        else:
            age = int((time.monotonic() - self._last_telemetry_monotonic) * 1000.0)
        if age != self._telemetry_age_ms:
            self._telemetry_age_ms = age
            if age > 3000 and self._connected:
                self._connected = False
                self._status_text = "遥测超时，运动已锁定"
            self.stateChanged.emit()

    def _apply_info(self, info: dict[str, Any]) -> None:
        self._info = dict(info)
        self._backend = str(info.get("backend", ""))
        self._control_mode = str(info.get("control_mode", ""))
        self._gripper_free_drive = bool(info.get("gripper_free_drive", False))
        self._gravity_comp_factor = float(info.get("gravity_comp_factor", 1.0))
        limits = dict(info.get("joint_limits_deg", {}) or {})
        rows = []
        for index, old in enumerate(self._joint_rows):
            pair = limits.get(f"J{index + 1}", [old["minimum"], old["maximum"]])
            rows.append(
                {
                    **old,
                    "minimum": float(pair[0]),
                    "maximum": float(pair[1]),
                }
            )
        self._joint_rows = rows

    def _apply_status(self, status: dict[str, Any]) -> None:
        positions = list(status.get("pos_deg", []) or [])
        velocities = list(status.get("vel_rad_s", []) or [])
        torques = list(status.get("torque_nm", []) or [])
        errors = list(status.get("error_codes", []) or [])
        temp_mos = list(status.get("temp_mos_c", []) or [])
        temp_rotor = list(status.get("temp_rotor_c", []) or [])
        rows = []
        for index in range(6):
            previous = self._joint_rows[index]
            rows.append(
                {
                    "name": f"J{index + 1}",
                    "position": float(positions[index]) if index < len(positions) else previous["position"],
                    "velocity": float(velocities[index]) if index < len(velocities) else 0.0,
                    "torque": float(torques[index]) if index < len(torques) else 0.0,
                    "minimum": previous["minimum"],
                    "maximum": previous["maximum"],
                    "errorCode": int(errors[index]) if index < len(errors) else 0,
                    "tempMos": float(temp_mos[index]) if index < len(temp_mos) else -1.0,
                    "tempRotor": float(temp_rotor[index]) if index < len(temp_rotor) else -1.0,
                }
            )
        self._joint_rows = rows
        legacy_gripper = status.get("gripper")
        measured = status.get("gripper_measured", legacy_gripper)
        target = status.get("gripper_target", legacy_gripper)
        self._gripper = (
            float(measured) if isinstance(measured, (int, float)) else None
        )
        self._gripper_target = (
            float(target) if isinstance(target, (int, float)) else None
        )
        self._estopped = bool(status.get("estopped", False))

    def _append_log(self, message: str) -> None:
        cleaned = str(message).strip()
        if not cleaned:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        for line in cleaned.splitlines():
            self._log_lines.append(f"[{stamp}] {line.rstrip()}")
        if len(self._log_lines) > 1200:
            self._log_lines = self._log_lines[-1000:]
        self._logs = "\n".join(self._log_lines)
        self.logsChanged.emit()

    def _set_error(self, message: str) -> None:
        self._last_error = str(message)
        self._status_text = "操作失败"
        self._append_log(f"错误：{message}")
        self.stateChanged.emit()

    @staticmethod
    def _empty_joint_rows() -> list[dict[str, Any]]:
        return [
            {
                "name": f"J{index + 1}",
                "position": 0.0,
                "velocity": 0.0,
                "torque": 0.0,
                "minimum": 0.0,
                "maximum": 0.0,
                "errorCode": 0,
                "tempMos": -1.0,
                "tempRotor": -1.0,
            }
            for index in range(6)
        ]

    # ------------------------------------------------------------------
    # Serialized SDK operations
    # ------------------------------------------------------------------

    def _motion_gate_error(self, *, allow_estop: bool = False) -> str:
        if self._command_busy or self._task_busy:
            return "已有命令或任务正在执行"
        if self._uncertain:
            return "上条命令结果不确定，运动入口保持锁定"
        if not self._connected or not self._backend_matched:
            return "控制服务未连接或后端身份不匹配"
        if not self.telemetryFresh:
            return "遥测已过期"
        if self._estopped and not allow_estop:
            return "机械臂处于软急停状态"
        return ""

    def _submit_verified(
        self,
        label: str,
        command: str,
        args: dict[str, Any] | None = None,
        *,
        motion: bool,
        timeout_s: float = 120.0,
        allow_estop: bool = False,
        result_handler: str = "",
    ) -> None:
        if motion:
            gate_error = self._motion_gate_error(allow_estop=allow_estop)
            if gate_error:
                self._set_error(gate_error)
                return
        elif self._command_busy:
            self._set_error("已有 SDK 请求正在执行")
            return
        profile = self._profile

        def operation() -> dict[str, Any]:
            client = A1ZProtocolClient(profile)
            data, endpoint = client.verified_request(
                command,
                args,
                timeout_s=timeout_s,
                motion=motion,
            )
            return {
                "data": data,
                "backend": endpoint.backend,
                "controlMode": endpoint.control_mode,
            }

        self._submit_operation(
            label,
            operation,
            motion=motion,
            result_handler=result_handler,
        )

    def _submit_operation(
        self,
        label: str,
        operation: Callable[[], dict[str, Any]],
        *,
        motion: bool,
        result_handler: str = "",
    ) -> None:
        if self._command_busy:
            self._set_error("已有 SDK 请求正在执行")
            return
        self._operation_sequence += 1
        sequence = self._operation_sequence
        self._command_busy = True
        self._last_error = ""
        self._status_text = f"{label}执行中"
        self._append_log(f"开始 #{sequence}：{label}")
        self.stateChanged.emit()
        future = self._executor.submit(operation)

        def done(completed: Future[dict[str, Any]]) -> None:
            try:
                payload = {
                    "ok": True,
                    "data": completed.result(),
                    "label": label,
                    "sequence": sequence,
                    "motion": motion,
                    "handler": result_handler,
                }
            except Exception as exc:
                payload = {
                    "ok": False,
                    "error": str(exc),
                    "label": label,
                    "sequence": sequence,
                    "motion": motion,
                    "ambiguous": isinstance(exc, AmbiguousCommandError),
                    "handler": result_handler,
                }
            self._bridge.operationFinished.emit(payload)

        future.add_done_callback(done)

    @Slot(object)
    def _on_operation_finished(self, payload: object) -> None:
        result = dict(payload)
        self._command_busy = False
        label = str(result.get("label", "命令"))
        if not result.get("ok"):
            self._last_error = str(result.get("error", "未知错误"))
            if result.get("ambiguous"):
                self._uncertain = True
                self._status_text = "命令结果不确定，运动已锁定"
            else:
                self._status_text = f"{label}失败"
            self._append_log(
                f"失败 #{result.get('sequence')}：{label}：{self._last_error}"
            )
            self.operationFinished.emit(label, False, self._last_error)
            self.stateChanged.emit()
            return

        envelope = dict(result.get("data", {}))
        data = dict(envelope.get("data", {}) or {})
        if envelope.get("backend"):
            self._backend = str(envelope["backend"])
            self._backend_matched = self._backend == self._profile.expected_backend
        if envelope.get("controlMode"):
            self._control_mode = str(envelope["controlMode"])
        handler = str(result.get("handler", ""))
        if handler == "status":
            self._apply_status(data)
        elif handler == "info":
            self._apply_info(data)
        elif handler == "camera":
            self._camera_summary = json.dumps(data, ensure_ascii=False)
        elif handler == "recording":
            frames = int(data.get("frames", 0) or 0)
            duration = float(data.get("duration_s", 0.0) or 0.0)
            path = str(data.get("path", ""))
            self._recording_summary = f"{frames} 帧 / {duration:.2f} s"
            if path:
                self._recording_summary += f" · {path}"
        elif handler == "gravity":
            if "gravity_comp_factor" in data:
                self._gravity_comp_factor = float(data["gravity_comp_factor"])
            if "control_mode" in data:
                self._control_mode = str(data["control_mode"])
        elif handler == "gripper":
            target = data.get("gripper_target", data.get("gripper"))
            if isinstance(target, (int, float)):
                self._gripper_target = float(target)
        elif handler == "helper":
            snapshot = dict(data.get("snapshot", {}) or {})
            if snapshot:
                self._apply_helper_snapshot(snapshot)
        self._last_error = ""
        self._status_text = f"{label}完成"
        self._append_log(
            f"完成 #{result.get('sequence')}：{label}"
            + (f" · {json.dumps(data, ensure_ascii=False)}" if data else "")
        )
        self.operationFinished.emit(label, True, self._status_text)
        self.stateChanged.emit()
        QTimer.singleShot(80, self.refreshNow)

    def _apply_helper_snapshot(self, snapshot: dict[str, Any]) -> None:
        joint_pos = list(snapshot.get("joint_pos_deg", []) or [])
        status = {
            "pos_deg": joint_pos,
            "vel_rad_s": [0.0] * 6,
            "torque_nm": [0.0] * 6,
            "gripper": snapshot.get("gripper"),
            "gripper_target": snapshot.get("gripper_target"),
            "gripper_measured": snapshot.get("gripper_measured"),
            "estopped": False,
        }
        self._apply_status(status)
        self._backend = str(snapshot.get("backend", self._backend))
        self._control_mode = str(snapshot.get("control_mode", self._control_mode))
        pose = dict(snapshot.get("pose", {}) or {})
        xyz = list(pose.get("xyz_mm", []) or [])
        rpy = list(pose.get("rpy_deg", []) or [])
        if len(xyz) >= 3 and len(rpy) >= 3:
            self._ee_pose_text = (
                "XYZ ["
                + ", ".join(f"{float(value):.1f}" for value in xyz[:3])
                + "] mm · RPY ["
                + ", ".join(f"{float(value):.1f}" for value in rpy[:3])
                + "]°"
            )
        rotation = list(pose.get("rotation_matrix", []) or [])
        if len(rotation) == 3 and all(isinstance(row, list) and len(row) == 3 for row in rotation):
            axes = []
            for column, axis_name in enumerate(("X", "Y", "Z")):
                values = [float(rotation[row][column]) for row in range(3)]
                axes.append(
                    f"{axis_name}→[{values[0]:+.2f}, {values[1]:+.2f}, {values[2]:+.2f}]"
                )
            self._ee_axis_text = "Tool 轴在 Base 中：" + " · ".join(axes)
        requested = dict(snapshot.get("requested_step", {}) or {})
        verification = dict(snapshot.get("verification", {}) or {})
        if requested:
            delta = float(requested.get("delta", 0.0))
            unit = "m" if requested.get("kind") == "translation" else "°"
            self._ee_motion_text = (
                f"已执行 {str(requested.get('frame', '')).title()} "
                f"{str(requested.get('axis', '')).upper()} {delta:+g}{unit}"
            )
            if verification:
                self._ee_motion_text += (
                    f" · FK 误差 {float(verification.get('translation_error_mm', 0.0)):.2f} mm / "
                    f"{float(verification.get('orientation_error_deg', 0.0)):.2f}°"
                )

    @Slot()
    def refreshKinematics(self) -> None:
        if self._command_busy:
            self._set_error("已有 SDK 请求正在执行")
            return
        profile = self._profile

        def operation() -> dict[str, Any]:
            command = [
                str(self._repo_root / "scripts" / "a1z_sdk_python_in_container.sh"),
                "/workspace/A1Z/scripts/a1z_ee_ik_helper.py",
                "--expected-backend",
                profile.expected_backend,
                "--end-effector-frame",
                "grasp_tcp",
                "snapshot",
            ]
            env = os.environ.copy()
            env.update(profile.environment)
            completed = subprocess.run(
                command,
                cwd=self._repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30.0,
                check=False,
                start_new_session=True,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            try:
                payload = json.loads(stdout.splitlines()[-1]) if stdout else {}
            except json.JSONDecodeError as exc:
                raise ProtocolError(f"FK helper 返回无效 JSON：{exc}") from exc
            if completed.returncode != 0 or not payload.get("ok"):
                raise ProtocolError(
                    str(payload.get("error") or stderr or "FK helper 执行失败")
                )
            return {
                "data": {"snapshot": payload},
                "backend": str(payload.get("backend", "")),
                "controlMode": str(payload.get("control_mode", "")),
            }

        self._submit_operation(
            "读取末端 FK",
            operation,
            motion=False,
            result_handler="helper",
        )

    @Slot("QVariantList", float)
    def sendJointTarget(self, joints_deg: list[Any], speed: float) -> None:
        try:
            values = [float(value) for value in joints_deg]
        except (TypeError, ValueError) as exc:
            self._set_error(f"关节目标不是有效数字：{exc}")
            return
        if len(values) != 6 or any(not math.isfinite(value) for value in values):
            self._set_error("关节目标必须包含 6 个有限数值")
            return
        self._submit_verified(
            "绝对关节运动",
            "move",
            {"joints": values, "speed": float(speed)},
            motion=True,
        )

    @Slot(int, float, float)
    def jogJoint(self, joint_index: int, delta_deg: float, speed: float) -> None:
        if not 0 <= joint_index < 6:
            self._set_error("关节编号超出 J1–J6")
            return
        gate_error = self._motion_gate_error()
        if gate_error:
            self._set_error(gate_error)
            return
        profile = self._profile

        def operation() -> dict[str, Any]:
            client = A1ZProtocolClient(profile)
            endpoint = client.verify_backend(timeout_s=3.0)
            status = client.request("status", timeout_s=3.0)
            current = list(status.get("pos_deg", []) or [])
            if len(current) < 6:
                raise ProtocolError(f"status 缺少 6 轴位置：{status}")
            limits = dict(endpoint.info.get("joint_limits_deg", {}) or {})
            pair = limits.get(f"J{joint_index + 1}")
            if not isinstance(pair, list) or len(pair) != 2:
                raise ProtocolError(f"J{joint_index + 1} 软限位不可用")
            target = [float(value) for value in current[:6]]
            requested = target[joint_index] + float(delta_deg)
            applied = min(max(requested, float(pair[0])), float(pair[1]))
            target[joint_index] = applied
            response = client.request(
                "move",
                {"joints": target, "speed": float(speed)},
                timeout_s=120.0,
                ambiguous_after_send=True,
            )
            return {
                "data": {
                    "response": response,
                    "joint": joint_index + 1,
                    "requestedDeg": requested,
                    "appliedDeg": applied,
                },
                "backend": endpoint.backend,
                "controlMode": endpoint.control_mode,
            }

        self._submit_operation(
            f"J{joint_index + 1} 点动 {float(delta_deg):+.2f}°",
            operation,
            motion=True,
        )

    @Slot(str, str, float, str, float)
    def jogCartesian(
        self,
        kind: str,
        axis: str,
        delta: float,
        frame: str,
        speed: float,
    ) -> None:
        if kind not in {"translation", "rotation"}:
            self._set_error("笛卡尔点动类型无效")
            return
        if axis not in {"x", "y", "z"} or frame not in {"base", "tool"}:
            self._set_error("笛卡尔点动坐标轴或坐标系无效")
            return
        gate_error = self._motion_gate_error()
        if gate_error:
            self._set_error(gate_error)
            return
        profile = self._profile

        def operation() -> dict[str, Any]:
            command = [
                str(self._repo_root / "scripts" / "a1z_sdk_python_in_container.sh"),
                "/workspace/A1Z/scripts/a1z_ee_ik_helper.py",
                "--expected-backend",
                profile.expected_backend,
                "--end-effector-frame",
                "grasp_tcp",
                "step",
                "--kind",
                kind,
                "--axis",
                axis,
                "--delta",
                str(float(delta)),
                "--frame",
                frame,
                "--speed",
                str(float(speed)),
                "--motion-mode",
                "move",
                "--joint-margin-deg",
                "2.0",
                "--max-joint-step-deg",
                "15.0",
            ]
            env = os.environ.copy()
            env.update(profile.environment)
            completed = subprocess.run(
                command,
                cwd=self._repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=150.0,
                check=False,
                start_new_session=True,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            payload: dict[str, Any] = {}
            if stdout:
                try:
                    payload = json.loads(stdout.splitlines()[-1])
                except json.JSONDecodeError as exc:
                    raise ProtocolError(
                        f"IK helper 返回无效 JSON：{exc}；输出={stdout[-500:]}"
                    ) from exc
            if completed.returncode != 0 or not payload.get("ok"):
                message = str(payload.get("error") or stderr or "IK helper 执行失败")
                if payload.get("motion_request_attempted"):
                    raise AmbiguousCommandError(message)
                raise ProtocolError(message)
            return {
                "data": {"snapshot": payload},
                "backend": str(payload.get("backend", "")),
                "controlMode": str(payload.get("control_mode", "")),
            }

        unit = "m" if kind == "translation" else "°"
        self._submit_operation(
            f"末端 {frame}/{axis.upper()} {float(delta):+g}{unit}",
            operation,
            motion=True,
            result_handler="helper",
        )

    @Slot(float)
    def setGripper(self, value: float) -> None:
        self._submit_verified(
            f"夹爪开度 {float(value):.2f}",
            "gripper",
            {"value": float(value)},
            motion=True,
            timeout_s=30.0,
            result_handler="gripper",
        )

    @Slot()
    def graspClose(self) -> None:
        self._submit_verified(
            "夹持并检测物体",
            "grasp_close",
            {"timeout_s": 15.0},
            motion=True,
            timeout_s=25.0,
        )

    @Slot()
    def graspRelease(self) -> None:
        self._submit_verified(
            "释放夹爪",
            "grasp_release",
            {"timeout_s": 3.0},
            motion=True,
            timeout_s=10.0,
        )

    @Slot()
    def emergencyStop(self) -> None:
        # This has a dedicated worker and the server handles it outside the
        # serialized motion lock, so an in-flight blocking move cannot delay it.
        if self._emergency_busy:
            self._set_error("软急停请求已经在发送")
            return
        if not self._connected or not self._backend_matched:
            self._set_error("控制服务未连接或后端身份不匹配；请使用现场硬件急停")
            return
        profile = self._profile
        self._emergency_busy = True
        self._append_log("发送高优先级软急停（独立通道、禁止重试）。")
        self.stateChanged.emit()

        def operation() -> dict[str, Any]:
            client = A1ZProtocolClient(profile)
            data, endpoint = client.verified_request(
                "estop",
                timeout_s=5.0,
                motion=True,
            )
            return {"data": data, "backend": endpoint.backend}

        future = self._emergency_executor.submit(operation)

        def done(completed: Future[dict[str, Any]]) -> None:
            try:
                payload = {"ok": True, "data": completed.result()}
            except Exception as exc:
                payload = {
                    "ok": False,
                    "error": str(exc),
                    "ambiguous": isinstance(exc, AmbiguousCommandError),
                }
            self._bridge.emergencyFinished.emit(payload)

        future.add_done_callback(done)

    @Slot(object)
    def _on_emergency_finished(self, payload: object) -> None:
        result = dict(payload)
        self._emergency_busy = False
        if result.get("ok"):
            self._estopped = True
            self._status_text = "软急停已锁定"
            self._last_error = ""
            self._append_log("高优先级软急停已确认。")
            self.operationFinished.emit("软急停", True, self._status_text)
        else:
            self._last_error = str(result.get("error", "软急停失败"))
            if result.get("ambiguous"):
                # Once bytes were sent, fail closed: the robot may already be
                # stopped even if the acknowledgment was lost.
                self._estopped = True
                self._uncertain = True
                self._status_text = "急停结果不确定；按已急停处理"
            else:
                self._status_text = "软急停发送失败，请使用现场硬件急停"
            self._append_log(f"软急停异常：{self._last_error}")
            self.operationFinished.emit("软急停", False, self._last_error)
        self.stateChanged.emit()
        QTimer.singleShot(50, self.refreshNow)

    @Slot()
    def releaseEmergencyStop(self) -> None:
        self._submit_verified(
            "解除软急停",
            "estop_release",
            motion=True,
            timeout_s=5.0,
            allow_estop=True,
        )

    @Slot(bool, float)
    def setGravityMode(self, enabled: bool, factor: float) -> None:
        self._submit_verified(
            "切换零力漂浮" if enabled else "切换位置保持",
            "gravity_mode",
            {"enabled": bool(enabled), "factor": float(factor)},
            motion=True,
            timeout_s=10.0,
            result_handler="gravity",
        )

    @Slot(float)
    def setGravityFactor(self, factor: float) -> None:
        self._submit_verified(
            f"设置重力补偿系数 {float(factor):.2f}",
            "gravity_factor",
            {"factor": float(factor)},
            motion=True,
            timeout_s=10.0,
            result_handler="gravity",
        )

    @Slot(str, float)
    def movePreset(self, preset: str, speed: float) -> None:
        self._submit_verified(
            f"预置位 {preset}",
            "move",
            {"preset": preset, "speed": float(speed)},
            motion=True,
        )

    @Slot(str, float)
    def runDance(self, move: str, speed: float) -> None:
        moves = [] if move == "all" else [move]
        args: dict[str, Any] = {"speed": float(speed)}
        if moves:
            args["moves"] = moves
        self._submit_verified(
            f"动作序列 {move}",
            "dance",
            args,
            motion=True,
            timeout_s=180.0,
        )

    @Slot(int)
    def startRecording(self, sample_hz: int) -> None:
        self._submit_verified(
            "开始示教录制",
            "record_start",
            {"sample_hz": int(sample_hz)},
            motion=True,
            timeout_s=10.0,
            result_handler="recording",
        )

    @Slot(str)
    def stopRecording(self, name: str) -> None:
        safe_name = self._safe_recording_name(name)
        self._submit_verified(
            "停止并保存示教录制",
            "record_stop",
            {"name": safe_name},
            motion=False,
            timeout_s=15.0,
            result_handler="recording",
        )

    @Slot(str, float)
    def playRecording(self, name: str, speed_factor: float) -> None:
        safe_name = self._safe_recording_name(name)
        self._submit_verified(
            f"回放示教轨迹 {safe_name}",
            "record_play",
            {"name": safe_name, "speed_factor": float(speed_factor)},
            motion=True,
            timeout_s=600.0,
            result_handler="recording",
        )

    @Slot(bool)
    def setGripperFreeDrive(self, enabled: bool) -> None:
        self._submit_verified(
            "夹爪自由拖动" if enabled else "夹爪恢复控制",
            "gripper_free_drive",
            {"enabled": bool(enabled)},
            motion=True,
            timeout_s=10.0,
        )

    @staticmethod
    def _safe_recording_name(name: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name).strip()) or "teach"
        if not stem.endswith(".json"):
            stem += ".json"
        return stem[:96]

    @Slot(str)
    def queryCamera(self, command: str) -> None:
        allowed = {"camera_status", "camera_capture", "camera_extrinsic"}
        if command not in allowed:
            self._set_error("相机命令不在允许列表中")
            return
        self._request_camera(
            command,
            manual=True,
            args={"preview_max_width": 960}
            if command == "camera_capture"
            else {},
        )

    @Slot(bool)
    def setCameraPreviewEnabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._camera_preview_enabled == enabled:
            return
        self._camera_preview_enabled = enabled
        self._camera_poll_counter = 0
        if enabled:
            self._poll_camera()

    def _poll_camera(self) -> None:
        if self._camera_pending:
            return
        self._camera_poll_counter += 1
        if self._camera_preview_enabled:
            if self._camera_ready:
                self._request_camera(
                    "camera_capture",
                    manual=False,
                    args={"preview_max_width": 960},
                )
            else:
                self._request_camera("camera_status", manual=False)
        elif self._camera_poll_counter == 1 or self._camera_poll_counter >= 3:
            self._camera_poll_counter = 0
            self._request_camera("camera_status", manual=False)

    def _request_camera(
        self,
        command: str,
        *,
        manual: bool,
        args: dict[str, Any] | None = None,
    ) -> None:
        if self._camera_pending:
            if manual:
                self._set_error("已有相机请求正在执行")
            return
        labels = {
            "camera_status": "读取 RGB-D 状态",
            "camera_capture": "采集 RGB-D 预览",
            "camera_extrinsic": "读取相机外参",
        }
        label = labels[command]
        profile = self._profile
        generation = self._profile_generation
        self._camera_pending = True
        self._camera_busy = True
        if manual:
            self._last_error = ""
            self._status_text = f"{label}执行中"
            self._append_log(f"开始：{label}")
        self.stateChanged.emit()

        def operation() -> dict[str, Any]:
            data = CameraProtocolClient(profile).request(
                command,
                args,
                timeout_s=5.0 if command == "camera_capture" else 3.0,
            )
            return {
                "generation": generation,
                "command": command,
                "label": label,
                "manual": manual,
                "data": data,
            }

        future = self._camera_executor.submit(operation)

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
            self._bridge.cameraFinished.emit(payload)

        future.add_done_callback(done)

    @Slot(object)
    def _on_camera_finished(self, payload: object) -> None:
        result = dict(payload)
        if int(result.get("generation", -1)) != self._profile_generation:
            return
        self._camera_pending = False
        self._camera_busy = False
        manual = bool(result.get("manual", False))
        label = str(result.get("label", "相机请求"))
        if not result.get("ok"):
            message = str(result.get("error", "相机桥请求失败"))
            self._camera_bridge_online = False
            self._camera_ready = False
            self._camera_summary = "相机桥离线"
            self._camera_details = message
            state = f"error:{message}"
            if manual:
                self._last_error = message
                self._status_text = f"{label}失败"
                self._append_log(f"失败：{label}：{message}")
                self.operationFinished.emit(label, False, message)
            elif state != self._camera_last_state:
                self._append_log(f"相机链路离线：{message}")
            self._camera_last_state = state
            self.stateChanged.emit()
            return

        data = dict(result.get("data", {}) or {})
        command = str(result.get("command", ""))
        self._camera_bridge_online = True
        ready = bool(data.get("ready", True))
        self._camera_ready = ready
        width = int(data.get("width", 0) or 0)
        height = int(data.get("height", 0) or 0)
        source = str(data.get("camera_source", "ROS"))
        if width > 0 and height > 0:
            self._camera_summary = (
                f"{width}×{height} · {source} · "
                f"{'在线' if ready else '等待帧'}"
            )
        else:
            self._camera_summary = (
                f"{source} · {'在线' if ready else '等待 RGB-D 帧'}"
            )

        if command == "camera_capture":
            preview_b64 = str(data.pop("preview_png_b64", ""))
            preview_mime = str(data.pop("preview_mime", "image/png"))
            if preview_b64:
                self._camera_preview_source = (
                    f"data:{preview_mime};base64,{preview_b64}"
                )
            depth_range = data.get("depth_range_m")
            depth_text = ""
            if isinstance(depth_range, list) and len(depth_range) == 2:
                depth_text = (
                    f" · 深度 {float(depth_range[0]):.3f}–"
                    f"{float(depth_range[1]):.3f} m"
                )
            self._camera_details = (
                f"RGB {data.get('rgb_encoding', '—')} · "
                f"Depth {data.get('depth_encoding', '—')} · "
                f"同步差 {float(data.get('sync_delta_ms', 0.0)):.1f} ms"
                f"{depth_text}"
            )
        elif command == "camera_extrinsic":
            matrix = data.get("extrinsic_camera_to_target")
            self._camera_details = (
                f"{data.get('camera_frame_id', 'camera')} → "
                f"{data.get('target_frame_id', 'target')} · "
                f"{data.get('lookup_mode', 'unknown')} · "
                f"T={json.dumps(matrix, ensure_ascii=False)}"
            )
        else:
            self._camera_details = (
                f"{data.get('color_topic', '—')} + "
                f"{data.get('depth_topic', '—')} · "
                f"同步={'是' if data.get('synchronized') else '否'} · "
                f"外参={'就绪' if data.get('extrinsic_ready') else '等待'}"
            )

        state = f"ready:{ready}:{width}x{height}:{source}"
        if state != self._camera_last_state:
            self._append_log(f"相机链路：{self._camera_summary}")
        self._camera_last_state = state
        if manual:
            self._last_error = ""
            self._status_text = f"{label}完成"
            self._append_log(f"完成：{label} · {self._camera_details}")
            self.operationFinished.emit(label, True, self._status_text)
        self.stateChanged.emit()

    # ------------------------------------------------------------------
    # Process tasks: lifecycle, AnyGrasp, ROS, preflight, maintenance
    # ------------------------------------------------------------------

    @Slot(bool, float)
    def startServer(self, gravity_mode: bool, gravity_factor: float) -> None:
        args = [
            str(self._repo_root / "scripts" / "manage_a1z_control_server.sh"),
            "start",
        ]
        if gravity_mode:
            args.append("--gravity-mode")
        args.extend(["--gravity-factor", f"{float(gravity_factor):.3f}"])
        self._start_process_task(
            "server_start",
            "启动控制服务",
            args[0],
            args[1:],
            motion=False,
            completion=lambda code, _output: self.refreshNow() if code == 0 else None,
        )

    @Slot()
    def stopServer(self) -> None:
        script = str(self._repo_root / "scripts" / "manage_a1z_control_server.sh")
        self._start_process_task(
            "server_stop",
            "停止控制服务",
            script,
            ["stop"],
            motion=False,
            completion=lambda code, _output: self.refreshNow() if code == 0 else None,
        )

    @Slot(str)
    def manageRos(self, action: str) -> None:
        if action not in {"start", "stop", "restart", "status", "wait"}:
            self._set_error("ROS 操作不在允许列表中")
            return
        script = str(self._repo_root / "scripts" / "run_a1z_ros2_stack_in_container.sh")
        self._start_process_task(
            "ros",
            f"ROS 2 {action}",
            script,
            [action],
            motion=False,
        )

    @Slot(str, str, str)
    def computeAnyGrasp(self, instruction: str, planner: str, vision_backend: str) -> None:
        instruction = str(instruction).strip()
        if not instruction:
            self._set_error("请输入目标物体描述")
            return
        if planner not in {"adapter", "best"}:
            self._set_error("AnyGrasp 规划器无效")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = self._repo_root / "runtime" / "gui_console" / "anygrasp" / stamp
        args = [
            str(self._repo_root / "scripts" / "run_pick_pipeline.py"),
            instruction,
            "--profile",
            self._profile_name,
            "--planner",
            planner,
            "--output-dir",
            str(output),
        ]
        if vision_backend in {"local", "remote_ssh"}:
            args.extend(["--vision-backend", vision_backend])
        self._pipeline_output_dir = str(output)
        self.planChanged.emit()

        def completed(code: int, _output: str) -> None:
            if code != 0:
                return
            try:
                self._plan_summary = summarize_pipeline(output, self._repo_root)
            except Exception as exc:
                self._set_error(f"AnyGrasp 完成但计划解析失败：{exc}")
                return
            self._append_log(
                f"AnyGrasp 只计算完成：{self._plan_summary.get('planPath', '')}"
            )
            self.planChanged.emit()

        self._start_process_task(
            "anygrasp_compute",
            "AnyGrasp 只计算",
            "/usr/bin/python3",
            args,
            motion=False,
            completion=completed,
        )

    @Slot(bool, str)
    def executePlan(self, dry_run: bool, confirmation: str) -> None:
        plan_path = Path(self.latestPlanPath)
        if not plan_path.is_file():
            self._set_error("没有可执行的已审阅计划")
            return
        planned_profile = str(self._plan_summary.get("profile", ""))
        if planned_profile != self._profile_name:
            self._set_error(
                f"计划属于 {planned_profile or 'unknown'}，当前选择 {self._profile_name}"
            )
            return
        if not self.planSafetyPassed:
            self._set_error("计划安全检查未全部通过，执行被阻止")
            return
        expected_phrase = f"执行 {self._profile_name.upper()}"
        if not dry_run and confirmation.strip() != expected_phrase:
            self._set_error(f"执行确认文本必须为：{expected_phrase}")
            return
        if (
            self._profile_name == "real"
            and not dry_run
            and self._profile.environment.get("A1Z_HAND_EYE_CALIBRATION_STATUS")
            != "verified"
        ):
            self._set_error("真机手眼标定未标记 verified，GUI 不允许绕过")
            return

        relative = plan_path.resolve().relative_to(self._repo_root)
        plan_in_container = f"/workspace/A1Z/{relative.as_posix()}"
        execution_dir = Path(self._pipeline_output_dir) / "execution"
        result_host = execution_dir / (
            "dry_run_result.json" if dry_run else "execution_result.json"
        )
        result_in_container = (
            f"/workspace/A1Z/{result_host.resolve().relative_to(self._repo_root).as_posix()}"
        )
        args = [
            "--plan",
            plan_in_container,
            "--output",
            result_in_container,
            "--pre-open",
            "--arm-speed",
            self._profile.environment.get("A1Z_EXEC_ARM_SPEED", "0.5"),
            "--expected-backend",
            self._profile.expected_backend,
        ]
        if dry_run:
            args.append("--dry-run")
        self._start_process_task(
            "plan_dry_run" if dry_run else "plan_execute",
            "计划演练（不发运动）" if dry_run else "执行已审阅 AnyGrasp 计划",
            str(self._repo_root / "scripts" / "execute_a1z_plan_in_container.sh"),
            args,
            motion=not dry_run,
        )

    @Slot()
    def runPreflight(self) -> None:
        script = str(self._repo_root / "scripts" / "a1z_console_preflight.py")

        def completed(code: int, output: str) -> None:
            try:
                payload = json.loads(output.splitlines()[-1]) if output.strip() else {}
                items = payload.get("checks", [])
                if not isinstance(items, list):
                    raise ValueError("checks 不是数组")
                self._preflight_items = [dict(item) for item in items]
                self.preflightChanged.emit()
            except Exception as exc:
                self._set_error(f"预检结果解析失败：{exc}")
            if code == 0:
                self.refreshNow()

        self._start_process_task(
            "preflight",
            f"{self._profile.label}全链路预检",
            "/usr/bin/python3",
            [script, "--profile", self._profile_name],
            motion=False,
            completion=completed,
            log_stdout=False,
        )

    @Slot(str, str)
    def runMaintenance(self, action: str, confirmation: str) -> None:
        if self._profile_name != "real":
            self._set_error("CAN 维护工具只能在真机配置中运行")
            return
        commands: dict[str, tuple[str, list[str], bool, bool]] = {
            "can_check": (
                "检查 SocketCAN",
                [
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/motor_diag.py",
                    "--check-can",
                ],
                False,
                False,
            ),
            "motor_scan": (
                "扫描 7 个电机",
                [
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/motor_diag.py",
                    "--scan",
                ],
                True,
                False,
            ),
            "motor_listen": (
                "被动监听 CAN 5 秒",
                [
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/motor_diag.py",
                    "--listen",
                    "--duration",
                    "5",
                ],
                False,
                False,
            ),
            "gripper_test": (
                "夹爪力位混控测试",
                [
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/examples/gripper_hybrid_test.py",
                    "--can",
                    self._profile.environment.get("A1Z_CAN_CHANNEL", "can0"),
                ],
                True,
                False,
            ),
            "set_zero_all": (
                "六轴零点标定",
                [
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/set_zero.py",
                    "--all",
                    "--channel",
                    self._profile.environment.get("A1Z_CAN_CHANNEL", "can0"),
                    "--yes",
                ],
                True,
                True,
            ),
            "set_zero_gripper": (
                "夹爪零点标定",
                [
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/gripper_set_zero.py",
                    "--can",
                    self._profile.environment.get("A1Z_CAN_CHANNEL", "can0"),
                    "--yes",
                ],
                True,
                True,
            ),
        }
        if action not in commands:
            self._set_error("维护操作不在允许列表中")
            return
        label, tool_args, motion, destructive = commands[action]
        if destructive and confirmation.strip() != "校零 A1Z":
            self._set_error("校零确认文本必须为：校零 A1Z")
            return
        if action not in {"can_check"} and self._connected:
            self._set_error("直接 CAN 工具要求先停止 SDK 控制服务，避免总线双主冲突")
            return
        wrapper = str(self._repo_root / "scripts" / "a1z_sdk_python_in_container.sh")
        self._start_process_task(
            "maintenance",
            label,
            wrapper,
            tool_args,
            motion=motion,
        )

    @Slot()
    def cancelTask(self) -> None:
        if self._process is None or self._process.state() == QProcess.NotRunning:
            return
        pid = int(self._process.processId())
        self._append_log(
            f"请求中止任务 {self._task_label}；不会自动发送任何替代运动命令。"
        )
        if pid > 0:
            try:
                os.killpg(pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            except PermissionError:
                self._process.terminate()
        QTimer.singleShot(5000, self._kill_process_if_running)

    def _kill_process_if_running(self) -> None:
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            pid = int(self._process.processId())
            if pid > 0:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    self._process.kill()

    def _start_process_task(
        self,
        kind: str,
        label: str,
        program: str,
        arguments: list[str],
        *,
        motion: bool,
        completion: Callable[[int, str], None] | None = None,
        log_stdout: bool = True,
    ) -> None:
        if self._task_busy or self._command_busy:
            self._set_error("已有命令或外部任务正在执行")
            return
        if motion:
            gate_error = self._motion_gate_error()
            if gate_error:
                self._set_error(gate_error)
                return
        self._task_busy = True
        self._task_motion = motion
        self._task_kind = kind
        self._task_label = label
        self._last_error = ""
        self._status_text = f"{label}进行中"
        self._pending_process_output.clear()
        self._process_completion = completion
        self._process_log_stdout = log_stdout
        self._append_log(f"启动任务：{label}")

        process = QProcess(self)
        self._process = process
        process.setWorkingDirectory(str(self._repo_root))
        process.setProcessChannelMode(QProcess.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        for key, value in self._profile.environment.items():
            environment.insert(key, value)
        environment.insert("A1Z_PROFILE", self._profile_name)
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_process_output)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)
        # setsid gives cancellation one process group, including docker/SSH
        # children launched by the AnyGrasp pipeline.
        process.start("/usr/bin/setsid", [program, *arguments])
        self.stateChanged.emit()

    @Slot()
    def _read_process_output(self) -> None:
        if self._process is None:
            return
        chunk = bytes(self._process.readAllStandardOutput())
        if not chunk:
            return
        self._pending_process_output.extend(chunk)
        if self._process_log_stdout:
            self._append_log(chunk.decode("utf-8", errors="replace").rstrip())

    @Slot(int, QProcess.ExitStatus)
    def _process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._read_process_output()
        label = self._task_label
        output = self._pending_process_output.decode("utf-8", errors="replace").strip()
        completion = self._process_completion
        was_motion = self._task_motion
        self._task_busy = False
        self._task_motion = False
        self._task_kind = ""
        self._task_label = ""
        self._process_completion = None
        if exit_code == 0:
            self._status_text = f"{label}完成"
            self._last_error = ""
            self._append_log(f"任务完成：{label}")
        else:
            tail = output[-1000:] if output else f"exit code {exit_code}"
            self._last_error = tail
            self._status_text = f"{label}失败"
            self._append_log(f"任务失败：{label}：{tail}")
            if was_motion:
                self._uncertain = True
                self._status_text = f"{label}失败，运动结果可能不确定"
        self.stateChanged.emit()
        self.operationFinished.emit(label, exit_code == 0, self._status_text)
        if completion is not None:
            completion(exit_code, output)
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        QTimer.singleShot(100, self.refreshNow)

    @Slot(QProcess.ProcessError)
    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            message = (
                f"任务无法启动："
                f"{self._process.errorString() if self._process else error}"
            )
            self._task_busy = False
            self._task_motion = False
            self._task_kind = ""
            self._task_label = ""
            self._process_completion = None
            self._set_error(message)

    def shutdown(self) -> None:
        self._telemetry_timer.stop()
        self._age_timer.stop()
        self._camera_timer.stop()
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            self.cancelTask()
            self._process.waitForFinished(1500)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._emergency_executor.shutdown(wait=False, cancel_futures=True)
        self._camera_executor.shutdown(wait=False, cancel_futures=True)
