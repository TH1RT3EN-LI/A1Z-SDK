from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
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
    assert profiles["sim"].manual_motion_defaults.speed_rad_s == 0.5
    assert profiles["real"].manual_motion_defaults.speed_rad_s == 0.25
    assert profiles["sim"].manual_motion_defaults.joint_step_deg == 2.0
    assert profiles["real"].manual_motion_defaults.joint_step_deg == 1.0


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


def _serve_raw_once(response: bytes) -> tuple[int, list[dict]]:
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
            connection.sendall(response)
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return port, requests


def _serve_stalled_request() -> tuple[int, threading.Event, threading.Event]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = int(listener.getsockname()[1])
    request_received = threading.Event()
    client_closed = threading.Event()

    def run() -> None:
        connection, _address = listener.accept()
        with connection:
            data = b""
            while b"\n" not in data:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                data += chunk
            request_received.set()
            while connection.recv(4096):
                pass
            client_closed.set()
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return port, request_received, client_closed


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


@pytest.mark.parametrize(
    "response",
    (
        b"not-json\n",
        b'{"ok": true, "data": []}\n',
        b'{"data": {}}\n',
    ),
)
def test_motion_malformed_response_is_ambiguous(response: bytes) -> None:
    from a1z_console.profiles import RuntimeProfile
    from a1z_console.protocol import A1ZProtocolClient, AmbiguousCommandError

    port, requests = _serve_raw_once(response)
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


def test_explicit_server_rejection_is_not_ambiguous() -> None:
    from a1z_console.profiles import RuntimeProfile
    from a1z_console.protocol import A1ZProtocolClient, ProtocolError

    port, _requests = _serve_once(
        {
            "ok": False,
            "execution_state": "rejected",
            "error": "rejected",
        }
    )
    profile = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", port, "", {}
    )
    with pytest.raises(ProtocolError, match="rejected") as captured:
        A1ZProtocolClient(profile).request(
            "move",
            timeout_s=1.0,
            ambiguous_after_send=True,
        )
    assert captured.type.__name__ == "ProtocolError"


@pytest.mark.parametrize("execution_state", ("", "submitted_unverified"))
def test_server_failure_without_pre_execution_rejection_is_ambiguous(
    execution_state: str,
) -> None:
    from a1z_console.profiles import RuntimeProfile
    from a1z_console.protocol import A1ZProtocolClient, AmbiguousCommandError

    response = {"ok": False, "error": "target not reached"}
    if execution_state:
        response["execution_state"] = execution_state
    port, _requests = _serve_once(response)
    profile = RuntimeProfile(
        "sim", "仿真", "isaacsim", "127.0.0.1", port, "", {}
    )
    with pytest.raises(AmbiguousCommandError, match="执行前被拒绝"):
        A1ZProtocolClient(profile).request(
            "move",
            timeout_s=1.0,
            ambiguous_after_send=True,
        )


def test_socket_cancellation_interrupts_stalled_name_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from a1z_console.cancellable_socket import (
        CancellableSocket,
        SocketRequestCancelledError,
    )

    resolver_started = threading.Event()
    release_resolver = threading.Event()
    resolver_finished = threading.Event()

    def blocked_getaddrinfo(*_args, **_kwargs):
        resolver_started.set()
        assert release_resolver.wait(5.0)
        resolver_finished.set()
        return []

    monkeypatch.setattr(socket, "getaddrinfo", blocked_getaddrinfo)
    owner = CancellableSocket()
    errors: list[BaseException] = []

    def request() -> None:
        try:
            owner.open_connection("blocked.invalid", 37103, timeout_s=5.0)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=request)
    worker.start()
    assert resolver_started.wait(1.0)
    owner.cancel()
    worker.join(0.5)
    release_resolver.set()

    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], SocketRequestCancelledError)
    assert resolver_finished.wait(1.0)


def test_stalled_name_resolution_has_a_global_thread_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from a1z_console.cancellable_socket import CancellableSocket

    resolver_started = threading.Event()
    release_resolver = threading.Event()
    resolver_finished = threading.Event()
    resolver_calls = 0

    def blocked_getaddrinfo(*_args, **_kwargs):
        nonlocal resolver_calls
        resolver_calls += 1
        resolver_started.set()
        release_resolver.wait(5.0)
        resolver_finished.set()
        return []

    monkeypatch.setattr(socket, "getaddrinfo", blocked_getaddrinfo)

    def start_and_cancel(owner: CancellableSocket) -> threading.Thread:
        def request() -> None:
            try:
                owner.open_connection(
                    "blocked.invalid",
                    37103,
                    timeout_s=5.0,
                )
            except Exception:
                pass

        worker = threading.Thread(target=request)
        worker.start()
        time.sleep(0.06)
        owner.cancel()
        worker.join(0.5)
        assert not worker.is_alive()
        return worker

    start_and_cancel(CancellableSocket())
    assert resolver_started.wait(1.0)
    for _index in range(5):
        start_and_cancel(CancellableSocket())

    assert resolver_calls == 1
    resolver_threads = [
        thread
        for thread in threading.enumerate()
        if thread.name == "a1z-console-dns-resolver"
    ]
    assert len(resolver_threads) == 1
    assert resolver_threads[0].daemon is True

    release_resolver.set()
    assert resolver_finished.wait(1.0)


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


@pytest.mark.parametrize("client_kind", ["robot", "camera"])
def test_protocol_request_can_be_cancelled_during_blocking_receive(
    client_kind: str,
) -> None:
    from a1z_console.camera_protocol import CameraProtocolClient
    from a1z_console.profiles import RuntimeProfile
    from a1z_console.protocol import A1ZProtocolClient

    port, request_received, client_closed = _serve_stalled_request()
    profile = RuntimeProfile(
        name="sim",
        label="仿真",
        expected_backend="isaacsim",
        host="127.0.0.1",
        port=port if client_kind == "robot" else 37103,
        socket_path="",
        environment={},
        camera_host="127.0.0.1",
        camera_port=port if client_kind == "camera" else 37203,
    )
    client = (
        A1ZProtocolClient(profile)
        if client_kind == "robot"
        else CameraProtocolClient(profile)
    )
    errors: list[Exception] = []

    def request() -> None:
        try:
            if client_kind == "robot":
                client.request("status", timeout_s=5.0)
            else:
                client.request("camera_status", timeout_s=5.0)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=request)
    worker.start()
    assert request_received.wait(1.0)

    started = time.monotonic()
    client.cancel_pending_requests()
    worker.join(0.5)

    assert not worker.is_alive()
    assert time.monotonic() - started < 0.5
    assert errors
    assert client_closed.wait(0.5)


def test_interaction_policy_gates_capabilities_by_device_effect() -> None:
    from dataclasses import replace

    from a1z_console.interaction_policy import (
        InteractionPolicy,
        OnlineCapability,
        ProcessAccess,
        ProcessTaskContract,
        ResourceEffect,
    )

    policy = InteractionPolicy(
        connected=True,
        backend_matched=True,
        connection_issue="",
        telemetry_fresh=True,
        robot_running=True,
        faulted=False,
        fault_message="",
        control_mode="gravity_comp_effort",
        gripper_free_drive=False,
        command_busy=False,
        task_busy=False,
        task_label="",
        emergency_busy=False,
        recording_active=False,
        outcome_uncertain=False,
        estopped=False,
        supports_hardware_inspection=True,
        supports_offline_maintenance=True,
    )

    assert "位置保持" in policy.online_error(OnlineCapability.ARM_MOTION)
    assert policy.online_error(OnlineCapability.GRIPPER_MOTION) == ""
    assert policy.online_error(OnlineCapability.ARM_MODE) == ""
    assert "自由拖动" in replace(
        policy,
        gripper_free_drive=True,
    ).online_error(OnlineCapability.GRIPPER_MOTION)
    position_hold_free_gripper = replace(
        policy,
        control_mode="position_hold",
        gripper_free_drive=True,
    )
    assert "自由拖动" in position_hold_free_gripper.online_error(
        OnlineCapability.ARM_GRIPPER_MOTION
    )
    assert "自由拖动" in position_hold_free_gripper.online_error(
        OnlineCapability.PLAYBACK
    )
    estop_recovery = replace(
        policy,
        control_mode="position_hold",
        estopped=True,
        faulted=True,
        robot_running=False,
    )
    assert estop_recovery.online_error(OnlineCapability.ESTOP_RELEASE) == ""
    assert "软急停锁" in estop_recovery.service_stop_error()
    assert "结果不确定" in replace(
        estop_recovery,
        estopped=False,
        outcome_uncertain=True,
    ).service_stop_error()
    offline_estop = replace(
        estop_recovery,
        connected=False,
        backend_matched=False,
        connection_issue="offline",
        telemetry_fresh=False,
    )
    assert offline_estop.service_start_error() == ""
    assert offline_estop.motion_recovery_action == "start_server"
    offline_recheck = replace(
        offline_estop,
        estopped=False,
        outcome_uncertain=True,
        outcome_recheck_requested=True,
    )
    assert offline_recheck.service_start_error() == ""
    assert offline_recheck.motion_recovery_action == "start_server"

    offline = replace(
        policy,
        connected=False,
        backend_matched=False,
        connection_issue="offline",
        telemetry_fresh=False,
        robot_running=False,
    )
    assert offline.offline_device_error() == ""
    assert "尚未确认为离线" in replace(
        offline,
        connection_issue="stale",
    ).offline_device_error()
    assert "结果不确定" in replace(
        offline,
        outcome_uncertain=True,
    ).offline_device_error()

    contract = ProcessTaskContract(
        ProcessAccess.OFFLINE_DEVICE,
        ResourceEffect.GRIPPER | ResourceEffect.CALIBRATION,
        uncertain_on_failure=True,
    )
    assert contract.affects_device is True
    assert contract.effects & ResourceEffect.GRIPPER
    assert "未声明具体控制能力" in policy.process_access_error(
        ProcessAccess.ONLINE_DEVICE
    )
    assert policy.process_access_error(
        ProcessAccess.ONLINE_DEVICE,
        online_capability=OnlineCapability.GRIPPER_MOTION,
    ) == ""
    recording_cleanup = replace(
        policy,
        recording_active=True,
        outcome_uncertain=True,
        estopped=True,
        faulted=True,
        robot_running=False,
    )
    assert (
        recording_cleanup.online_error(OnlineCapability.RECORDING_STOP) == ""
    )
    assert "录制中" in recording_cleanup.online_error(
        OnlineCapability.ESTOP_RELEASE
    )
    recording_orphan = replace(
        recording_cleanup,
        connected=False,
        backend_matched=False,
        connection_issue="offline",
        telemetry_fresh=False,
        recording_state="orphaned",
    )
    assert "状态待确认" in recording_orphan.online_error(
        OnlineCapability.ARM_MOTION
    )
    assert "恢复连接" in recording_orphan.motion_gate_text


def test_mode_confirmation_state_covers_pending_and_uncertain_results() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.device_command_executor import DeviceCommandRequest
    from a1z_console.interaction_policy import ResourceEffect

    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT)
    try:
        controller._connected = True
        controller._backend_matched = True
        controller._telemetry._age_ms = 0
        controller._control_mode = "position_hold"

        assert controller.armModeState == "confirmed"
        assert controller.gripperModeState == "confirmed"

        sequence = controller._commands.submit_command(
            DeviceCommandRequest(
                label="mode",
                operation=lambda: {},
                effects=ResourceEffect.ARM,
                result_handler="gravity",
            )
        )
        assert sequence is not None
        assert controller.armModeState == "pending"

        controller._uncertain = True
        assert controller.armModeState == "uncertain"
        assert controller.gripperModeState == "uncertain"
    finally:
        controller.shutdown()


def test_manual_refresh_uses_telemetry_task_capability_gate() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.interaction_policy import ProcessAccess, ProcessTaskContract
    from a1z_console.process_task_runner import ProcessTaskRequest

    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT)
    request = ProcessTaskRequest.create(
        kind="blocking",
        label="阻断遥测的设备任务",
        program="/bin/sh",
        arguments=["-c", "exec sleep 10"],
        working_directory=ROOT,
        environment={},
        contract=ProcessTaskContract(
            ProcessAccess.TASK_SLOT,
            blocks_telemetry=True,
        ),
    )
    try:
        assert controller._task_runner.start(request) is True
        assert controller.telemetryRefreshEnabled is False

        controller.refreshNow()

        assert controller.operationFeedbackState == "warning"
        assert "遥测读取已暂停" in controller.operationFeedbackMessage
    finally:
        controller.shutdown()


def test_controller_reuses_policy_snapshot_until_an_input_changes() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController

    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    try:
        first = controller._policy
        assert controller._policy is first
        assert controller.motionEnabled is False
        assert controller._policy is first

        controller._connected = True
        assert controller._policy is not first
    finally:
        controller.shutdown()


