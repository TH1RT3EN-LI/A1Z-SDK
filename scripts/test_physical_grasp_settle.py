#!/usr/bin/env python3

from __future__ import annotations

from argparse import Namespace
import unittest
from unittest.mock import patch

from scripts import execute_a1z_plan


TARGET = [0.0] * 6


def status(*, wrist_velocity: float) -> dict:
    return {
        "pos_deg": [0.0] * 6,
        "vel_rad_s": [0.0, 0.0, 0.0, 0.0, wrist_velocity, 0.0],
    }


class PhysicalGraspSettleTests(unittest.TestCase):
    def test_physical_close_allows_targetless_discovery_request(self) -> None:
        response = {
            "success": True,
            "phase": "holding",
            "target_body_path": "/World/TrashSet/discovered",
        }
        with patch.object(
            execute_a1z_plan,
            "_send_control",
            return_value=response,
        ) as send:
            result = execute_a1z_plan._grasp_close_physical(
                Namespace(),
                timeout_s=10.0,
                controller_profile={"controller_profile_id": "test"},
            )
        self.assertEqual(result, response)
        self.assertEqual(send.call_args.args[1], "grasp_close_v2")
        self.assertNotIn("target_body_path", send.call_args.args[2])

    def test_acceptance_uses_discovery_time_pose_as_lift_baseline(self) -> None:
        release = {
            "success": True,
            "phase": "released",
            "bilateral_contact": False,
            "constraint_count_delta": 0,
            "attached_object_path": None,
            "attachment_joint_path": None,
        }
        result = execute_a1z_plan._evaluate_physical_execution(
            target_before={},
            close={
                "success": True,
                "phase": "holding",
                "initial_target_world_translation_m": [0.0, 0.0, 0.02],
                "constraint_count_delta": 0,
            },
            lift_samples=[
                {
                    "phase": "holding",
                    "bilateral_contact": True,
                    "target_world_translation_m": [0.0, 0.0, 0.06],
                    "constraint_count_delta": 0,
                }
            ],
            retreat_samples=[],
            release=release,
            release_samples=[release],
            minimum_lift_m=0.03,
            minimum_hold_ratio=0.8,
        )
        self.assertTrue(result["passed"])
        self.assertAlmostEqual(result["metrics"]["lift_m"], 0.04)

    def test_requires_three_consecutive_stable_samples(self) -> None:
        samples = [
            status(wrist_velocity=0.21),
            status(wrist_velocity=0.19),
            status(wrist_velocity=0.18),
            status(wrist_velocity=0.17),
        ]
        with (
            patch.object(execute_a1z_plan, "_status", side_effect=samples) as query,
            patch.object(execute_a1z_plan.time, "sleep"),
        ):
            result = execute_a1z_plan._wait_for_arm_target(
                Namespace(),
                TARGET,
                timeout_s=1.0,
                require_grasp_settle=True,
            )
        self.assertEqual(query.call_count, 4)
        self.assertEqual(result["grasp_settle_summary"]["stable_samples"], 3)

    def test_non_grasp_move_remains_position_only(self) -> None:
        with patch.object(
            execute_a1z_plan,
            "_status",
            return_value={"pos_deg": [0.0] * 6},
        ) as query:
            result = execute_a1z_plan._wait_for_arm_target(
                Namespace(),
                TARGET,
                timeout_s=1.0,
            )
        self.assertEqual(query.call_count, 1)
        self.assertIn("target_error_summary", result)
        self.assertNotIn("grasp_settle_summary", result)


if __name__ == "__main__":
    unittest.main()
