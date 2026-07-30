from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RosSensorQosContractTest(unittest.TestCase):
    def test_d405_consumers_use_sensor_data_qos(self) -> None:
        paths = (
            ROOT / "a1z_ext" / "runtime" / "frame_sources" / "ros_rgbd.py",
            ROOT / "a1z_ext" / "runtime" / "image_input.py",
            ROOT
            / "ros2_ws"
            / "src"
            / "a1z_d405"
            / "a1z_d405"
            / "console_bridge.py",
        )
        for path in paths:
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertIn("ReliabilityPolicy.BEST_EFFORT", source)
                self.assertIn("DurabilityPolicy.VOLATILE", source)
                self.assertNotIn("ReliabilityPolicy.RELIABLE", source)


if __name__ == "__main__":
    unittest.main()