def test_console_log_model_appends_incrementally_and_stays_bounded() -> None:
    pytest.importorskip("PySide6")

    from a1z_console.log_model import ConsoleLogModel

    model = ConsoleLogModel(maximum_lines=3)
    inserted: list[tuple[int, int]] = []
    removed: list[tuple[int, int]] = []
    model.rowsInserted.connect(
        lambda _parent, first, last: inserted.append((first, last))
    )
    model.rowsRemoved.connect(
        lambda _parent, first, last: removed.append((first, last))
    )
    maximum_changes: list[int] = []
    column_changes: list[int] = []
    model.maximumLineLengthChanged.connect(
        lambda: maximum_changes.append(model.maximumLineLength)
    )
    model.maximumDisplayColumnsChanged.connect(
        lambda: column_changes.append(model.maximumDisplayColumns)
    )

    model.append_lines(["one", "two-long"])
    model.append_lines(["three", "four"])

    assert model.entries() == ["two-long", "three", "four"]
    assert inserted == [(0, 1), (1, 2)]
    assert removed == [(0, 0)]
    assert model.maximumLineLength == len("two-long")
    assert model.maximumDisplayColumns == len("two-long")
    assert maximum_changes == [len("two-long")]
    model.append_lines(["x", "y", "z"])
    assert model.maximumLineLength == 1
    assert model.maximumDisplayColumns == 1
    model.clear()
    assert model.rowCount() == 0
    assert model.maximumLineLength == 0
    assert model.maximumDisplayColumns == 0
    assert column_changes[-1] == 0


def test_console_log_model_accounts_for_wide_unicode_columns() -> None:
    pytest.importorskip("PySide6")

    from a1z_console.log_model import ConsoleLogModel

    model = ConsoleLogModel(maximum_lines=4)
    model.append_lines(["ascii", "夹爪状态", "A\tB"])

    assert model.maximumDisplayColumns == 9


def test_console_log_model_measures_only_new_log_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")

    from a1z_console.log_model import ConsoleLogModel

    model = ConsoleLogModel(maximum_lines=3)
    measured: list[str] = []
    original = model._display_columns

    def measure(line: str) -> int:
        measured.append(line)
        return original(line)

    monkeypatch.setattr(model, "_display_columns", measure)
    model.append_lines(["longest", "middle", "short"])
    model.append_lines(["new"])

    assert measured == ["longest", "middle", "short", "new"]
    assert model.entries() == ["middle", "short", "new"]
    assert model.maximumLineLength == len("middle")


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
    camera_qml = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "CameraPanel.qml"
    ).read_text()
    main_qml = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ConsoleHeader.qml"
    ).read_text()
    controller = (
        CONSOLE_ROOT / "a1z_console" / "controller.py"
    ).read_text()
    coordinator = (
        CONSOLE_ROOT / "a1z_console" / "camera_coordinator.py"
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
    for qml in (dashboard_qml, camera_qml):
        assert "cameraPreviewSource" in qml
        assert "cameraPreviewAvailable" in qml
        assert "cameraPreviewSource.length" not in qml
        assert "retainWhileLoading: true" in qml
        assert "sourceSize.width:" in qml
        assert "source: root.visible" in qml
    assert "status !== Image.Error" in dashboard_qml
    assert "dashboardCameraPreview.status === Image.Error" in dashboard_qml
    assert 'qsTr("画面解码失败，请刷新")' in dashboard_qml
    assert "cameraPreviewChanged = Signal()" in controller
    assert "cameraStateChanged = Signal()" in controller
    assert "notify=cameraPreviewChanged" in controller
    assert "notify=cameraStateChanged" in controller
    assert "def cameraPreviewAvailable(self) -> bool:" in controller
    assert "cameraBridgeOnline" in main_qml
    assert "控制服务离线" in main_qml
    assert '"camera_capture" if self._ready else "camera_status"' in coordinator
    assert "CameraProtocolClient" not in controller
    assert "CameraCoordinator(self._profile, self)" in controller
    assert "camera_console_bridge" in launch


def test_arm_page_presents_control_mode_as_exclusive_state() -> None:
    page = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ArmModePanel.qml"
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


def test_console_uses_pinned_apple_light_visual_system() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    theme = (qml_root / "Theme.qml").read_text()
    main = (qml_root / "Main.qml").read_text()
    qmldir = (qml_root / "qmldir").read_text()
    app_button = (qml_root / "AppButton.qml").read_text()

    assert 'readonly property color canvas: "#FFF2F2F7"' in theme
    assert 'readonly property color surface: "#FFFFFFFF"' in theme
    assert 'readonly property color accent: "#FF007AFF"' in theme
    assert 'readonly property color accentFill: "#FF1E6EF4"' in theme
    assert 'readonly property color red: "#FFFF383C"' in theme
    assert "gradient:" not in main
    assert "glyph:" not in main
    assert "implicitContentWidth + leftPadding + rightPadding" in app_button

    for component in (
        "AppToolTip",
        "AppIcon",
        "AppTextField",
        "AppTextArea",
        "AppSlider",
        "AppSpinBox",
        "AppComboBox",
        "InlineBanner",
        "StartupGuidePanel",
    ):
        assert f"{component} 1.0 {component}.qml" in qmldir

    for page_name in (
        "ArmControlPage.qml",
        "GripperControlPage.qml",
        "VisionPage.qml",
        "GraspTaskPage.qml",
        "TeachingPage.qml",
        "DeviceSettingsPage.qml",
        "DashboardPage.qml",
        "DiagnosticsPage.qml",
    ):
        page = (qml_root / page_name).read_text()
        assert '"#FF0B0E13"' not in page

    for page_name, redundant_title in (
        ("DashboardPage.qml", 'title: qsTr("运行总览")'),
        ("ArmControlPage.qml", 'title: qsTr("机械臂运动")'),
        ("GripperControlPage.qml", 'title: qsTr("夹爪控制")'),
        ("GraspTaskPage.qml", 'title: qsTr("抓取任务")'),
        ("DiagnosticsPage.qml", 'title: qsTr("诊断与维护")'),
    ):
        page = (qml_root / page_name).read_text()
        assert redundant_title not in page


def test_qml_shell_organizes_pages_by_function_and_preserves_state() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    main = (qml_root / "Main.qml").read_text()
    workspace = (qml_root / "ConsoleWorkspace.qml").read_text()
    navigation = (qml_root / "ConsoleNavigation.qml").read_text()
    manual_page = (qml_root / "ManualControlPage.qml").read_text()
    arm_page = (qml_root / "ArmControlPage.qml").read_text()
    grasp_page = (qml_root / "GraspTaskPage.qml").read_text()
    settings_page = (qml_root / "DeviceSettingsPage.qml").read_text()
    qmldir = (qml_root / "qmldir").read_text()

    assert "ConsoleHeader" in main
    assert "ConsoleFeedback" in main
    assert "ConsoleWorkspace" in main
    assert 'objectName: "sharedRuntimeLog"' in main
    assert "DashboardPage {" not in main
    assert "A1Z SDK Console" not in main
    assert 'objectName: "pageStack"' in workspace
    assert "currentIndex: root.pageIndex(root.currentPage)" in workspace
    assert "sourceComponent:" not in workspace
    assert workspace.count("SafetyRail {") == 1
    for page in (
        "DashboardPage",
        "ManualControlPage",
        "VisionPage",
        "GraspTaskPage",
        "TeachingPage",
        "DeviceSettingsPage",
        "DiagnosticsPage",
    ):
        assert f"{page} {{" in workspace

    assert "ArmControlPage {" in manual_page
    assert "GripperControlPage {" in manual_page
    assert 'qsTr("运动与定位")' in manual_page
    assert 'qsTr("末端工具")' in manual_page
    for panel_name in (
        "GripperModePanel.qml",
        "GripperOpeningPanel.qml",
        "GripperActionPanel.qml",
    ):
        panel = (qml_root / panel_name).read_text()
        assert "required property var controller" not in panel
        assert "root.controller" not in panel

    for route, label in (
        ("manual", "手动操控"),
        ("vision", "感知检查"),
        ("grasp", "自动抓取"),
        ("teaching", "示教与回放"),
        ("settings", "运行配置"),
    ):
        assert f'route: "{route}"' in navigation
        assert label in navigation
    assert "SDK 功能" not in navigation
    assert "AnyGrasp" not in navigation
    assert "PresetMotionPanel {" in arm_page
    assert "ArmModePanel {" in arm_page
    assert "EndEffectorPosePanel {" in arm_page
    assert "JointControlPanel {" in arm_page
    assert "CartesianControlPanel {" in arm_page
    assert "ListModel {" not in arm_page
    assert "jogCartesian(" not in arm_page
    assert "GraspComputePanel {" in grasp_page
    assert "GraspPlanReviewPanel {" in grasp_page
    assert "GraspExecutionPanel {" in grasp_page
    assert "Repeater {" not in grasp_page
    assert "executePlan(" not in grasp_page
    assert "ControlServicePanel {" in settings_page
    assert "GravityCompensationPanel {" in settings_page
    for component in (
        "ArmControlPage",
        "ManualControlPage",
        "EndEffectorPosePanel",
        "JointControlPanel",
        "JointControlRow",
        "CartesianControlPanel",
        "CartesianTranslationPanel",
        "CartesianRotationPanel",
        "PageScrollView",
        "GripperControlPage",
        "GripperModePanel",
        "GripperOpeningPanel",
        "GripperActionPanel",
        "VisionPage",
        "GraspTaskPage",
        "GraspComputePanel",
        "GraspPlanReviewPanel",
        "GraspPlanSegmentRow",
        "GraspExecutionPanel",
        "TeachingPage",
        "DeviceSettingsPage",
    ):
        assert f"{component} 1.0 {component}.qml" in qmldir


def test_qml_page_stack_preserves_unsent_drafts_across_navigation() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    from a1z_console.controller import ConsoleController

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT, app)
    QQmlEngine.setObjectOwnership(controller, QQmlEngine.CppOwnership)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller})
    engine.addImportPath(str(CONSOLE_ROOT / "qml"))
    engine.loadFromModule("A1ZConsole", "Main")
    roots = engine.rootObjects()
    assert roots

    window = roots[0]
    arm = window.findChild(QObject, "armControlPage")
    joint_control = window.findChild(QObject, "jointControlPanel")
    gripper = window.findChild(QObject, "gripperControlPage")
    gravity = window.findChild(QObject, "gravityCompensationPanel")
    preset = window.findChild(QObject, "presetMotionPanel")
    grasp = window.findChild(QObject, "graspTaskPage")
    grasp_execution = window.findChild(QObject, "graspExecutionPanel")
    grasp_phrase = window.findChild(QObject, "graspExecutePhrase")
    teaching = window.findChild(QObject, "teachingPage")
    settings = window.findChild(QObject, "deviceSettingsPage")
    safety = window.findChild(QObject, "safetyRail")
    pending_pill = window.findChild(QObject, "pendingDraftPill")
    real_profile_button = window.findChild(QObject, "realProfileButton")
    assert arm is not None
    assert joint_control is not None
    assert gripper is not None
    assert gravity is not None
    assert preset is not None
    assert grasp is not None
    assert grasp_execution is not None
    assert grasp_phrase is not None
    assert teaching is not None
    assert settings is not None
    assert safety is not None
    assert pending_pill is not None
    assert real_profile_button is not None
    try:
        assert real_profile_button.property("enabled") is True
        joint_control.setProperty("jointDraftDirty", True)
        gripper.setProperty("gripperTargetDirty", True)
        gravity.setProperty("gravityFactorDirty", True)
        app.processEvents()
        assert joint_control.property("jointDraftDirty") is True
        assert real_profile_button.property("enabled") is False
        assert pending_pill.property("visible") is True
        assert preset.property("armDraftPending") is True
        assert grasp.property("motionDraftPending") is True
        assert teaching.property("motionDraftPending") is True
        assert settings.property("armDraftPending") is True
        assert settings.property("gripperDraftPending") is True
        assert safety.property("armDraftPending") is True
        assert safety.property("gripperDraftPending") is True
        assert safety.property("configurationDraftPending") is True
        assert controller.pendingDrafts is True
        assert controller.pendingDraftSummary == (
            "机械臂目标、夹爪开度、重力补偿系数"
        )
        window.setProperty("currentPage", "manual")
        app.processEvents()
        window.setProperty("currentPage", "diagnostics")
        app.processEvents()
        window.setProperty("currentPage", "settings")
        app.processEvents()

        assert window.findChild(QObject, "armControlPage") == arm
        assert window.findChild(QObject, "jointControlPanel") == joint_control
        assert window.findChild(QObject, "gripperControlPage") == gripper
        assert window.findChild(QObject, "gravityCompensationPanel") == gravity
        assert window.findChild(QObject, "graspExecutionPanel") == grasp_execution
        assert arm.property("jointDraftDirty") is True
        assert gripper.property("gripperTargetDirty") is True
        assert gravity.property("gravityFactorDirty") is True
        assert real_profile_button.property("enabled") is False
        assert controller._monitoring_started is False
        assert controller.cameraBusy is False
        assert QMetaObject.invokeMethod(arm, "discardJointDraft")
        assert QMetaObject.invokeMethod(gripper, "discardGripperDraft")
        assert QMetaObject.invokeMethod(gravity, "discardGravityFactorDraft")
        app.processEvents()
        assert arm.property("jointDraftDirty") is False
        assert joint_control.property("jointDraftDirty") is False
        assert gripper.property("gripperTargetDirty") is False
        assert gravity.property("gravityFactorDirty") is False
        assert real_profile_button.property("enabled") is True
        assert pending_pill.property("visible") is False
        assert controller.pendingDrafts is False

        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._telemetry._age_ms = 0
        controller.stateChanged.emit()
        controller.telemetryTimingChanged.emit()

        controller._plan._current = True
        controller._plan._state = "ready"
        controller._plan._summary = {"allSafetyPassed": True}
        controller._robot_running = True
        controller._control_mode = "position_hold"
        controller._estopped = False
        controller._camera._bridge_online = True
        controller._camera._ready = True
        controller._diagnostics._state = "ready"
        controller._plan.changed.emit()
        controller.stateChanged.emit()
        controller.cameraStateChanged.emit()
        controller.preflightChanged.emit()
        app.processEvents()
        assert grasp_execution.property("actualExecutionAvailable") is True
        grasp_phrase.setProperty("text", "执行 SIM")
        app.processEvents()
        assert grasp_phrase.property("text") == "执行 SIM"

        controller._estopped = True
        controller.stateChanged.emit()
        app.processEvents()
        app.processEvents()
        assert grasp_execution.property("actualExecutionAvailable") is False
        assert grasp_phrase.property("text") == ""
        controller._estopped = False
        controller.stateChanged.emit()

        controller._gripper_target = 0.23
        controller._gripper = 0.23
        window.setProperty("currentPage", "manual")
        window.setProperty("manualSection", "tool")
        controller.gripperTelemetryChanged.emit()
        app.processEvents()
        assert gripper.property("gripperDraftInitialized") is True
        assert gripper.property("gripperTargetDraft") == pytest.approx(0.23)

        gripper.setProperty("gripperTargetDraft", 0.4)
        gripper.setProperty("gripperTargetDirty", True)
        controller._connected = False
        controller._connection_issue = "offline"
        controller._telemetry._age_ms = -1
        controller.stateChanged.emit()
        controller.telemetryTimingChanged.emit()
        app.processEvents()
        assert gripper.property("gripperTargetDirty") is True
        assert gripper.property("gripperTargetStale") is True
        slider = window.findChild(QObject, "gripperTargetSlider")
        assert slider is not None
        assert slider.property("enabled") is False

        controller._connected = True
        controller._connection_issue = ""
        controller._telemetry._age_ms = 0
        controller.stateChanged.emit()
        controller.telemetryTimingChanged.emit()
        app.processEvents()
        assert gripper.property("gripperTargetStale") is True
        assert QMetaObject.invokeMethod(gripper, "discardGripperDraft")

        window.setProperty("currentPage", "manual")
        app.processEvents()
        controller._profile_name = "real"
        controller._gripper_target = None
        controller._gripper = None
        controller.stateChanged.emit()
        app.processEvents()
        assert gripper.property("gripperDraftProfile") == "real"
        assert gripper.property("gripperDraftInitialized") is False
        assert gripper.property("gripperTargetDirty") is False
    finally:
        window.setProperty("visible", False)
        controller.shutdown()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def test_qml_shared_resource_actions_observe_cross_page_draft_locks() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    workspace = (qml_root / "ConsoleWorkspace.qml").read_text()
    arm = (qml_root / "ArmControlPage.qml").read_text()
    arm_mode = (qml_root / "ArmModePanel.qml").read_text()
    presets = (qml_root / "PresetMotionPanel.qml").read_text()
    gripper = "\n".join(
        (qml_root / name).read_text()
        for name in (
            "GripperControlPage.qml",
            "GripperModePanel.qml",
            "GripperOpeningPanel.qml",
            "GripperActionPanel.qml",
        )
    )
    grasp = (qml_root / "GraspTaskPage.qml").read_text()
    grasp_execution = (qml_root / "GraspExecutionPanel.qml").read_text()
    teaching = (qml_root / "TeachingPlaybackPanel.qml").read_text()
    settings = (qml_root / "DeviceSettingsPage.qml").read_text()
    diagnostics = (qml_root / "DiagnosticsPage.qml").read_text()
    maintenance = (qml_root / "MaintenancePanel.qml").read_text()
    ros_stack = (qml_root / "RosStackPanel.qml").read_text()
    safety = (qml_root / "SafetyRail.qml").read_text()
    header = (qml_root / "ConsoleHeader.qml").read_text()

    assert "armDraftPending: root.jointDraftDirty" in arm
    assert "&& !root.armDraftPending" in arm_mode
    assert presets.count("&& !root.armDraftPending") == 4
    assert "draftPending: root.gripperTargetDirty" in gripper
    assert "motionDraftPending:" in workspace
    assert "&& !root.motionDraftPending" in grasp_execution
    assert teaching.count("&& !root.motionDraftPending") >= 3
    assert "readonly property bool armDraftPending: manualPage.armDraftPending" in workspace
    assert "readonly property bool gripperDraftPending: manualPage.gripperDraftPending" in workspace
    assert "controlTargetPending: root.controlTargetPending" in settings
    assert "configurationDraftPending: root.hasPendingDrafts" in settings
    assert "armDraftPending: root.armDraftPending" in workspace
    assert "gripperDraftPending: root.gripperDraftPending" in workspace
    assert "configurationDraftPending: root.configurationDraftPending" in workspace
    assert "&& !root.armDraftPending" in maintenance
    assert maintenance.count("&& !root.gripperDraftPending") >= 3
    assert "&& !root.anyDraftPending" in maintenance
    assert "|| !root.anyDraftPending" in ros_stack
    assert "MaintenancePanel" in diagnostics
    assert "RosStackPanel" in diagnostics
    assert "root.controller.setDraftLocks(" in workspace
    assert "先处理未发送的控制草稿" in safety
    assert 'text: qsTr("有未处理草稿")' in header


