#!/usr/bin/env python3
"""Render an RTX preview focused on the A1Z wrist camera bracket."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from isaacsim import SimulationApp


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        type=Path,
        default=ROOT / "build" / "scenes" / "A1Z_G1Z_world.usd",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runtime" / "validation" / "camera_bracket_preview.png",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=960)
    parser.add_argument("--warmup-frames", type=int, default=48)
    args, _ = parser.parse_known_args()
    if args.width < 640 or args.height < 480:
        parser.error("preview resolution must be at least 640x480")
    if args.warmup_frames < 1:
        parser.error("--warmup-frames must be positive")
    return args


ARGS = parse_args()
APP = SimulationApp(
    {
        "headless": True,
        "renderer": "RayTracedLighting",
        "width": ARGS.width,
        "height": ARGS.height,
    }
)

import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux  # noqa: E402


BRACKET_LINK_SUFFIX = "/camera_bracket_link"


def _open_stage(path: Path):
    result = stage_utils.open_stage(str(path.resolve()))
    success = bool(result[0]) if isinstance(result, tuple) else bool(result)
    if not success:
        raise RuntimeError(f"failed to open stage: {path}")
    while stage_utils.is_stage_loading():
        APP.update()
    for _ in range(8):
        APP.update()
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError(f"failed to open stage: {path}")
    return stage


def _bracket_bounds(stage) -> tuple[Gf.Vec3d, Gf.Vec3d]:
    matches = [
        prim
        for prim in stage.Traverse()
        if str(prim.GetPath()).endswith(BRACKET_LINK_SUFFIX)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one camera bracket link, found {len(matches)}")
    cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
    )
    bounds = cache.ComputeWorldBound(matches[0]).ComputeAlignedRange()
    if bounds.IsEmpty():
        raise RuntimeError("camera bracket has an empty render bound")
    return Gf.Vec3d(bounds.GetMin()), Gf.Vec3d(bounds.GetMax())


def render() -> dict[str, object]:
    stage = _open_stage(ARGS.stage)
    bounds_min, bounds_max = _bracket_bounds(stage)
    center = (bounds_min + bounds_max) * 0.5
    camera_position = center + Gf.Vec3d(0.32, -0.34, 0.20)

    key_light = UsdLux.SphereLight.Define(
        stage,
        Sdf.Path("/World/CameraBracketPreviewKeyLight"),
    )
    key_light.CreateIntensityAttr(10000.0)
    key_light.CreateRadiusAttr(0.12)
    key_light.AddTranslateOp().Set(center + Gf.Vec3d(0.16, -0.18, 0.28))
    fill_light = UsdLux.DistantLight.Define(
        stage,
        Sdf.Path("/World/CameraBracketPreviewFillLight"),
    )
    fill_light.CreateIntensityAttr(3500.0)
    fill_light.AddRotateXYZOp().Set(Gf.Vec3f(30.0, -25.0, 40.0))
    preview_dome = UsdLux.DomeLight.Define(
        stage,
        Sdf.Path("/World/CameraBracketPreviewDomeLight"),
    )
    preview_dome.CreateIntensityAttr(1000.0)

    camera = rep.create.camera(
        position=tuple(camera_position),
        look_at=tuple(center),
        focal_length=62.0,
        clipping_range=(0.01, 10.0),
    )
    render_product = rep.create.render_product(
        camera,
        resolution=(ARGS.width, ARGS.height),
    )
    annotator = rep.AnnotatorRegistry.get_annotator("rgb")
    annotator.attach(render_product)
    try:
        for _ in range(ARGS.warmup_frames):
            rep.orchestrator.step(rt_subframes=2)
        rgb = np.asarray(annotator.get_data())
    finally:
        annotator.detach()
        render_product.destroy()

    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise RuntimeError(f"unexpected RGB output shape: {rgb.shape}")
    rgb = np.ascontiguousarray(rgb[:, :, :3], dtype=np.uint8)
    if float(rgb.mean()) < 30.0:
        raise RuntimeError(f"preview appears too dark: mean RGB={float(rgb.mean()):.2f}")

    output = ARGS.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(output, format="PNG", optimize=False)
    if output.stat().st_size < 150_000:
        raise RuntimeError(f"preview PNG is unexpectedly small: {output.stat().st_size} bytes")

    return {
        "stage": str(ARGS.stage.resolve()),
        "root_layer": stage.GetRootLayer().realPath,
        "bracket_bbox_min_m": list(bounds_min),
        "bracket_bbox_max_m": list(bounds_max),
        "camera_position_m": list(camera_position),
        "camera_target_m": list(center),
        "resolution": [ARGS.width, ARGS.height],
        "rgb_mean": float(rgb.mean()),
        "output": str(output),
        "output_bytes": output.stat().st_size,
    }


def main() -> int:
    try:
        report = render()
        for key, value in report.items():
            print(f"{key}={value}")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        APP.close()


if __name__ == "__main__":
    raise SystemExit(main())
