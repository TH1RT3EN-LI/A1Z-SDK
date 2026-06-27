"""Segmentation stub that turns boxes into deterministic binary masks."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from a1z_ext.interfaces.schemas import GroundingCandidate, MaskCandidate


def _write_mask(mask: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, mask.astype(np.uint8))


def segment_candidates(
    image_shape: tuple[int, int],
    candidates: list[GroundingCandidate],
    *,
    output_dir: str | Path,
) -> list[MaskCandidate]:
    height, width = image_shape
    result: list[MaskCandidate] = []
    output_root = Path(output_dir)

    for candidate in candidates:
        bbox = candidate.bbox_xyxy
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[y0 : y1 + 1, x0 : x1 + 1] = 1

        mask_path = output_root / f"{candidate.candidate_id}.npy"
        _write_mask(mask, mask_path)

        area = int(mask.sum())
        perimeter_touch = float(
            np.any(mask[0, :]) or np.any(mask[-1, :]) or np.any(mask[:, 0]) or np.any(mask[:, -1])
        )
        result.append(
            MaskCandidate(
                mask_id=f"{candidate.candidate_id}-mask",
                candidate_id=candidate.candidate_id,
                source_model="stub_sam2",
                prompt_type="box+point",
                mask_path=str(mask_path),
                bbox_xyxy=bbox,
                mask_area_px=area,
                stability_score=0.95 - (candidate.rank * 0.05),
                mask_score=max(0.0, candidate.score - 0.03),
                depth_valid_ratio=1.0,
                boundary_touch_ratio=perimeter_touch,
                rank=candidate.rank,
            )
        )
    return result