def test_semantic_motion_completion_invalidates_arm_drafts() -> None:
    controller = (CONSOLE_ROOT / "a1z_console" / "controller.py").read_text()
    joint_control = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "JointControlPanel.qml"
    ).read_text()

    assert 'result_handler="helper"' in controller
    assert "online_capability_effects(capability)" in controller
    assert "if effects & ResourceEffect.ARM:" in controller
    assert 'handler in {"motion", "recording", "gravity"}' not in controller
    assert "self.armPoseChanged.emit()" in controller
    assert "function onArmPoseChanged()" in joint_control
    assert "self.armStateInvalidated.emit()" in controller
    assert "function onArmStateInvalidated()" in joint_control
    assert "!root.controller.commandOutcomeUncertain" in joint_control


def test_unresolved_gripper_effect_invalidates_cached_target() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.device_command_executor import DeviceCommandResult
    from a1z_console.interaction_policy import ResourceEffect

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    invalidations: list[None] = []
    controller.gripperStateInvalidated.connect(
        lambda: invalidations.append(None)
    )
    try:
        controller._gripper = 0.4
        controller._gripper_target = 0.4
        controller._on_operation_finished(
            DeviceCommandResult(
                label="夹爪恢复控制",
                sequence=1,
                effects=ResourceEffect.GRIPPER,
                result_handler="",
                success=True,
                data={"data": {"gripper_free_drive": True}},
            )
        )

        assert invalidations == [None]
        assert controller.gripperFreeDrive is True
        assert controller.gripperMeasured == -1.0
        assert controller.gripperTarget == -1.0
    finally:
        controller.shutdown()


def test_grasp_safety_checks_use_a_wrapping_layout() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    grasp = (qml_root / "GraspTaskPage.qml").read_text()
    compute = (qml_root / "GraspComputePanel.qml").read_text()
    review = (qml_root / "GraspPlanReviewPanel.qml").read_text()
    execution = (qml_root / "GraspExecutionPanel.qml").read_text()

    assert "Flow {" in review
    assert "Layout.preferredHeight: implicitHeight" in review
    assert review.index('qsTr("全部通过")') < review.index("Flow {")
    assert "reviewColumn.implicitHeight" in review
    assert "+ 2 * root.padding" in review
    assert "minimumReviewHeight: Math.max(" in grasp
    assert 'objectName: "selectedGraspPointCloudPreview"' in review
    assert "root.controller.graspPreviewSource" in review
    assert "root.controller.graspBasePositionText" in review
    assert "computePanel.implicitHeight" in grasp
    assert "executionPanel.implicitHeight" in grasp
    assert "computeColumn.implicitHeight" in compute
    assert "executionColumn.implicitHeight" in execution
    assert 'objectName: "dryRunGraspPlanButton"' in execution
    assert 'objectName: "executeGraspPlanButton"' in execution
    assert "200\n                                                  + root.controller.planSegments.length" not in review


def test_scrollable_pages_share_the_available_width_contract() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    page_scroll = (qml_root / "PageScrollView.qml").read_text()

    assert "contentWidth: availableWidth" in page_scroll
    assert "ScrollBar.horizontal.policy: ScrollBar.AlwaysOff" in page_scroll
    for page_name in (
        "DashboardPage.qml",
        "ArmControlPage.qml",
        "GripperControlPage.qml",
        "GraspTaskPage.qml",
        "TeachingPage.qml",
        "DeviceSettingsPage.qml",
        "DiagnosticsPage.qml",
        "SafetyRail.qml",
    ):
        page = (qml_root / page_name).read_text()
        assert "PageScrollView {" in page, page_name
        assert ".availableWidth" in page, page_name


def test_camera_preview_and_focus_audit_follow_semantic_window_state() -> None:
    main = (CONSOLE_ROOT / "qml" / "A1ZConsole" / "Main.qml").read_text()
    workspace = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ConsoleWorkspace.qml"
    ).read_text()

    assert 'window.currentPage === "overview"' in main
    assert 'window.currentPage === "vision"' in main
    assert "workspace.cameraPreviewPage" not in main
    assert "cameraPreviewPage" not in workspace
    assert main.count("window.controller.neutralizeUi()") == 1
    assert "onCurrentPageChanged: window.updateCameraPreviewActivity()" in main
    assert "window.controller.closeBlocked" in main
    assert "window.controller.explainCloseBlocked()" in main


def test_uncertain_outcome_must_be_acknowledged_before_close() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    try:
        controller._uncertain = True
        assert controller.closeBlocked is True
        controller.explainCloseBlocked()

        assert "结果仍不确定" in controller.lastError
        assert "解除不确定锁" in controller.operationFeedbackMessage
    finally:
        controller.shutdown()


def test_confirmed_estop_does_not_force_release_before_console_close() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    try:
        controller._estopped = True

        assert controller.closeBlocked is False
    finally:
        controller.shutdown()


def test_uncertain_outcome_unlock_waits_for_fresh_joint_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    refreshes: list[None] = []
    monkeypatch.setattr(
        controller,
        "refreshNow",
        lambda: refreshes.append(None),
    )
    try:
        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._backend = "isaacsim"
        controller._control_mode = "position_hold"
        controller._robot_running = True
        controller._telemetry._age_ms = 0
        controller._uncertain = True

        controller.acknowledgeUncertain()

        assert refreshes == [None]
        assert controller.commandOutcomeUncertain is True
        assert controller.uncertainRecoveryPending is True
        assert controller.motionEnabled is False

        controller._telemetry._handle_result(
            {
                "ok": True,
                "generation": 0,
                "profile_name": "sim",
                "info": None,
                "status": {
                    "pos_deg": [0.0] * 6,
                    "running": True,
                    "faulted": False,
                },
            }
        )
        assert controller.commandOutcomeUncertain is True
        assert controller.uncertainRecoveryPending is True
        app.processEvents()
        assert len(refreshes) >= 2

        controller._telemetry._handle_result(
            {
                "ok": True,
                "generation": 0,
                "profile_name": "sim",
                "info": {
                    "backend": "isaacsim",
                    "control_mode": "position_hold",
                    "running": True,
                    "faulted": False,
                },
                "status": {
                    "pos_deg": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                    "running": True,
                    "faulted": False,
                },
            }
        )

        assert controller.commandOutcomeUncertain is False
        assert controller.uncertainRecoveryPending is False
        assert controller.motionEnabled is True
        assert controller.joints[0]["position"] == pytest.approx(1.0)
    finally:
        controller.shutdown()


