from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONSOLE_ROOT = ROOT / "console"


@pytest.fixture(autouse=True)
def _console_import_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(CONSOLE_ROOT))


def test_real_and_sim_console_endpoints_are_isolated() -> None:
    from a1z_console.profiles import load_profiles

    profiles = load_profiles(ROOT)
    assert profiles["sim"].expected_backend == "isaacsim"
    assert profiles["real"].expected_backend == "socketcan"
    assert profiles["sim"].port == 37103
    assert profiles["real"].port == 37104
    assert profiles["sim"].port != profiles["real"].port


def _serve_once(response: dict, *, close_without_response: bool = False) -> tuple[int, list[dict]]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = int(listener.getsockname()[1])
    requests: list[dict] = []

    def run() -> None:
        connection, _address = listener.accept()
        with connection:
            data = b""
            while b"\n" not in data:
                data += connection.recv(4096)
            requests.append(json.loads(data.split(b"\n", 1)[0]))
            if not close_without_response:
                connection.sendall((json.dumps(response) + "\n").encode())
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return port, requests


def test_motion_response_loss_is_ambiguous_and_never_retried() -> None:
    from a1z_console.profiles import RuntimeProfile
    from a1z_console.protocol import A1ZProtocolClient, AmbiguousCommandError

    port, requests = _serve_once({}, close_without_response=True)
    profile = RuntimeProfile(
        name="sim",
        label="仿真",
        expected_backend="isaacsim",
        host="127.0.0.1",
        port=port,
        socket_path="",
        environment={},
    )
    with pytest.raises(AmbiguousCommandError):
        A1ZProtocolClient(profile).request(
            "move",
            {"joints": [0.0] * 6, "speed": 0.5},
            timeout_s=1.0,
            ambiguous_after_send=True,
        )
    assert len(requests) == 1
    assert requests[0]["cmd"] == "move"


def test_backend_identity_mismatch_fails_closed() -> None:
    from a1z_console.profiles import RuntimeProfile
    from a1z_console.protocol import A1ZProtocolClient, BackendMismatchError

    port, requests = _serve_once(
        {"ok": True, "data": {"backend": "socketcan", "control_mode": "position_hold"}}
    )
    profile = RuntimeProfile(
        name="sim",
        label="仿真",
        expected_backend="isaacsim",
        host="127.0.0.1",
        port=port,
        socket_path="",
        environment={},
    )
    with pytest.raises(BackendMismatchError):
        A1ZProtocolClient(profile).verify_backend(timeout_s=1.0)
    assert [request["cmd"] for request in requests] == ["info"]


def test_anygrasp_summary_outputs_pose_and_joint_degrees(tmp_path: Path) -> None:
    from a1z_console.plan_parser import summarize_pipeline

    output = tmp_path / "run"
    planning = output / "planning"
    anygrasp = output / "anygrasp" / "anygrasp"
    planning.mkdir(parents=True)
    anygrasp.mkdir(parents=True)
    plan = {
        "plan_id": "p1",
        "selected_grasp_candidate_id": "g1",
        "candidate_rank": 0,
        "frame_id": "base_link",
        "joint_trajectory_segments": [
            {
                "segment_type": "approach",
                "target_joint_rad": [0.0, 0.1, -0.2, 0.3, -0.4, 0.5],
                "timeout_s": 3.0,
            }
        ],
        "safety_summary": {"joint_margin_ok": True, "continuity_ok": True},
    }
    (planning / "selected_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    result = {
        "top_grasps": [
            {
                "rank": 0,
                "score": 0.9,
                "width_m": 0.04,
                "translation_xyz_m": [0.1, -0.2, 0.3],
                "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            }
        ]
    }
    (anygrasp / "anygrasp_result.json").write_text(json.dumps(result), encoding="utf-8")
    manifest = {
        "profile": "sim",
        "instruction": "pick",
        "artifacts": {
            "plan": str(planning / "selected_plan.json"),
            "anygrasp": str(anygrasp / "anygrasp_result.json"),
        },
    }
    (output / "pipeline_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    summary = summarize_pipeline(output, ROOT)
    assert summary["profile"] == "sim"
    assert summary["grasp"]["translationMm"] == [100.0, -200.0, 300.0]
    assert summary["segments"][0]["jointsDeg"][1] == pytest.approx(5.73, abs=0.01)
    assert summary["allSafetyPassed"] is True


def test_console_safety_contract_is_present_in_sources() -> None:
    controller = (CONSOLE_ROOT / "a1z_console" / "controller.py").read_text()
    helper = (ROOT / "scripts" / "a1z_ee_ik_helper.py").read_text()
    server = (ROOT / "a1z_ext" / "robots" / "server.py").read_text()

    assert "ThreadPoolExecutor(" in controller
    assert "max_workers=1" in controller
    assert "AmbiguousCommandError" in controller
    assert "--max-joint-step-deg" in controller
    assert "motion_request_attempted" in helper
    assert "record_start" in server
    assert "gravity_mode" in server


def test_estop_and_status_bypass_a_blocking_move() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.mock_robot import MockArmRobot
    from a1z_ext.robots.server import RobotServer

    robot = MockArmRobot(with_gripper=True)
    robot.start()
    server = RobotServer(robot, with_gripper=True)
    result: dict = {}

    def run_move() -> None:
        try:
            result.update(server._dispatch_request(
                "move",
                {"joints": np.rad2deg(np.full(6, 0.2)).tolist(), "speed": 0.05},
            ))
        except Exception as exc:
            result.update({"ok": False, "error": str(exc)})

    motion = threading.Thread(target=run_move, daemon=True)
    motion.start()
    deadline = time.monotonic() + 1.0
    while np.max(robot.get_joint_state()["pos"]) <= 1e-5:
        assert time.monotonic() < deadline
        time.sleep(0.005)

    started = time.monotonic()
    assert server._dispatch_request("status", {})["ok"] is True
    assert server._dispatch_request("estop", {})["ok"] is True
    assert time.monotonic() - started < 0.5

    motion.join(timeout=1.0)
    assert not motion.is_alive()
    assert result["ok"] is False
    assert "estop" in result["error"].lower()
    assert server._dispatch_request("status", {})["data"]["estopped"] is True
    assert server._dispatch_request("move", {"preset": "home"}) == {
        "ok": False,
        "error": "Robot is in estop.",
    }
    assert server._dispatch_request("estop_release", {})["ok"] is True
    robot.stop()


def test_console_sdk_recording_and_control_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.mock_robot import MockArmRobot
    from a1z_ext.robots.server import RobotServer

    robot = MockArmRobot(with_gripper=True, zero_gravity_mode=False)
    robot.start()
    server = RobotServer(robot, with_gripper=True)
    monkeypatch.setattr(
        RobotServer,
        "_recording_path",
        staticmethod(lambda name: tmp_path / Path(str(name)).name),
    )

    assert server._dispatch_request("gravity_mode", {"enabled": True})["ok"] is True
    assert server._dispatch_request("gripper_free_drive", {"enabled": True})["ok"] is True
    assert server._dispatch_request("record_start", {"sample_hz": 50})["ok"] is True
    time.sleep(0.05)
    stopped = server._dispatch_request("record_stop", {"name": "teach.json"})
    assert stopped["ok"] is True
    assert stopped["data"]["frames"] >= 1
    assert (tmp_path / "teach.json").is_file()
    info = server._dispatch_request("record_info", {})["data"]
    assert info["recording"] is False
    assert info["name"] == "teach.json"
    robot.stop()
