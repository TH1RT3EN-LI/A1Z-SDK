"""Profile-scoped grasp-plan session and task contracts."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from .interaction_policy import (
    OnlineCapability,
    ProcessAccess,
    ProcessTaskContract,
    ResourceEffect,
)
from .plan_parser import summarize_pipeline
from .profiles import RuntimeProfile


class PlanSessionError(ValueError):
    """A plan action is invalid for the current session."""


@dataclass(frozen=True)
class PlanProcessTask:
    """Process intent prepared by the plan domain for the shared task runner."""

    kind: str
    label: str
    program: str
    arguments: tuple[str, ...]
    contract: ProcessTaskContract


@dataclass(frozen=True)
class PlanComputationRequest:
    sequence: int
    profile_name: str
    output_dir: Path
    task: PlanProcessTask


@dataclass(frozen=True)
class PlanComputationResult:
    accepted: bool
    success: bool
    error: str = ""
    plan_path: str = ""


class PlanSessionCoordinator(QObject):
    """Own one generated plan's identity, validation, and execution intent."""

    changed = Signal()

    def __init__(
        self,
        repo_root: Path,
        profile: RuntimeProfile,
        parent: QObject | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo_root = repo_root.resolve()
        self._profile = profile
        self._now = now or datetime.now
        self._summary: dict[str, Any] = {}
        self._output_dir: Path | None = None
        self._state = "empty"
        self._status = "尚未计算抓取计划"
        self._current = False
        self._plan_digest = ""
        self._sequence = 0
        self._active_computation: int | None = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def status(self) -> str:
        return self._status

    @property
    def latest_plan_path(self) -> str:
        return str(self._summary.get("planPath", ""))

    @property
    def output_dir(self) -> str:
        return "" if self._output_dir is None else str(self._output_dir)

    @property
    def plan_id(self) -> str:
        return str(self._summary.get("planId", ""))

    @property
    def frame_id(self) -> str:
        return str(self._summary.get("frameId", ""))

    @property
    def profile_name(self) -> str:
        return str(self._summary.get("profile", ""))

    @property
    def instruction(self) -> str:
        return str(self._summary.get("instruction", ""))

    @property
    def segments(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._summary.get("segments", []) or []]

    @property
    def safety(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._summary.get("safety", []) or []]

    @property
    def safety_passed(self) -> bool:
        return bool(self._summary.get("allSafetyPassed", False))

    @property
    def current(self) -> bool:
        return self._current

    @property
    def grasp_summary(self) -> str:
        grasp = dict(self._summary.get("grasp", {}) or {})
        if not grasp:
            return "暂无抓取位姿"
        xyz = grasp.get("translationMm", [])
        xyz_text = ", ".join(f"{float(value):.1f}" for value in xyz)
        return (
            f"候选 #{grasp.get('rank', '—')} · "
            f"score {float(grasp.get('score', 0.0)):.4f} · "
            f"宽度 {float(grasp.get('widthMm', 0.0)):.1f} mm · "
            f"相机坐标 [{xyz_text}] mm"
        )

    @property
    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self._profile.name,
            self._state,
            self._status,
            self._current,
            self.latest_plan_path,
            self.output_dir,
            self.plan_id,
            self.profile_name,
            self.safety_passed,
            len(self.segments),
            self._active_computation,
        )

    def select_profile(self, profile: RuntimeProfile) -> None:
        self._profile = profile
        self._sequence += 1
        self._active_computation = None
        self._summary = {}
        self._output_dir = None
        self._state = "empty"
        self._status = "尚未计算抓取计划"
        self._current = False
        self._plan_digest = ""
        self.changed.emit()

    def prepare_computation(
        self,
        instruction: str,
        planner: str,
        vision_backend: str,
    ) -> PlanComputationRequest:
        target = str(instruction).strip()
        if not target:
            raise PlanSessionError("请输入目标物体描述")
        if planner not in {"adapter", "best"}:
            raise PlanSessionError("AnyGrasp 规划器无效")
        if vision_backend not in {"auto", "local", "remote_ssh"}:
            raise PlanSessionError("视觉计算位置无效")
        if self._active_computation is not None:
            raise PlanSessionError("抓取计划正在计算")

        self._sequence += 1
        stamp = self._now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = (
            self._repo_root
            / "runtime"
            / "gui_console"
            / "anygrasp"
            / f"{stamp}_{self._sequence:04d}"
        )
        arguments = [
            str(self._repo_root / "scripts" / "run_pick_pipeline.py"),
            target,
            "--profile",
            self._profile.name,
            "--planner",
            planner,
            "--output-dir",
            str(output_dir),
        ]
        if vision_backend != "auto":
            arguments.extend(["--vision-backend", vision_backend])
        return PlanComputationRequest(
            sequence=self._sequence,
            profile_name=self._profile.name,
            output_dir=output_dir,
            task=PlanProcessTask(
                kind="anygrasp_compute",
                label="AnyGrasp 只计算",
                program="/usr/bin/python3",
                arguments=tuple(arguments),
                contract=ProcessTaskContract(
                    ProcessAccess.TASK_SLOT,
                    cancelable=True,
                ),
            ),
        )

    def activate_computation(self, request: PlanComputationRequest) -> None:
        if request.profile_name != self._profile.name:
            raise PlanSessionError("计划计算请求已不属于当前配置")
        self._active_computation = request.sequence
        self._summary = {}
        self._output_dir = request.output_dir
        self._state = "computing"
        self._status = "正在生成抓取候选和机械臂轨迹…"
        self._current = False
        self._plan_digest = ""
        self.changed.emit()

    def complete_computation(
        self,
        request: PlanComputationRequest,
        exit_code: int,
    ) -> PlanComputationResult:
        if request.sequence != self._active_computation:
            return PlanComputationResult(False, False)
        self._active_computation = None
        if exit_code != 0:
            self._summary = {}
            self._state = "failed"
            self._status = "计算未完成；请查看错误后重试"
            self._current = False
            self._plan_digest = ""
            self.changed.emit()
            return PlanComputationResult(True, False)

        try:
            summary = summarize_pipeline(request.output_dir, self._repo_root)
            if str(summary.get("profile", "")) != self._profile.name:
                raise PlanSessionError(
                    "计算产物的 profile 与当前配置不一致"
                )
            plan_path = Path(str(summary.get("planPath", ""))).resolve()
            if not self._is_within(plan_path, request.output_dir.resolve()):
                raise PlanSessionError("计划文件不在本次计算输出目录内")
            if not plan_path.is_file():
                raise PlanSessionError("计划文件不存在")
            digest_before = self._digest_file(plan_path)
            reviewed_summary = summarize_pipeline(
                request.output_dir,
                self._repo_root,
            )
            reviewed_plan_path = Path(
                str(reviewed_summary.get("planPath", ""))
            ).resolve()
            if str(reviewed_summary.get("profile", "")) != self._profile.name:
                raise PlanSessionError(
                    "审阅期间计算产物的 profile 发生改变"
                )
            if reviewed_plan_path != plan_path:
                raise PlanSessionError("审阅期间计划文件路径发生改变")
            if not self._is_within(
                reviewed_plan_path,
                request.output_dir.resolve(),
            ):
                raise PlanSessionError("计划文件不在本次计算输出目录内")
            digest_after = self._digest_file(reviewed_plan_path)
            if digest_after != digest_before:
                raise PlanSessionError("审阅期间计划文件内容发生改变")
            summary = reviewed_summary
        except Exception as exc:
            self._summary = {}
            self._state = "invalid"
            self._status = "计算完成，但产物无法安全审阅或执行"
            self._current = False
            self._plan_digest = ""
            self.changed.emit()
            return PlanComputationResult(
                True,
                False,
                f"AnyGrasp 完成但计划解析失败：{exc}",
            )

        self._summary = summary
        self._plan_digest = digest_after
        self._current = True
        if self.safety_passed:
            self._state = "ready"
            self._status = "计划安全检查已通过；建议先演练，再确认执行"
        else:
            self._state = "unsafe"
            self._status = "计划已生成，但安全检查未通过；只能演练或重新计算"
        self.changed.emit()
        return PlanComputationResult(
            True,
            True,
            plan_path=self.latest_plan_path,
        )

    def prepare_execution(
        self,
        *,
        dry_run: bool,
        confirmation: str,
    ) -> PlanProcessTask:
        if not self.current:
            if self.profile_name and self.profile_name != self._profile.name:
                raise PlanSessionError(
                    f"计划属于 {self.profile_name}，当前选择 {self._profile.name}"
                )
            raise PlanSessionError("没有可执行的已审阅计划")
        plan_path = Path(self.latest_plan_path).resolve()
        output_dir = self._output_dir.resolve() if self._output_dir else None
        if (
            output_dir is None
            or not self._is_within(output_dir, self._repo_root)
            or not self._is_within(plan_path, output_dir)
        ):
            raise PlanSessionError("计划路径不属于当前工作区的计算会话")
        if not plan_path.is_file():
            self._invalidate_artifact("已审阅计划文件已不存在；请重新计算")
            raise PlanSessionError("已审阅计划文件已不存在")
        try:
            current_digest = self._digest_file(plan_path)
        except OSError as exc:
            self._invalidate_artifact("已审阅计划文件无法读取；请重新计算")
            raise PlanSessionError("已审阅计划文件无法读取") from exc
        if not self._plan_digest or current_digest != self._plan_digest:
            self._invalidate_artifact("已审阅计划文件内容已改变；请重新计算")
            raise PlanSessionError("已审阅计划文件内容已改变")
        if not dry_run and not self.safety_passed:
            raise PlanSessionError("计划安全检查未全部通过，实际执行被阻止")

        expected_phrase = f"执行 {self._profile.name.upper()}"
        if not dry_run and confirmation.strip() != expected_phrase:
            raise PlanSessionError(f"执行确认文本必须为：{expected_phrase}")
        if (
            self._profile.name == "real"
            and not dry_run
            and self._profile.environment.get(
                "A1Z_HAND_EYE_CALIBRATION_STATUS"
            )
            != "verified"
        ):
            raise PlanSessionError("真机手眼标定未标记 verified，GUI 不允许绕过")

        execution_dir = output_dir / "execution"
        result_host = execution_dir / (
            "dry_run_result.json" if dry_run else "execution_result.json"
        )
        plan_in_container = self._container_path(plan_path)
        result_in_container = self._container_path(result_host)
        arguments = [
            "--plan",
            plan_in_container,
            "--expected-plan-sha256",
            self._plan_digest,
            "--output",
            result_in_container,
            "--pre-open",
            "--arm-speed",
            self._profile.environment.get("A1Z_EXEC_ARM_SPEED", "0.5"),
            "--expected-backend",
            self._profile.expected_backend,
        ]
        if dry_run:
            arguments.append("--dry-run")
        return PlanProcessTask(
            kind="plan_dry_run" if dry_run else "plan_execute",
            label=(
                "计划演练（不发运动）"
                if dry_run
                else "执行已审阅 AnyGrasp 计划"
            ),
            program=str(
                self._repo_root
                / "scripts"
                / "execute_a1z_plan_in_container.sh"
            ),
            arguments=tuple(arguments),
            contract=(
                ProcessTaskContract(
                    ProcessAccess.TASK_SLOT,
                    cancelable=True,
                )
                if dry_run
                else ProcessTaskContract(
                    ProcessAccess.ONLINE_DEVICE,
                    ResourceEffect.ARM | ResourceEffect.GRIPPER,
                    uncertain_on_failure=True,
                    blocks_telemetry=True,
                    online_capability=OnlineCapability.ARM_GRIPPER_MOTION,
                    cancelable=True,
                )
            ),
        )

    def _container_path(self, host_path: Path) -> str:
        try:
            relative = host_path.resolve().relative_to(self._repo_root)
        except ValueError as exc:
            raise PlanSessionError("计划路径不属于当前工作区") from exc
        return f"/workspace/A1Z/{relative.as_posix()}"

    @staticmethod
    def _is_within(path: Path, parent: Path) -> bool:
        try:
            path.resolve().relative_to(parent.resolve())
        except ValueError:
            return False
        return True

    @staticmethod
    def _digest_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _invalidate_artifact(self, status: str) -> None:
        self._current = False
        self._plan_digest = ""
        self._state = "invalid"
        self._status = status
        self.changed.emit()
