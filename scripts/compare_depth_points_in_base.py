#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare base-frame points from the same depth pixels using two camera->base extrinsics."
    )
    parser.add_argument("--depth", required=True, help="Path to depth_m.npy")
    parser.add_argument("--intrinsics", required=True, help="Path to intrinsics.json")
    parser.add_argument("--ros-extrinsic-json", required=True, help="Path to ROS TF JSON payload")
    parser.add_argument("--isaac-extrinsic-json", required=True, help="Path to Isaac TF JSON payload")
    parser.add_argument(
        "--pixels",
        default="",
        help="Semicolon-separated pixel list 'u,v;u,v;...'. If omitted, auto-sample valid pixels.",
    )
    parser.add_argument("--sample-count", type=int, default=12, help="Auto-sampled pixel count when --pixels is empty.")
    parser.add_argument("--min-depth-m", type=float, default=0.05)
    parser.add_argument("--max-depth-m", type=float, default=2.0)
    parser.add_argument("--output", default="")
    return parser


def _load_intrinsics(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "fx": float(payload["fx"]),
        "fy": float(payload["fy"]),
        "cx": float(payload["cx"]),
        "cy": float(payload["cy"]),
    }


def _load_transform(path: Path) -> np.ndarray:
    payload = json.loads(path.read_text(encoding="utf-8"))
    matrix = np.asarray(payload["transform"]["matrix"], dtype=np.float64)
    if matrix.shape != (4, 4):
        raise ValueError(f"transform matrix must be 4x4, got {matrix.shape}: {path}")
    return matrix


def _parse_pixels(raw: str) -> list[tuple[int, int]]:
    pixels: list[tuple[int, int]] = []
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        u_str, v_str = [part.strip() for part in item.split(",", 1)]
        pixels.append((int(u_str), int(v_str)))
    return pixels


def _auto_sample_pixels(
    depth_m: np.ndarray,
    *,
    sample_count: int,
    min_depth_m: float,
    max_depth_m: float,
) -> list[tuple[int, int]]:
    valid = np.isfinite(depth_m) & (depth_m >= float(min_depth_m)) & (depth_m <= float(max_depth_m))
    ys, xs = np.where(valid)
    if xs.size == 0:
        raise RuntimeError("no valid depth pixels available for auto-sampling")
    count = min(int(sample_count), int(xs.size))
    if count <= 0:
        raise ValueError("sample_count must be positive")
    indices = np.linspace(0, xs.size - 1, num=count, dtype=int)
    return [(int(xs[idx]), int(ys[idx])) for idx in indices]


def _pixel_to_camera_xyz(
    *,
    u: int,
    v: int,
    depth_m: float,
    intrinsics: dict[str, float],
) -> np.ndarray:
    fx = float(intrinsics["fx"])
    fy = float(intrinsics["fy"])
    cx = float(intrinsics["cx"])
    cy = float(intrinsics["cy"])
    x = (float(u) - cx) * float(depth_m) / fx
    y = (float(v) - cy) * float(depth_m) / fy
    z = float(depth_m)
    return np.array([x, y, z, 1.0], dtype=np.float64)


def _payload(
    *,
    pixel: tuple[int, int],
    depth_m: float,
    point_camera: np.ndarray,
    point_base_ros: np.ndarray,
    point_base_isaac: np.ndarray,
) -> dict[str, object]:
    delta = point_base_isaac[:3] - point_base_ros[:3]
    return {
        "pixel_uv": [int(pixel[0]), int(pixel[1])],
        "depth_m": float(depth_m),
        "point_camera_xyz_m": [float(v) for v in point_camera[:3].tolist()],
        "point_base_ros_xyz_m": [float(v) for v in point_base_ros[:3].tolist()],
        "point_base_isaac_xyz_m": [float(v) for v in point_base_isaac[:3].tolist()],
        "delta_xyz_m": [float(v) for v in delta.tolist()],
        "delta_norm_m": float(np.linalg.norm(delta)),
    }


def main() -> int:
    args = _build_parser().parse_args()
    depth_m = np.load(Path(args.depth)).astype(np.float64, copy=False)
    if depth_m.ndim != 2:
        raise ValueError(f"depth must be HxW, got {depth_m.shape}")
    intrinsics = _load_intrinsics(Path(args.intrinsics))
    t_ros = _load_transform(Path(args.ros_extrinsic_json))
    t_isaac = _load_transform(Path(args.isaac_extrinsic_json))

    pixels = _parse_pixels(args.pixels) if args.pixels.strip() else _auto_sample_pixels(
        depth_m,
        sample_count=int(args.sample_count),
        min_depth_m=float(args.min_depth_m),
        max_depth_m=float(args.max_depth_m),
    )

    comparisons: list[dict[str, object]] = []
    deltas: list[float] = []
    for u, v in pixels:
        if not (0 <= v < depth_m.shape[0] and 0 <= u < depth_m.shape[1]):
            raise ValueError(f"pixel out of bounds: ({u}, {v}) for depth shape {depth_m.shape}")
        depth_val = float(depth_m[v, u])
        if not math.isfinite(depth_val) or depth_val <= 0.0:
            raise ValueError(f"invalid depth at pixel ({u}, {v}): {depth_val}")
        point_cam = _pixel_to_camera_xyz(u=u, v=v, depth_m=depth_val, intrinsics=intrinsics)
        point_base_ros = t_ros @ point_cam
        point_base_isaac = t_isaac @ point_cam
        item = _payload(
            pixel=(u, v),
            depth_m=depth_val,
            point_camera=point_cam,
            point_base_ros=point_base_ros,
            point_base_isaac=point_base_isaac,
        )
        comparisons.append(item)
        deltas.append(float(item["delta_norm_m"]))

    summary = {
        "point_count": len(comparisons),
        "max_delta_norm_m": max(deltas) if deltas else 0.0,
        "mean_delta_norm_m": (sum(deltas) / len(deltas)) if deltas else 0.0,
        "min_delta_norm_m": min(deltas) if deltas else 0.0,
    }
    report = {
        "depth_path": str(Path(args.depth).resolve()),
        "intrinsics_path": str(Path(args.intrinsics).resolve()),
        "ros_extrinsic_json": str(Path(args.ros_extrinsic_json).resolve()),
        "isaac_extrinsic_json": str(Path(args.isaac_extrinsic_json).resolve()),
        "summary": summary,
        "points": comparisons,
    }
    payload = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
