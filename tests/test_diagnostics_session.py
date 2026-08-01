from __future__ import annotations

import json
from pathlib import Path

import pytest


def _profile(name: str = "sim"):
    from a1z_console.profiles import RuntimeProfile

    return RuntimeProfile(
        name=name,
        label="仿真" if name == "sim" else "真机",
        expected_backend="isaacsim" if name == "sim" else "socketcan",
        host="127.0.0.1",
        port=37103 if name == "sim" else 37104,
        socket_path="",
        environment={"A1Z_CAN_CHANNEL": "can-test"},
    )


def _payload(
    *,
    profile: str = "sim",
    required_ok: bool = True,
) -> str:
    failures = 0 if required_ok else 1
    return json.dumps(
        {
            "profile": profile,
            "ready": required_ok,
            "required_failure_count": failures,
            "checks": [
                {
                    "name": "控制服务",
                    "ok": required_ok,
                    "detail": "online" if required_ok else "offline",
                    "severity": "required",
                },
                {
                    "name": "状态文件",
                    "ok": False,
                    "detail": "missing",
                    "severity": "advisory",
                },
            ],
        },
        ensure_ascii=False,
    )


def test_controller_facade_does_not_own_diagnostic_catalog_or_results() -> None:
    root = Path(__file__).resolve().parents[1]
    controller = (root / "console" / "a1z_console" / "controller.py").read_text()
    diagnostics = (
        root / "console" / "a1z_console" / "diagnostics_session.py"
    ).read_text()
    runner = (
        root / "console" / "a1z_console" / "process_task_runner.py"
    ).read_text()

    assert "_preflight_items" not in controller
    assert '"motor_scan": (' not in controller
    assert "--require-control-server-stopped" not in controller
    assert "class DiagnosticsSessionCoordinator" in diagnostics
    assert "ProcessAccess.HARDWARE_INSPECTION" in diagnostics
    assert "self.contract.cancelable" in runner
    assert 'self.kind in {' not in runner


def test_preflight_has_explicit_profile_scoped_states(tmp_path: Path) -> None:
    from a1z_console.diagnostics_session import DiagnosticsSessionCoordinator

    session = DiagnosticsSessionCoordinator(tmp_path, _profile())
    request = session.prepare_preflight()
    assert request.task.kind == "preflight"
    assert request.task.log_stdout is False
    assert request.task.contract.cancelable is True
    assert request.task.arguments[-2:] == ("--profile", "sim")

    session.activate_preflight(request)
    assert session.state == "running"
    assert session.items == []

    result = session.complete_preflight(request, 0, _payload())
    assert result.accepted is True
    assert result.valid is True
    assert result.ready is True
    assert session.state == "ready"
    assert session.items[0]["name"] == "控制服务"

    copied = session.items
    copied[0]["name"] = "mutated"
    assert session.items[0]["name"] == "控制服务"


def test_preflight_issues_are_valid_but_not_reported_as_ready(
    tmp_path: Path,
) -> None:
    from a1z_console.diagnostics_session import DiagnosticsSessionCoordinator

    session = DiagnosticsSessionCoordinator(tmp_path, _profile())
    request = session.prepare_preflight()
    session.activate_preflight(request)
    result = session.complete_preflight(
        request,
        0,
        "diagnostic output\n" + _payload(required_ok=False),
    )

    assert result.valid is True
    assert result.ready is False
    assert session.state == "issues"
    assert "1 项" in session.status
    assert session.items[0]["ok"] is False


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json",
        json.dumps({"profile": "sim", "checks": {}}),
        _payload(profile="real"),
        json.dumps(
            {
                "profile": "sim",
                "ready": True,
                "required_failure_count": 0,
                "checks": [
                    {
                        "name": "bad",
                        "ok": "yes",
                        "detail": "bad",
                        "severity": "required",
                    }
                ],
            }
        ),
        json.dumps(
            {
                "profile": "sim",
                "ready": True,
                "required_failure_count": 0,
                "checks": [
                    {
                        "name": "failed",
                        "ok": False,
                        "detail": "offline",
                        "severity": "required",
                    }
                ],
            }
        ),
    ],
)
def test_preflight_rejects_malformed_or_inconsistent_results(
    tmp_path: Path,
    payload: str,
) -> None:
    from a1z_console.diagnostics_session import DiagnosticsSessionCoordinator

    session = DiagnosticsSessionCoordinator(tmp_path, _profile())
    request = session.prepare_preflight()
    session.activate_preflight(request)
    result = session.complete_preflight(request, 0, payload)

    assert result.accepted is True
    assert result.valid is False
    assert result.error
    assert session.state == "invalid"
    assert session.items == []


