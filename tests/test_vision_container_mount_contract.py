from __future__ import annotations

import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VisionContainerMountContractTests(unittest.TestCase):
    def test_ensure_script_repairs_stale_workspace_without_losing_environment(self) -> None:
        path = ROOT / "scripts" / "ensure_a1z_vision_container.sh"
        source = path.read_text(encoding="utf-8")

        self.assertTrue(os.access(path, os.X_OK))
        self.assertIn('WORKSPACE_DESTINATION="/workspace/A1Z"', source)
        self.assertIn("{{range .Mounts}}", source)
        self.assertIn('docker commit "$VISION_CONTAINER_NAME"', source)
        self.assertIn('docker rename "$VISION_CONTAINER_NAME" "$backup_name"', source)
        self.assertIn('-v "$expected_source:$WORKSPACE_DESTINATION"', source)
        self.assertIn("trap rollback ERR", source)

    def test_ros_to_vision_pipelines_validate_shared_capture(self) -> None:
        anygrasp = (
            ROOT / "scripts" / "run_target_mask_to_anygrasp_from_ros.sh"
        ).read_text(encoding="utf-8")
        target_mask = (
            ROOT / "scripts" / "run_target_mask_pipeline_from_ros.sh"
        ).read_text(encoding="utf-8")
        grconvnet = (
            ROOT / "scripts" / "run_target_mask_to_grconvnet_from_ros.sh"
        ).read_text(encoding="utf-8")

        for source in (anygrasp, target_mask, grconvnet):
            self.assertIn("ensure_a1z_vision_container.sh", source)
            self.assertIn('docker exec "$VISION_CONTAINER_NAME" test -f', source)

    def test_create_entrypoint_validates_existing_container_before_build(self) -> None:
        source = (
            ROOT / "scripts" / "create_a1z_vision_gpu_container.sh"
        ).read_text(encoding="utf-8")
        existing_check = source.index('docker inspect "$VISION_CONTAINER_NAME"')
        ensure_call = source.index("ensure_a1z_vision_container.sh")
        build_call = source.index("docker build")
        self.assertLess(existing_check, ensure_call)
        self.assertLess(ensure_call, build_call)


if __name__ == "__main__":
    unittest.main()
