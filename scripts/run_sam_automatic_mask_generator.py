#!/usr/bin/env python3

"""Run SAM2 automatic mask generation on a single image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import torch
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
SAM2_REPO_ROOT = REPO_ROOT / "vendor" / "vision" / "sam2"
if str(SAM2_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SAM2_REPO_ROOT))

from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
from sam2.build_sam import build_sam2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SAM2 automatic mask generator.")
    parser.add_argument(
        "--image",
        default=str(REPO_ROOT / "runtime" / "vlm_grounding" / "ros_pen_capture.png"),
        help="Input image path.",
    )
    parser.add_argument(
        "--sam-checkpoint",
        default=str(REPO_ROOT / "runtime" / "models" / "sam2" / "sam2.1_hiera_small.pt"),
        help="SAM2 checkpoint path.",
    )
    parser.add_argument(
        "--sam-config",
        default="configs/sam2.1/sam2.1_hiera_s.yaml",
        help="SAM2 config path relative to the SAM2 repo.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "runtime" / "vlm_grounding" / "sam_amg_ros_pen"),
        help="Directory for generated masks and metadata.",
    )
    parser.add_argument("--points-per-side", type=int, default=32)
    parser.add_argument("--points-per-batch", type=int, default=64)
    parser.add_argument("--pred-iou-thresh", type=float, default=0.8)
    parser.add_argument("--stability-score-thresh", type=float, default=0.95)
    parser.add_argument("--stability-score-offset", type=float, default=1.0)
    parser.add_argument("--box-nms-thresh", type=float, default=0.7)
    parser.add_argument("--crop-n-layers", type=int, default=0)
    parser.add_argument("--crop-nms-thresh", type=float, default=0.7)
    parser.add_argument("--crop-overlap-ratio", type=float, default=512 / 1500)
    parser.add_argument("--crop-n-points-downscale-factor", type=int, default=1)
    parser.add_argument("--min-mask-region-area", type=int, default=0)
    parser.add_argument("--max-preview-masks", type=int, default=24)
    return parser


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_file():
        return path.resolve()
    if path_str.startswith("/workspace/A1Z/"):
        remapped = REPO_ROOT / path_str.removeprefix("/workspace/A1Z/")
        if remapped.is_file():
            return remapped.resolve()
    raise FileNotFoundError(path_str)


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
    records: list[dict],
    max_preview_masks: int,
    output_path: Path,
) -> None:
    overlay = image_rgb.copy()
    for idx, (mask, record) in enumerate(zip(masks[:max_preview_masks], records[:max_preview_masks])):
        color = _make_color(idx)
        alpha = 0.35
        mask_bool = mask.astype(bool)
        overlay[mask_bool] = (overlay[mask_bool] * (1.0 - alpha) + color * alpha).astype(np.uint8)

        x, y, w, h = [int(v) for v in record["bbox_xywh"]]
        cx = int(x + (w / 2))
        cy = int(y + (h / 2))
        cv2.rectangle(overlay, (x, y), (x + w, y + h), tuple(int(v) for v in color.tolist()), 2)
        cv2.circle(overlay, (cx, cy), 4, (255, 255, 255), -1)
        cv2.putText(
            overlay,
            str(record["mask_index"]),
            (x, max(18, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(output_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))


def _write_mask_preview(mask: np.ndarray, path: Path) -> None:
    cv2.imwrite(str(path), (mask.astype(np.uint8) * 255))


def main() -> int:
    args = build_parser().parse_args()

    image_path = _resolve_path(args.image)
    checkpoint_path = _resolve_path(args.sam_checkpoint)
    image_rgb = np.array(Image.open(image_path).convert("RGB"))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(args.sam_config, str(checkpoint_path), device=device)
    generator = SAM2AutomaticMaskGenerator(
        model=model,
        points_per_side=args.points_per_side,
        points_per_batch=args.points_per_batch,
        pred_iou_thresh=args.pred_iou_thresh,
        stability_score_thresh=args.stability_score_thresh,
        stability_score_offset=args.stability_score_offset,
        box_nms_thresh=args.box_nms_thresh,
        crop_n_layers=args.crop_n_layers,
        crop_nms_thresh=args.crop_nms_thresh,
        crop_overlap_ratio=args.crop_overlap_ratio,
        crop_n_points_downscale_factor=args.crop_n_points_downscale_factor,
        min_mask_region_area=args.min_mask_region_area,
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

    output_dir = Path(args.output_dir).resolve()
    masks_dir = output_dir / "masks"
    output_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
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
            {
                "mask_index": index,
                "area": int(ann["area"]),
                "bbox_xywh": [x, y, w, h],
                "predicted_iou": float(ann["predicted_iou"]),
                "stability_score": float(ann["stability_score"]),
                "point_coords": [float(point[0]), float(point[1])],
                "crop_box_xywh": [int(v) for v in ann["crop_box"]],
                "mask_png_path": str(mask_png_path),
                "mask_npy_path": str(mask_npy_path),
            }
        )

    overlay_path = output_dir / "overlay_top_masks.png"
    _draw_indexed_overlay(
        image_rgb=image_rgb,
        masks=masks,
        records=records,
        max_preview_masks=args.max_preview_masks,
        output_path=overlay_path,
    )

    summary = {
        "image_path": str(image_path),
        "device": device,
        "sam_config": args.sam_config,
        "sam_checkpoint": str(checkpoint_path),
        "generator_params": {
            "points_per_side": args.points_per_side,
            "points_per_batch": args.points_per_batch,
            "pred_iou_thresh": args.pred_iou_thresh,
            "stability_score_thresh": args.stability_score_thresh,
            "stability_score_offset": args.stability_score_offset,
            "box_nms_thresh": args.box_nms_thresh,
            "crop_n_layers": args.crop_n_layers,
            "crop_nms_thresh": args.crop_nms_thresh,
            "crop_overlap_ratio": args.crop_overlap_ratio,
            "crop_n_points_downscale_factor": args.crop_n_points_downscale_factor,
            "min_mask_region_area": args.min_mask_region_area,
        },
        "mask_count": len(records),
        "overlay_path": str(overlay_path),
        "records": records,
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    print(json.dumps(
        {
            "mask_count": len(records),
            "summary_path": str(summary_path),
            "overlay_path": str(overlay_path),
        },
        ensure_ascii=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
