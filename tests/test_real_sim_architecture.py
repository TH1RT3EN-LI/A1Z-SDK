from __future__ import annotations

from pathlib import Path
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
        self.assertEqual(real["A1Z_CAN_CHANNEL"], "can0")
        self.assertEqual(real["A1Z_GRIPPER_MAX_TORQUE"], "0.5")
        self.assertEqual(real["A1Z_HAND_EYE_CALIBRATION_STATUS"], "unverified")

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

    def test_official_sdk_revision_is_pinned(self) -> None:
        revision = (ROOT / "vendor" / "GALAXEA-A1Z_UPSTREAM").read_text()
        self.assertIn("branch=gripper", revision)
        self.assertIn("commit=e931ecd0e25ad35df251097ba42921b3d2fa7224", revision)


if __name__ == "__main__":
    unittest.main()
