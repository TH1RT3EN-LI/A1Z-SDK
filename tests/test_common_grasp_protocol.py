from __future__ import annotations

import unittest

from a1z_ext.robots.mock_robot import MockArmRobot
from a1z_ext.robots.server import RobotServer


class CommonGraspProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.robot = MockArmRobot(with_gripper=True)
        self.robot.start()
        self.server = RobotServer(self.robot, with_gripper=True)

    def tearDown(self) -> None:
        self.robot.stop()

    def test_close_status_release_use_one_backend_neutral_contract(self) -> None:
        close = self.server._dispatch_request("grasp_close", {"timeout_s": 1.0})
        self.assertTrue(close["ok"])
        self.assertTrue(close["data"]["success"])
        self.assertTrue(close["data"]["object_detected"])
        self.assertEqual(close["data"]["backend"], "mock")

        status = self.server._dispatch_request("grasp_status", {})
        self.assertTrue(status["ok"])
        self.assertEqual(status["data"]["phase"], "holding")

        release = self.server._dispatch_request("grasp_release", {"timeout_s": 1.0})
        self.assertTrue(release["ok"])
        self.assertTrue(release["data"]["success"])
        self.assertFalse(release["data"]["object_detected"])

    def test_removed_legacy_command_is_unknown(self) -> None:
        response = self.server._dispatch_request("grasp_close_v2", {})
        self.assertFalse(response["ok"])
        self.assertIn("Unknown command", response["error"])
        self.assertFalse(hasattr(self.robot, "grasp_close_physical"))
        self.assertFalse(hasattr(self.robot, "grasp_close_and_attach"))


if __name__ == "__main__":
    unittest.main()
