#!/usr/bin/env python3

"""Prepare AnyGrasp inputs from a selected mask and optionally run detection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.perception import (
    build_anygrasp_inputs_from_mask,
    load_mask_array,
    load_rgb_array,
    run_anygrasp_detection,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert selected mask + RGB-D into AnyGrasp inputs and run detection."
    )
    parser.add_argument("--rgb", required=True, help="Path to RGB image or rgb.npy.")
    parser.add_argument("--depth", required=True, help="Path to depth_m.npy.")
    parser.add_argument("--intrinsics", required=True, help="Path to intrinsics.json.")
    parser.add_argument("--mask", default="", help="Path to selected_mask.npy.")
    parser.add_argument(
        "--selection-json",
        default="",
        help="Optional selection.json; if --mask is omitted, selected_mask path is read from here.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "runtime" / "anygrasp_from_mask"),
        help="Directory for point cloud artifacts and AnyGrasp outputs.",
    )
    parser.add_argument("--workspace-margin-m", type=float, default=0.02)
    parser.add_argument("--depth-min-m", type=float, default=0.0)
    parser.add_argument("--depth-max-m", type=float, default=1.5)
    parser.add_argument("--max-points", type=int, default=0)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument(
        "--sdk-dir",
        default=str(REPO_ROOT / "vendor" / "vision" / "anygrasp_sdk"),
    )
    parser.add_argument(
        "--checkpoint-path",
        default=str(REPO_ROOT / "runtime" / "models" / "anygrasp" / "checkpoint_detection.tar"),
    )
    parser.add_argument(
        "--license-dir",
        default=str(REPO_ROOT / "runtime" / "licenses" / "anygrasp"),
    )
    parser.add_argument("--max-gripper-width", type=float, default=0.7)
    parser.add_argument("--gripper-height", type=float, default=0.022)
    parser.add_argument("--top-down-grasp", action="store_true", default=True)
    parser.add_argument("--no-top-down-grasp", dest="top_down_grasp", action="store_false")
    parser.add_argument("--disable-collision-detection", action="store_true")
    parser.add_argument("--dense-grasp", action="store_true")
    parser.add_argument("--top-k", type=int, default=20)
    return parser


def _resolve_mask_path(mask_arg: str, selection_json_arg: str) -> Path:
    if mask_arg:
        return Path(mask_arg).resolve()
    if not selection_json_arg:
        raise ValueError("either --mask or --selection-json must be provided")
    selection_payload = json.loads(Path(selection_json_arg).read_text(encoding="utf-8"))
    selected_mask = selection_payload.get("selected_mask") or {}
    mask_path = selected_mask.get("mask_npy_path")
    if not mask_path:
        raise ValueError(f"selection json does not contain selected mask path: {selection_json_arg}")
    return Path(mask_path).resolve()


def main() -> int:
    args = build_parser().parse_args()
    output_root = Path(args.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    mask_path = _resolve_mask_path(args.mask, args.selection_json)
    rgb = load_rgb_array(args.rgb)
    depth_m = np.load(Path(args.depth)).astype(np.float32, copy=False)
    intrinsics = json.loads(Path(args.intrinsics).read_text(encoding="utf-8"))
    mask = load_mask_array(mask_path)

    point_cloud_dir = output_root / "masked_point_cloud"
    point_cloud = build_anygrasp_inputs_from_mask(
        rgb=rgb,
        depth_m=depth_m,
        intrinsics=intrinsics,
        mask=mask,
        output_dir=point_cloud_dir,
        workspace_margin_m=args.workspace_margin_m,
        depth_min_m=args.depth_min_m,
        depth_max_m=args.depth_max_m,
        max_points=(args.max_points if args.max_points > 0 else None),
        random_seed=args.random_seed,
    )

    points = np.load(Path(point_cloud.points_path)).astype(np.float32, copy=False)
    colors = np.load(Path(point_cloud.colors_path)).astype(np.float32, copy=False)
    anygrasp_result = run_anygrasp_detection(
        points=points,
        colors=colors,
        lims=point_cloud.lims,
        output_dir=output_root / "anygrasp",
        sdk_dir=args.sdk_dir,
        checkpoint_path=args.checkpoint_path,
        license_dir=args.license_dir,
        max_gripper_width=args.max_gripper_width,
        gripper_height=args.gripper_height,
        top_down_grasp=args.top_down_grasp,
        collision_detection=(not args.disable_collision_detection),
        dense_grasp=args.dense_grasp,
        top_k=args.top_k,
    )

    pipeline_result = {
        "mask_path": str(mask_path),
        "point_cloud": point_cloud.to_dict(),
        "anygrasp": anygrasp_result.to_dict(),
    }
    pipeline_result_path = output_root / "pipeline_result.json"
    pipeline_result_path.write_text(json.dumps(pipeline_result, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(pipeline_result, ensure_ascii=True))
    return 0 if anygrasp_result.ran else 1


if __name__ == "__main__":
    raise SystemExit(main())
