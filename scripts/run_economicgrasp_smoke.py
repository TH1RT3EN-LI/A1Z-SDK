#!/usr/bin/env python3

"""Run EconomicGrasp on a single RGB-D frame and emit raw grasp candidates."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_runner():
    module_path = REPO_ROOT / "a1z_ext" / "perception" / "economicgrasp.py"
    spec = importlib.util.spec_from_file_location("a1z_economicgrasp_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.run_economicgrasp_smoke


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run EconomicGrasp on a single RGB-D frame.")
    parser.add_argument("--rgb", required=True, help="Path to rgb.npy or an RGB image.")
    parser.add_argument("--depth", required=True, help="Path to depth_m.npy.")
    parser.add_argument("--intrinsics", required=True, help="Path to intrinsics.json.")
    parser.add_argument(
        "--checkpoint-path",
        default=str(REPO_ROOT / "runtime" / "models" / "economicgrasp" / "economicgrasp_realsense.tar"),
    )
    parser.add_argument(
        "--vendor-repo-dir",
        default=str(REPO_ROOT / "vendor" / "vision" / "EconomicGrasp"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "runtime" / "economicgrasp_smoke"),
    )
    parser.add_argument("--camera", default="realsense")
    parser.add_argument("--num-points", type=int, default=20000)
    parser.add_argument("--voxel-size-m", type=float, default=0.005)
    parser.add_argument("--depth-min-m", type=float, default=0.05)
    parser.add_argument("--depth-max-m", type=float, default=1.5)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--allow-random-weights", action="store_true")
    parser.add_argument("--force-all-graspable", action="store_true")
    return parser


def _load_rgb(path: str | Path) -> np.ndarray:
    source = Path(path)
    if source.suffix.lower() == ".npy":
        array = np.load(source)
        if array.ndim != 3 or array.shape[2] < 3:
            raise ValueError(f"rgb.npy must have shape (H, W, C>=3), got {array.shape}")
        return np.ascontiguousarray(array[:, :, :3].astype(np.uint8, copy=False))
    from PIL import Image

    return np.asarray(Image.open(source).convert("RGB"), dtype=np.uint8)


def main() -> int:
    args = build_parser().parse_args()
    run_economicgrasp_smoke = _load_runner()
    rgb = _load_rgb(args.rgb)
    depth_m = np.load(Path(args.depth)).astype(np.float32, copy=False)
    intrinsics = json.loads(Path(args.intrinsics).read_text(encoding="utf-8"))

    result = run_economicgrasp_smoke(
        rgb=rgb,
        depth_m=depth_m,
        intrinsics=intrinsics,
        checkpoint_path=args.checkpoint_path,
        vendor_repo_dir=args.vendor_repo_dir,
        output_dir=args.output_dir,
        camera=args.camera,
        num_points=args.num_points,
        voxel_size_m=args.voxel_size_m,
        depth_min_m=args.depth_min_m,
        depth_max_m=args.depth_max_m,
        random_seed=args.random_seed,
        top_k=args.top_k,
        force_cpu=args.force_cpu,
        allow_random_weights=bool(args.allow_random_weights),
        force_all_graspable=bool(args.force_all_graspable),
    )
    print(json.dumps(result.to_dict(), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
