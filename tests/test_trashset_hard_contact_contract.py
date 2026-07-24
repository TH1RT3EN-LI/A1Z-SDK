from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "place_trash_assets_in_world.py"
OVERLAY = ROOT / "build" / "scenes" / "A1Z_G1Z_world_trashset.usda"


def _literal_constants(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            values[target.id] = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            continue
    return values


class TrashSetHardContactContractTests(TestCase):
    def test_generator_defaults_disable_compliant_contact(self) -> None:
        constants = _literal_constants(GENERATOR)

        self.assertEqual(constants["DEFAULT_TRASH_COMPLIANT_STIFFNESS"], 0.0)
        self.assertEqual(constants["DEFAULT_TRASH_COMPLIANT_DAMPING"], 0.0)
        self.assertTrue(constants["DEFAULT_TRASH_ENABLE_CCD"])
        self.assertEqual(constants["DEFAULT_TRASH_SOLVER_POSITION_ITERS"], 64)
        self.assertEqual(constants["DEFAULT_TRASH_SOLVER_VELOCITY_ITERS"], 16)

    def test_baked_overlay_uses_hard_contact_for_every_trash_body(self) -> None:
        overlay = OVERLAY.read_text(encoding="utf-8")

        self.assertEqual(
            overlay.count("float physxMaterial:compliantContactStiffness = 0"),
            5,
        )
        self.assertEqual(
            overlay.count("float physxMaterial:compliantContactDamping = 0"),
            5,
        )
        self.assertEqual(overlay.count("bool physxRigidBody:enableCCD = 1"), 5)
        self.assertEqual(
            overlay.count("int physxRigidBody:solverPositionIterationCount = 64"),
            5,
        )
        self.assertEqual(
            overlay.count("int physxRigidBody:solverVelocityIterationCount = 16"),
            5,
        )

    def test_contact_offsets_still_create_constraints_before_overlap(self) -> None:
        overlay = OVERLAY.read_text(encoding="utf-8")

        self.assertEqual(overlay.count("float physxCollision:contactOffset = 0.002"), 6)
        self.assertEqual(overlay.count("float physxCollision:restOffset = 0.001"), 6)