def test_gravity_factor_slider_keeps_user_draft_during_live_telemetry() -> None:
    page = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "GravityCompensationPanel.qml"
    ).read_text()

    assert "property real gravityFactorDraft: 1.0" in page
    assert "property bool gravityFactorDirty: false" in page
    assert "function synchronizeGravityFactorDraft()" in page
    assert "if (gravityFactor.pressed)" in page
    assert "root.gravityFactorDirty = true" in page
    assert 'objectName: "gravityFactor"' in page
    assert "value: root.gravityFactorDraft" in page
    assert "gravityFactor.value = liveFactor" not in page
    assert "root.controller.setGravityFactor(" in page
    assert "root.gravityFactorDraft)" in page
    assert 'qsTr("应用到 %1（重启）")' in page
    assert "property string gravityDraftProfile" in page
    assert "系数不热切换" in page
    assert "value: root.controller.connected" not in page


def test_diagnostics_log_view_can_scroll_without_forced_tail_follow() -> None:
    page = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "DiagnosticLogPanel.qml"
    ).read_text()

    assert "id: logView" in page
    assert "model: root.controller.logModel" in page
    assert "reuseItems: true" in page
    assert "ScrollBar.horizontal: ScrollBar" in page
    assert "ScrollBar.vertical: ScrollBar" in page
    assert "property bool followTail: true" in page
    assert "maximumDisplayColumns" in page
    assert "contentItem.childrenRect" not in page
    assert "currentIndex: -1" in page
    assert "textFormat: Text.PlainText" in page
    assert 'qsTr("暂停跟随")' in page
    assert 'qsTr("跟随最新")' in page
    assert "root.controller.logs" not in page
    assert "AppTextArea" not in page
    assert "cursorPosition = length" not in page
    assert "onContentHeightChanged" in page
    assert "logView.contentHeight - logView.height" in page


def test_single_motor_fault_maintenance_is_scoped_and_guarded() -> None:
    maintenance = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "MaintenancePanel.qml"
    ).read_text()

    assert '"motor_check_j" + root.selectedMotorNumber' in maintenance
    assert '"motor_clear_j" + root.selectedMotorNumber' in maintenance
    assert "root.selectedMotorNumber >= 4" in maintenance
    assert "currentIndex: 3" in maintenance
    assert '=== "清错 " + root.selectedMotorName' in maintenance
    assert "单电机检查会短暂使能后失能选中轴" in maintenance
    assert "清错只解除故障锁存" in maintenance
    assert "!root.armDraftPending" in maintenance


def test_startup_guide_gates_control_routes_until_every_link_is_ready() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    guide = (qml_root / "StartupGuidePanel.qml").read_text()
    workspace = (qml_root / "ConsoleWorkspace.qml").read_text()
    navigation = (qml_root / "ConsoleNavigation.qml").read_text()
    main = (qml_root / "Main.qml").read_text()

    for prerequisite in (
        "startupControlReady",
        "startupRosReady",
        "startupCameraReady",
        "startupPreflightReady",
    ):
        assert prerequisite in guide
    assert "root.controller.startupReady" in navigation
    assert 'route === "settings"' in workspace
    assert 'route === "diagnostics"' in workspace
    assert 'root.pageRequested("overview")' in workspace
    assert "onStartupStateChanged" in workspace
    assert 'root.controller.startServer(false, 1.0)' in guide
    assert 'root.controller.ensureRos()' in guide
    assert 'root.controller.runPreflight()' in guide
    assert 'objectName: "sharedRuntimeLog"' in main


def test_controller_startup_gate_requires_live_control_camera_and_preflight() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController

    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    try:
        assert controller.startupReady is False
        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._telemetry._age_ms = 0
        controller._robot_running = True
        controller._faulted = False
        controller._control_mode = "position_hold"
        controller._camera._bridge_online = True
        controller._camera._ready = True
        controller._diagnostics._state = "ready"

        assert controller.startupControlReady is True
        assert controller.startupRosReady is True
        assert controller.startupCameraReady is True
        assert controller.startupPreflightReady is True
        assert controller.startupReady is True

        controller._faulted = True
        controller._fault_message = "joint4 under voltage"
        assert controller.startupReady is False
        assert "under voltage" in controller.startupGateText

        controller._faulted = False
        assert controller._diagnostics.invalidate("链路已变更") is True
        assert controller.startupPreflightReady is False
        assert controller.startupReady is False
        assert controller.preflightStatus == "链路已变更"
    finally:
        controller.shutdown()


def test_qml_startup_gate_redirects_locked_routes_and_allows_ready_routes() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    from a1z_console.controller import ConsoleController

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT, app)
    QQmlEngine.setObjectOwnership(controller, QQmlEngine.CppOwnership)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller})
    engine.addImportPath(str(CONSOLE_ROOT / "qml"))
    engine.loadFromModule("A1ZConsole", "Main")
    roots = engine.rootObjects()
    assert roots
    window = roots[0]
    try:
        window.setProperty("currentPage", "manual")
        app.processEvents()
        app.processEvents()
        assert window.property("currentPage") == "overview"

        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._telemetry._age_ms = 0
        controller._robot_running = True
        controller._faulted = False
        controller._control_mode = "position_hold"
        controller._camera._bridge_online = True
        controller._camera._ready = True
        controller._diagnostics._state = "ready"
        controller.stateChanged.emit()
        controller.cameraStateChanged.emit()
        controller.preflightChanged.emit()
        app.processEvents()

        assert controller.startupReady is True
        window.setProperty("currentPage", "manual")
        app.processEvents()
        app.processEvents()
        assert window.property("currentPage") == "manual"

        controller._camera._ready = False
        controller.cameraStateChanged.emit()
        app.processEvents()
        app.processEvents()
        assert window.property("currentPage") == "overview"
    finally:
        window.setProperty("visible", False)
        controller.shutdown()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def test_qml_busy_buttons_keep_their_enabled_palette() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(str(CONSOLE_ROOT / "qml"))
    component = QQmlComponent(engine)
    component.setData(
        b"""
import QtQuick
import A1ZConsole
Item {
    width: 300
    height: 100
    Theme { id: theme }
    AppButton {
        objectName: "buttonUnderTest"
        theme: theme
        text: "Refresh"
    }
}
""",
        QUrl(),
    )
    root = component.create()
    assert root is not None, component.errors()
    button = root.findChild(QObject, "buttonUnderTest")
    assert button is not None
    background = button.property("background")
    content = button.property("contentItem")
    try:
        enabled_background = background.property("color")
        enabled_foreground = content.property("color")
        button.setProperty("enabled", False)
        button.setProperty("busy", True)
        app.processEvents()
        assert background.property("color") == enabled_background
        assert content.property("color") == enabled_foreground

        button.setProperty("busy", False)
        app.processEvents()
        assert content.property("color") != enabled_foreground
    finally:
        root.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def test_shared_runtime_log_follows_tail_and_respects_pause() -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent, QObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest

    from a1z_console.controller import ConsoleController

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    controller = ConsoleController(ROOT, app)
    QQmlEngine.setObjectOwnership(controller, QQmlEngine.CppOwnership)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller})
    engine.addImportPath(str(CONSOLE_ROOT / "qml"))
    engine.loadFromModule("A1ZConsole", "Main")
    roots = engine.rootObjects()
    assert roots
    window = roots[0]
    panel = window.findChild(QObject, "sharedRuntimeLog")
    log_view = window.findChild(QObject, "sharedLogView")
    assert panel is not None
    assert log_view is not None
    try:
        for index in range(120):
            controller._append_log(f"tail-follow-line-{index:03d}")
        controller._flush_logs()
        QTest.qWait(80)
        app.processEvents()
        maximum_y = max(
            0.0,
            float(log_view.property("contentHeight"))
            - float(log_view.property("height")),
        )
        assert maximum_y > 0
        assert float(log_view.property("contentY")) >= maximum_y - 2.0

        panel.setProperty("followTail", False)
        log_view.setProperty("contentY", 0.0)
        controller._append_log("paused-tail-line")
        controller._flush_logs()
        QTest.qWait(80)
        app.processEvents()
        assert float(log_view.property("contentY")) <= 2.0
    finally:
        window.setProperty("visible", False)
        controller.shutdown()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def test_runtime_and_operator_text_is_rendered_as_plain_text() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"

    for component in (
        "AppToolTip.qml",
        "InlineBanner.qml",
        "SectionHeader.qml",
        "StatusPill.qml",
        "MetricTile.qml",
        "CameraPanel.qml",
        "PreflightPanel.qml",
        "GraspPlanReviewPanel.qml",
    ):
        qml = (qml_root / component).read_text()
        assert "textFormat: Text.PlainText" in qml, component


def test_console_autostarts_only_normal_interactive_sessions() -> None:
    main = (CONSOLE_ROOT / "a1z_console" / "main.py").read_text()
    controller = (CONSOLE_ROOT / "a1z_console" / "controller.py").read_text()

    assert '"--no-ros-autostart"' in main
    assert "not args.smoke_test" in main
    assert "args.screenshot is None" in main
    assert "controller.startMonitoring()" in main
    assert "QTimer.singleShot(300, controller.ensureRos)" in main
    assert 'self.manageRos("ensure")' in controller


def test_console_cli_uses_function_routes_instead_of_source_categories() -> None:
    pytest.importorskip("PySide6")

    from a1z_console.main import build_parser

    parser = build_parser()
    assert parser.parse_args([]).page == "overview"
    manual = parser.parse_args(
        ["--page", "manual", "--manual-section", "tool"]
    )
    assert manual.page == "manual"
    assert manual.manual_section == "tool"
    assert parser.parse_args(["--page", "settings"]).page == "settings"
    with pytest.raises(SystemExit):
        parser.parse_args(["--page", "gripper"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--page", "sdk"])


def test_ros_log_rotation_preserves_only_the_bounded_tail(tmp_path: Path) -> None:
    destination = tmp_path / "ros.log"
    payload = b"0123456789abcdefghijKLMNOP"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rotate_stream_log.py"),
            "--path",
            str(destination),
            "--max-bytes",
            "10",
            "--backup-count",
            "2",
        ],
        input=payload,
        check=True,
    )

    paths = [
        destination.with_name("ros.log.2"),
        destination.with_name("ros.log.1"),
        destination,
    ]
    assert all(path.stat().st_size <= 10 for path in paths)
    assert b"".join(path.read_bytes() for path in paths) == payload


