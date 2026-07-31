"""Profile-scoped preflight state and diagnostic maintenance intents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .interaction_policy import (
    ProcessAccess,
    ProcessTaskContract,
    ResourceEffect,
)
from .profiles import RuntimeProfile


class DiagnosticsSessionError(ValueError):
    """A diagnostic action or result violates the domain contract."""


@dataclass(frozen=True)
class DiagnosticsTask:
    kind: str
    label: str
    program: str
    arguments: tuple[str, ...]
    contract: ProcessTaskContract
    log_stdout: bool = True


@dataclass(frozen=True)
class PreflightRequest:
    sequence: int
    profile_name: str
    task: DiagnosticsTask


@dataclass(frozen=True)
class PreflightResult:
    accepted: bool
    valid: bool
    ready: bool = False
    error: str = ""


class DiagnosticsSessionCoordinator:
    """Own diagnostic results and prepare resource-aware maintenance tasks."""

    def __init__(self, repo_root: Path, profile: RuntimeProfile) -> None:
        self._repo_root = repo_root.resolve()
        self._profile = profile
        self._state = "idle"
        self._status = "尚未运行全链路预检"
        self._items: list[dict[str, Any]] = []
        self._sequence = 0
        self._active_preflight: int | None = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def status(self) -> str:
        return self._status

    @property
    def items(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._items]

    @property
    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self._profile.name,
            self._state,
            self._status,
            tuple(
                (
                    item["name"],
                    item["ok"],
                    item["detail"],
                    item["severity"],
                )
                for item in self._items
            ),
            self._active_preflight,
        )

    def select_profile(self, profile: RuntimeProfile) -> bool:
        if profile.name == self._profile.name:
            return False
        self._profile = profile
        self._sequence += 1
        self._active_preflight = None
        self._state = "idle"
        self._status = "尚未运行全链路预检"
        self._items = []
        return True

    def prepare_preflight(self) -> PreflightRequest:
        if self._active_preflight is not None:
            raise DiagnosticsSessionError("全链路预检正在运行")
        self._sequence += 1
        script = self._repo_root / "scripts" / "a1z_console_preflight.py"
        return PreflightRequest(
            sequence=self._sequence,
            profile_name=self._profile.name,
            task=DiagnosticsTask(
                kind="preflight",
                label=f"{self._profile.label}全链路预检",
                program="/usr/bin/python3",
                arguments=(
                    str(script),
                    "--profile",
                    self._profile.name,
                ),
                contract=ProcessTaskContract(
                    ProcessAccess.TASK_SLOT,
                    cancelable=True,
                ),
                log_stdout=False,
            ),
        )

    def activate_preflight(self, request: PreflightRequest) -> None:
        if request.profile_name != self._profile.name:
            raise DiagnosticsSessionError("预检请求已不属于当前配置")
        if self._active_preflight is not None:
            raise DiagnosticsSessionError("全链路预检正在运行")
        self._active_preflight = request.sequence
        self._state = "running"
        self._status = "正在检查控制、遥测、相机与运行环境…"
        self._items = []

    def complete_preflight(
        self,
        request: PreflightRequest,
        exit_code: int,
        output: str,
    ) -> PreflightResult:
        if (
            request.sequence != self._active_preflight
            or request.profile_name != self._profile.name
        ):
            return PreflightResult(False, False)
        self._active_preflight = None
        if exit_code != 0:
            self._state = "failed"
            self._status = "预检未完成；请查看任务错误后重试"
            self._items = []
            return PreflightResult(True, False)

        try:
            payload = self._parse_payload(output, request.profile_name)
        except DiagnosticsSessionError as exc:
            self._state = "invalid"
            self._status = "预检完成，但结果格式无效"
            self._items = []
            return PreflightResult(True, False, error=str(exc))

        self._items = payload["checks"]
        ready = bool(payload["ready"])
        self._state = "ready" if ready else "issues"
        self._status = (
            "全链路预检通过"
            if ready
            else f"发现 {payload['required_failure_count']} 项必需条件未满足"
        )
        return PreflightResult(True, True, ready=ready)

    def prepare_maintenance(
        self,
        action: str,
        confirmation: str,
    ) -> DiagnosticsTask:
        channel = self._profile.environment.get("A1Z_CAN_CHANNEL", "can0")
        commands: dict[
            str,
            tuple[str, tuple[str, ...], ResourceEffect, bool, bool],
        ] = {
            "can_check": (
                "检查 SocketCAN",
                (
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/motor_diag.py",
                    "--check-can",
                ),
                ResourceEffect.NONE,
                False,
                False,
            ),
            "motor_scan": (
                "扫描 7 个电机",
                (
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/motor_diag.py",
                    "--scan",
                ),
                ResourceEffect.ARM | ResourceEffect.GRIPPER,
                True,
                False,
            ),
            "motor_listen": (
                "被动监听 CAN 5 秒",
                (
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/motor_diag.py",
                    "--listen",
                    "--duration",
                    "5",
                ),
                ResourceEffect.NONE,
                False,
                False,
            ),
            "gripper_test": (
                "夹爪力位混控测试",
                (
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/examples/gripper_hybrid_test.py",
                    "--can",
                    channel,
                ),
                ResourceEffect.GRIPPER,
                True,
                False,
            ),
            "set_zero_all": (
                "六轴零点标定",
                (
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/set_zero.py",
                    "--all",
                    "--channel",
                    channel,
                    "--yes",
                ),
                ResourceEffect.ARM | ResourceEffect.CALIBRATION,
                True,
                True,
            ),
            "set_zero_gripper": (
                "夹爪零点标定",
                (
                    "/workspace/A1Z/vendor/GALAXEA-A1Z/tools/gripper_set_zero.py",
                    "--can",
                    channel,
                    "--yes",
                ),
                ResourceEffect.GRIPPER | ResourceEffect.CALIBRATION,
                True,
                True,
            ),
        }
        if action not in commands:
            raise DiagnosticsSessionError("维护操作不在允许列表中")
        label, tool_args, effects, uncertain, destructive = commands[action]
        if destructive and str(confirmation).strip() != "校零 A1Z":
            raise DiagnosticsSessionError("校零确认文本必须为：校零 A1Z")

        access = (
            ProcessAccess.HARDWARE_INSPECTION
            if action == "can_check"
            else ProcessAccess.OFFLINE_DEVICE
        )
        arguments = list(tool_args)
        if action != "can_check":
            arguments.insert(0, "--require-control-server-stopped")
        return DiagnosticsTask(
            kind=f"maintenance_{action}",
            label=label,
            program=str(
                self._repo_root
                / "scripts"
                / "a1z_sdk_python_in_container.sh"
            ),
            arguments=tuple(arguments),
            contract=ProcessTaskContract(
                access,
                effects,
                uncertain_on_failure=uncertain,
                blocks_telemetry=uncertain,
                cancelable=action in {
                    "motor_scan",
                    "motor_listen",
                    "gripper_test",
                },
            ),
        )

    @staticmethod
    def _parse_payload(output: str, profile_name: str) -> dict[str, Any]:
        lines = [line for line in str(output).splitlines() if line.strip()]
        if not lines:
            raise DiagnosticsSessionError("预检没有返回 JSON 结果")
        try:
            payload = json.loads(lines[-1])
        except (json.JSONDecodeError, TypeError) as exc:
            raise DiagnosticsSessionError(f"预检 JSON 解析失败：{exc}") from exc
        if not isinstance(payload, dict):
            raise DiagnosticsSessionError("预检结果必须是对象")
        if payload.get("profile") != profile_name:
            raise DiagnosticsSessionError("预检结果不属于当前配置")
        raw_checks = payload.get("checks")
        if not isinstance(raw_checks, list):
            raise DiagnosticsSessionError("预检 checks 必须是数组")

        checks: list[dict[str, Any]] = []
        for index, raw_item in enumerate(raw_checks):
            if not isinstance(raw_item, dict):
                raise DiagnosticsSessionError(f"第 {index + 1} 项预检不是对象")
            name = raw_item.get("name")
            ok = raw_item.get("ok")
            detail = raw_item.get("detail")
            severity = raw_item.get("severity")
            if not isinstance(name, str) or not name.strip():
                raise DiagnosticsSessionError(f"第 {index + 1} 项预检缺少名称")
            if not isinstance(ok, bool):
                raise DiagnosticsSessionError(f"第 {index + 1} 项预检状态无效")
            if not isinstance(detail, str):
                raise DiagnosticsSessionError(f"第 {index + 1} 项预检详情无效")
            if severity not in {"required", "advisory"}:
                raise DiagnosticsSessionError(f"第 {index + 1} 项预检级别无效")
            checks.append(
                {
                    "name": name,
                    "ok": ok,
                    "detail": detail,
                    "severity": severity,
                }
            )

        required_failures = sum(
            1
            for item in checks
            if item["severity"] == "required" and not item["ok"]
        )
        ready = payload.get("ready")
        reported_failures = payload.get("required_failure_count")
        if not isinstance(ready, bool) or ready != (required_failures == 0):
            raise DiagnosticsSessionError("预检 ready 与检查明细不一致")
        if (
            not isinstance(reported_failures, int)
            or isinstance(reported_failures, bool)
            or reported_failures != required_failures
        ):
            raise DiagnosticsSessionError("预检失败计数与检查明细不一致")
        return {
            "ready": ready,
            "checks": checks,
            "required_failure_count": required_failures,
        }