def test_profile_change_rejects_late_preflight_result(tmp_path: Path) -> None:
    from a1z_console.diagnostics_session import DiagnosticsSessionCoordinator

    session = DiagnosticsSessionCoordinator(tmp_path, _profile())
    request = session.prepare_preflight()
    session.activate_preflight(request)
    assert session.select_profile(_profile("real")) is True

    result = session.complete_preflight(request, 0, _payload())
    assert result.accepted is False
    assert session.state == "idle"
    assert session.items == []


def test_maintenance_catalog_encodes_access_effects_and_confirmation(
    tmp_path: Path,
) -> None:
    from a1z_console.diagnostics_session import (
        DiagnosticsSessionCoordinator,
        DiagnosticsSessionError,
    )
    from a1z_console.interaction_policy import ProcessAccess, ResourceEffect

    session = DiagnosticsSessionCoordinator(tmp_path, _profile("real"))
    inspection = session.prepare_maintenance("can_check", "")
    assert inspection.contract.access is ProcessAccess.HARDWARE_INSPECTION
    assert inspection.contract.effects is ResourceEffect.NONE
    assert "--require-control-server-stopped" not in inspection.arguments

    gripper = session.prepare_maintenance("gripper_test", "")
    assert gripper.contract.access is ProcessAccess.OFFLINE_DEVICE
    assert gripper.contract.effects & ResourceEffect.GRIPPER
    assert gripper.contract.uncertain_on_failure is True
    assert gripper.contract.blocks_telemetry is True
    assert gripper.contract.cancelable is True
    assert gripper.arguments[0] == "--require-control-server-stopped"
    assert gripper.arguments[-1] == "can-test"

    joint_check = session.prepare_maintenance("motor_check_j4", "")
    assert joint_check.contract.access is ProcessAccess.OFFLINE_DEVICE
    assert joint_check.contract.effects is ResourceEffect.ARM
    assert joint_check.contract.uncertain_on_failure is True
    assert joint_check.contract.blocks_telemetry is True
    assert joint_check.contract.cancelable is True
    assert joint_check.arguments[0] == "--require-control-server-stopped"
    assert joint_check.arguments[-5:] == (
        "--scan",
        "--joints",
        "3",
        "--channel",
        "can-test",
    )

    with pytest.raises(DiagnosticsSessionError, match="MotorA"):
        session.prepare_maintenance("motor_clear_j3", "清错 J3")
    with pytest.raises(DiagnosticsSessionError, match="确认文本"):
        session.prepare_maintenance("motor_clear_j4", "wrong")
    joint_clear = session.prepare_maintenance("motor_clear_j4", "清错 J4")
    assert joint_clear.contract.access is ProcessAccess.OFFLINE_DEVICE
    assert joint_clear.contract.effects is ResourceEffect.ARM
    assert joint_clear.contract.uncertain_on_failure is True
    assert joint_clear.contract.blocks_telemetry is True
    assert joint_clear.contract.cancelable is False
    assert joint_clear.arguments[0] == "--require-control-server-stopped"
    assert joint_clear.arguments[-5:] == (
        "--clear-error",
        "--joints",
        "3",
        "--channel",
        "can-test",
    )

    with pytest.raises(DiagnosticsSessionError, match="确认文本"):
        session.prepare_maintenance("set_zero_all", "wrong")
    zero = session.prepare_maintenance("set_zero_all", "校零 A1Z")
    assert zero.contract.effects & ResourceEffect.ARM
    assert zero.contract.effects & ResourceEffect.CALIBRATION
    assert zero.contract.cancelable is False

    with pytest.raises(DiagnosticsSessionError, match="允许列表"):
        session.prepare_maintenance("shell", "")