def test_real_ros_runner_suppresses_realsense_error_floods() -> None:
    real_env = (ROOT / "config" / "real.env").read_text()
    runner = (ROOT / "scripts" / "run_a1z_ros2_stack_in_container.sh").read_text()

    assert "LRS_LOG_LEVEL=fatal" in real_env
    assert "A1Z_REALSENSE_MIN_USB_SPEED_MBPS=5000" in real_env
    assert '-e LRS_LOG_LEVEL="${LRS_LOG_LEVEL:-fatal}"' in runner
    assert "validate_realsense_usb_link" in runner
    assert "camera bridge reports stale or incomplete RGB-D data" in runner
    assert "A1Z_ROS2_MOTION_LOG_MAX_BYTES" in runner


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
                "segment_type": segment_type,
                "target_joint_rad": [0.0, 0.1, -0.2, 0.3, -0.4, 0.5],
                "timeout_s": 3.0,
            }
            for segment_type in (
                "move_to_pregrasp",
                "approach",
                "lift",
                "retreat",
            )
        ],
        "safety_summary": {
            "topdown_ok": True,
            "table_clearance_ok": True,
            "camera_keepout_ok": True,
            "joint_margin_ok": True,
            "continuity_ok": True,
        },
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
    preview_png = planning / "selected_grasp_point_cloud.png"
    preview_png.write_bytes(b"preview")
    preview_metadata = {
        "candidate_id": "g1",
        "candidate_rank": 0,
        "score": 0.9,
        "gripper_pose_6dof": {
            "position_xyz_m": [0.45, 0.02, 0.25],
            "rpy_deg": [-10.0, 20.0, 30.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            "transform_matrix": [],
        },
        "gripper": {"opening_m": 0.04},
    }
    preview_metadata_path = planning / "selected_grasp_preview.json"
    preview_metadata_path.write_text(
        json.dumps(preview_metadata),
        encoding="utf-8",
    )
    manifest = {
        "profile": "sim",
        "instruction": "pick",
        "artifacts": {
            "plan": str(planning / "selected_plan.json"),
            "anygrasp": str(anygrasp / "anygrasp_result.json"),
            "grasp_preview": str(preview_png),
            "grasp_preview_metadata": str(preview_metadata_path),
        },
    }
    (output / "pipeline_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    summary = summarize_pipeline(output, ROOT)
    assert summary["profile"] == "sim"
    assert summary["grasp"]["translationMm"] == [100.0, -200.0, 300.0]
    assert summary["grasp"]["baseTranslationMm"] == [450.0, 20.0, 250.0]
    assert summary["grasp"]["baseRpyDeg"] == [-10.0, 20.0, 30.0]
    assert summary["graspPreviewSource"].startswith("file://")
    assert summary["segments"][0]["jointsDeg"][1] == pytest.approx(5.73, abs=0.01)
    assert summary["allSafetyPassed"] is True
    assert next(
        item
        for item in summary["safety"]
        if item["name"] == "physical_sequence_ok"
    )["ok"] is True

    plan["joint_trajectory_segments"] = [
        plan["joint_trajectory_segments"][1]
    ]
    (planning / "selected_plan.json").write_text(
        json.dumps(plan),
        encoding="utf-8",
    )
    incomplete_sequence = summarize_pipeline(output, ROOT)
    assert incomplete_sequence["allSafetyPassed"] is False
    assert next(
        item
        for item in incomplete_sequence["safety"]
        if item["name"] == "physical_sequence_ok"
    )["ok"] is False

    del plan["safety_summary"]["camera_keepout_ok"]
    (planning / "selected_plan.json").write_text(
        json.dumps(plan),
        encoding="utf-8",
    )
    incomplete = summarize_pipeline(output, ROOT)
    assert incomplete["allSafetyPassed"] is False
    camera_check = next(
        item
        for item in incomplete["safety"]
        if item["name"] == "camera_keepout_ok"
    )
    assert camera_check["ok"] is False


def test_console_safety_contract_is_present_in_sources() -> None:
    controller = (CONSOLE_ROOT / "a1z_console" / "controller.py").read_text()
    command_executor = (
        CONSOLE_ROOT / "a1z_console" / "device_command_executor.py"
    ).read_text()
    kinematics_adapter = (
        CONSOLE_ROOT / "a1z_console" / "kinematics_command_adapter.py"
    ).read_text()
    helper = (ROOT / "scripts" / "a1z_ee_ik_helper.py").read_text()
    server = (ROOT / "a1z_ext" / "robots" / "server.py").read_text()
    dashboard = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "DashboardPage.qml"
    ).read_text()

    assert "ThreadPoolExecutor(" not in controller
    assert command_executor.count("max_workers=1") == 2
    assert "superseded_by_emergency" in command_executor
    assert "AmbiguousCommandError" in kinematics_adapter
    assert "--max-joint-step-deg" in kinematics_adapter
    assert "subprocess.run" not in controller
    assert "motion_request_attempted" in helper
    assert "record_start" in server
    assert "gravity_mode" in server
    assert '"errorIsFault": error_is_fault' in controller
    assert "jointRow.jointData.errorIsFault" in dashboard


def test_gripper_slider_draft_is_not_bound_to_periodic_telemetry() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    page = (qml_root / "GripperControlPage.qml").read_text()
    qml = "\n".join(
        [
            page,
            (qml_root / "GripperModePanel.qml").read_text(),
            (qml_root / "GripperOpeningPanel.qml").read_text(),
        ]
    )

    assert "property real gripperTargetDraft" in qml
    assert "property bool gripperDraftInitialized" in qml
    assert "property bool gripperTargetDirty" in qml
    assert "property bool gripperTargetStale" in qml
    assert "targetDraft: root.gripperTargetDraft" in page
    assert "value: root.targetDraft" in qml
    assert "onMoved:" in qml
    assert "value: root.controller.gripper" not in qml
    assert "root.controller.gripperMeasured" in qml
    assert "root.controller.gripperTarget" in qml
    assert "editingEnabled: root.gripperDraftInitialized" in qml
    assert "root.controller.gripperControlEnabled" in qml
    assert "function onGripperStateInvalidated()" in qml
    assert 'qsTr("开度控制")' in qml
    assert 'qsTr("自由拖动")' in qml
    assert "readonly property bool modeStateConfirmed" in page
    assert 'root.controller.gripperModeState === "confirmed"' in page


def test_arm_control_uses_stable_editors_and_persistent_feedback_surface() -> None:
    arm = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ArmControlPage.qml"
    ).read_text()
    joint_control = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "JointControlPanel.qml"
    ).read_text()
    joint_row = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "JointControlRow.qml"
    ).read_text()
    safety = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "SafetyRail.qml"
    ).read_text()
    feedback = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ConsoleFeedback.qml"
    ).read_text()
    dashboard = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "DashboardPage.qml"
    ).read_text()

    assert "JointControlPanel" in arm
    assert "model: 6" in joint_control
    assert "model: root.controller.joints" not in joint_control
    assert "property bool jointDraftDirty" in joint_control
    assert "onJointTelemetryChanged" in joint_control
    assert "motionRecoveryAction.length > 0" in safety
    assert "runMotionRecovery()" in safety
    assert "operationFeedbackMessage" in feedback
    assert "model: 6" in dashboard
    assert "root.jointSnapshot.length > jointRow.index" in dashboard
    assert ": root.emptyJointData" in dashboard
    assert "visible: window.controller.lastError.length > 0" not in feedback
    assert "property bool jointDraftStale" in joint_control
    assert "function discardJointDraft()" in joint_control
    assert 'objectName: "discardJointDraftButton"' in joint_control
    assert "连接已变化 · 请放弃旧目标后重新同步" in joint_control
    assert 'qsTr("放弃并重新载入")' in joint_control
    assert "&& !root.jointDraftStale" in joint_control
    assert "function onArmPoseChanged()" in joint_control
    assert "function onGripperTelemetryChanged()" not in joint_control
    assert "function onOperationFinished(" not in joint_control
    assert "enabled: root.controller.motionEnabled" in joint_row
    assert "&& root.draftInitialized" in joint_row
    mode_selector = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ArmControlModeSelector.qml"
    ).read_text()
    assert "property bool stateConfirmed" in mode_selector
    assert 'selected && root.stateConfirmed ? qsTr("当前")' in mode_selector
    assert 'selected ? qsTr("最后显示")' in mode_selector
    gravity = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "GravityCompensationPanel.qml"
    ).read_text()
    assert 'objectName: "discardGravityFactorButton"' in gravity
    assert "&& !root.controller.emergencyBusy" in gravity


def test_navigation_and_operator_inputs_have_accessible_names() -> None:
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    nav = (qml_root / "NavButton.qml").read_text()
    safety = (qml_root / "SafetyRail.qml").read_text()
    presets = (qml_root / "PresetMotionPanel.qml").read_text()
    teaching = (qml_root / "TeachingPlaybackPanel.qml").read_text()
    grasp = "\n".join(
        (qml_root / name).read_text()
        for name in (
            "GraspTaskPage.qml",
            "GraspComputePanel.qml",
            "GraspExecutionPanel.qml",
        )
    )
    diagnostics = "\n".join(
        (qml_root / name).read_text()
        for name in (
            "DiagnosticsPage.qml",
            "MaintenancePanel.qml",
            "DiagnosticLogPanel.qml",
        )
    )
    arm = "\n".join(
        (qml_root / name).read_text()
        for name in (
            "ArmControlPage.qml",
            "JointControlPanel.qml",
            "JointControlRow.qml",
        )
    )

    assert "Accessible.name: text" in nav
    assert "Accessible.role: Accessible.PageTab" in nav
    assert "Accessible.checked: root.selected" in nav
    assert safety.count("Accessible.name:") >= 4
    assert presets.count("Accessible.name:") >= 2
    assert teaching.count("Accessible.name:") >= 3
    assert grasp.count("Accessible.name:") >= 4
    assert diagnostics.count("Accessible.name:") >= 2
    assert 'qsTr("%1 目标角度")' in arm
    header = (qml_root / "ConsoleHeader.qml").read_text()
    gripper = "\n".join(
        (qml_root / name).read_text()
        for name in (
            "GripperControlPage.qml",
            "GripperModePanel.qml",
            "GripperOpeningPanel.qml",
        )
    )
    banner = (qml_root / "InlineBanner.qml").read_text()
    tooltip = (qml_root / "AppToolTip.qml").read_text()
    assert header.count("Accessible.role: Accessible.RadioButton") >= 2
    assert gripper.count("Accessible.role: Accessible.RadioButton") >= 2
    assert safety.count("Accessible.role: Accessible.RadioButton") >= 2
    assert "Accessible.role: Accessible.AlertMessage" in banner
    assert "Accessible.announce(root.text)" in banner
    assert "ToolTip.text: root.text" not in banner
    assert "AppToolTip" in banner
    assert "background: Rectangle" in tooltip
    assert "textFormat: Text.PlainText" in tooltip


def test_console_persistent_modes_and_drafts_are_visibly_interlocked() -> None:
    arm = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ArmControlPage.qml"
    ).read_text()
    teaching = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "TeachingPlaybackPanel.qml"
    ).read_text()
    presets = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "PresetMotionPanel.qml"
    ).read_text()
    qml_root = CONSOLE_ROOT / "qml" / "A1ZConsole"
    grasp = "\n".join(
        (qml_root / name).read_text()
        for name in (
            "GraspTaskPage.qml",
            "GraspPlanReviewPanel.qml",
            "GraspExecutionPanel.qml",
        )
    )
    diagnostics = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "DiagnosticsPage.qml"
    ).read_text()
    joint_control = (qml_root / "JointControlPanel.qml").read_text()
    joint_row = (qml_root / "JointControlRow.qml").read_text()
    preflight = (qml_root / "PreflightPanel.qml").read_text()
    maintenance = (qml_root / "MaintenancePanel.qml").read_text()
    header = (
        CONSOLE_ROOT / "qml" / "A1ZConsole" / "ConsoleHeader.qml"
    ).read_text()

    assert "readonly property bool jointDraftValid:" in arm
    assert "property bool jointDraftValid" in joint_control
    assert 'String(draftModel.get(i).target).trim()' in joint_control
    assert "Number(draftModel.get(i).target)" not in joint_control
    assert "&& !root.jointDraftDirty" in joint_control
    assert "!root.draftPending" in joint_row

    assert "root.controller.recordingActive" in teaching
    assert "root.controller.recordingState" in teaching
    assert "root.controller.recordingStopEnabled" in teaching
    assert 'qsTr("停止并保存")' in teaching
    assert 'qsTr("状态待确认")' in teaching
    assert "visible: !root.recordingOrphaned" in teaching
    assert "presetSelection.currentValue" in presets
    assert "danceSelection.currentValue" in presets
    assert 'text: modelData.label' not in teaching

    assert "root.controller.planCurrent" in grasp
    assert "root.controller.planExecutionEnabled" in grasp
    assert "root.controller.planState" in grasp
    assert "root.actualExecutionAvailable" in grasp
    assert 'qsTr("安全检查未通过；仅允许无运动演练")' in grasp
    assert "executePhrase.clear()" in grasp
    assert "visible: root.controller.taskBusy" not in grasp
    assert "calibrationPhrase.clear()" in maintenance
    assert "root.controller.diagnosticsEnabled" in preflight
    assert "root.controller.hardwareInspectionEnabled" in maintenance
    assert "root.controller.offlineMaintenanceEnabled" in maintenance
    assert "root.controller.exclusiveTaskEnabled" not in diagnostics + maintenance
    assert "root.controller.profileSwitchEnabled" in header
    assert "root.controller.taskCancelable" in header


def test_direct_can_wrapper_proves_sdk_owner_has_stopped() -> None:
    wrapper = (ROOT / "scripts" / "a1z_sdk_python_in_container.sh").read_text()
    manager = (ROOT / "scripts" / "manage_a1z_control_server.sh").read_text()
    diagnostics = (
        CONSOLE_ROOT / "a1z_console" / "diagnostics_session.py"
    ).read_text()

    assert "--require-control-server-stopped" in wrapper
    assert "tools/[a]1zctl serve" in wrapper
    assert "Refusing direct CAN access" in wrapper
    assert 'arguments.insert(0, "--require-control-server-stopped")' in diagnostics
    assert "find_real_server_pids" in manager
    assert "stop_orphaned_real_servers" in manager
    assert "Refusing to start a second SDK owner" in manager


def test_real_service_manager_prepares_can_and_fails_fast() -> None:
    manager = (ROOT / "scripts" / "manage_a1z_control_server.sh").read_text()

    assert 'CAN_BITRATE="${A1Z_CAN_BITRATE:-1000000}"' in manager
    assert "ensure_real_can_ready()" in manager
    assert "for _ in $(seq 1 20)" in manager
    assert 'ip link set "$can_channel" type can bitrate "$CAN_BITRATE"' in manager
    assert 'ip link set "$can_channel" up' in manager
    assert "ensure_real_can_ready\n\n  ENV_ARGS=()" in manager
    assert "A1Z real control-server process exited before becoming ready" in manager
    assert 'tail -n 20 "$LOG_PATH"' in manager


def test_offline_gripper_maintenance_uses_an_offline_device_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.interaction_policy import (
        ProcessAccess,
        ResourceEffect,
    )

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    captured: dict[str, object] = {}

    def capture(
        kind: str,
        label: str,
        program: str,
        arguments: list[str],
        **kwargs: object,
    ) -> None:
        captured.update(
            kind=kind,
            label=label,
            program=program,
            arguments=arguments,
            **kwargs,
        )

    monkeypatch.setattr(controller, "_start_process_task", capture)
    try:
        controller._profile_name = "real"
        controller._connected = False
        controller._backend_matched = False
        controller._connection_issue = "offline"

        assert controller.offlineMaintenanceEnabled is True
        assert controller.motionEnabled is False
        controller.runMaintenance("gripper_test", "")

        contract = captured["contract"]
        assert contract.access is ProcessAccess.OFFLINE_DEVICE
        assert contract.effects & ResourceEffect.GRIPPER
        assert contract.uncertain_on_failure is True
        assert "--require-control-server-stopped" in captured["arguments"]
        assert controller.lastError == ""
    finally:
        controller.shutdown()


