"""Perception modules for the open-vocabulary pipeline."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS = {
    "AutomaticMaskBundle": (".automatic_masks", "AutomaticMaskBundle"),
    "AutomaticMaskRecord": (".automatic_masks", "AutomaticMaskRecord"),
    "AnyGraspDetectionResult": (".grasping", "AnyGraspDetectionResult"),
    "AnyGraspPreflightResult": (".grasping", "AnyGraspPreflightResult"),
    "GRConvNetInferenceResult": (".grconvnet", "GRConvNetInferenceResult"),
    "MaskedPointCloudResult": (".grasping", "MaskedPointCloudResult"),
    "SelectedMaskDecision": (".mask_selection", "SelectedMaskDecision"),
    "SelectedMaskResult": (".mask_selection", "SelectedMaskResult"),
    "TargetMaskPipelineResult": (".target_mask_pipeline", "TargetMaskPipelineResult"),
    "build_anygrasp_inputs_from_mask": (".grasping", "build_anygrasp_inputs_from_mask"),
    "check_anygrasp_runtime": (".grasping", "check_anygrasp_runtime"),
    "generate_automatic_masks": (".automatic_masks", "generate_automatic_masks"),
    "load_mask_array": (".grasping", "load_mask_array"),
    "load_rgb_array": (".grasping", "load_rgb_array"),
    "run_anygrasp_detection": (".grasping", "run_anygrasp_detection"),
    "run_grconvnet_inference": (".grconvnet", "run_grconvnet_inference"),
    "select_mask_with_vlm": (".mask_selection", "select_mask_with_vlm"),
    "run_pipeline_from_frame_capture": (".pipeline", "run_pipeline_from_frame_capture"),
    "run_pipeline_from_observation": (".pipeline", "run_pipeline_from_observation"),
    "run_target_mask_pipeline": (".target_mask_pipeline", "run_target_mask_pipeline"),
}

if TYPE_CHECKING:
    from .automatic_masks import AutomaticMaskBundle, AutomaticMaskRecord, generate_automatic_masks
    from .grasping import (
        AnyGraspDetectionResult,
        AnyGraspPreflightResult,
        MaskedPointCloudResult,
        build_anygrasp_inputs_from_mask,
        check_anygrasp_runtime,
        load_mask_array,
        load_rgb_array,
        run_anygrasp_detection,
    )
    from .grconvnet import GRConvNetInferenceResult, run_grconvnet_inference
    from .mask_selection import SelectedMaskDecision, SelectedMaskResult, select_mask_with_vlm
    from .pipeline import run_pipeline_from_frame_capture, run_pipeline_from_observation
    from .target_mask_pipeline import TargetMaskPipelineResult, run_target_mask_pipeline

__all__ = [
    "AutomaticMaskBundle",
    "AutomaticMaskRecord",
    "AnyGraspDetectionResult",
    "AnyGraspPreflightResult",
    "GRConvNetInferenceResult",
    "MaskedPointCloudResult",
    "SelectedMaskDecision",
    "SelectedMaskResult",
    "TargetMaskPipelineResult",
    "build_anygrasp_inputs_from_mask",
    "check_anygrasp_runtime",
    "generate_automatic_masks",
    "load_mask_array",
    "load_rgb_array",
    "run_anygrasp_detection",
    "run_grconvnet_inference",
    "select_mask_with_vlm",
    "run_pipeline_from_frame_capture",
    "run_pipeline_from_observation",
    "run_target_mask_pipeline",
]


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
