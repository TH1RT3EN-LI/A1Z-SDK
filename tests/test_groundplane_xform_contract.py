from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
IMPORT_SCRIPT = ROOT / "scripts" / "import_a1z_g1z_to_usd.py"


class GroundPlaneXformContractTests(TestCase):
    def test_translate_op_is_authored_before_scale_op(self) -> None:
        tree = ast.parse(IMPORT_SCRIPT.read_text(encoding="utf-8"))
        configure_world_stage = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "configure_world_stage"
        )

        calls: dict[str, int] = {}
        for node in ast.walk(configure_world_stage):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if not isinstance(owner, ast.Name) or owner.id != "ground":
                continue
            if node.func.attr in {"AddTranslateOp", "AddScaleOp"}:
                calls[node.func.attr] = node.lineno

        self.assertLess(calls["AddTranslateOp"], calls["AddScaleOp"])
