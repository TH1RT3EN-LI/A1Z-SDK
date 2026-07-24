from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "scripts" / "execute_a1z_plan.py"


class PhysicalGraspSettleContractTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = EXECUTOR.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.functions = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def _function_source(self, name: str) -> str:
        return ast.get_source_segment(self.source, self.functions[name]) or ""

    def test_grasp_approach_requires_consecutive_stable_samples(self) -> None:
        source = self._function_source("_wait_for_arm_target")
        self.assertIn("require_grasp_settle", source)
        self.assertIn("stable_samples = stable_samples + 1 if grasp_ready else 0", source)
        self.assertIn("GRASP_SETTLE_REQUIRED_SAMPLES", source)
        self.assertIn("GRASP_SETTLE_MAX_LEAD_VEL_RAD_S", source)
        self.assertIn("GRASP_SETTLE_MAX_WRIST_VEL_RAD_S", source)

    def test_only_physical_approach_enables_grasp_settle_gate(self) -> None:
        source = self._function_source("main")
        self.assertIn('step["type"] == "approach" and grasp_mode == "physical_v2"', source)
        self.assertIn("require_grasp_settle=(", source)

    def test_settle_diagnostics_are_recorded_in_status(self) -> None:
        source = self._function_source("_wait_for_arm_target")
        self.assertIn('status["grasp_settle_summary"]', source)
        self.assertIn('"stable_samples": stable_samples', source)
