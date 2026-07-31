from __future__ import annotations

import math
from pathlib import Path

import pytest


def test_controller_facade_does_not_own_teaching_session_state() -> None:
    root = Path(__file__).resolve().parents[1]
    controller = (root / "console" / "a1z_console" / "controller.py").read_text()
    session = (root / "console" / "a1z_console" / "teaching_session.py").read_text()

    assert "_recording_active" not in controller
    assert "_recording_summary" not in controller
    assert "_safe_recording_name" not in controller
    assert "class TeachingSessionCoordinator" in session
    assert "mark_endpoint_unavailable" in session


def test_recording_session_retains_ownership_when_endpoint_is_lost() -> None:
    from a1z_console.teaching_session import TeachingSessionCoordinator

    session = TeachingSessionCoordinator("sim")
    assert session.apply_info({"recording": True}) is True
    assert session.active is True
    assert session.state == "recording"

    assert session.mark_endpoint_unavailable() is True
    assert session.active is True
    assert session.state == "orphaned"
    assert "待确认" in session.summary

    assert session.apply_info({"recording": True}) is True
    assert session.active is True
    assert session.state == "recording"

    session.mark_endpoint_unavailable()
    assert session.apply_info({"recording": False}) is True
    assert session.active is False
    assert session.state == "idle"
    assert "已确认" in session.summary


def test_verified_stop_and_later_idle_info_preserve_saved_summary() -> None:
    from a1z_console.teaching_session import TeachingSessionCoordinator

    session = TeachingSessionCoordinator("real")
    session.apply_command_result({"recording": True, "sample_hz": 50})
    assert "50 Hz" in session.summary

    session.apply_command_result(
        {
            "recording": False,
            "frames": 125,
            "duration_s": 2.5,
            "path": "/recordings/teach.json",
        }
    )
    assert session.state == "saved"
    assert session.active is False
    assert session.summary == "125 帧 / 2.50 s · /recordings/teach.json"

    assert session.apply_info({"recording": False}) is False
    assert session.state == "saved"
    assert "125 帧" in session.summary


def test_profile_change_cannot_clear_an_active_teaching_session() -> None:
    from a1z_console.teaching_session import (
        TeachingSessionCoordinator,
        TeachingSessionError,
    )

    session = TeachingSessionCoordinator("sim")
    session.apply_info({"recording": True})
    with pytest.raises(TeachingSessionError, match="不能切换配置"):
        session.select_profile("real")
    assert session.profile_name == "sim"
    assert session.active is True

    session.discard_offline()
    assert session.select_profile("real") is True
    assert session.profile_name == "real"
    assert session.state == "idle"
    assert session.summary == "未录制"


@pytest.mark.parametrize("value", [0, 251, 1.5, math.inf, True, "bad"])
def test_sample_rate_is_validated_at_the_session_boundary(value: object) -> None:
    from a1z_console.teaching_session import (
        TeachingSessionCoordinator,
        TeachingSessionError,
    )

    with pytest.raises(TeachingSessionError, match="采样率"):
        TeachingSessionCoordinator.normalize_sample_hz(value)

    assert TeachingSessionCoordinator.normalize_sample_hz(50) == 50


@pytest.mark.parametrize("value", [0.0, 3.1, math.inf, math.nan, "bad"])
def test_playback_speed_is_finite_and_bounded(value: object) -> None:
    from a1z_console.teaching_session import (
        TeachingSessionCoordinator,
        TeachingSessionError,
    )

    with pytest.raises(TeachingSessionError, match="回放倍率"):
        TeachingSessionCoordinator.normalize_playback_speed(value)

    assert TeachingSessionCoordinator.normalize_playback_speed(1.5) == 1.5


def test_recording_name_keeps_json_suffix_after_sanitizing_and_truncating() -> None:
    from a1z_console.teaching_session import TeachingSessionCoordinator

    assert (
        TeachingSessionCoordinator.normalize_recording_name(" ../示教 one.JSON ")
        == "_one.json"
    )
    long_name = TeachingSessionCoordinator.normalize_recording_name("a" * 200)
    assert len(long_name) == 96
    assert long_name.endswith(".json")
    assert "/" not in long_name
