from __future__ import annotations

import json
import socket
import threading
import time
import xml.etree.ElementTree as ET
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
    assert profiles["sim"].camera_port == 37203
    assert profiles["real"].camera_port == 37204
    assert profiles["sim"].camera_port != profiles["real"].camera_port


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


def test_camera_bridge_is_profile_isolated_and_independent_of_robot_endpoint() -> None:
    from a1z_console.camera_protocol import CameraProtocolClient
    from a1z_console.profiles import RuntimeProfile

    port, requests = _serve_once(
        {
            "ok": True,
            "data": {
                "profile": "real",
                "ready": True,
                "camera_source": "realsense",
                "width": 640,
                "height": 480,
            },
        }
    )
    profile = RuntimeProfile(
        name="real",
        label="真机",
        expected_backend="socketcan",
        host="127.0.0.1",
        port=1,
        socket_path="",
        environment={},
        camera_host="127.0.0.1",
        camera_port=port,
    )
    result = CameraProtocolClient(profile).request(
        "camera_status",
        timeout_s=1.0,
    )
    assert result["ready"] is True
    assert [request["cmd"] for request in requests] == ["camera_status"]


def test_camera_bridge_rejects_another_profile() -> None:
    from a1z_console.camera_protocol import (
        CameraProfileMismatchError,
        CameraProtocolClient,
    )
    from a1z_console.profiles import RuntimeProfile

    port, _requests = _serve_once(
        {"ok": True, "data": {"profile": "sim", "ready": True}}
    )
    profile = RuntimeProfile(
        name="real",
        label="真机",
        expected_backend="socketcan",
        host="127.0.0.1",
        port=37104,
        socket_path="",
        environment={},
        camera_host="127.0.0.1",
        camera_port=port,
    )
    with pytest.raises(CameraProfileMismatchError):
        CameraProtocolClient(profile).request("camera_status", timeout_s=1.0)


def test_rgbd_preview_is_generated_without_video_node_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    np = pytest.importorskip("numpy")
    monkeypatch.syspath_prepend(str(ROOT / "ros2_ws" / "src" / "a1z_d405"))
    from a1z_d405.console_bridge import compose_rgbd_preview_png
    from a1z_ext.runtime.image_input import read_image_size

    rgb = np.zeros((48, 64, 3), dtype=np.uint8)
    rgb[:, :, 0] = np.arange(64, dtype=np.uint8)
    depth = np.linspace(0.08, 0.5, 48 * 64, dtype=np.float32).reshape(48, 64)
    png = compose_rgbd_preview_png(rgb, depth, max_width=96)

    path = ROOT / "runtime" / "test-camera-preview.png"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
        width, height = read_image_size(path)
    finally:
        path.unlink(missing_ok=True)
    assert width <= 96
    assert height > 0


def test_rgbd_preview_depth_colors_use_a_stable_physical_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    np = pytest.importorskip("numpy")
    monkeypatch.syspath_prepend(str(ROOT / "ros2_ws" / "src" / "a1z_d405"))
    from a1z_d405.console_bridge import _depth_colormap

    first = np.array([[0.1, 0.5, 0.9]], dtype=np.float32)
    with_far_outlier = np.array([[0.1, 0.5, 5.0]], dtype=np.float32)
    depth_range_m = (0.1, 1.0)

    first_colors = _depth_colormap(first, depth_range_m=depth_range_m)
    outlier_colors = _depth_colormap(
        with_far_outlier,
        depth_range_m=depth_range_m,
    )

    assert np.array_equal(first_colors[0, 1], outlier_colors[0, 1])
    with pytest.raises(ValueError, match="finite and increasing"):
        _depth_colormap(first, depth_range_m=(1.0, 0.1))


