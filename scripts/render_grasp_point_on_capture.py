#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project one base-frame grasp point into a captured RGB image.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--intrinsics", required=True)
    parser.add_argument("--observation", required=True)
    parser.add_argument("--point-base-xyz", required=True, help="x,y,z in target/base frame, meters")
    parser.add_argument("--label", default="grasp")
    parser.add_argument("--output", required=True)
    return parser


def _parse_vec3(raw: str) -> np.ndarray:
    parts = [float(v.strip()) for v in raw.replace(",", " ").split()]
    if len(parts) != 3:
        raise ValueError(f"expected 3 numbers, got: {raw}")
    return np.asarray(parts, dtype=np.float64)


def main() -> int:
    args = _build_parser().parse_args()
    intr = json.loads(Path(args.intrinsics).read_text(encoding="utf-8"))
    obs = json.loads(Path(args.observation).read_text(encoding="utf-8"))
    t_cam_to_base = np.asarray(obs["extrinsic_camera_to_target"], dtype=np.float64)
    t_base_to_cam = np.linalg.inv(t_cam_to_base)

    p_base = np.ones(4, dtype=np.float64)
    p_base[:3] = _parse_vec3(args.point_base_xyz)
    p_cam = t_base_to_cam @ p_base
    if p_cam[2] <= 0.0:
        raise ValueError(f"projected point is behind camera: {p_cam[:3].tolist()}")

    fx = float(intr["fx"])
    fy = float(intr["fy"])
    cx = float(intr["cx"])
    cy = float(intr["cy"])
    u = fx * (p_cam[0] / p_cam[2]) + cx
    v = fy * (p_cam[1] / p_cam[2]) + cy

    image = Image.open(args.image).convert("RGB")
    draw = ImageDraw.Draw(image)
    r = 10
    draw.ellipse((u - r, v - r, u + r, v + r), outline=(255, 0, 0), width=4)
    draw.line((u - 16, v, u + 16, v), fill=(255, 0, 0), width=3)
    draw.line((u, v - 16, u, v + 16), fill=(255, 0, 0), width=3)
    text = f"{args.label} ({u:.1f}, {v:.1f})"
    tx = min(max(8, u + 14), image.width - 220)
    ty = min(max(8, v - 28), image.height - 24)
    draw.rectangle((tx - 4, ty - 2, tx + 210, ty + 18), fill=(0, 0, 0))
    draw.text((tx, ty), text, fill=(255, 255, 0))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(
        json.dumps(
            {
                "output_image": str(output),
                "pixel_uv": [float(u), float(v)],
                "point_camera_xyz_m": [float(vv) for vv in p_cam[:3].tolist()],
                "point_base_xyz_m": [float(vv) for vv in p_base[:3].tolist()],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
