#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import unittest


A1Z_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = A1Z_ROOT / "a1z_ext" / "robots" / "server.py"
MOCK_PATH = A1Z_ROOT / "a1z_ext" / "robots" / "mock_robot.py"
CLI_PATH = A1Z_ROOT / "tools" / "a1zctl"


def _class_methods(path: Path, class_name: str) -> tuple[str, dict[str, ast.FunctionDef]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return source, {
        node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)
    }


class PhysicalGraspProtocolV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server_source, cls.server_methods = _class_methods(SERVER_PATH, "RobotServer")
        cls.mock_source, cls.mock_methods = _class_methods(MOCK_PATH, "MockArmRobot")
        cls.cli_source = CLI_PATH.read_text(encoding="utf-8")

    @staticmethod
    def _method_source(source: str, methods: dict[str, ast.FunctionDef], name: str) -> str:
        return ast.get_source_segment(source, methods[name]) or ""

    def test_server_exposes_versioned_close_release_and_status_commands(self) -> None:
        for command in ("grasp_close_v2", "grasp_release_v2", "grasp_status_v2"):
            self.assertIn(f'"{command}"', self.server_source)
        close_source = self._method_source(
            self.server_source, self.server_methods, "_cmd_grasp_close_v2"
        )
        self.assertNotIn("target_body_path", close_source)
        self.assertIn("controller_profile=controller_profile", close_source)

    def test_v2_protocol_does_not_encode_attachment_success(self) -> None:
        method_names = (
            "_cmd_grasp_close_v2",
            "_cmd_grasp_release_v2",
            "_cmd_grasp_status_v2",
        )
        source = "\n".join(
            self._method_source(self.server_source, self.server_methods, name)
            for name in method_names
        )
        self.assertNotIn("grasp_close_and_attach", source)
        self.assertNotIn("release_attached_object", source)

    def test_mock_contract_is_explicitly_simulated_and_constraint_free(self) -> None:
        idle_source = self._method_source(
            self.mock_source, self.mock_methods, "_idle_physical_grasp_state"
        )
        self.assertIn('"contract_version": 2', idle_source)
        self.assertIn('"simulated": True', idle_source)
        self.assertIn('"constraint_count_delta": 0', idle_source)
        self.assertIn('"attachment_joint_path": None', idle_source)
        self.assertIn('"attached_object_path": None', idle_source)

    def test_cli_exposes_profile_driven_physical_commands(self) -> None:
        for command in (
            "grasp-close-physical",
            "grasp-release-physical",
            "grasp-status-physical",
        ):
            self.assertIn(f'"{command}"', self.cli_source)
        self.assertIn('"--controller-profile"', self.cli_source)
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "grasp-close-physical", "--help"],
            cwd=A1Z_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("--controller-profile", result.stdout)
        self.assertNotIn("--target-body-path", result.stdout)


if __name__ == "__main__":
    unittest.main()