def test_console_camera_path_uses_ros_topics_not_video_node_numbers() -> None:
    preview = (ROOT / "scripts" / "d405_mosaic_preview.py").read_text()
    dashboard_qml = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "DashboardPage.qml"
    ).read_text()
    sdk_qml = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "SdkFunctionsPage.qml"
    ).read_text()
    main_qml = (CONSOLE_ROOT / "qml" / "A1ZConsole" / "Main.qml").read_text()
    controller = (
        CONSOLE_ROOT / "a1z_console" / "controller.py"
    ).read_text()
    launch = (
        ROOT
        / "ros2_ws"
        / "src"
        / "a1z_motion"
        / "launch"
        / "a1z_stack.launch.py"
    ).read_text()

    assert "/dev/video" not in preview
    for qml in (dashboard_qml, sdk_qml):
        assert "cameraPreviewSource" in qml
        assert "retainWhileLoading: true" in qml
        assert "sourceSize.width:" in qml
        assert "source: root.visible" in qml
    assert "cameraPreviewChanged = Signal()" in controller
    assert "notify=cameraPreviewChanged" in controller
    assert "cameraBridgeOnline" in main_qml
    assert "控制服务离线" in main_qml
    assert "if self._camera_ready:" in controller
    assert "camera_console_bridge" in launch


def test_sdk_console_presents_arm_control_mode_as_exclusive_state() -> None:
    page = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "SdkFunctionsPage.qml"
    ).read_text()
    selector = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ArmControlModeSelector.qml"
    ).read_text()
    qmldir = (CONSOLE_ROOT / "qml" / "A1ZConsole" / "qmldir").read_text()

    assert "ArmControlModeSelector" in page
    assert "controlMode: root.controller.controlMode" in page
    assert "root.controller.setGravityMode(" in page
    assert 'controlMode === "position_hold"' in selector
    assert 'controlMode === "gravity_comp_effort"' in selector
    assert "Accessible.RadioButton" in selector
    assert "ArmControlModeSelector 1.0 ArmControlModeSelector.qml" in qmldir


def test_diagnostics_log_view_can_scroll_without_forced_tail_follow() -> None:
    page = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "DiagnosticsPage.qml"
    ).read_text()

    assert "id: logScroll" in page
    assert "ScrollBar.horizontal.policy: ScrollBar.AsNeeded" in page
    assert "ScrollBar.vertical.policy: ScrollBar.AsNeeded" in page
    assert "property bool followTail: true" in page
    assert 'qsTr("暂停跟随")' in page
    assert 'qsTr("跟随最新")' in page
    assert "cursorPosition = length" not in page


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


def test_gripper_slider_draft_is_not_bound_to_periodic_telemetry() -> None:
    qml = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ManualControlPage.qml"
    ).read_text()

    assert "property real gripperTargetDraft" in qml
    assert "property bool gripperTargetDirty" in qml
    assert "value: root.gripperTargetDraft" in qml
    assert "onMoved:" in qml
    assert "value: root.controller.gripper" not in qml
    assert "root.controller.gripperMeasured" in qml
    assert "root.controller.gripperTarget" in qml


def test_status_separates_gripper_target_from_measured_feedback() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class GripperTelemetrySpy:
        is_estopped = False

        def get_joint_state(self) -> dict[str, object]:
            return {
                "pos": np.zeros(6),
                "vel": np.zeros(6),
                "eff": np.zeros(6),
            }

        def get_gripper_pos(self) -> float:
            return 0.8

        def get_gripper_target_pos(self) -> float:
            return 0.8

        def get_gripper_measured_pos(self) -> float:
            return 0.35

        def command_gripper(self, value: float) -> None:
            self.commanded = float(value)

    robot = GripperTelemetrySpy()
    server = RobotServer(robot, with_gripper=True)
    status = server._dispatch_request("status", {})["data"]
    assert status["gripper_target"] == pytest.approx(0.8)
    assert status["gripper_measured"] == pytest.approx(0.35)
    assert status["gripper"] == pytest.approx(0.35)

    command = server._dispatch_request("gripper", {"value": 0.6})
    assert command["ok"] is True
    assert command["data"]["gripper_target"] == pytest.approx(0.6)
    assert robot.commanded == pytest.approx(0.6)