def test_controller_monitoring_has_an_explicit_application_lifetime() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    assert controller._monitoring_started is False
    assert controller._telemetry.poll_timer_active is False
    assert controller._telemetry.age_timer_active is False
    assert controller._camera.timer_active is False

    controller.startMonitoring()
    assert controller._monitoring_started is True
    assert controller._telemetry.poll_timer_active is True
    assert controller._telemetry.age_timer_active is True
    assert controller._camera.timer_active is True

    controller.shutdown()
    controller.shutdown()
    assert controller._shutting_down is True
    assert controller._telemetry.poll_timer_active is False
    assert controller._telemetry.age_timer_active is False
    assert controller._camera.timer_active is False


def test_profile_switch_invalidates_profile_scoped_preflight_results() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    events: list[None] = []
    controller.preflightChanged.connect(lambda: events.append(None))
    try:
        request = controller._diagnostics.prepare_preflight()
        controller._diagnostics.activate_preflight(request)
        result = controller._diagnostics.complete_preflight(
            request,
            0,
            json.dumps(
                {
                    "profile": "sim",
                    "ready": True,
                    "required_failure_count": 0,
                    "checks": [
                        {
                            "name": "SIM SDK",
                            "ok": True,
                            "detail": "old profile",
                            "severity": "required",
                        }
                    ],
                }
            ),
        )
        assert result.valid is True
        controller.setProfile("real")

        assert controller.profile == "real"
        assert controller.preflightItems == []
        assert len(events) == 1
        assert controller._telemetry.poll_timer_active is False
    finally:
        controller.shutdown()


def test_telemetry_clock_isolated_from_ui_state_and_stale_profile_is_locked() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    timing_events: list[None] = []
    state_events: list[None] = []
    controller.telemetryTimingChanged.connect(lambda: timing_events.append(None))
    controller.stateChanged.connect(lambda: state_events.append(None))
    try:
        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._control_mode = "position_hold"
        controller._robot_running = True
        controller._telemetry._age_ms = 0
        controller._telemetry._last_received_monotonic = time.monotonic() - 0.1
        controller._telemetry._update_age()

        assert len(timing_events) == 1
        assert state_events == []
        assert controller.telemetryFresh is True

        controller._control_mode = "gravity_comp_effort"
        controller._telemetry._last_received_monotonic = time.monotonic() - 4.0
        controller._telemetry._update_age()

        assert controller._connection_issue == "stale"
        assert controller.connected is False
        assert controller.profileSwitchEnabled is False
        assert len(state_events) == 1
    finally:
        controller.shutdown()


def test_capability_bindings_are_notified_when_telemetry_becomes_fresh() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    state_events: list[None] = []
    timing_events: list[None] = []
    controller.stateChanged.connect(lambda: state_events.append(None))
    controller.telemetryTimingChanged.connect(lambda: timing_events.append(None))
    try:
        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._backend = "isaacsim"
        controller._control_mode = "position_hold"
        controller._robot_running = True
        controller._faulted = False
        controller._health_error = ""
        controller._status_text = "遥测在线 · 控制循环运行中"
        controller._telemetry._age_ms = 2200

        assert controller.telemetryFresh is False
        assert controller.motionEnabled is False
        controller._telemetry._handle_result(
            {
                "ok": True,
                "generation": 0,
                "profile_name": "sim",
                "info": None,
                "status": {
                    "pos_deg": [0.0] * 6,
                    "running": True,
                    "faulted": False,
                },
            }
        )

        assert controller.telemetryFresh is True
        assert controller.motionEnabled is True
        assert len(timing_events) == 1
        assert len(state_events) == 1
    finally:
        controller.shutdown()


def test_telemetry_does_not_clear_operator_error_and_offline_state_is_stable() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    state_events: list[None] = []
    joint_events: list[None] = []
    controller.stateChanged.connect(lambda: state_events.append(None))
    controller.jointTelemetryChanged.connect(lambda: joint_events.append(None))
    try:
        controller._set_error("手动命令反馈未到位")
        events_after_error = len(state_events)
        offline = {
            "ok": False,
            "error": "A1Z control service is offline",
            "mismatch": False,
            "generation": 0,
            "profile_name": "sim",
        }
        controller._telemetry._handle_result(offline)
        events_after_first_offline = len(state_events)
        controller._telemetry._handle_result(offline)

        assert controller.lastError == "手动命令反馈未到位"
        assert controller.operationFeedbackState == "error"
        assert controller.operationFeedbackMessage == "手动命令反馈未到位"
        assert controller.motionRecoveryAction == "start_server"
        assert events_after_first_offline == events_after_error + 1
        assert len(state_events) == events_after_first_offline

        healthy = {
            "ok": True,
            "generation": 0,
            "profile_name": "sim",
            "info": {
                "backend": "isaacsim",
                "control_mode": "position_hold",
                "running": True,
                "faulted": False,
                "joint_limits_deg": {
                    f"J{index}": [-180.0, 180.0]
                    for index in range(1, 7)
                },
            },
            "status": {
                "pos_deg": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "running": True,
                "faulted": False,
            },
        }
        controller._telemetry._handle_result(healthy)
        joint_events_after_first_healthy = len(joint_events)
        controller._telemetry._handle_result(healthy)

        assert controller.lastError == "手动命令反馈未到位"
        assert controller.operationFeedbackState == "error"
        assert len(joint_events) == joint_events_after_first_healthy
    finally:
        controller.shutdown()


def test_controller_models_recording_as_an_exclusive_persistent_state() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.telemetry_coordinator import TelemetryResult

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    try:
        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._robot_running = True
        controller._telemetry._age_ms = 0
        controller._apply_info(
            {
                "backend": "isaacsim",
                "control_mode": "gravity_comp_effort",
                "running": True,
                "recording": True,
                "gripper_free_drive": True,
            }
        )

        assert controller.recordingActive is True
        assert controller.recordingState == "recording"
        assert controller.motionEnabled is False
        assert controller.modeControlEnabled is False
        assert controller.gripperControlEnabled is False
        assert controller.profileSwitchEnabled is False
        assert controller.serviceStopEnabled is False
        assert controller.recordingStopEnabled is True
        assert "停止保存" in controller.motionGateText

        controller.setProfile("real")
        assert controller.profile == "sim"
        assert "示教录制仍在进行" in controller.lastError
        controller._on_telemetry_result(
            TelemetryResult(
                success=False,
                profile_name="sim",
                error="endpoint offline",
            )
        )
        assert controller.recordingState == "orphaned"
        assert "待确认" in controller.recordingSummary
        assert controller.recordingRecoveryEnabled is True
        controller._connected = True
        controller._backend_matched = True
        controller._connection_issue = ""
        controller._teaching.apply_info({"recording": False})
        controller._control_mode = "gravity_comp_effort"
        controller._gripper_free_drive = False
        assert controller.profileSwitchEnabled is False
        controller._control_mode = "position_hold"
        controller._gripper_free_drive = True
        assert controller.profileSwitchEnabled is False
        controller._gripper_free_drive = False
        assert controller.profileSwitchEnabled is True
    finally:
        controller.shutdown()


def test_offline_recording_recovery_resolves_local_safety_latches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from a1z_console.controller import ConsoleController

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    controller = ConsoleController(ROOT)
    captured: dict[str, object] = {}
    invalidated: list[str] = []
    controller.armStateInvalidated.connect(lambda: invalidated.append("arm"))
    controller.gripperStateInvalidated.connect(
        lambda: invalidated.append("gripper")
    )

    def capture_task(*_args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(controller, "_start_process_task", capture_task)
    monkeypatch.setattr(controller, "refreshNow", lambda: None)
    try:
        controller._connected = False
        controller._backend_matched = False
        controller._connection_issue = "offline"
        controller._teaching.apply_info({"recording": True})
        controller._teaching.mark_endpoint_unavailable()
        controller._uncertain = True
        controller._estopped = True

        assert controller.recordingRecoveryEnabled is True
        controller.discardDisconnectedRecording()
        completion = captured["completion"]
        completion(0, "")

        assert controller.recordingActive is False
        assert controller.recordingState == "discarded"
        assert controller.commandOutcomeUncertain is False
        assert controller.estopped is False
        assert controller.profileSwitchEnabled is True
        assert invalidated == ["arm", "gripper"]
    finally:
        controller.shutdown()


def test_controller_sends_each_manual_target_once_and_keeps_gripper_mode_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    import a1z_console.controller as controller_module

    app = QCoreApplication.instance() or QCoreApplication([])
    calls: list[tuple[str, dict[str, object]]] = []

    class Endpoint:
        backend = "isaacsim"
        control_mode = "position_hold"

    class FakeProtocolClient:
        def __init__(self, _profile) -> None:
            pass

        def verified_request(
            self,
            command: str,
            args: dict[str, object] | None = None,
            **_kwargs,
        ) -> tuple[dict[str, object], Endpoint]:
            request_args = dict(args or {})
            calls.append((command, request_args))
            if command == "move":
                measured = [float(value) for value in request_args["joints"]]
                data: dict[str, object] = {
                    "pos_deg": measured,
                    "motion_performed": True,
                    "verification": {
                        "reached": True,
                        "measured_deg": measured,
                        "max_error_deg": 0.1,
                    },
                }
            elif command == "joint_jog":
                measured = [5.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                data = {
                    "pos_deg": measured,
                    "motion_performed": True,
                    "verification": {
                        "reached": True,
                        "settled": True,
                        "measured_deg": measured,
                        "max_sample_delta_deg": 0.02,
                    },
                }
            else:
                value = float(request_args["value"])
                data = {
                    "gripper_target": value,
                    "gripper_measured": value,
                    "motion_performed": True,
                    "verification": {"reached": True, "measured": value},
                }
            return data, Endpoint()

    monkeypatch.setattr(controller_module, "A1ZProtocolClient", FakeProtocolClient)
    monkeypatch.setattr(
        controller_module.ConsoleController,
        "refreshNow",
        lambda _self: None,
    )
    controller = controller_module.ConsoleController(ROOT)
    controller._connected = True
    controller._backend_matched = True
    controller._connection_issue = ""
    controller._backend = "isaacsim"
    controller._robot_running = True
    controller._faulted = False
    controller._telemetry._age_ms = 0

    def wait_for_command() -> None:
        deadline = time.monotonic() + 1.0
        while controller.commandBusy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.002)
        app.processEvents()
        assert controller.commandBusy is False

    try:
        controller._control_mode = "position_hold"
        controller.sendJointTarget([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 0.5)
        wait_for_command()
        assert controller.operationFeedbackState == "success"
        assert "最大误差 0.100°" in controller.operationFeedbackMessage

        controller.jogJoint(0, 5.0, 0.5)
        wait_for_command()
        assert controller.operationFeedbackState == "success"
        assert "运动已稳定" in controller.operationFeedbackMessage
        assert calls[1] == (
            "joint_jog",
            {"joint_index": 1, "delta_deg": 5.0, "speed": 0.5},
        )

        controller._control_mode = "gravity_comp_effort"
        assert controller.motionEnabled is False
        assert controller.gripperControlEnabled is True
        controller.setGripper(0.42)
        wait_for_command()

        assert [command for command, _args in calls] == [
            "move",
            "joint_jog",
            "gripper",
        ]
        assert calls[2][1]["value"] == pytest.approx(0.42)
        assert controller.gripperMeasured == pytest.approx(0.42)
        assert controller.operationFeedbackState == "success"
        assert "实际 0.420" in controller.operationFeedbackMessage
    finally:
        controller.shutdown()


def test_recording_stop_response_loss_latches_uncertain_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    import a1z_console.controller as controller_module
    from a1z_console.protocol import AmbiguousCommandError

    app = QCoreApplication.instance() or QCoreApplication([])
    captured: dict[str, object] = {}

    class FakeProtocolClient:
        def __init__(self, _profile) -> None:
            pass

        def verified_request(self, command: str, _args=None, **kwargs):
            captured.update(command=command, **kwargs)
            raise AmbiguousCommandError("record_stop response was lost")

    monkeypatch.setattr(controller_module, "A1ZProtocolClient", FakeProtocolClient)
    monkeypatch.setattr(
        controller_module.ConsoleController,
        "refreshNow",
        lambda _self: None,
    )
    controller = controller_module.ConsoleController(ROOT)
    controller._connected = True
    controller._backend_matched = True
    controller._connection_issue = ""
    controller._backend = "isaacsim"
    controller._robot_running = True
    controller._faulted = False
    controller._telemetry._age_ms = 0
    controller._control_mode = "gravity_comp_effort"
    controller._teaching.apply_info({"recording": True})
    try:
        controller.stopRecording("teach.json")
        deadline = time.monotonic() + 1.0
        while controller.commandBusy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.002)
        app.processEvents()

        assert captured["command"] == "record_stop"
        assert captured["require_running"] is False
        assert captured["ambiguous_after_send"] is True
        assert controller.commandOutcomeUncertain is True
        assert controller.operationFeedbackState == "uncertain"
    finally:
        controller.shutdown()


def test_estop_release_is_available_when_control_loop_is_faulted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    import a1z_console.controller as controller_module

    app = QCoreApplication.instance() or QCoreApplication([])
    captured: dict[str, object] = {}

    class Endpoint:
        backend = "isaacsim"
        control_mode = "position_hold"

    class FakeProtocolClient:
        def __init__(self, _profile) -> None:
            pass

        def verified_request(self, command: str, _args=None, **kwargs):
            captured.update(command=command, **kwargs)
            return {"estopped": False}, Endpoint()

    monkeypatch.setattr(
        controller_module,
        "A1ZProtocolClient",
        FakeProtocolClient,
    )
    monkeypatch.setattr(
        controller_module.ConsoleController,
        "refreshNow",
        lambda _self: None,
    )
    controller = controller_module.ConsoleController(ROOT)
    controller._connected = True
    controller._backend_matched = True
    controller._connection_issue = ""
    controller._backend = "isaacsim"
    controller._control_mode = "position_hold"
    controller._telemetry._age_ms = 0
    controller._estopped = True
    controller._faulted = True
    controller._robot_running = False
    try:
        assert controller.estopReleaseEnabled is True
        controller.releaseEmergencyStop()
        deadline = time.monotonic() + 1.0
        while controller.commandBusy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.002)
        app.processEvents()

        assert captured["command"] == "estop_release"
        assert captured["require_running"] is False
        assert controller.estopped is False
    finally:
        controller.shutdown()


