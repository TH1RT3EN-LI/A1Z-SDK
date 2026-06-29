#!/usr/bin/env python3

"""Run SAM2 image segmentation from a grounding JSON payload."""

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

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SAM2 from grounding JSON.")
    parser.add_argument(
        "--grounding-json",
        default=str(REPO_ROOT / "runtime" / "vlm_grounding" / "ros_pen_grounding_for_sam.json"),
        help="Path to grounding JSON with image_path and candidates[0].",
    )
    parser.add_argument(
        "--candidate-index",
        type=int,
        default=0,
        help="Candidate index inside the grounding JSON.",
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
        default=str(REPO_ROOT / "runtime" / "vlm_grounding" / "sam_from_grounding"),
        help="Directory for mask and overlay artifacts.",
    )
    parser.add_argument(
        "--multimask-output",
        action="store_true",
        default=True,
        help="Ask SAM2 for multiple mask candidates.",
    )
    return parser


def _load_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("grounding JSON root must be an object")
    return payload


def _resolve_image_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_file():
        return path
    if raw_path.startswith("/workspace/A1Z/"):
        remapped = REPO_ROOT / raw_path.removeprefix("/workspace/A1Z/")
        if remapped.is_file():
            return remapped
    raise FileNotFoundError(f"image referenced by grounding JSON not found: {raw_path}")


def _save_overlay(
    *,
    image_rgb: np.ndarray,
    mask: np.ndarray,
    bbox_xyxy: list[int],
    point_xy: list[int],
    path: Path,
) -> None:
    overlay = image_rgb.copy()
    color = np.array([255, 64, 64], dtype=np.uint8)
    alpha = 0.45
    mask_bool = mask.astype(bool)
    overlay[mask_bool] = (overlay[mask_bool] * (1.0 - alpha) + color * alpha).astype(np.uint8)

    x0, y0, x1, y1 = bbox_xyxy
    px, py = point_xy
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (64, 255, 64), 2)
    cv2.circle(overlay, (px, py), 5, (255, 255, 0), -1)
    cv2.imwrite(str(path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))


def main() -> int:
    args = build_parser().parse_args()

    grounding_path = Path(args.grounding_json).resolve()
    payload = _load_payload(grounding_path)
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("grounding JSON does not contain any candidates")
    if args.candidate_index < 0 or args.candidate_index >= len(candidates):
        raise IndexError(
            f"candidate-index {args.candidate_index} out of range for {len(candidates)} candidates"
        )

    candidate = candidates[args.candidate_index]
    image_path = _resolve_image_path(str(payload["image_path"]))
    image_rgb = np.array(Image.open(image_path).convert("RGB"))

    box = np.array(candidate["bbox_xyxy"], dtype=np.float32)
    point_coords = np.array([candidate["point_xy"]], dtype=np.float32)
    point_labels = np.array([1], dtype=np.int32)

    checkpoint_path = Path(args.sam_checkpoint).resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"SAM checkpoint not found: {checkpoint_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(args.sam_config, str(checkpoint_path), device=device)
    predictor = SAM2ImagePredictor(model)

    with torch.inference_mode():
        if device == "cuda":
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                predictor.set_image(image_rgb)
                masks, scores, low_res_masks = predictor.predict(
                    box=box,
                    point_coords=point_coords,
                    point_labels=point_labels,
                    multimask_output=bool(args.multimask_output),
                )
        else:
            predictor.set_image(image_rgb)
            masks, scores, low_res_masks = predictor.predict(
                box=box,
                point_coords=point_coords,
                point_labels=point_labels,
                multimask_output=bool(args.multimask_output),
            )

    best_index = int(np.argmax(scores))
    best_mask = masks[best_index].astype(np.uint8)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    mask_npy_path = output_dir / "mask.npy"
    mask_png_path = output_dir / "mask.png"
    overlay_path = output_dir / "overlay.png"
    summary_path = output_dir / "summary.json"

    np.save(mask_npy_path, best_mask)
    cv2.imwrite(str(mask_png_path), best_mask * 255)
    _save_overlay(
        image_rgb=image_rgb,
        mask=best_mask,
        bbox_xyxy=[int(v) for v in candidate["bbox_xyxy"]],
        point_xy=[int(v) for v in candidate["point_xy"]],
        path=overlay_path,
    )

    summary = {
        "grounding_json": str(grounding_path),
        "image_path": str(image_path),
        "candidate_index": int(args.candidate_index),
        "candidate_id": candidate.get("candidate_id"),
        "bbox_xyxy": [int(v) for v in candidate["bbox_xyxy"]],
        "point_xy": [int(v) for v in candidate["point_xy"]],
        "device": device,
        "sam_config": args.sam_config,
        "sam_checkpoint": str(checkpoint_path),
        "multimask_scores": [float(v) for v in scores.tolist()],
        "best_index": best_index,
        "best_score": float(scores[best_index]),
        "mask_area_px": int(best_mask.sum()),
        "mask_npy_path": str(mask_npy_path),
        "mask_png_path": str(mask_png_path),
        "overlay_path": str(overlay_path),
        "low_res_shape": list(low_res_masks.shape),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
