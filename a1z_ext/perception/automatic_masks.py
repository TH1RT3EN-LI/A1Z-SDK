"""SAM2 automatic mask generation with numbered preview artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
SAM2_REPO_ROOT = REPO_ROOT / "vendor" / "vision" / "sam2"
if str(SAM2_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SAM2_REPO_ROOT))

from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
from sam2.build_sam import build_sam2


@dataclass(frozen=True, slots=True)
class AutomaticMaskRecord:
    mask_index: int
    area: int
    bbox_xywh: list[int]
    predicted_iou: float
    stability_score: float
    point_coords: list[float]
    crop_box_xywh: list[int]
    mask_png_path: str
    mask_npy_path: str


@dataclass(frozen=True, slots=True)
class AutomaticMaskBundle:
    image_path: str
    device: str
    sam_config: str
    sam_checkpoint: str
    generator_params: dict[str, Any]
    mask_count: int
    overlay_path: str
    records: list[AutomaticMaskRecord]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_workspace_path(path_str: str | Path) -> Path:
    raw = str(path_str)
    path = Path(raw)
    if path.is_file():
        return path.resolve()
    if raw.startswith("/workspace/A1Z/"):
        remapped = REPO_ROOT / raw.removeprefix("/workspace/A1Z/")
        if remapped.is_file():
            return remapped.resolve()
    raise FileNotFoundError(raw)


def _make_color(index: int) -> np.ndarray:
    palette = np.array(
        [
            [255, 99, 71],
            [135, 206, 235],
            [60, 179, 113],
            [255, 215, 0],
            [186, 85, 211],
            [255, 140, 0],
            [0, 191, 255],
            [124, 252, 0],
            [255, 105, 180],
            [72, 209, 204],
            [238, 130, 238],
            [154, 205, 50],
        ],
        dtype=np.uint8,
    )
    return palette[index % len(palette)]


def _draw_indexed_overlay(
    *,
    image_rgb: np.ndarray,
    masks: list[np.ndarray],
    records: list[AutomaticMaskRecord],
    max_preview_masks: int | None,
    output_path: Path,
) -> None:
    overlay = image_rgb.copy()
    limit = len(records) if max_preview_masks is None else min(max_preview_masks, len(records))
    for idx in range(limit):
        mask = masks[idx]
        record = records[idx]
        color = _make_color(idx)
        alpha = 0.35
        mask_bool = mask.astype(bool)
        overlay[mask_bool] = (overlay[mask_bool] * (1.0 - alpha) + color * alpha).astype(np.uint8)

        x, y, w, h = record.bbox_xywh
        cx = int(x + (w / 2))
        cy = int(y + (h / 2))
        cv2.rectangle(overlay, (x, y), (x + w, y + h), tuple(int(v) for v in color.tolist()), 2)
        cv2.circle(overlay, (cx, cy), 4, (255, 255, 255), -1)
        cv2.putText(
            overlay,
            str(record.mask_index),
            (x, max(18, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(output_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))


def _write_mask_preview(mask: np.ndarray, path: Path) -> None:
    cv2.imwrite(str(path), mask.astype(np.uint8) * 255)


def _bundle_from_summary_dict(data: dict[str, Any]) -> AutomaticMaskBundle:
    return AutomaticMaskBundle(
        image_path=str(data["image_path"]),
        device=str(data["device"]),
        sam_config=str(data["sam_config"]),
        sam_checkpoint=str(data["sam_checkpoint"]),
        generator_params=dict(data["generator_params"]),
        mask_count=int(data["mask_count"]),
        overlay_path=str(data["overlay_path"]),
        records=[
            AutomaticMaskRecord(
                mask_index=int(record["mask_index"]),
                area=int(record["area"]),
                bbox_xywh=[int(v) for v in record["bbox_xywh"]],
                predicted_iou=float(record["predicted_iou"]),
                stability_score=float(record["stability_score"]),
                point_coords=[float(v) for v in record["point_coords"]],
                crop_box_xywh=[int(v) for v in record["crop_box_xywh"]],
                mask_png_path=str(record["mask_png_path"]),
                mask_npy_path=str(record["mask_npy_path"]),
            )
            for record in data["records"]
        ],
    )


def load_automatic_mask_bundle(summary_path: str | Path) -> AutomaticMaskBundle:
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError("automatic mask summary must be a JSON object")
    return _bundle_from_summary_dict(summary)


def generate_automatic_masks(
    *,
    image_path: str | Path,
    output_dir: str | Path,
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
    max_preview_masks: int | None = None,
) -> AutomaticMaskBundle:
    resolved_image_path = resolve_workspace_path(image_path)
    resolved_checkpoint_path = resolve_workspace_path(sam_checkpoint)
    image_rgb = np.array(Image.open(resolved_image_path).convert("RGB"))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(sam_config, str(resolved_checkpoint_path), device=device)
    generator = SAM2AutomaticMaskGenerator(
        model=model,
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
        output_mode="binary_mask",
        multimask_output=True,
    )

    with torch.inference_mode():
        if device == "cuda":
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                anns = generator.generate(image_rgb)
        else:
            anns = generator.generate(image_rgb)

    anns = sorted(
        anns,
        key=lambda ann: (
            float(ann["predicted_iou"]),
            float(ann["stability_score"]),
            int(ann["area"]),
        ),
        reverse=True,
    )

    output_root = Path(output_dir).resolve()
    masks_dir = output_root / "masks"
    output_root.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    records: list[AutomaticMaskRecord] = []
    masks: list[np.ndarray] = []
    for index, ann in enumerate(anns):
        mask = ann["segmentation"].astype(np.uint8)
        masks.append(mask)
        mask_png_path = masks_dir / f"mask_{index:03d}.png"
        mask_npy_path = masks_dir / f"mask_{index:03d}.npy"
        _write_mask_preview(mask, mask_png_path)
        np.save(mask_npy_path, mask)

        x, y, w, h = [int(v) for v in ann["bbox"]]
        point = ann["point_coords"][0]
        records.append(
            AutomaticMaskRecord(
                mask_index=index,
                area=int(ann["area"]),
                bbox_xywh=[x, y, w, h],
                predicted_iou=float(ann["predicted_iou"]),
                stability_score=float(ann["stability_score"]),
                point_coords=[float(point[0]), float(point[1])],
                crop_box_xywh=[int(v) for v in ann["crop_box"]],
                mask_png_path=str(mask_png_path),
                mask_npy_path=str(mask_npy_path),
            )
        )

    overlay_path = output_root / "overlay_top_masks.png"
    _draw_indexed_overlay(
        image_rgb=image_rgb,
        masks=masks,
        records=records,
        max_preview_masks=max_preview_masks,
        output_path=overlay_path,
    )

    bundle = AutomaticMaskBundle(
        image_path=str(resolved_image_path),
        device=device,
        sam_config=sam_config,
        sam_checkpoint=str(resolved_checkpoint_path),
        generator_params={
            "points_per_side": points_per_side,
            "points_per_batch": points_per_batch,
            "pred_iou_thresh": pred_iou_thresh,
            "stability_score_thresh": stability_score_thresh,
            "stability_score_offset": stability_score_offset,
            "box_nms_thresh": box_nms_thresh,
            "crop_n_layers": crop_n_layers,
            "crop_nms_thresh": crop_nms_thresh,
            "crop_overlap_ratio": crop_overlap_ratio,
            "crop_n_points_downscale_factor": crop_n_points_downscale_factor,
            "min_mask_region_area": min_mask_region_area,
        },
        mask_count=len(records),
        overlay_path=str(overlay_path),
        records=records,
    )
    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(bundle.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return bundle
