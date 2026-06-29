#!/usr/bin/env python3

"""Run GR-ConvNet on selected mask + RGB-D and persist grasp maps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.perception import load_mask_array, load_rgb_array, run_grconvnet_inference


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GR-ConvNet on selected mask RGB-D.")
    parser.add_argument("--rgb", required=True)
    parser.add_argument("--depth", required=True)
    parser.add_argument("--mask", default="")
    parser.add_argument("--selection-json", default="")
    parser.add_argument("--vendor-repo-dir", default=str(REPO_ROOT / "vendor" / "vision" / "robotic-grasping"))
    parser.add_argument(
        "--checkpoint-path",
        default=str(
            REPO_ROOT
            / "runtime"
            / "models"
            / "grconvnet"
            / "jacquard-rgbd-grconvnet3-drop0-ch32"
            / "epoch_48_iou_0.93"
        ),
    )
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "runtime" / "grconvnet_inference"))
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--min-quality", type=float, default=0.1)
    parser.add_argument("--peak-min-distance", type=int, default=12)
    parser.add_argument("--force-cpu", action="store_true")
    return parser


def _resolve_mask_path(mask_arg: str, selection_json_arg: str) -> Path | None:
    if mask_arg:
        return Path(mask_arg).resolve()
    if not selection_json_arg:
        return None
    selection_payload = json.loads(Path(selection_json_arg).read_text(encoding="utf-8"))
    selected_mask = selection_payload.get("selected_mask") or {}
    mask_path = selected_mask.get("mask_npy_path")
    if not mask_path:
        raise ValueError(f"selection json does not contain selected mask path: {selection_json_arg}")
    return Path(mask_path).resolve()


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rgb = load_rgb_array(args.rgb)
    depth_m = np.load(Path(args.depth)).astype(np.float32, copy=False)
    mask_path = _resolve_mask_path(args.mask, args.selection_json)
    mask = load_mask_array(mask_path) if mask_path is not None else None

    result = run_grconvnet_inference(
        rgb=rgb,
        depth_m=depth_m,
        checkpoint_path=args.checkpoint_path,
        vendor_repo_dir=args.vendor_repo_dir,
        output_dir=output_dir,
        mask=mask,
        top_k=args.top_k,
        force_cpu=args.force_cpu,
        peak_local_max_min_distance=args.peak_min_distance,
        min_quality=args.min_quality,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=True))
    return 0 if result.ran else 1


if __name__ == "__main__":
    raise SystemExit(main())
