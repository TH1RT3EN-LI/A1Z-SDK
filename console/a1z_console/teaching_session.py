"""Server-authoritative teaching-recording session state and inputs."""

from __future__ import annotations

import math
import re
from typing import Any


class TeachingSessionError(ValueError):
    """A teaching-session action contains invalid or conflicting input."""


class TeachingSessionCoordinator:
    """Own the durable recording state independently of endpoint reachability."""

    def __init__(self, profile_name: str) -> None:
        self._profile_name = str(profile_name)
        self._state = "idle"
        self._active = False
        self._summary = "未录制"

    @property
    def profile_name(self) -> str:
        return self._profile_name

    @property
    def state(self) -> str:
        return self._state

    @property
    def active(self) -> bool:
        return self._active

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def fingerprint(self) -> tuple[str, str, bool, str]:
        return (
            self._profile_name,
            self._state,
            self._active,
            self._summary,
        )

    def select_profile(self, profile_name: str) -> bool:
        """Reset only after the caller has proved no durable session remains."""

        profile_name = str(profile_name)
        if profile_name == self._profile_name:
            return False
        if self._active:
            raise TeachingSessionError("示教录制会话仍未结束，不能切换配置")
        self._profile_name = profile_name
        self._state = "idle"
        self._summary = "未录制"
        return True

    def apply_info(self, info: dict[str, Any]) -> bool:
        """Apply the service's authoritative durable-session snapshot."""

        if "recording" not in info:
            return False
        before = self.fingerprint
        server_active = bool(info["recording"])
        if server_active:
            self._active = True
            self._state = "recording"
            self._summary = "录制中 · 仅停止保存和急停可用"
        else:
            was_orphaned = self._state == "orphaned"
            was_active = self._active
            self._active = False
            if was_active:
                self._state = "idle"
                self._summary = (
                    "控制服务已确认当前没有进行中的录制"
                    if was_orphaned
                    else "未录制"
                )
        return self.fingerprint != before

    def apply_command_result(self, data: dict[str, Any]) -> bool:
        """Project a verified teaching command result into the session."""

        before = self.fingerprint
        if "recording" in data:
            self._active = bool(data["recording"])

        if self._active:
            self._state = "recording"
            sample_hz = self._safe_int(data.get("sample_hz"))
            self._summary = (
                f"录制中 · {sample_hz} Hz · 机械臂零力 / 夹爪自由拖动"
                if sample_hz > 0
                else "录制中 · 机械臂零力 / 夹爪自由拖动"
            )
            return self.fingerprint != before

        frames = self._safe_int(data.get("frames"))
        duration = self._safe_float(data.get("duration_s"))
        path = str(data.get("path", "") or "")
        has_trajectory = bool(path) or frames > 0 or duration > 0.0
        if has_trajectory:
            self._state = "saved"
            self._summary = f"{frames} 帧 / {duration:.2f} s"
            if path:
                self._summary += f" · {path}"
        elif "recording" in data:
            self._state = "idle"
            self._summary = "未录制"
        return self.fingerprint != before

    def mark_endpoint_unavailable(self) -> bool:
        """Retain ownership when the endpoint can no longer confirm the state."""

        if not self._active:
            return False
        before = self.fingerprint
        self._state = "orphaned"
        self._summary = (
            "录制状态待确认 · 控制端点不可用；"
            "请恢复连接，或放弃未保存会话并停止服务"
        )
        return self.fingerprint != before

    def discard_offline(self) -> bool:
        """Resolve an orphan only after lifecycle shutdown has succeeded."""

        before = self.fingerprint
        self._active = False
        self._state = "discarded"
        self._summary = "未保存录制已放弃 · 控制服务已停止"
        return self.fingerprint != before

    @staticmethod
    def normalize_sample_hz(value: object) -> int:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TeachingSessionError("示教采样率必须是 1–250 Hz 的整数") from exc
        if (
            isinstance(value, bool)
            or not math.isfinite(numeric_value)
            or not numeric_value.is_integer()
        ):
            raise TeachingSessionError("示教采样率必须是 1–250 Hz 的整数")
        sample_hz = int(numeric_value)
        if not 1 <= sample_hz <= 250:
            raise TeachingSessionError("示教采样率必须在 1–250 Hz 之间")
        return sample_hz

    @staticmethod
    def normalize_playback_speed(value: object) -> float:
        try:
            speed = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TeachingSessionError("轨迹回放倍率必须在 0.1×–3.0× 之间") from exc
        if not math.isfinite(speed) or not 0.1 <= speed <= 3.0:
            raise TeachingSessionError("轨迹回放倍率必须在 0.1×–3.0× 之间")
        return speed

    @staticmethod
    def normalize_recording_name(value: object) -> str:
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
        if name.lower().endswith(".json"):
            name = name[:-5]
        name = name.lstrip(".") or "teach"
        return f"{name[:91]}.json"

    @staticmethod
    def _safe_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError, OverflowError):
            return 0

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            result = float(value or 0.0)
        except (TypeError, ValueError, OverflowError):
            return 0.0
        return result if math.isfinite(result) else 0.0
