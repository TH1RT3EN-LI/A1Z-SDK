"""Shared assembly helpers for the non-grasping open-vocabulary pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from a1z_ext.interfaces.observation import RGBDObservation
from a1z_ext.interfaces.schemas import PipelineBundle, write_json
from a1z_ext.perception.grounding import ground_object_candidates
from a1z_ext.perception.object_3d import recover_object_descriptors
from a1z_ext.perception.segmentation import segment_candidates
from a1z_ext.perception.task_interpreter import interpret_text_instruction
from a1z_ext.runtime.frame_sources.base import RGBDFrameCapture


def _update_mask_depth_statistics(mask_candidates: list, depth_m: np.ndarray) -> None:
    valid_depth = np.isfinite(depth_m) & (depth_m > 0.0)
    for candidate in mask_candidates:
        mask = np.load(Path(candidate.mask_path)).astype(bool)
        total = int(mask.sum())
        if total <= 0:
            candidate.depth_valid_ratio = 0.0
            continue
        candidate.depth_valid_ratio = float((valid_depth & mask).sum()) / float(total)


def run_pipeline_from_frame_capture(
    *,
    instruction: str,
    capture: RGBDFrameCapture,
    output_dir: str | Path,
) -> PipelineBundle:
    """Build the non-grasping bundle from a single RGB-D observation."""
    capture.validate()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    observation = capture.observation
    rgb = capture.rgb
    depth_m = capture.depth_m
    intrinsics = observation.intrinsics_dict()
    extrinsic_camera_to_target = observation.extrinsic_matrix()

    task = interpret_text_instruction(instruction)
    image_shape = (int(rgb.shape[0]), int(rgb.shape[1]))
    grounding = ground_object_candidates(
        task,
        image_shape,
        rgb=rgb,
        frame_id=observation.camera_frame_id,
    )
    masks = segment_candidates(image_shape, grounding, output_dir=output_root / "masks")
    _update_mask_depth_statistics(masks, depth_m)
    objects = recover_object_descriptors(
        depth_m=depth_m,
        intrinsics=intrinsics,
        extrinsic_camera_to_base=extrinsic_camera_to_target,
        mask_candidates=masks,
        frame_id=observation.target_frame_id,
    )

    bundle = PipelineBundle(
        task=task,
        grounding_candidates=grounding,
        mask_candidates=masks,
        object_descriptors=objects,
    )

    observation.rgb_path = str(output_root / "rgb.npy")
    observation.depth_path = str(output_root / "depth_m.npy")

    np.save(output_root / "rgb.npy", rgb)
    np.save(output_root / "depth_m.npy", depth_m)
    np.save(output_root / "extrinsic_camera_to_target.npy", extrinsic_camera_to_target)
    np.save(output_root / "extrinsic_camera_to_base.npy", extrinsic_camera_to_target)
    with (output_root / "intrinsics.json").open("w", encoding="utf-8") as fh:
        json.dump(intrinsics, fh, ensure_ascii=True, indent=2)
    write_json(output_root / "observation.json", observation)
    write_json(output_root / "bundle.json", bundle)
    if capture.source_info:
        with (output_root / "observation_metadata.json").open("w", encoding="utf-8") as fh:
            json.dump(capture.source_info, fh, ensure_ascii=True, indent=2)
    return bundle


def run_pipeline_from_observation(
    *,
    instruction: str,
    rgb: np.ndarray,
    depth_m: np.ndarray,
    intrinsics: dict[str, float],
    extrinsic_camera_to_base: np.ndarray,
    output_dir: str | Path,
    observation_metadata: dict[str, Any] | None = None,
) -> PipelineBundle:
    """Backward-compatible wrapper around the frame-capture entrypoint."""
    metadata = dict(observation_metadata or {})
    observation = RGBDObservation.create(
        source_backend=str(metadata.get("source_backend", "unknown")),
        width=int(rgb.shape[1]),
        height=int(rgb.shape[0]),
        camera_frame_id=str(metadata.get("camera_frame_id", "camera_color_frame")),
        target_frame_id=str(metadata.get("target_frame_id", "robot_base_frame")),
        intrinsics=intrinsics,
        extrinsic_camera_to_target=extrinsic_camera_to_base,
        calibration_version=str(metadata.get("calibration_version", "unknown")),
        sensor_model=str(metadata.get("sensor_model", "unknown")),
        scene_context={
            key: value
            for key, value in metadata.items()
            if key
            not in {"source_backend", "camera_frame_id", "target_frame_id", "calibration_version", "sensor_model"}
        },
    )
    capture = RGBDFrameCapture(
        observation=observation,
        rgb=rgb,
        depth_m=depth_m,
        source_info=metadata,
    )
    return run_pipeline_from_frame_capture(
        instruction=instruction,
        capture=capture,
        output_dir=output_dir,
    )
