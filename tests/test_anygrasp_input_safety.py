from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

import numpy as np

from a1z_ext.perception.grasping import (
    AnyGraspPreflightResult,
    run_anygrasp_detection,
)


def _ready_preflight() -> AnyGraspPreflightResult:
    return AnyGraspPreflightResult(
        ready=True,
        sdk_dir="/tmp/sdk",
        checkpoint_path="/tmp/checkpoint",
        license_dir="/tmp/license",
        feature_id="test",
        configured_license_feature_id="test",
        detector_import_ok=True,
        graspnet_api_import_ok=True,
        checkpoint_exists=True,
        license_dir_exists=True,
        license_cfg_exists=True,
        detector_create_ok=True,
        missing=[],
        notes=[],
        detector_error="",
    )


class AnyGraspInputSafetyTest(unittest.TestCase):
    def test_rejects_tiny_point_cloud_before_sdk_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "a1z_ext.perception.grasping.check_anygrasp_runtime"
            ) as preflight:
                result = run_anygrasp_detection(
                    points=np.zeros((97, 3), dtype=np.float32),
                    colors=np.zeros((97, 3), dtype=np.float32),
                    lims=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
                    output_dir=temp_dir,
                    sdk_dir="/tmp/sdk",
                    checkpoint_path="/tmp/checkpoint",
                    license_dir="/tmp/license",
                    minimum_point_count=256,
                )
            preflight.assert_not_called()
            self.assertFalse(result.ran)
            self.assertEqual(result.grasp_count, 0)
            self.assertIn("97 points, minimum 256", result.error)

    def test_sdk_none_result_becomes_explicit_no_grasp_result(self) -> None:
        class _Detector:
            def get_grasp(self, *args, **kwargs):
                return None, None

        gsnet = ModuleType("gsnet")
        gsnet.create_detector = lambda _config: _Detector()  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "a1z_ext.perception.grasping.check_anygrasp_runtime",
                    return_value=_ready_preflight(),
                ),
                patch.dict(sys.modules, {"gsnet": gsnet}),
            ):
                result = run_anygrasp_detection(
                    points=np.zeros((300, 3), dtype=np.float32),
                    colors=np.zeros((300, 3), dtype=np.float32),
                    lims=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
                    output_dir=temp_dir,
                    sdk_dir="/tmp/sdk",
                    checkpoint_path="/tmp/checkpoint",
                    license_dir="/tmp/license",
                )
            self.assertTrue(result.ran)
            self.assertEqual(result.grasp_count, 0)
            self.assertEqual(result.top_grasps, [])
            self.assertEqual(
                result.error,
                "no grasp detected for selected target mask",
            )
            saved = json.loads(
                (Path(temp_dir) / "anygrasp_result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved["error"], result.error)


if __name__ == "__main__":
    unittest.main()
