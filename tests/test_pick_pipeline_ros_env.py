from __future__ import annotations

from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class PickPipelineRosEnvironmentTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "scripts" / "run_pick_pipeline.py").read_text(
            encoding="utf-8"
        )

    def test_numeric_docker_user_gets_writable_home(self) -> None:
        self.assertIn('f"HOME=/tmp/a1z-home-{host_uid}"', self.source)

    def test_ros_setup_is_sourced_with_nounset_disabled(self) -> None:
        capture_start = self.source.index('"set -eo pipefail; "')
        capture_end = self.source.index(
            '"python3 /workspace/A1Z/scripts/capture_rgbd.py "', capture_start
        )
        capture_shell = self.source[capture_start:capture_end]

        disable_nounset = capture_shell.index('"set +u; "')
        ros_setup = capture_shell.index(
            '"source /opt/ros/humble/setup.bash; "'
        )
        overlay_setup = capture_shell.index(
            '"source /workspace/A1Z/ros2_ws/install/setup.bash; "'
        )
        restore_nounset = capture_shell.index('"set -u; "')

        self.assertLess(disable_nounset, ros_setup)
        self.assertLess(ros_setup, overlay_setup)
        self.assertLess(overlay_setup, restore_nounset)
