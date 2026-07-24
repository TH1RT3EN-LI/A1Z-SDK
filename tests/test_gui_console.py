from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOST_ROOT = Path("/opt/a1z-gui-contract")

from a1z_ext.gui_console import (  # noqa: E402
    AnyGraspOptions,
    allocate_anygrasp_run_dir,
    build_anygrasp_command,
    build_host_isaac_env,
    build_isaac_command,
    build_ros_bridge_env,
    build_ros_bridge_start_command,
    build_ros_bridge_stop_command,
    build_rviz_command,
    build_rviz_env,
    classify_log_message,
    host_to_workspace_path,
    normalize_process_log_line,
    probe_a1z_server,
    summarize_anygrasp_output,
)


class _OneShotServer:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = int(self.server.getsockname()[1])
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        try:
            connection, _address = self.server.accept()
            with connection:
                data = b""
                while b"\n" not in data:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                connection.sendall((json.dumps(self.response) + "\n").encode("utf-8"))
        finally:
            self.server.close()

    def start(self) -> None:
        self.thread.start()


class GuiConsoleContractTest(unittest.TestCase):
    def test_anygrasp_runs_get_unique_directories(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "runtime") as temp_dir:
            root = Path(temp_dir)
            run_root = root / "runtime" / "anygrasp_gui"
            now = datetime(2026, 7, 23, 20, 30, 0)
            first = allocate_anygrasp_run_dir(root, run_root, now=now)
            second = allocate_anygrasp_run_dir(root, first, now=now)
            self.assertEqual(first, run_root / "20260723_203000")
            self.assertEqual(second, run_root / "20260723_203000_01")
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())

    def test_host_isaac_launcher_uses_full_app_entry(self) -> None:
        command = build_isaac_command(
            ROOT,
            Path("/opt/isaacsim"),
            ROOT / "build" / "scenes" / "A1Z_G1Z_world.usd",
        )
        self.assertEqual(command[0], str(ROOT / "scripts" / "open_a1z_isaac_app.sh"))
        launcher = (ROOT / "scripts" / "open_a1z_isaac_app.sh").read_text(encoding="utf-8")
        self.assertIn('ISAAC_SIM_LAUNCHER="$ISAAC_SIM_ROOT/isaac-sim.sh"', launcher)
        self.assertNotIn("webrtc", launcher.lower())
        self.assertIn("--no-ros-env", launcher)
        self.assertIn("default_engine=physx", launcher)
        self.assertIn("auto_switch_on_startup=false", launcher)
        self.assertIn('A1Z_EE_DRAG_TARGET_ENABLED:-0', launcher)

    def test_host_environment_rewrites_workspace_paths(self) -> None:
        env = build_host_isaac_env(
            HOST_ROOT,
            Path("/opt/isaacsim"),
            HOST_ROOT / "build" / "scenes" / "A1Z_G1Z_world.usd",
            base_env={},
        )
        self.assertEqual(env["A1Z_ISAAC_API_PROFILE"], "native_6_0")
        self.assertEqual(env["A1Z_TCP_PORT"], "37103")
        self.assertEqual(env["A1Z_SOCKET_PATH"], "")
        self.assertEqual(env["A1Z_EE_DRAG_TARGET_ENABLED"], "0")
        self.assertEqual(
            env["A1Z_SDK_VENV_DIR"],
            str(HOST_ROOT / "runtime" / "venvs" / "a1z-sdk"),
        )
        self.assertEqual(
            env["A1Z_PHYSICAL_GRASP_CONTROLLER_PROFILE"],
            str(
                HOST_ROOT
                / "config"
                / "grasping"
                / "controllers"
                / "a1z_physical_gripper_v1.json"
            ),
        )
        for key in ("A1Z_WORLD_USD", "A1Z_D405_STATUS_PATH"):
            self.assertTrue(env[key].startswith(str(HOST_ROOT)))
            self.assertNotIn("/workspace/A1Z", env[key])

    def test_ee_drag_can_be_enabled_explicitly(self) -> None:
        env = build_host_isaac_env(
            HOST_ROOT,
            Path("/opt/isaacsim"),
            HOST_ROOT / "build" / "scenes" / "A1Z_G1Z_world.usd",
            ee_drag_enabled=True,
            base_env={},
        )
        self.assertEqual(env["A1Z_EE_DRAG_TARGET_ENABLED"], "1")

    def test_rviz_command_uses_project_launcher_and_mounted_config(self) -> None:
        command = build_rviz_command(
            HOST_ROOT,
            HOST_ROOT / "ros2_ws" / "rviz" / "a1z_d405.rviz",
            rebuild=True,
        )
        self.assertEqual(
            command[0],
            str(HOST_ROOT / "scripts" / "open_a1z_rviz_in_container.sh"),
        )
        self.assertEqual(command[1], "--rebuild")
        self.assertEqual(
            command[-1],
            "/workspace/A1Z/ros2_ws/rviz/a1z_d405.rviz",
        )

    def test_rviz_environment_has_explicit_domain_and_scoped_container(self) -> None:
        env = build_rviz_env(ROOT, base_env={"DISPLAY": ":9"})
        self.assertEqual(env["DISPLAY"], ":9")
        self.assertEqual(env["ROS_DOMAIN_ID"], "62")
        self.assertEqual(env["A1Z_RVIZ_CONTAINER_NAME"], "a1z-rviz-humble-isaac6")
        rviz_config = (ROOT / "ros2_ws" / "rviz" / "a1z_d405.rviz").read_text(
            encoding="utf-8"
        )
        self.assertEqual(rviz_config.count("Reliability Policy: Best Effort"), 2)

    def test_rviz_config_must_stay_inside_repository(self) -> None:
        with self.assertRaises(ValueError):
            build_rviz_command(ROOT, Path("/tmp/outside.rviz"))

    def test_ros_bridge_chain_uses_explicit_runtime_contract(self) -> None:
        env = build_ros_bridge_env(
            ROOT,
            tcp_host="127.0.0.9",
            tcp_port=37123,
            base_env={},
        )
        self.assertEqual(env["ROS_DOMAIN_ID"], "62")
        self.assertEqual(env["A1Z_ROS2_CONTAINER_NAME"], "a1z-ros2-humble-isaac6")
        self.assertEqual(env["A1Z_TCP_HOST"], "127.0.0.9")
        self.assertEqual(env["A1Z_TCP_PORT"], "37123")

        status_path = ROOT / "runtime" / "gui-console" / "test-ros-status.json"
        command = build_ros_bridge_start_command(
            ROOT,
            tcp_host="127.0.0.9",
            tcp_port=37123,
            status_path=status_path,
            python_executable="/usr/bin/python3",
            timeout_s=90,
        )
        self.assertEqual(command[0], "/usr/bin/python3")
        self.assertEqual(command[1], str(ROOT / "scripts" / "start_a1z_ros2_stack.py"))
        self.assertIn(str(status_path), command)
        self.assertIn("90", command)
        self.assertEqual(
            build_ros_bridge_stop_command(ROOT),
            [
                str(ROOT / "scripts" / "run_a1z_ros2_motion_in_container.sh"),
                "stop",
            ],
        )

    def test_ros_bridge_startup_validates_both_image_topics(self) -> None:
        launcher = (ROOT / "scripts" / "start_a1z_ros2_stack.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"camera_status"', launcher)
        self.assertIn('"/a1z/d405/color/image_raw"', launcher)
        self.assertIn('"/a1z/d405/depth/image_rect"', launcher)
        self.assertIn('"wait"', launcher)
        self.assertIn("--no-daemon", launcher)

        motion_launcher = (
            ROOT / "scripts" / "run_a1z_ros2_motion_in_container.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('"$ROOT_DIR/scripts/create_a1z_ros2_container.sh"', motion_launcher)
        self.assertIn("ROS 2 container does not exist", motion_launcher)
        create_launcher = (
            ROOT / "scripts" / "create_a1z_ros2_container.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("A1Z_ROS2_REBUILD_IMAGE", create_launcher)
        self.assertIn("docker image inspect", create_launcher)
        sdk_launcher = (
            ROOT / "scripts" / "a1z_sdk_python_in_container.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("-w /workspace/A1Z", sdk_launcher)

    def test_anygrasp_command_keeps_container_path_boundary(self) -> None:
        output = HOST_ROOT / "runtime" / "gui-test"
        command = build_anygrasp_command(
            HOST_ROOT,
            AnyGraspOptions(
                instruction="抓取红色盒子",
                host_output_dir=output,
                target_prim_path="/World/TrashSet/pudding_box",
                resolve_target_prim=True,
                dry_run=True,
            ),
        )
        self.assertEqual(
            command[0],
            str(HOST_ROOT / "scripts" / "run_target_mask_to_anygrasp_pick_attempt.sh"),
        )
        self.assertIn("--dry-run", command)
        self.assertIn("--require-current-joints", command)
        self.assertNotIn("--resolve-target-prim", command)
        self.assertNotIn("--target-prim-path", command)
        self.assertIn("/workspace/A1Z/runtime/gui-test", command)
        self.assertNotIn(str(output), command)

    def test_console_dry_run_defaults_off_and_is_persisted(self) -> None:
        source = (ROOT / "scripts" / "a1z_gui_console.py").read_text(encoding="utf-8")
        self.assertIn('self.settings.get("dry_run", False)', source)
        self.assertIn('"dry_run": self.dry_run_var.get()', source)
        self.assertIn("if execute and not self.dry_run_var.get()", source)

    def test_console_does_not_expose_target_path_assistance(self) -> None:
        source = (ROOT / "scripts" / "a1z_gui_console.py").read_text(encoding="utf-8")
        self.assertNotIn("target_prim_var", source)
        self.assertNotIn("resolve_target_var", source)
        self.assertIn('target_prim_path=""', source)
        self.assertIn("resolve_target_prim=False", source)

    def test_analysis_command_does_not_add_execution_flags(self) -> None:
        command = build_anygrasp_command(
            HOST_ROOT,
            AnyGraspOptions(
                instruction="只分析桌面目标",
                host_output_dir=HOST_ROOT / "runtime" / "gui-analysis",
                execute=False,
            ),
        )
        self.assertEqual(
            command[0],
            str(HOST_ROOT / "scripts" / "run_target_mask_to_anygrasp_from_ros.sh"),
        )
        self.assertNotIn("--arm-speed", command)
        self.assertNotIn("--grasp-mode", command)

    def test_output_path_must_stay_inside_repository(self) -> None:
        with self.assertRaises(ValueError):
            host_to_workspace_path(ROOT, Path("/tmp/a1z-outside"))

    def test_probe_recognizes_a1z_protocol(self) -> None:
        server = _OneShotServer(
            {
                "ok": True,
                "data": {
                    "backend": "isaacsim",
                    "presets": ["home", "ready"],
                    "articulation_root_prim": "/World/A1Z_G1Z/Geometry",
                },
            }
        )
        server.start()
        result = probe_a1z_server("127.0.0.1", server.port)
        server.thread.join(timeout=1.0)
        self.assertTrue(result.reachable)
        self.assertTrue(result.recognized)
        self.assertIn("isaacsim", result.detail)

    def test_probe_rejects_unrelated_listener(self) -> None:
        server = _OneShotServer({"hello": "world"})
        server.start()
        result = probe_a1z_server("127.0.0.1", server.port)
        server.thread.join(timeout=1.0)
        self.assertTrue(result.reachable)
        self.assertFalse(result.recognized)
        self.assertIn("不是可识别的 A1Z", result.detail)

    def test_warning_text_and_empty_json_errors_are_not_marked_as_failures(self) -> None:
        self.assertEqual(
            classify_log_message("[Open3D WARNING] GLFW Error: Failed to create window"),
            "warn",
        )
        self.assertEqual(classify_log_message('{"ran": true, "error": ""}'), "")
        self.assertEqual(
            classify_log_message('{"capture_ok": false, "render_error": "optional preview"}'),
            "warn",
        )
        self.assertEqual(classify_log_message("进程结束，退出码 0"), "good")

    def test_anygrasp_optional_dependency_noise_is_explained(self) -> None:
        self.assertIn(
            "不使用该扩展",
            normalize_process_log_line(
                "AnyGrasp",
                "WARNING:root:Failed to import geometry msgs in rigid_transformations.py.",
            ),
        )
        self.assertIn(
            "EGL 主渲染",
            normalize_process_log_line(
                "AnyGrasp",
                "[Open3D WARNING] GLFW Error: OSMesa: Library not found",
            ),
        )

    def test_anygrasp_summary_labels_dry_run_as_non_actuating(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            (output / "execute").mkdir()
            (output / "pipeline_status.json").write_text(
                json.dumps(
                    {
                        "anygrasp_grasp_count": 20,
                        "selected_plan_present": True,
                        "best_direct_plan_present": False,
                    }
                ),
                encoding="utf-8",
            )
            (output / "execute" / "execution_result.json").write_text(
                json.dumps({"dry_run": True, "success": True}),
                encoding="utf-8",
            )
            summary = summarize_anygrasp_output(output)
        self.assertIn("干运行验证 成功（未驱动机械臂）", summary)


if __name__ == "__main__":
    unittest.main()
