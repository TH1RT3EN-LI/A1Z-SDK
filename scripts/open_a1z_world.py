#!/usr/bin/env python3

import argparse
import os

import carb
import omni.kit.app
import omni.kit.async_engine
import omni.usd
from omni.kit.viewport.utility import frame_viewport_prims, get_active_viewport
from omni.kit.viewport.utility.camera_state import ViewportCameraState
from pxr import Gf


def parse_args():
    default_stage_path = os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd")
    parser = argparse.ArgumentParser(
        description="Open the prepared A1Z world USD for inspection only. This script does not start the A1Z control server."
    )
    parser.add_argument(
        "--stage-path",
        default=default_stage_path,
        help="Absolute path to the world USD.",
    )
    args, extras = parser.parse_known_args()
    for token in extras:
        if token.endswith(".usd"):
            args.stage_path = token
            break
    return args


async def open_world(stage_path):
    success, error = await omni.usd.get_context().open_stage_async(stage_path)
    if not success:
        carb.log_error(f"Failed to open stage {stage_path}: {error}")
        return

    app = omni.kit.app.get_app()
    for _ in range(10):
        await app.next_update_async()

    viewport = None
    for _ in range(600):
        viewport = get_active_viewport()
        if viewport is not None and viewport.stage is not None:
            break
        await app.next_update_async()

    if viewport is None or viewport.stage is None:
        carb.log_warn("Active viewport was not ready; camera framing skipped.")
    else:
        try:
            framed = frame_viewport_prims(viewport, ["/World/A1Z_G1Z"])
            camera_state = ViewportCameraState(viewport=viewport)
            camera_state.set_position_world(Gf.Vec3d(1.4, -1.6, 1.1), True)
            camera_state.set_target_world(Gf.Vec3d(0.0, 0.0, 0.35), True)
            carb.log_info(f"A1Z viewport framing applied: framed={framed} camera={viewport.camera_path}")
        except Exception as exc:
            carb.log_warn(f"Viewport camera framing skipped: {exc}")

    carb.log_info(f"A1Z world opened: {stage_path}")


def main():
    args = parse_args()
    omni.kit.async_engine.run_coroutine(open_world(args.stage_path))


main()
