"""Synchronous FK/IK helper adapter used inside the command executor."""

from __future__ import annotations

import json
import math
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .profiles import RuntimeProfile
from .protocol import AmbiguousCommandError, ProtocolError


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class KinematicsStepRequest:
    kind: str
    axis: str
    delta: float
    frame: str
    speed: float


class KinematicsCommandAdapter:
    """Own the external helper command and its response contract."""

    def __init__(
        self,
        repo_root: Path,
        *,
        run_process: ProcessRunner = subprocess.run,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._run_process = run_process

    @staticmethod
    def prepare_step(
        kind: str,
        axis: str,
        delta: float,
        frame: str,
        speed: float,
    ) -> KinematicsStepRequest:
        if kind not in {"translation", "rotation"}:
            raise ValueError("笛卡尔点动类型无效")
        if axis not in {"x", "y", "z"}:
            raise ValueError("笛卡尔点动坐标轴无效")
        if frame not in {"base", "tool"}:
            raise ValueError("笛卡尔点动坐标系无效")
        numeric_delta = float(delta)
        numeric_speed = float(speed)
        if not math.isfinite(numeric_delta) or abs(numeric_delta) <= 1e-12:
            raise ValueError("笛卡尔点动增量必须是非零有限数值")
        if not math.isfinite(numeric_speed) or numeric_speed <= 0.0:
            raise ValueError("笛卡尔点动速度必须是大于 0 的有限数值")
        return KinematicsStepRequest(
            kind=kind,
            axis=axis,
            delta=numeric_delta,
            frame=frame,
            speed=numeric_speed,
        )

    def snapshot(self, profile: RuntimeProfile) -> dict[str, Any]:
        payload = self._run_helper(
            profile,
            ["snapshot"],
            timeout_s=30.0,
            result_name="FK",
            ambiguous_motion=False,
        )
        return self._command_result(payload)

    def step(
        self,
        profile: RuntimeProfile,
        request: KinematicsStepRequest,
    ) -> dict[str, Any]:
        payload = self._run_helper(
            profile,
            [
                "step",
                "--kind",
                request.kind,
                "--axis",
                request.axis,
                "--delta",
                str(request.delta),
                "--frame",
                request.frame,
                "--speed",
                str(request.speed),
                "--motion-mode",
                "move",
                "--joint-margin-deg",
                "2.0",
                "--max-joint-step-deg",
                "15.0",
            ],
            timeout_s=150.0,
            result_name="IK",
            ambiguous_motion=True,
        )
        return self._command_result(payload)

    def _run_helper(
        self,
        profile: RuntimeProfile,
        arguments: list[str],
        *,
        timeout_s: float,
        result_name: str,
        ambiguous_motion: bool,
    ) -> dict[str, Any]:
        command = [
            str(self._repo_root / "scripts" / "a1z_sdk_python_in_container.sh"),
            "/workspace/A1Z/scripts/a1z_ee_ik_helper.py",
            "--expected-backend",
            profile.expected_backend,
            "--end-effector-frame",
            "grasp_tcp",
            *arguments,
        ]
        environment = os.environ.copy()
        environment.update(profile.environment)
        completed = self._run_process(
            command,
            cwd=self._repo_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            start_new_session=True,
        )
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        try:
            raw_payload = json.loads(stdout.splitlines()[-1]) if stdout else {}
        except json.JSONDecodeError as exc:
            raise ProtocolError(
                f"{result_name} helper 返回无效 JSON：{exc}；输出={stdout[-500:]}"
            ) from exc
        if not isinstance(raw_payload, dict):
            raise ProtocolError(f"{result_name} helper 返回值不是 JSON object")
        payload = dict(raw_payload)
        if completed.returncode != 0 or not payload.get("ok"):
            message = str(
                payload.get("error")
                or stderr
                or f"{result_name} helper 执行失败"
            )
            if (
                ambiguous_motion
                and payload.get("motion_request_attempted")
                and not payload.get("motion_outcome_verified")
            ):
                raise AmbiguousCommandError(message)
            raise ProtocolError(message)
        return payload

    @staticmethod
    def _command_result(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {"snapshot": payload},
            "backend": str(payload.get("backend", "")),
            "controlMode": str(payload.get("control_mode", "")),
        }
