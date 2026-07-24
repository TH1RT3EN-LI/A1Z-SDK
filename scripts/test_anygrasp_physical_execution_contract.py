#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import unittest


A1Z_ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = A1Z_ROOT / "scripts" / "execute_a1z_plan.py"
PIPELINE = A1Z_ROOT / "scripts" / "run_target_mask_to_anygrasp_pick_attempt.sh"


class AnyGraspPhysicalExecutionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executor_source = EXECUTOR.read_text(encoding="utf-8")
        cls.executor_tree = ast.parse(cls.executor_source)
        cls.pipeline_source = PIPELINE.read_text(encoding="utf-8")

    def test_executor_uses_versioned_physical_commands(self) -> None:
        self.assertIn('"grasp_close_v2"', self.executor_source)
        self.assertIn('"grasp_release_v2"', self.executor_source)
        self.assertIn('grasp_mode == "physical_v2"', self.executor_source)
        self.assertIn('"controller_profile": controller_profile', self.executor_source)
        self.assertIn('"grasp_status_v2"', self.executor_source)
        self.assertIn('"prim_debug"', self.executor_source)
        self.assertIn('"physical_v2_acceptance"', self.executor_source)
        self.assertIn('speed=float(args.arm_speed)', self.executor_source)

    def test_executor_rejects_hidden_constraint_fallback(self) -> None:
        self.assertIn('get("constraint_count_delta", -1)', self.executor_source)
        self.assertIn("physical_grasp_created_constraint", self.executor_source)
        physical_function = next(
            node
            for node in self.executor_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_grasp_close_physical"
        )
        source = ast.get_source_segment(self.executor_source, physical_function) or ""
        self.assertNotIn("grasp_attach", source)

    def test_pipeline_uses_contact_discovery_and_versioned_profile(self) -> None:
        self.assertIn('--grasp-mode <physical_v2|sim_contact_attach|raw_gripper>', self.pipeline_source)
        self.assertIn('policy.pop("target_body_path", None)', self.pipeline_source)
        self.assertIn('policy.pop("target_prim_path", None)', self.pipeline_source)
        self.assertIn('policy["target_discovery_mode"] = "bilateral_contact"', self.pipeline_source)
        self.assertIn('policy["controller_profile"] = profile', self.pipeline_source)
        self.assertNotIn("physical_v2 requires --resolve-target-prim", self.pipeline_source)
        self.assertIn("AUTO_RESOLVE_TARGET_PRIM=0", self.pipeline_source)
        self.assertIn('policy["release_after_retreat"] = True', self.pipeline_source)
        self.assertIn('policy["hold_after_lift_s"] = 1.0', self.pipeline_source)

    def test_pipeline_shell_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(PIPELINE)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
