from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest import TestCase

import numpy as np

from a1z_ext.robots.position_hold import bounded_position_hold_feedforward


ROOT = Path(__file__).resolve().parents[1]


class PositionHoldGravityCompensationTests(TestCase):
    def test_gravity_and_command_feedforward_are_combined_and_bounded(self) -> None:
        result = bounded_position_hold_feedforward(
            np.array([0.0, -7.672, -4.457]),
            np.array([0.25, -0.5, 1.0]),
            np.array([20.0, 7.8, 5.0]),
        )
        np.testing.assert_allclose(result, [0.25, -7.8, -3.457], atol=1e-12)

    def test_invalid_feedforward_limit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite and positive"):
            bounded_position_hold_feedforward(
                np.zeros(2),
                np.zeros(2),
                np.array([1.0, 0.0]),
            )

    def test_default_profile_enables_rated_torque_limited_compensation(self) -> None:
        defaults = json.loads(
            (ROOT / "a1z_ext" / "config" / "control_defaults.json").read_text(
                encoding="utf-8"
            )
        )
        isaac = defaults["isaacsim"]
        self.assertTrue(isaac["position_hold_gravity_compensation"])
        self.assertEqual(
            isaac["position_hold_feedforward_limit_nm"],
            defaults["arm_rated_torque_nm"],
        )

    def test_isaac_position_command_carries_gravity_feedforward(self) -> None:
        source = (
            ROOT / "a1z_ext" / "robots" / "isaacsim_robot.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_apply_control_action"
        )
        method_source = ast.get_source_segment(source, method) or ""
        self.assertIn("bounded_position_hold_feedforward(", method_source)
        self.assertIn("joint_positions=pos_target.astype(np.float32)", method_source)
        self.assertIn("joint_efforts=arm_feedforward.astype(np.float32)", method_source)

    def test_arm_settle_requires_three_consecutive_precision_samples(self) -> None:
        source = (
            ROOT / "a1z_ext" / "robots" / "isaacsim_robot.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_ARM_SETTLE_TOL_RAD = np.deg2rad(0.50)", source)
        self.assertIn("_ARM_SETTLE_REQUIRED_SAMPLES = 3", source)
        self.assertIn("_ARM_FORCE_SNAP_TOL_RAD = np.deg2rad(0.75)", source)
        self.assertIn("_ARM_LEAD_JOINT_SNAP_TOL_RAD = np.deg2rad(0.75)", source)
        self.assertIn("_ARM_WRIST_JOINT_SNAP_TOL_RAD = np.deg2rad(3.0)", source)
        tree = ast.parse(source)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_wait_for_arm_target"
        )
        method_source = ast.get_source_segment(source, method) or ""
        self.assertIn("stable_samples += 1", method_source)
        self.assertIn("stable_samples = 0", method_source)
