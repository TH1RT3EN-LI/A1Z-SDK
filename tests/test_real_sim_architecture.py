from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


class RealSimArchitectureTests(unittest.TestCase):
    def test_profiles_select_only_device_adapters(self) -> None:
        common = read_env(ROOT / "config" / "common.env")
        sim = read_env(ROOT / "config" / "sim.env")
        real = read_env(ROOT / "config" / "real.env")
        self.assertNotIn("A1Z_BACKEND", common)
        self.assertEqual(sim["A1Z_BACKEND"], "isaacsim")
        self.assertEqual(sim["A1Z_CAMERA_SOURCE"], "isaac")
        self.assertEqual(sim["A1Z_CONTROL_FREQ_HZ"], "60")
        self.assertEqual(real["A1Z_BACKEND"], "socketcan")
        self.assertEqual(real["A1Z_CAMERA_SOURCE"], "realsense")
        self.assertEqual(real["A1Z_REAL_VISION_BACKEND"], "remote_ssh")
        self.assertEqual(real["A1Z_REMOTE_GPU_HOST"], "10.66.0.11")
        self.assertEqual(real["A1Z_REMOTE_GPU_USER"], "th1rt3en")
        self.assertEqual(
            real["A1Z_REMOTE_GPU_ROOT"],
            "/home/th1rt3en/dev/forge/A1Z",
        )
        self.assertEqual(real["A1Z_REALSENSE_CAMERA_NAME"], "d405")
        self.assertEqual(real["A1Z_REALSENSE_BASE_FRAME_ID"], "link")
        self.assertEqual(real["A1Z_REALSENSE_INITIAL_RESET"], "0")
        self.assertEqual(real["A1Z_CAN_CHANNEL"], "can0")
        self.assertEqual(real["A1Z_CAN_BITRATE"], "1000000")
        self.assertEqual(real["A1Z_GRIPPER_MAX_TORQUE"], "0.5")
        self.assertNotIn("A1Z_HAND_EYE_CALIBRATION_STATUS", real)

    def test_shell_loader_applies_profile_over_common_defaults(self) -> None:
        command = (
            "source scripts/load_a1z_env.sh; "
            'printf "%s %s %s" "$A1Z_PROFILE" "$A1Z_TCP_PORT" "$A1Z_CAMERA_SOURCE"'
        )
        real = subprocess.run(
            ["bash", "-lc", command],
            cwd=ROOT,
            env={"PATH": "/usr/bin:/bin", "A1Z_PROFILE": "real"},
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(real.stdout, "real 37104 realsense")

        explicit = subprocess.run(
            ["bash", "-lc", command],
            cwd=ROOT,
            env={
                "PATH": "/usr/bin:/bin",
                "A1Z_PROFILE": "real",
                "A1Z_TCP_PORT": "39999",
            },
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(explicit.stdout, "real 39999 realsense")

    def test_task_layer_has_no_simulator_control_branches(self) -> None:
        executor = (ROOT / "scripts" / "execute_a1z_plan.py").read_text()
        pipeline = (ROOT / "scripts" / "run_pick_pipeline.py").read_text()
        forbidden = (
            "grasp_attach",
            "physical_v2",
            "sim_contact_attach",
            "target_prim_path",
            "grasp_close_v2",
        )
        for token in forbidden:
            self.assertNotIn(token, executor)
            self.assertNotIn(token, pipeline)

    def test_control_server_exposes_only_common_grasp_commands(self) -> None:
        source = (ROOT / "a1z_ext" / "robots" / "server.py").read_text()
        for command in ('"grasp_close"', '"grasp_status"', '"grasp_release"'):
            self.assertIn(command, source)
        for command in (
            '"grasp_attach"',
            '"grasp_close_v2"',
            '"grasp_status_v2"',
            '"grasp_release_v2"',
        ):
            self.assertNotIn(command, source)

    def test_real_container_has_required_can_and_d405_packages(self) -> None:
        dockerfile = (ROOT / "docker" / "ros2-humble" / "Dockerfile").read_text()
        create = (ROOT / "scripts" / "create_a1z_ros2_container.sh").read_text()
        for package in (
            "can-utils",
            "iproute2",
            "python3-can",
            "ros-humble-realsense2-camera",
        ):
            self.assertIn(package, dockerfile)
        self.assertIn("/dev/bus/usb:/dev/bus/usb", create)
        self.assertIn('c 189:* rmw', create)
        self.assertIn("--cap-add NET_ADMIN", create)
        self.assertIn("--group-add 0", create)
        self.assertIn("discover_realsense_device_nodes", create)
        self.assertIn('--device "$node:$node"', create)
        for hardcoded_node in ("/dev/video0", "/dev/video4", "/dev/media2"):
            self.assertNotIn(hardcoded_node, create)

    def test_realsense_reset_is_opt_in_and_forwarded_to_ros(self) -> None:
        launch = (
            ROOT
            / "ros2_ws"
            / "src"
            / "a1z_motion"
            / "launch"
            / "a1z_stack.launch.py"
        ).read_text(encoding="utf-8")
        runner = (
            ROOT / "scripts" / "run_a1z_ros2_stack_in_container.sh"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"initial_reset": _env_bool("A1Z_REALSENSE_INITIAL_RESET", False)',
            launch,
        )
        self.assertIn(
            'A1Z_REALSENSE_INITIAL_RESET="${A1Z_REALSENSE_INITIAL_RESET:-0}"',
            runner,
        )

    def test_camera_bridge_rejects_stale_cached_frames(self) -> None:
        bridge = (
            ROOT
            / "ros2_ws"
            / "src"
            / "a1z_d405"
            / "a1z_d405"
            / "console_bridge.py"
        ).read_text(encoding="utf-8")
        self.assertIn("color_age_s > self._cfg.stale_after_s", bridge)
        self.assertIn("depth_age_s > self._cfg.stale_after_s", bridge)
        self.assertIn("RGB-D 帧已过期", bridge)

    def test_official_sdk_revision_is_pinned(self) -> None:
        revision = (ROOT / "vendor" / "GALAXEA-A1Z_UPSTREAM").read_text()
        self.assertIn("branch=gripper", revision)
        self.assertIn("commit=e931ecd0e25ad35df251097ba42921b3d2fa7224", revision)


if __name__ == "__main__":
    unittest.main()