def test_operator_facing_sdk_capabilities_have_protocol_handlers() -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    expected = {
        "status",
        "info",
        "move",
        "command",
        "gripper",
        "grasp_close",
        "grasp_status",
        "grasp_release",
        "estop",
        "estop_release",
        "gravity_mode",
        "gravity_factor",
        "gripper_free_drive",
        "record_start",
        "record_stop",
        "record_play",
        "record_info",
        "dance",
    }
    assert expected <= set(RobotServer._HANDLERS)
    assert {
        "move",
        "command",
        "gripper",
        "grasp_close",
        "grasp_release",
        "gravity_mode",
        "gravity_factor",
        "gripper_free_drive",
        "record_start",
        "record_play",
        "dance",
    } <= RobotServer._MOTION_COMMANDS
    assert {"status", "info", "grasp_status", "record_info"} <= RobotServer._READ_COMMANDS
    assert RobotServer._EMERGENCY_COMMANDS == {"estop"}


def test_cartesian_jog_uses_selected_base_or_tool_axes() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.cartesian_jog import apply_rotation, apply_translation

    base_to_tool = np.eye(4, dtype=np.float64)
    base_to_tool[:3, :3] = np.array(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )

    base_step = apply_translation(
        base_to_tool, axis="x", delta_m=0.01, frame="base"
    )
    tool_step = apply_translation(
        base_to_tool, axis="x", delta_m=0.01, frame="tool"
    )
    assert base_step[:3, 3] == pytest.approx([0.01, 0.0, 0.0])
    assert tool_step[:3, 3] == pytest.approx([0.0, 0.01, 0.0])

    base_rotation = apply_rotation(
        base_to_tool, axis="x", delta_deg=15.0, frame="base"
    )
    tool_rotation = apply_rotation(
        base_to_tool, axis="x", delta_deg=15.0, frame="tool"
    )
    assert base_rotation[:3, :3] == pytest.approx(
        apply_rotation(np.eye(4), axis="x", delta_deg=15.0, frame="base")[:3, :3]
        @ base_to_tool[:3, :3]
    )
    assert tool_rotation[:3, :3] == pytest.approx(
        base_to_tool[:3, :3]
        @ apply_rotation(np.eye(4), axis="x", delta_deg=15.0, frame="tool")[:3, :3]
    )


def test_official_kinematics_reaches_a_tool_tcp_increment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("pinocchio")
    monkeypatch.syspath_prepend(str(ROOT / "vendor" / "GALAXEA-A1Z"))

    from a1z.robots.kinematics import Kinematics
    from a1z_ext.robots.cartesian_jog import apply_rotation, apply_translation, pose_error

    kinematics = Kinematics(
        str(
            ROOT
            / "build"
            / "robot_packages"
            / "A1Z_G1Z"
            / "urdf"
            / "A1Z_G1Z_control.urdf"
        ),
        end_effector_frame="grasp_tcp",
    )
    current_q = np.deg2rad([10.0, 50.0, -65.0, 20.0, 25.0, -15.0])
    current_pose = kinematics.fk(current_q, frame_name="grasp_tcp")

    target_translation = apply_translation(
        current_pose, axis="x", delta_m=0.005, frame="tool"
    )
    converged, translated_q = kinematics.ik(
        target_translation,
        init_q=current_q,
        frame_name="grasp_tcp",
        dt=0.1,
        pos_threshold=1e-4,
        ori_threshold=np.deg2rad(0.1),
        damping=1e-6,
        max_iters=1000,
    )
    assert converged is True
    translated_pose = kinematics.fk(translated_q, frame_name="grasp_tcp")
    expected_delta_base = current_pose[:3, :3] @ np.array([0.005, 0.0, 0.0])
    actual_delta_base = translated_pose[:3, 3] - current_pose[:3, 3]
    assert actual_delta_base == pytest.approx(expected_delta_base, abs=1e-4)
    assert pose_error(target_translation, translated_pose)[0] < 1e-4

    target_rotation = apply_rotation(
        current_pose, axis="z", delta_deg=2.0, frame="tool"
    )
    converged, rotated_q = kinematics.ik(
        target_rotation,
        init_q=current_q,
        frame_name="grasp_tcp",
        dt=0.1,
        pos_threshold=1e-4,
        ori_threshold=np.deg2rad(0.1),
        damping=1e-6,
        max_iters=1000,
    )
    assert converged is True
    rotation_error = pose_error(
        target_rotation,
        kinematics.fk(rotated_q, frame_name="grasp_tcp"),
    )
    assert rotation_error[0] < 1e-4
    assert rotation_error[1] < 0.1