def test_status_separates_gripper_target_from_measured_feedback() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class GripperTelemetrySpy:
        is_estopped = False
        is_running = True

        def __init__(self) -> None:
            self.target = 0.8
            self.measured = 0.35
            self.commanded = -1.0

        def get_robot_info(self) -> dict[str, object]:
            return {
                "control_mode": "gravity_comp_effort",
                "gripper_free_drive": False,
            }

        def get_joint_state(self) -> dict[str, object]:
            return {
                "pos": np.zeros(6),
                "vel": np.zeros(6),
                "eff": np.zeros(6),
            }

        def get_gripper_pos(self) -> float:
            return self.target

        def get_gripper_target_pos(self) -> float:
            return self.target

        def get_gripper_measured_pos(self) -> float:
            return self.measured

        def command_gripper(self, value: float) -> None:
            self.commanded = float(value)
            self.target = float(value)
            self.measured = float(value)

    robot = GripperTelemetrySpy()
    server = RobotServer(robot, with_gripper=True)
    status = server._dispatch_request("status", {})["data"]
    assert status["gripper_target"] == pytest.approx(0.8)
    assert status["gripper_measured"] == pytest.approx(0.35)
    assert status["gripper"] == pytest.approx(0.35)

    command = server._dispatch_request("gripper", {"value": 0.6})
    assert command["ok"] is True
    assert command["data"]["gripper_target"] == pytest.approx(0.6)
    assert command["data"]["gripper_measured"] == pytest.approx(0.6)
    assert command["data"]["verification"]["reached"] is True
    assert robot.commanded == pytest.approx(0.6)


def test_gripper_command_fails_when_sdk_measured_feedback_does_not_move() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class StalledGripper:
        is_estopped = False
        is_running = True

        def __init__(self) -> None:
            self.target = 0.8
            self.measured = 0.35
            self.command_calls = 0

        def get_robot_info(self) -> dict[str, object]:
            return {
                "control_mode": "position_hold",
                "gripper_free_drive": False,
            }

        def get_gripper_pos(self) -> float:
            return self.target

        def get_gripper_target_pos(self) -> float:
            return self.target

        def get_gripper_measured_pos(self) -> float:
            return self.measured

        def command_gripper(self, value: float) -> None:
            self.target = float(value)
            self.command_calls += 1

    robot = StalledGripper()
    server = RobotServer(
        robot,
        with_gripper=True,
        gripper_feedback_timeout_s=0.0,
    )
    result = server._dispatch_request("gripper", {"value": 0.6})

    assert result["ok"] is False
    assert result["execution_state"] == "submitted_unverified"
    assert robot.command_calls == 1
    assert "not reached" in result["error"]
    assert result["data"]["verification"]["measured"] == pytest.approx(0.35)


def test_operator_facing_sdk_capabilities_have_protocol_handlers() -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    expected = {
        "status",
        "info",
        "move",
        "cartesian_jog",
        "joint_jog",
        "command",
        "gripper",
        "grasp_close",
        "grasp_status",
        "grasp_release",
        "estop",
        "estop_release",
        "gravity_mode",
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
        "cartesian_jog",
        "joint_jog",
        "command",
        "gripper",
        "grasp_close",
        "grasp_release",
        "gravity_mode",
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


def test_cartesian_ik_increment_is_transferred_to_command_space() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.cartesian_jog import compose_command_space_joint_target

    measured = np.deg2rad([-0.75, 31.29, -25.41, 4.27, 42.61, 0.82])
    commanded = np.deg2rad([0.0, 30.0, -30.0, 5.0, 40.0, 0.0])
    solved = measured + np.deg2rad([1.2, -0.4, 0.8, 0.1, -0.2, 0.3])

    command_target, joint_delta = compose_command_space_joint_target(
        measured,
        solved,
        commanded,
    )

    assert np.rad2deg(joint_delta) == pytest.approx(
        [1.2, -0.4, 0.8, 0.1, -0.2, 0.3]
    )
    assert command_target == pytest.approx(commanded + joint_delta)
    assert command_target - solved == pytest.approx(commanded - measured)


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

    robot = MockArmRobot(with_gripper=True, zero_gravity_mode=False)
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
        "execution_state": "rejected",
    }
    assert server._dispatch_request("estop_release", {})["ok"] is True
    robot.stop()


def test_console_sdk_recording_and_control_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.mock_robot import MockArmRobot
    from a1z_ext.robots.server import RobotServer

    robot = MockArmRobot(
        with_gripper=True,
        zero_gravity_mode=False,
        joint_limits=[(-np.pi, np.pi)] * 6,
    )
    robot.start()
    server = RobotServer(robot, with_gripper=True)
    monkeypatch.setattr(
        RobotServer,
        "_recording_path",
        staticmethod(lambda name: tmp_path / Path(str(name)).name),
    )

    rejected_hot_factor = server._dispatch_request(
        "gravity_mode", {"enabled": True, "factor": 0.3}
    )
    assert rejected_hot_factor["ok"] is False
    assert robot.zero_gravity_mode is False
    gravity = server._dispatch_request("gravity_mode", {"enabled": True})
    assert gravity["ok"] is True
    assert gravity["data"]["gravity_comp_factor"] == pytest.approx(1.0)
    status = server._dispatch_request("status", {})["data"]
    assert status["control_mode"] == "gravity_comp_effort"
    assert status["gravity_comp_factor"] == pytest.approx(1.0)
    np.testing.assert_allclose(
        status["joint_limits_deg"],
        [[-180.0, 180.0]] * 6,
    )
    assert status["arm_motion_speed_rad_s"] == {
        "minimum": pytest.approx(0.05),
        "default": pytest.approx(0.5),
        "maximum": pytest.approx(1.5),
    }
    assert server._dispatch_request("info", {})["data"]["gravity_comp_factor"] == pytest.approx(1.0)
    rejected = server._dispatch_request("gravity_factor", {"factor": 0.65})
    assert rejected["ok"] is False
    assert "Unknown command" in rejected["error"]
    assert robot.gravity_comp_factor == pytest.approx(1.0)
    assert server._dispatch_request("gripper_free_drive", {"enabled": True})["ok"] is True
    assert server._dispatch_request("record_start", {"sample_hz": 50})["ok"] is True
    assert server._dispatch_request("info", {})["data"]["recording"] is True
    for command, args in (
        ("gravity_mode", {"enabled": False}),
        ("gripper", {"value": 0.4}),
        ("move", {"preset": "home"}),
        ("stop", {}),
    ):
        blocked = server._dispatch_request(command, args)
        assert blocked["ok"] is False
        assert "Recording is active" in blocked["error"]
    time.sleep(0.05)
    stopped = server._dispatch_request("record_stop", {"name": "teach.json"})
    assert stopped["ok"] is True
    assert stopped["data"]["frames"] >= 1
    assert stopped["data"]["safe_state_restored"] is True
    assert stopped["data"]["control_mode"] == "position_hold"
    assert stopped["data"]["gripper_free_drive"] is False
    assert robot.zero_gravity_mode is False
    assert robot.get_robot_info()["gripper_free_drive"] is False
    assert (tmp_path / "teach.json").is_file()
    saved = json.loads((tmp_path / "teach.json").read_text(encoding="utf-8"))
    assert saved["metadata"]["backend"] == "mock"
    info = server._dispatch_request("record_info", {})["data"]
    assert info["recording"] is False
    assert info["name"] == "teach.json"
    # MockArmRobot records six joints. Make the fixture explicitly represent
    # the seven-dimensional real A1Z+G1Z trajectory that exercises the
    # server-side free-drive playback guard.
    saved["num_joints"] = 7
    for frame in saved["frames"]:
        frame[1].append(0.5)
    (tmp_path / "teach.json").write_text(
        json.dumps(saved),
        encoding="utf-8",
    )
    assert server._dispatch_request(
        "gripper_free_drive", {"enabled": True}
    )["ok"] is True
    blocked_playback = server._dispatch_request(
        "record_play", {"name": "teach.json"}
    )
    assert blocked_playback["ok"] is False
    assert "free-drive" in blocked_playback["error"]
    robot.stop()


def test_gravity_mode_transition_never_mutates_startup_factor() -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class GravitySpy:
        is_estopped = False
        is_running = True

        def __init__(self) -> None:
            self.factor = 1.0
            self.enabled = False
            self.calls: list[tuple[str, float | bool]] = []

        def set_gravity_mode(self, enabled: bool) -> None:
            self.enabled = bool(enabled)
            self.calls.append(("mode", self.enabled))

        def get_robot_info(self) -> dict[str, object]:
            return {
                "gravity_comp_factor": self.factor,
                "control_mode": (
                    "gravity_comp_effort" if self.enabled else "position_hold"
                ),
            }

    robot = GravitySpy()
    server = RobotServer(robot, with_gripper=False)
    rejected = server._dispatch_request(
        "gravity_mode", {"enabled": True, "factor": 0.3}
    )
    assert rejected["ok"] is False
    assert "startup parameter" in rejected["error"]
    assert robot.calls == []
    assert robot.factor == pytest.approx(1.0)

    robot.factor = 0.0
    rejected_zero_factor = server._dispatch_request(
        "gravity_mode", {"enabled": True}
    )
    assert rejected_zero_factor["ok"] is False
    assert "(0.0, 1.0]" in rejected_zero_factor["error"]
    assert robot.calls == []

    robot.factor = 1.1
    rejected_excess_factor = server._dispatch_request(
        "gravity_mode", {"enabled": True}
    )
    assert rejected_excess_factor["ok"] is False
    assert robot.calls == []

    robot.factor = 1.0
    assert server._dispatch_request("gravity_mode", {"enabled": True})["ok"]
    assert robot.calls == [("mode", True)]
    assert robot.factor == pytest.approx(1.0)


def test_recording_playback_rejects_missing_or_foreign_backend_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.mock_robot import MockArmRobot
    from a1z_ext.robots.server import RobotServer

    path = tmp_path / "teach.json"
    robot = MockArmRobot(with_gripper=True)
    robot.start()
    server = RobotServer(robot, with_gripper=True)
    monkeypatch.setattr(
        RobotServer,
        "_recording_path",
        staticmethod(lambda _name: path),
    )
    try:
        base = {
            "version": 1,
            "num_joints": 6,
            "frames": [[0.0, np.zeros(6).tolist()]],
        }
        path.write_text(json.dumps(base), encoding="utf-8")
        missing = server._dispatch_request("record_play", {"name": "teach.json"})
        assert missing["ok"] is False
        assert "no backend metadata" in missing["error"]

        base["metadata"] = {"backend": "socketcan"}
        path.write_text(json.dumps(base), encoding="utf-8")
        foreign = server._dispatch_request("record_play", {"name": "teach.json"})
        assert foreign["ok"] is False
        assert "backend mismatch" in foreign["error"]
    finally:
        robot.stop()


