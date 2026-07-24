"""End-to-end target mask selection from instruction plus image input."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Any

from a1z_ext.llm import LLMProviderConfig
from a1z_ext.runtime.image_input import ResolvedImageInput, load_env_file, resolve_image_input

from .automatic_masks import AutomaticMaskBundle, generate_automatic_masks
from .mask_selection import SelectedMaskResult, select_mask_with_vlm


@dataclass(frozen=True, slots=True)
class TargetMaskPipelineResult:
    instruction: str
    image_input: dict[str, Any]
    automatic_mask_summary_path: str
    selection_json_path: str
    selected_mask: dict[str, Any] | None
    direct_grasp_recommended: bool
    target_found: bool
    selected_mask_index: int
    confidence: float
    reason: str
    mask_quality: dict[str, Any]
    refinement_attempted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_llm_config_from_env(*, provider: str | None, max_tokens: int) -> LLMProviderConfig:
    base = LLMProviderConfig.from_env()
    if provider:
        return LLMProviderConfig.for_provider(
            provider,
            model=os.environ.get("A1Z_VLM_MODEL") or None,
            base_url=os.environ.get("A1Z_VLM_BASE_URL") or None,
            api_key_env=os.environ.get("A1Z_VLM_API_KEY_ENV") or None,
            timeout_s=float(os.environ.get("A1Z_VLM_TIMEOUT_S", str(base.timeout_s))),
            max_tokens=max_tokens,
            temperature=float(os.environ.get("A1Z_VLM_TEMPERATURE", str(base.temperature))),
        )
    return LLMProviderConfig(
        provider=base.provider,
        model=base.model,
        base_url=base.base_url,
        api_key_env=base.api_key_env,
        timeout_s=base.timeout_s,
        max_tokens=max_tokens,
        temperature=base.temperature,
    )


def evaluate_selected_mask_quality(
    selected_mask: dict[str, Any] | None,
    *,
    minimum_area_px: int = 256,
) -> dict[str, Any]:
    """Return the grasp-readiness gate for a VLM-selected segmentation mask."""
    required_area = max(1, int(minimum_area_px))
    area = int((selected_mask or {}).get("area", 0) or 0)
    usable = area >= required_area
    if selected_mask is None:
        reason = "target selection did not produce a mask"
    elif not usable:
        reason = (
            f"selected mask is too small for reliable grasping: "
            f"{area} px, minimum {required_area} px"
        )
    else:
        reason = "selected mask passed grasp input quality checks"
    return {
        "area_px": area,
        "minimum_area_px": required_area,
        "usable_for_grasp": usable,
        "reason": reason,
    }


def run_target_mask_pipeline(
    *,
    instruction: str,
    image_arg: str = "",
    ros_topic: str = "",
    ros_timeout_s: float = 10.0,
    capture_path_arg: str = "",
    output_dir: str | Path,
    env_file: str | Path | None = None,
    provider: str | None = None,
    image_detail: str = "high",
    vlm_max_tokens: int = 600,
    sam_checkpoint: str | Path,
    sam_config: str = "configs/sam2.1/sam2.1_hiera_s.yaml",
    points_per_side: int = 32,
    points_per_batch: int = 64,
    pred_iou_thresh: float = 0.8,
    stability_score_thresh: float = 0.95,
    stability_score_offset: float = 1.0,
    box_nms_thresh: float = 0.7,
    crop_n_layers: int = 0,
    crop_nms_thresh: float = 0.7,
    crop_overlap_ratio: float = 512 / 1500,
    crop_n_points_downscale_factor: int = 1,
    min_mask_region_area: int = 0,
    max_preview_masks: int | None = 24,
    max_area_ratio: float = 0.7,
    max_boundary_touches: int = 2,
    minimum_selected_mask_area_px: int = 256,
    refine_small_masks: bool = True,
) -> TargetMaskPipelineResult:
    if env_file is not None:
        load_env_file(env_file)

    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    automatic_dir = output_root / "automatic_masks"
    selection_dir = output_root / "selection"

    resolved_image: ResolvedImageInput = resolve_image_input(
        image_arg=image_arg,
        ros_topic=ros_topic,
        ros_timeout_s=ros_timeout_s,
        capture_path_arg=capture_path_arg,
        default_capture_path=output_root / "captured_input.png",
    )

    automatic_bundle: AutomaticMaskBundle = generate_automatic_masks(
        image_path=resolved_image.image_path,
        output_dir=automatic_dir,
        sam_checkpoint=sam_checkpoint,
        sam_config=sam_config,
        points_per_side=points_per_side,
        points_per_batch=points_per_batch,
        pred_iou_thresh=pred_iou_thresh,
        stability_score_thresh=stability_score_thresh,
        stability_score_offset=stability_score_offset,
        box_nms_thresh=box_nms_thresh,
        crop_n_layers=crop_n_layers,
        crop_nms_thresh=crop_nms_thresh,
        crop_overlap_ratio=crop_overlap_ratio,
        crop_n_points_downscale_factor=crop_n_points_downscale_factor,
        min_mask_region_area=min_mask_region_area,
        max_preview_masks=max_preview_masks,
    )

    llm_config = _build_llm_config_from_env(provider=provider, max_tokens=vlm_max_tokens)
    selection_result: SelectedMaskResult = select_mask_with_vlm(
        instruction=instruction,
        automatic_mask_bundle=automatic_bundle,
        output_dir=selection_dir,
        llm_config=llm_config,
        image_detail=image_detail,
        max_area_ratio=max_area_ratio,
        max_boundary_touches=max_boundary_touches,
    )
    mask_quality = evaluate_selected_mask_quality(
        selection_result.selected_mask,
        minimum_area_px=minimum_selected_mask_area_px,
    )
    refinement_attempted = False

    if (
        refine_small_masks
        and selection_result.decision.target_found
        and not mask_quality["usable_for_grasp"]
    ):
        refinement_attempted = True
        initial_selection = selection_dir / "selection.json"
        if initial_selection.is_file():
            shutil.copy2(initial_selection, selection_dir / "selection_initial.json")

        refined_dir = output_root / "automatic_masks_refined"
        automatic_bundle = generate_automatic_masks(
            image_path=resolved_image.image_path,
            output_dir=refined_dir,
            sam_checkpoint=sam_checkpoint,
            sam_config=sam_config,
            points_per_side=max(int(points_per_side), 64),
            points_per_batch=points_per_batch,
            pred_iou_thresh=min(float(pred_iou_thresh), 0.75),
            stability_score_thresh=min(float(stability_score_thresh), 0.9),
            stability_score_offset=stability_score_offset,
            box_nms_thresh=min(float(box_nms_thresh), 0.65),
            crop_n_layers=max(int(crop_n_layers), 1),
            crop_nms_thresh=crop_nms_thresh,
            crop_overlap_ratio=crop_overlap_ratio,
            crop_n_points_downscale_factor=max(
                int(crop_n_points_downscale_factor),
                2,
            ),
            min_mask_region_area=0,
            max_preview_masks=(
                None
                if max_preview_masks is None
                else max(int(max_preview_masks), 48)
            ),
        )
        selection_result = select_mask_with_vlm(
            instruction=instruction,
            automatic_mask_bundle=automatic_bundle,
            output_dir=selection_dir,
            llm_config=llm_config,
            image_detail=image_detail,
            max_area_ratio=max_area_ratio,
            max_boundary_touches=max_boundary_touches,
        )
        mask_quality = evaluate_selected_mask_quality(
            selection_result.selected_mask,
            minimum_area_px=minimum_selected_mask_area_px,
        )
        automatic_dir = refined_dir

    result = TargetMaskPipelineResult(
        instruction=instruction,
        image_input={
            "image_path": str(resolved_image.image_path),
            "width": int(resolved_image.width),
            "height": int(resolved_image.height),
            "source_metadata": resolved_image.source_metadata,
        },
        automatic_mask_summary_path=str(automatic_dir / "summary.json"),
        selection_json_path=selection_result.selection_json_path,
        selected_mask=selection_result.selected_mask,
        direct_grasp_recommended=(
            selection_result.decision.direct_grasp_recommended
            and bool(mask_quality["usable_for_grasp"])
        ),
        target_found=selection_result.decision.target_found,
        selected_mask_index=selection_result.decision.selected_mask_index,
        confidence=selection_result.decision.confidence,
        reason=selection_result.decision.reason,
        mask_quality=mask_quality,
        refinement_attempted=refinement_attempted,
    )
    (output_root / "pipeline_result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return result
