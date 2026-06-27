"""Grounding stub for the initial docker-runnable data loop."""

from __future__ import annotations

import numpy as np

from a1z_ext.interfaces.schemas import GroundingCandidate, TaskSpec


def _infer_base_box(
    image_shape: tuple[int, int],
    *,
    rgb: np.ndarray | None = None,
) -> list[int]:
    height, width = image_shape
    if rgb is not None:
        if rgb.ndim != 3 or rgb.shape[0] != height or rgb.shape[1] != width or rgb.shape[2] < 3:
            raise ValueError(f"rgb shape must match image_shape and have 3 channels, got {rgb.shape}")
        rgb_int = rgb[:, :, :3].astype(np.int16)
        red_mask = (rgb_int[:, :, 0] > rgb_int[:, :, 1] + 20) & (rgb_int[:, :, 0] > rgb_int[:, :, 2] + 20)
        if int(red_mask.sum()) >= max(64, (height * width) // 2000):
            ys, xs = np.where(red_mask)
            x0 = max(0, int(xs.min()) - max(4, width // 64))
            y0 = max(0, int(ys.min()) - max(4, height // 64))
            x1 = min(width - 1, int(xs.max()) + max(4, width // 64))
            y1 = min(height - 1, int(ys.max()) + max(4, height // 64))
            return [x0, y0, x1, y1]

    center_x = width // 2
    center_y = height // 2
    return [
        max(0, center_x - width // 8),
        max(0, center_y - height // 8),
        min(width - 1, center_x + width // 8),
        min(height - 1, center_y + height // 8),
    ]


def ground_object_candidates(
    task: TaskSpec,
    image_shape: tuple[int, int],
    *,
    rgb: np.ndarray | None = None,
    max_candidates: int = 3,
    frame_id: str = "camera_color_frame",
) -> list[GroundingCandidate]:
    height, width = image_shape
    if height <= 0 or width <= 0:
        raise ValueError("image_shape must be positive")

    base_box = _infer_base_box(image_shape, rgb=rgb)
    center_x = (base_box[0] + base_box[2]) // 2
    center_y = (base_box[1] + base_box[3]) // 2

    candidates: list[GroundingCandidate] = []
    for rank in range(max_candidates):
        dx = rank * max(4, width // 32)
        dy = rank * max(4, height // 48)
        bbox = [
            max(0, base_box[0] - dx),
            max(0, base_box[1] - dy),
            min(width - 1, base_box[2] + dx),
            min(height - 1, base_box[3] + dy),
        ]
        point = [min(width - 1, center_x + dx // 2), min(height - 1, center_y + dy // 2)]
        score = max(0.0, 0.95 - (rank * 0.12))
        candidates.append(
            GroundingCandidate(
                candidate_id=f"{task.task_id}-ground-{rank}",
                task_id=task.task_id,
                source_model="stub_grounding",
                text_prompt=task.target_object.text,
                bbox_xyxy=bbox,
                point_xy=point,
                score=score,
                rank=rank,
                frame_id=frame_id,
            )
        )
    return candidates
