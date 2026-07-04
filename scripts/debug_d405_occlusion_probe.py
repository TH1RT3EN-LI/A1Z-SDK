#!/usr/bin/env python3

"""Probe which local geometry is occluding the Isaac-hosted D405 view."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
from pathlib import Path

import carb
import numpy as np
import omni.kit.app
import omni.kit.async_engine
import omni.usd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.dirname(__file__)
SDK_DIR = os.path.join(ROOT_DIR, "vendor", "GALAXEA-A1Z")
SDK_VENV_DIR = os.environ.get("A1Z_SDK_VENV_DIR", "/home/ubuntu/.venvs/a1z-sdk")
SDK_VENV_SITE_DIRS = [
    os.path.join(SDK_VENV_DIR, "lib", "python3.11", "site-packages"),
    os.path.join(
        SDK_VENV_DIR,
        "lib",
        "python3.11",
        "site-packages",
        "cmeel.prefix",
        "lib",
        "python3.11",
        "site-packages",
    ),
]

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)
for site_dir in SDK_VENV_SITE_DIRS:
    if os.path.isdir(site_dir) and site_dir not in sys.path:
        sys.path.insert(0, site_dir)

from a1z_ext.runtime.d405 import attach_d405_wrist_camera
from a1z_ext.robots.get_robot import get_a1z_isaacsim_robot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe D405 self-occlusion inside Isaac headless.")
    parser.add_argument(
        "--stage-path",
        default=os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd"),
        help="World USD path to open.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("A1Z_D405_OCCLUSION_OUTPUT_DIR", "/workspace/A1Z/runtime/d405_occlusion_probe"),
        help="Directory for probe artifacts.",
    )
    parser.add_argument(
        "--articulation-root",
        default=os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", "/World/A1Z_G1Z/Geometry"),
        help="Articulation root prim path.",
    )
    parser.add_argument("--width", type=int, default=int(os.environ.get("A1Z_D405_WIDTH", "1280")))
    parser.add_argument("--height", type=int, default=int(os.environ.get("A1Z_D405_HEIGHT", "720")))
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--post-camera-warmup-frames", type=int, default=45)
    parser.add_argument("--control-freq", type=int, default=int(os.environ.get("A1Z_ISAAC_CONTROL_FREQ_HZ", "60")))
    return parser


async def _step_app(frames: int) -> None:
    app = omni.kit.app.get_app()
    for _ in range(max(0, int(frames))):
        await app.next_update_async()


def _snapshot(camera, output_dir: Path, tag: str) -> dict[str, object]:
    rgb = np.asarray(camera.get_rgb(), dtype=np.uint8)
    if rgb.ndim == 3 and rgb.shape[2] > 3:
        rgb = rgb[:, :, :3]
    depth = np.asarray(camera.get_depth(), dtype=np.float32)
    if depth.ndim == 3 and depth.shape[2] == 1:
        depth = depth[:, :, 0]
    np.save(output_dir / f"rgb_{tag}.npy", rgb)
    np.save(output_dir / f"depth_{tag}.npy", depth)
    finite = np.isfinite(depth)
    center_y = rgb.shape[0] // 2
    center_x = rgb.shape[1] // 2
    center_depth = float(depth[center_y, center_x])
    return {
        "rgb_mean": float(rgb.mean()) if rgb.size else None,
        "rgb_center": rgb[center_y, center_x].tolist() if rgb.size else None,
        "rgb_p10": rgb[center_y, rgb.shape[1] // 10].tolist() if rgb.size else None,
        "rgb_p90": rgb[center_y, int(rgb.shape[1] * 0.9)].tolist() if rgb.size else None,
        "depth_finite_ratio": float(finite.mean()) if depth.size else None,
        "depth_center": center_depth if math.isfinite(center_depth) else None,
        "depth_p10": float(depth[center_y, depth.shape[1] // 10])
        if math.isfinite(float(depth[center_y, depth.shape[1] // 10]))
        else None,
        "depth_p90": float(depth[center_y, int(depth.shape[1] * 0.9)])
        if math.isfinite(float(depth[center_y, int(depth.shape[1] * 0.9)]))
        else None,
    }


def _set_visibility(stage, prim_paths: list[str], *, visible: bool) -> None:
    from pxr import UsdGeom

    token = UsdGeom.Tokens.inherited if visible else UsdGeom.Tokens.invisible
    for prim_path in prim_paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            continue
        imageable = UsdGeom.Imageable(prim)
        imageable.CreateVisibilityAttr().Set(token)


async def startup() -> None:
    from isaacsim.core.api import World
    from isaacsim.sensors.camera import Camera

    args, _extras = _build_parser().parse_known_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    error_path = output_dir / "error.txt"
    if error_path.exists():
        error_path.unlink()

    report: dict[str, object] = {}
    camera = None
    robot = None
    try:
        success, error = await omni.usd.get_context().open_stage_async(args.stage_path)
        if not success:
            raise RuntimeError(f"Failed to open stage {args.stage_path}: {error}")
        await _step_app(args.warmup_frames)

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("No active stage after open_stage_async")

        attachment = attach_d405_wrist_camera(stage)
        if attachment is None:
            raise RuntimeError("attach_d405_wrist_camera returned None")

        world = World(stage_units_in_meters=1.0)
        world.reset()
        await _step_app(5)

        robot = get_a1z_isaacsim_robot(
            control_freq_hz=int(args.control_freq),
            with_gripper=True,
            articulation_root_prim=args.articulation_root,
            zero_gravity_mode=False,
        )
        robot.start()
        await _step_app(2)
        robot.process_pending()
        attachment.update(robot.get_joint_state()["pos"])
        await _step_app(2)

        color_camera_path = str(attachment.camera_paths.get("color") or "")
        if not color_camera_path:
            raise RuntimeError(f"Missing color camera path: {attachment.camera_paths}")
        camera = Camera(
            prim_path=color_camera_path,
            resolution=(int(args.width), int(args.height)),
        )
        camera.initialize(attach_rgb_annotator=True)
        camera.add_distance_to_image_plane_to_frame()
        await _step_app(int(args.post_camera_warmup_frames))

        d405_body_paths = [
            "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/d405_link",
        ]
        local_wrist_paths = [
            "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6",
            "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/arm_link6",
            "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_left_link",
            "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_rIght_link",
        ]

        report["baseline"] = _snapshot(camera, output_dir, "baseline")

        _set_visibility(stage, d405_body_paths, visible=False)
        await _step_app(5)
        report["hide_d405_body"] = _snapshot(camera, output_dir, "hide_d405_body")
        _set_visibility(stage, d405_body_paths, visible=True)
        await _step_app(5)

        _set_visibility(stage, local_wrist_paths, visible=False)
        await _step_app(5)
        report["hide_wrist_links"] = _snapshot(camera, output_dir, "hide_wrist_links")
        _set_visibility(stage, local_wrist_paths, visible=True)
        await _step_app(5)

        (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True, indent=2))
    except Exception as exc:
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        carb.log_error(f"D405 occlusion probe failed: {exc}")
        raise
    finally:
        if camera is not None:
            try:
                camera.destroy()
            except Exception:
                pass
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        try:
            omni.kit.app.get_app().post_quit()
        except Exception:
            pass


def main() -> None:
    omni.kit.async_engine.run_coroutine(startup())


if __name__ == "__main__":
    main()
