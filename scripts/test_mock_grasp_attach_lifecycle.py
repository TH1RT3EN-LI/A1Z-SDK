#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.robots.mock_robot import MockArmRobot


class MockGraspAttachLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.robot = MockArmRobot(with_gripper=True, zero_gravity_mode=False)
        self.robot.start()

    def tearDown(self) -> None:
        self.robot.stop()

    def test_repeated_attach_same_target_is_noop(self) -> None:
        first = self.robot.grasp_close_and_attach("/World/TrashSet/mock_target")
        second = self.robot.grasp_close_and_attach("/World/TrashSet/mock_target")
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(first["attached_object_path"], "/World/TrashSet/mock_target")
        self.assertEqual(second["attached_object_path"], "/World/TrashSet/mock_target")
        self.assertEqual(second["contact_summary"]["mode"], "mock_already_attached")
        self.assertTrue(self.robot.get_sim_grasp_status()["has_attached_object"])

    def test_attach_different_target_without_release_fails(self) -> None:
        self.robot.grasp_close_and_attach("/World/TrashSet/mock_target")
        with self.assertRaisesRegex(RuntimeError, "Already attached"):
            self.robot.grasp_close_and_attach("/World/TrashSet/other_target")

    def test_repeated_release_is_lightweight(self) -> None:
        self.robot.grasp_close_and_attach("/World/TrashSet/mock_target")
        first = self.robot.release_attached_object(open_gripper=True)
        second = self.robot.release_attached_object(open_gripper=True)
        self.assertTrue(first["success"])
        self.assertTrue(first["released"])
        self.assertEqual(first["attached_object_path"], "/World/TrashSet/mock_target")
        self.assertIsNone(second["attached_object_path"])
        self.assertTrue(second["success"])
        self.assertTrue(second["released"])
        status = self.robot.get_sim_grasp_status()
        self.assertFalse(status["has_attached_object"])
        self.assertEqual(status["grasp_state"], "idle")
        self.assertAlmostEqual(self.robot.get_gripper_pos() or -1.0, 1.0)


if __name__ == "__main__":
    unittest.main()