def test_grasp_tcp_axes_follow_the_official_gripper_mount_frame() -> None:
    official = ET.parse(
        ROOT / "vendor" / "GALAXEA-A1Z" / "a1z" / "robot_models" / "a1z" / "A1Z_G1Z.urdf"
    ).getroot()
    generated = ET.parse(
        ROOT / "build" / "robot_packages" / "A1Z_G1Z" / "urdf" / "A1Z_G1Z_control.urdf"
    ).getroot()

    finger_joints = {
        joint.attrib["name"]: joint
        for joint in official.findall("joint")
        if joint.attrib.get("name", "").startswith("gripper_finger_")
    }
    assert len(finger_joints) == 2
    for joint in finger_joints.values():
        assert joint.find("parent").attrib["link"] == "arm_link6"
        assert joint.find("origin").attrib["rpy"] == "0 0 0"
        assert float(joint.find("origin").attrib["xyz"].split()[0]) > 0.0

    tcp_joint = generated.find("joint[@name='grasp_tcp_joint']")
    assert tcp_joint is not None
    assert tcp_joint.find("parent").attrib["link"] == "arm_link6"
    assert tcp_joint.find("child").attrib["link"] == "grasp_tcp"
    assert tcp_joint.find("origin").attrib["rpy"] == "0 0 0"
    assert [float(value) for value in tcp_joint.find("origin").attrib["xyz"].split()] == [
        0.08,
        0.0,
        0.0,
    ]


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

    gravity = server._dispatch_request(
        "gravity_mode", {"enabled": True, "factor": 0.3}
    )
    assert gravity["ok"] is True
    assert gravity["data"]["gravity_comp_factor"] == pytest.approx(0.3)
    assert server._dispatch_request("info", {})["data"]["gravity_comp_factor"] == pytest.approx(0.3)
    rejected = server._dispatch_request("gravity_factor", {"factor": 1.2})
    assert rejected["ok"] is False
    assert robot.gravity_comp_factor == pytest.approx(0.3)
    changed = server._dispatch_request("gravity_factor", {"factor": 0.65})
    assert changed["ok"] is True
    assert robot.gravity_comp_factor == pytest.approx(0.65)
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


def test_gravity_mode_transition_applies_factor_in_safe_order() -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class GravitySpy:
        is_estopped = False

        def __init__(self) -> None:
            self.factor = 1.0
            self.enabled = False
            self.calls: list[tuple[str, float | bool]] = []

        def set_gravity_comp_factor(self, factor: float) -> None:
            self.factor = float(factor)
            self.calls.append(("factor", self.factor))

        def set_gravity_mode(self, enabled: bool) -> None:
            self.enabled = bool(enabled)
            self.calls.append(("mode", self.enabled))

        def get_robot_info(self) -> dict[str, float]:
            return {"gravity_comp_factor": self.factor}

    robot = GravitySpy()
    server = RobotServer(robot, with_gripper=False)
    assert server._dispatch_request(
        "gravity_mode", {"enabled": True, "factor": 0.3}
    )["ok"]
    assert robot.calls == [("factor", 0.3), ("mode", True)]

    robot.calls.clear()
    assert server._dispatch_request(
        "gravity_mode", {"enabled": False, "factor": 0.8}
    )["ok"]
    assert robot.calls == [("mode", False), ("factor", 0.8)]


def test_robot_factory_rejects_unsafe_gravity_scale_before_backend_creation() -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.get_robot import create_a1z_robot

    for factor in (-0.01, 1.01, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="gravity_comp_factor"):
            create_a1z_robot(backend="mock", gravity_comp_factor=factor)
