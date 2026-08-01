from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def _profile():
    from a1z_console.profiles import RuntimeProfile

    return RuntimeProfile(
        name="sim",
        label="仿真",
        expected_backend="isaacsim",
        host="127.0.0.1",
        port=37201,
        socket_path="",
        environment={"A1Z_PROFILE": "sim", "ADAPTER_TEST": "1"},
    )


def test_kinematics_adapter_validates_step_before_worker_submission(
    tmp_path: Path,
) -> None:
    from a1z_console.kinematics_command_adapter import KinematicsCommandAdapter

    adapter = KinematicsCommandAdapter(tmp_path)
    with pytest.raises(ValueError, match="类型"):
        adapter.prepare_step("pose", "x", 0.01, "base", 0.5)
    with pytest.raises(ValueError, match="坐标轴"):
        adapter.prepare_step("translation", "q", 0.01, "base", 0.5)
    with pytest.raises(ValueError, match="坐标系"):
        adapter.prepare_step("translation", "x", 0.01, "camera", 0.5)
    with pytest.raises(ValueError, match="非零有限"):
        adapter.prepare_step("translation", "x", math.nan, "base", 0.5)
    with pytest.raises(ValueError, match="非零有限"):
        adapter.prepare_step("translation", "x", 0.0, "base", 0.5)
    with pytest.raises(ValueError, match="大于 0"):
        adapter.prepare_step("rotation", "z", 5.0, "tool", 0.0)


def test_snapshot_builds_profile_scoped_helper_command(tmp_path: Path) -> None:
    from a1z_console.kinematics_command_adapter import KinematicsCommandAdapter

    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "backend": "isaacsim",
                    "control_mode": "position_hold",
                    "pose": {},
                }
            ),
            stderr="",
        )

    adapter = KinematicsCommandAdapter(tmp_path, run_process=run)
    result = adapter.snapshot(_profile())
    command, kwargs = calls[0]
    assert command[0].endswith("scripts/a1z_sdk_python_in_container.sh")
    assert command[-1] == "snapshot"
    assert command[command.index("--expected-backend") + 1] == "isaacsim"
    assert kwargs["cwd"] == tmp_path.resolve()
    assert dict(kwargs["env"])["ADAPTER_TEST"] == "1"
    assert kwargs["start_new_session"] is True
    assert result["backend"] == "isaacsim"
    assert result["controlMode"] == "position_hold"


def test_step_routes_normalized_request_and_preserves_ambiguity(tmp_path: Path) -> None:
    from a1z_console.kinematics_command_adapter import KinematicsCommandAdapter
    from a1z_console.protocol import AmbiguousCommandError

    calls: list[list[str]] = []

    def ambiguous(
        command: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=json.dumps(
                {
                    "ok": False,
                    "error": "ack lost",
                    "motion_request_attempted": True,
                    "motion_outcome_verified": False,
                }
            ),
            stderr="",
        )

    adapter = KinematicsCommandAdapter(tmp_path, run_process=ambiguous)
    request = adapter.prepare_step("rotation", "z", -5.0, "tool", 0.4)
    with pytest.raises(AmbiguousCommandError, match="ack lost"):
        adapter.step(_profile(), request)
    command = calls[0]
    assert command[command.index("--kind") + 1] == "rotation"
    assert command[command.index("--axis") + 1] == "z"
    assert command[command.index("--delta") + 1] == "-5.0"
    assert command[command.index("--frame") + 1] == "tool"
    assert command[command.index("--motion-mode") + 1] == "cartesian_jog"
    assert command[command.index("--pos-threshold-m") + 1] == "0.00005"
    assert command[command.index("--ori-threshold-deg") + 1] == "0.05"
    assert command[command.index("--max-joint-step-deg") + 1] == "15.0"


@pytest.mark.parametrize(
    ("stdout", "message"),
    [
        ("not-json", "返回无效 JSON"),
        (json.dumps(["not", "object"]), "不是 JSON object"),
    ],
)
def test_helper_rejects_malformed_results(
    tmp_path: Path,
    stdout: str,
    message: str,
) -> None:
    from a1z_console.kinematics_command_adapter import KinematicsCommandAdapter
    from a1z_console.protocol import ProtocolError

    def malformed(
        command: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    adapter = KinematicsCommandAdapter(tmp_path, run_process=malformed)
    with pytest.raises(ProtocolError, match=message):
        adapter.snapshot(_profile())


def test_controller_contains_no_kinematics_process_mechanics() -> None:
    root = Path(__file__).resolve().parents[1]
    controller = (root / "console" / "a1z_console" / "controller.py").read_text()

    assert "subprocess.run" not in controller
    assert "a1z_ee_ik_helper.py" not in controller
    assert "--max-joint-step-deg" not in controller
    assert "KinematicsCommandAdapter" in controller


def test_cartesian_completion_uses_settling_not_fixed_fk_error() -> None:
    root = Path(__file__).resolve().parents[1]
    helper = (root / "scripts" / "a1z_ee_ik_helper.py").read_text()
    rotation_panel = (
        root / "console" / "qml" / "A1ZConsole" / "CartesianRotationPanel.qml"
    ).read_text()

    assert '"completion_basis": "joint_feedback_settled"' in helper
    assert '"diagnostic_only": True' in helper
    assert "End-effector target was not reached from SDK joint feedback" not in helper
    assert "verify_translation" not in helper
    assert "verify_orientation" not in helper
    assert 'qsTr("RX")' in rotation_panel
    assert 'qsTr("RY")' in rotation_panel
    assert 'qsTr("RZ")' in rotation_panel


def test_controller_cartesian_jog_executes_through_owned_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    root = Path(__file__).resolve().parents[1]
    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(root)
    calls: list[tuple[str, str, float, str, float]] = []

    class FakeKinematics:
        def prepare_step(
            self,
            kind: str,
            axis: str,
            delta: float,
            frame: str,
            speed: float,
        ) -> SimpleNamespace:
            return SimpleNamespace(
                kind=kind,
                axis=axis,
                delta=float(delta),
                frame=frame,
                speed=float(speed),
            )

        def step(self, _profile: object, request: SimpleNamespace) -> dict:
            calls.append(
                (
                    request.kind,
                    request.axis,
                    request.delta,
                    request.frame,
                    request.speed,
                )
            )
            return {"data": {"snapshot": {}}}

    captured: dict[str, object] = {}

    def submit(
        _label: str,
        operation: object,
        **_kwargs: object,
    ) -> None:
        captured["result"] = operation()

    try:
        controller._kinematics = FakeKinematics()
        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._telemetry._age_ms = 0
        controller._robot_running = True
        controller._control_mode = "position_hold"
        monkeypatch.setattr(controller, "_submit_operation", submit)

        controller.jogCartesian("translation", "x", 0.01, "base", 0.5)

        assert calls == [("translation", "x", 0.01, "base", 0.5)]
        assert captured["result"] == {"data": {"snapshot": {}}}
    finally:
        controller.shutdown()
