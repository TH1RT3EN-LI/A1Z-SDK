from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from a1z_ext.config import get_arm_motion_speed_limits, validate_arm_motion_speed


ROOT = Path(__file__).resolve().parents[1]


class ArmSpeedLimitTests(TestCase):
    def test_shared_limits_allow_slow_and_faster_smooth_motion(self) -> None:
        limits = get_arm_motion_speed_limits()
        self.assertEqual(limits.minimum, 0.05)
        self.assertEqual(limits.default, 0.5)
        self.assertEqual(limits.maximum, 1.5)
        self.assertEqual(validate_arm_motion_speed(0.05), 0.05)
        self.assertEqual(validate_arm_motion_speed(1.0), 1.0)
        self.assertEqual(validate_arm_motion_speed(1.5), 1.5)

    def test_out_of_range_speed_is_rejected(self) -> None:
        for speed in (0.0, 0.049, 1.501, 20.0):
            with self.subTest(speed=speed):
                with self.assertRaisesRegex(ValueError, r"\[0.05, 1.5\]"):
                    validate_arm_motion_speed(speed)

    def test_all_motion_entry_points_use_the_shared_policy(self) -> None:
        isaac_source = (
            ROOT / "a1z_ext" / "robots" / "isaacsim_robot.py"
        ).read_text(encoding="utf-8")
        server_source = (
            ROOT / "a1z_ext" / "robots" / "server.py"
        ).read_text(encoding="utf-8")
        executor_source = (
            ROOT / "scripts" / "execute_a1z_plan.py"
        ).read_text(encoding="utf-8")
        pipeline_source = (
            ROOT / "scripts" / "run_pick_pipeline.py"
        ).read_text(encoding="utf-8")
        self.assertIn("self._arm_motion_speed_limits.validate(speed)", isaac_source)
        self.assertIn("validate_arm_motion_speed(", server_source)
        self.assertIn("type=validate_arm_motion_speed", executor_source)
        self.assertIn('"--arm-speed"', pipeline_source)