def test_recording_start_rolls_back_zero_force_modes_on_failure() -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class RecordingFailureSpy:
        is_estopped = False
        is_running = True

        def __init__(self) -> None:
            self.gravity = False
            self.gripper_free_drive = False

        def get_robot_info(self) -> dict[str, object]:
            return {
                "backend": "mock",
                "control_mode": (
                    "gravity_comp_effort" if self.gravity else "position_hold"
                ),
                "gripper_free_drive": self.gripper_free_drive,
            }

        def set_gravity_mode(self, enabled: bool) -> None:
            self.gravity = bool(enabled)

        def set_gripper_free_drive(self, enabled: bool) -> None:
            self.gripper_free_drive = bool(enabled)

        def start_recording(self, _sample_hz: int) -> None:
            raise RuntimeError("recorder unavailable")

    robot = RecordingFailureSpy()
    server = RobotServer(robot, with_gripper=True)
    result = server._dispatch_request("record_start", {"sample_hz": 50})

    assert result["ok"] is False
    assert "recorder unavailable" in result["error"]
    assert robot.gravity is False
    assert robot.gripper_free_drive is False
    assert server._dispatch_request("info", {})["data"]["recording"] is False


def test_move_fails_when_endpoint_feedback_stalls_outside_half_mm() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class MotionFeedbackSpy:
        is_estopped = False
        is_running = True

        def __init__(self) -> None:
            self.frame_calls = 0
            self.writer_threads: set[int] = set()
            self.command = np.zeros(6, dtype=np.float64)

        def get_robot_info(self) -> dict[str, object]:
            return {
                "control_mode": "position_hold",
                "command_pos": self.command.copy(),
            }

        def get_joint_pos(self):
            return np.zeros(6, dtype=np.float64)

        def command_motion_frame(self, target, velocity, acceleration) -> None:
            del velocity, acceleration
            self.command = np.asarray(target, dtype=np.float64).copy()
            self.frame_calls += 1
            self.writer_threads.add(threading.get_ident())

    def linear_fk(joints):
        pose = np.eye(4, dtype=np.float64)
        pose[0, 3] = float(np.sum(joints)) * 0.1
        return pose

    robot = MotionFeedbackSpy()
    server = RobotServer(
        robot,
        with_gripper=False,
        forward_kinematics=linear_fk,
        endpoint_feedback_timeout_s=0.0,
        endpoint_stable_samples=2,
    )
    result = server._dispatch_request(
        "move",
        {
            "joints": [5.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "speed": 0.5,
            "timeout_s": 3.0,
        },
    )
    assert result["ok"] is False
    assert result["execution_state"] == "submitted_unverified"
    assert robot.frame_calls > 1
    assert len(robot.writer_threads) == 1
    verification = result["data"]["verification"]
    assert verification["reached"] is False
    assert verification["position_error_mm"] > 0.5
    assert verification["position_tolerance_mm"] == pytest.approx(0.5)


def test_joint_jog_preserves_unselected_command_targets_and_feedback_pose() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class CommandSpaceJogSpy:
        is_estopped = False
        is_running = True

        def __init__(self) -> None:
            self.command = np.deg2rad(
                np.array([0.0, 30.0, -30.0, 5.0, 40.0, 0.0])
            )
            self.measured = self.command.copy()
            self.submitted_targets: list[object] = []

        def get_robot_info(self) -> dict[str, object]:
            return {
                "control_mode": "position_hold",
                "command_pos": self.command.copy(),
                "joint_limits": np.deg2rad(
                    np.array(
                        [
                            [-120.0, 120.0],
                            [0.0, 180.0],
                            [-180.0, 0.0],
                            [-85.0, 85.0],
                            [-85.0, 85.0],
                            [-115.0, 115.0],
                        ]
                    )
                ),
            }

        def get_joint_pos(self):
            return self.measured.copy()

        def command_motion_frame(self, target, velocity, acceleration) -> None:
            del velocity, acceleration
            target = np.asarray(target, dtype=np.float64).copy()
            self.submitted_targets.append(target)
            self.command = target
            self.measured = target.copy()

    def linear_fk(joints):
        pose = np.eye(4, dtype=np.float64)
        pose[0, 3] = float(np.sum(joints)) * 0.1
        return pose

    robot = CommandSpaceJogSpy()
    command_before = robot.command.copy()
    server = RobotServer(
        robot,
        with_gripper=False,
        forward_kinematics=linear_fk,
        endpoint_stable_samples=2,
    )

    result = server._dispatch_request(
        "joint_jog",
        {"joint_index": 1, "delta_deg": 5.0, "speed": 0.5},
    )

    assert result["ok"] is True
    assert len(robot.submitted_targets) > 1
    expected = command_before.copy()
    expected[0] += np.deg2rad(5.0)
    assert robot.command == pytest.approx(expected)
    assert robot.measured == pytest.approx(expected)
    verification = result["data"]["verification"]
    assert verification["reached"] is True
    assert verification["joint_index"] == 1
    assert verification["target_deg"] == pytest.approx(np.rad2deg(expected), abs=1e-3)
    assert verification["position_error_mm"] <= 0.5


def test_cartesian_jog_uses_command_space_and_feedback_settling() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class CartesianCommandSpaceSpy:
        is_estopped = False
        is_running = True
        is_faulted = False
        runtime_fault = ""

        def __init__(self) -> None:
            self.command = np.deg2rad(
                np.array([0.0, 30.0, -30.0, 5.0, 40.0, 0.0])
            )
            self.measured = self.command.copy()
            self.submitted_targets: list[object] = []

        def get_robot_info(self) -> dict[str, object]:
            return {
                "control_mode": "position_hold",
                "command_pos": self.command.copy(),
                "joint_limits": np.deg2rad(
                    np.array(
                        [
                            [-120.0, 120.0],
                            [0.0, 180.0],
                            [-180.0, 0.0],
                            [-85.0, 85.0],
                            [-85.0, 85.0],
                            [-115.0, 115.0],
                        ]
                    )
                ),
            }

        def get_joint_pos(self):
            return self.measured.copy()

        def command_motion_frame(self, target, velocity, acceleration) -> None:
            del velocity, acceleration
            target = np.asarray(target, dtype=np.float64).copy()
            self.submitted_targets.append(target)
            self.command = target
            self.measured = target.copy()

    def linear_fk(joints):
        pose = np.eye(4, dtype=np.float64)
        pose[0, 3] = float(np.sum(joints)) * 0.1
        return pose

    robot = CartesianCommandSpaceSpy()
    command_before = robot.command.copy()
    requested_delta_deg = [1.2, -0.4, 0.8, 0.1, -0.2, 0.3]
    server = RobotServer(
        robot,
        with_gripper=False,
        forward_kinematics=linear_fk,
        endpoint_stable_samples=2,
    )

    result = server._dispatch_request(
        "cartesian_jog",
        {"joint_delta_deg": requested_delta_deg, "speed": 0.4},
    )

    assert result["ok"] is True
    assert len(robot.submitted_targets) > 1
    expected_delta = np.deg2rad(requested_delta_deg)
    expected = command_before + expected_delta
    verification = result["data"]["verification"]
    assert verification["reached"] is True
    assert verification["joint_delta_deg"] == pytest.approx(requested_delta_deg)
    assert verification["target_deg"] == pytest.approx(np.rad2deg(expected), abs=1e-3)
    assert verification["position_error_mm"] <= 0.5


def test_move_reports_runtime_fault_instead_of_hiding_it_as_tolerance() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class MotionFaultSpy:
        is_estopped = False

        def __init__(self) -> None:
            self.is_running = True
            self.runtime_fault = ""
            self.is_faulted = False
            self.move_calls = 0

        def get_robot_info(self) -> dict[str, object]:
            return {"control_mode": "position_hold"}

        def get_joint_pos(self):
            return np.zeros(6, dtype=np.float64)

        def command_motion_frame(self, target, velocity, acceleration) -> None:
            del target, velocity, acceleration
            self.move_calls += 1
            self.is_running = False
            self.is_faulted = True
            self.runtime_fault = "MotorB fault on joint4: under voltage"

    robot = MotionFaultSpy()
    server = RobotServer(
        robot,
        with_gripper=False,
        forward_kinematics=lambda joints: np.eye(4, dtype=np.float64),
    )
    result = server._dispatch_request(
        "move",
        {"joints": [5.0, 0.0, 0.0, 0.0, 0.0, 0.0], "speed": 0.5},
    )

    assert result["ok"] is False
    assert result["execution_state"] == "submitted_unverified"
    assert robot.move_calls == 1
    assert "control loop faulted" in result["error"]
    assert "MotorB fault on joint4: under voltage" in result["error"]
    assert "tolerance" not in result["error"]
    assert result["data"]["verification"] == {}


def test_move_reports_already_at_target_without_submitting_sdk_motion() -> None:
    np = pytest.importorskip("numpy")
    from a1z_ext.robots.server import RobotServer

    class AlreadyAtTarget:
        is_estopped = False
        is_running = True

        def get_robot_info(self) -> dict[str, object]:
            return {"control_mode": "position_hold"}

        def get_joint_pos(self):
            return np.zeros(6, dtype=np.float64)

        def move_joints(self, target, speed: float) -> None:
            del target, speed
            raise AssertionError("already-at-target must not call move_joints")

    server = RobotServer(
        AlreadyAtTarget(),
        with_gripper=False,
        forward_kinematics=lambda joints: np.eye(4, dtype=np.float64),
    )
    result = server._dispatch_request(
        "move",
        {"joints": [0.0] * 6, "speed": 0.5},
    )

    assert result["ok"] is True
    assert result["data"]["motion_performed"] is False
    assert result["data"]["completion"] == "already_at_target"


def test_socketcan_adapter_holds_measured_pose_when_leaving_zero_gravity() -> None:
    np = pytest.importorskip("numpy")
    monkeypatch_path = str(ROOT / "vendor" / "GALAXEA-A1Z")
    if monkeypatch_path not in sys.path:
        sys.path.insert(0, monkeypatch_path)
    from a1z.robots.arm_robot import JointCommand, JointState
    from a1z_ext.robots.socketcan_robot import SocketCANArmRobot

    robot = SocketCANArmRobot.__new__(SocketCANArmRobot)
    measured = np.array([0.2, 0.3, -0.4, 0.1, -0.2, 0.05])
    robot._num_joints = 6
    robot._running = True
    robot._estop_latch = threading.Event()
    robot._state_lock = threading.Lock()
    robot._command_lock = threading.Lock()
    robot._state = JointState(
        pos=measured.copy(),
        vel=np.zeros(6),
        eff=np.zeros(6),
    )
    robot._command = JointCommand(
        pos=np.zeros(6),
        vel=np.ones(6),
        acc=np.ones(6),
        kp=np.zeros(6),
        kd=np.zeros(6),
        torque_ff=np.ones(6),
    )
    robot._default_kp = np.arange(1.0, 7.0)
    robot._default_kd = np.arange(0.1, 0.7, 0.1)
    robot._joint_limits = None
    robot.gravity_comp_factor = 1.0
    robot._control_freq_hz = 250
    robot.gripper = None
    robot._gripper_free_drive = False
    robot._runtime_fault_lock = threading.Lock()
    robot._runtime_fault = ""
    robot._motor_a_status_codes = [0, 0, 0]
    robot.zero_gravity_mode = True

    robot.set_gravity_mode(False)

    assert robot.zero_gravity_mode is False
    assert robot._command.pos == pytest.approx(measured)
    assert robot._command.vel == pytest.approx(np.zeros(6))
    assert robot._command.acc == pytest.approx(np.zeros(6))
    assert robot._command.torque_ff == pytest.approx(np.zeros(6))
    assert robot._command.kp == pytest.approx(robot._default_kp)
    assert robot._command.kd == pytest.approx(robot._default_kd)
    assert robot.get_robot_info()["command_pos"] == pytest.approx(measured)
    robot._running = False


def test_socketcan_adapter_does_not_apply_motor_b_codes_to_motor_a() -> None:
    np = pytest.importorskip("numpy")
    sdk_path = str(ROOT / "vendor" / "GALAXEA-A1Z")
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
    from a1z.robots.arm_robot import JointState
    from a1z_ext.robots.socketcan_robot import SocketCANArmRobot

    robot = SocketCANArmRobot.__new__(SocketCANArmRobot)
    robot._running = False
    robot._state_lock = threading.Lock()
    robot._state = JointState(
        pos=np.zeros(6),
        vel=np.zeros(6),
        eff=np.zeros(6),
        error_codes=np.array([4, 4, 4, 1, 1, 1]),
    )
    robot._motor_a_status_codes = [0, 0, 0]

    robot._check_motor_errors()
    assert robot._motor_a_status_codes == [4, 4, 4]

    robot._state.error_codes = np.array([4, 4, 4, 8, 1, 1])
    with pytest.raises(RuntimeError, match="MotorB fault on joint4"):
        robot._check_motor_errors()


def test_robot_factory_rejects_unsafe_gravity_scale_before_backend_creation() -> None:
    pytest.importorskip("numpy")
    from a1z_ext.robots.get_robot import create_a1z_robot

    for factor in (-0.01, 1.01, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="gravity_comp_factor"):
            create_a1z_robot(backend="mock", gravity_comp_factor=factor)
