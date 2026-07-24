from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from a1z_ext.perception.target_mask_pipeline import (
    evaluate_selected_mask_quality,
    run_target_mask_pipeline,
)


ROOT = Path(__file__).resolve().parents[1]


class TargetMaskPipelineSafetyTest(unittest.TestCase):
    def test_small_mask_is_not_grasp_ready(self) -> None:
        quality = evaluate_selected_mask_quality(
            {"area": 97},
            minimum_area_px=256,
        )
        self.assertFalse(quality["usable_for_grasp"])
        self.assertIn("97 px, minimum 256 px", quality["reason"])

    def test_refinement_and_downstream_short_circuit_are_wired(self) -> None:
        pipeline = (
            ROOT / "a1z_ext" / "perception" / "target_mask_pipeline.py"
        ).read_text(encoding="utf-8")
        shell = (
            ROOT / "scripts" / "run_target_mask_to_anygrasp_from_ros.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('refined_dir = output_root / "automatic_masks_refined"', pipeline)
        self.assertIn("points_per_side=max(int(points_per_side), 64)", pipeline)
        self.assertIn("crop_n_layers=max(int(crop_n_layers), 1)", pipeline)
        validation = shell.index("AnyGrasp produced no executable grasp candidates")
        adapter = shell.index("run_anygrasp_adapter_in_container.sh")
        self.assertLess(validation, adapter)
        self.assertIn("archive_previous_output", shell)
        self.assertIn("_previous_runs", shell)

    def test_small_mask_triggers_dense_refinement(self) -> None:
        first = SimpleNamespace(
            selected_mask={"area": 97},
            selection_json_path="/tmp/selection.json",
            decision=SimpleNamespace(
                target_found=True,
                selected_mask_index=4,
                confidence=0.92,
                direct_grasp_recommended=True,
                reason="partial marker",
            ),
        )
        refined = SimpleNamespace(
            selected_mask={"area": 640},
            selection_json_path="/tmp/selection.json",
            decision=SimpleNamespace(
                target_found=True,
                selected_mask_index=12,
                confidence=0.96,
                direct_grasp_recommended=True,
                reason="whole marker",
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "a1z_ext.perception.target_mask_pipeline.resolve_image_input",
                    return_value=SimpleNamespace(
                        image_path=Path("/tmp/color.png"),
                        width=320,
                        height=240,
                        source_metadata={"source": "test"},
                    ),
                ),
                patch(
                    "a1z_ext.perception.target_mask_pipeline.generate_automatic_masks",
                    side_effect=[SimpleNamespace(), SimpleNamespace()],
                ) as generate,
                patch(
                    "a1z_ext.perception.target_mask_pipeline.select_mask_with_vlm",
                    side_effect=[first, refined],
                ),
                patch(
                    "a1z_ext.perception.target_mask_pipeline._build_llm_config_from_env",
                    return_value=SimpleNamespace(),
                ),
            ):
                result = run_target_mask_pipeline(
                    instruction="抓取白板笔",
                    output_dir=temp_dir,
                    sam_checkpoint="/tmp/sam.pt",
                )

        self.assertTrue(result.refinement_attempted)
        self.assertTrue(result.mask_quality["usable_for_grasp"])
        self.assertEqual(result.selected_mask_index, 12)
        self.assertEqual(generate.call_count, 2)
        refined_call = generate.call_args_list[1].kwargs
        self.assertEqual(refined_call["points_per_side"], 64)
        self.assertEqual(refined_call["crop_n_layers"], 1)


if __name__ == "__main__":
    unittest.main()
