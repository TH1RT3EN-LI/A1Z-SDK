#!/usr/bin/env python3

"""Run the reusable target-mask pipeline from instruction plus image input."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.perception import run_target_mask_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run instruction -> automatic masks -> VLM select target mask."
    )
    parser.add_argument("--instruction", required=True, help="Natural-language pick instruction.")
    parser.add_argument("--image", default="", help="Path to an RGB image file.")
    parser.add_argument("--ros-topic", default="", help="ROS image topic to capture one frame from.")
    parser.add_argument("--ros-timeout-s", type=float, default=10.0)
    parser.add_argument("--capture-path", default="", help="Optional capture path for a ROS frame.")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "runtime" / "target_mask_pipeline"),
        help="Directory for all intermediate and final artifacts.",
    )
    parser.add_argument(
        "--env-file",
        default=str(REPO_ROOT / "config" / "a1z_vlm.env"),
        help="Env file for VLM credentials and defaults.",
    )
    parser.add_argument("--provider", default="", help="Optional provider override, e.g. kimi.")
    parser.add_argument("--image-detail", default="high")
    parser.add_argument("--vlm-max-tokens", type=int, default=600)
    parser.add_argument(
        "--sam-checkpoint",
        default=str(REPO_ROOT / "runtime" / "models" / "sam2" / "sam2.1_hiera_small.pt"),
    )
    parser.add_argument("--sam-config", default="configs/sam2.1/sam2.1_hiera_s.yaml")
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
    parser.add_argument("--max-area-ratio", type=float, default=0.7)
    parser.add_argument("--max-boundary-touches", type=int, default=2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_target_mask_pipeline(
        instruction=args.instruction,
        image_arg=args.image,
        ros_topic=args.ros_topic,
        ros_timeout_s=args.ros_timeout_s,
        capture_path_arg=args.capture_path,
        output_dir=args.output_dir,
        env_file=args.env_file,
        provider=args.provider or None,
        image_detail=args.image_detail,
        vlm_max_tokens=args.vlm_max_tokens,
        sam_checkpoint=args.sam_checkpoint,
        sam_config=args.sam_config,
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
        max_preview_masks=args.max_preview_masks,
        max_area_ratio=args.max_area_ratio,
        max_boundary_touches=args.max_boundary_touches,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
