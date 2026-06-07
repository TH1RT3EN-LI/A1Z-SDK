#!/usr/bin/env python3

import argparse
import os
import sys
import threading
from pathlib import Path

import carb
import omni.kit.app
import omni.kit.async_engine
import omni.timeline
import omni.usd
from importlib import import_module
from omni.kit.viewport.utility import capture_viewport_to_file, frame_viewport_prims, get_active_viewport
from omni.kit.viewport.utility.camera_state import ViewportCameraState
from pxr import Gf, Usd, UsdGeom

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

if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)

for site_dir in SDK_VENV_SITE_DIRS:
    if os.path.isdir(site_dir) and site_dir not in sys.path:
        sys.path.insert(0, site_dir)

from a1z.config import get_socket_path  # noqa: E402
from a1z.config import get_control_defaults  # noqa: E402
from a1z.robots.get_robot import create_a1z_robot  # noqa: E402
from a1z.robots.server import RobotServer  # noqa: E402


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _viewport_enabled() -> bool:
    if "A1Z_VIEWPORT_ENABLED" in os.environ:
        return _env_flag("A1Z_VIEWPORT_ENABLED", False)
    return bool(os.environ.get("DISPLAY"))


def _enable_local_d405_extension() -> None:
    try:
        app = omni.kit.app.get_app()
        ext_manager = app.get_extension_manager()
        ext_manager.set_extension_enabled_immediate("a1z.d405.runtime", True)
    except Exception as exc:
        carb.log_warn(f"A1Z D405 runtime extension enable failed: {exc}")


def _load_d405_runtime_services():
    try:
        services = import_module("a1z.d405.runtime.services")
        return services.attach_d405_asset, services.setup_d405_ros2_publishers
    except Exception as exc:
        carb.log_warn(f"A1Z D405 runtime services import failed: {exc}")
        return None, None


def _format_vec3(vec) -> str:
    return f"({float(vec[0]):.6f}, {float(vec[1]):.6f}, {float(vec[2]):.6f})"


def _dump_d405_stage_state(stage, path: str) -> None:
    lines = []
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
    )
    for prim in stage.Traverse():
        prim_path = str(prim.GetPath())
        if "D405" not in prim_path and "d405" not in prim_path:
            continue
        lines.append(f"path={prim_path}")
        lines.append(f"type={prim.GetTypeName()}")
        lines.append(f"active={prim.IsActive()} loaded={prim.IsLoaded()} valid={prim.IsValid()}")
        if prim.IsA(UsdGeom.Xformable):
            xformable = UsdGeom.Xformable(prim)
            lines.append("ops=" + ",".join(op.GetOpName() for op in xformable.GetOrderedXformOps()))
            local_result = xformable.GetLocalTransformation()
            if isinstance(local_result, tuple):
                local_transform = local_result[0]
                resets = local_result[1] if len(local_result) > 1 else False
            else:
                local_transform = local_result
                resets = False
            world_transform = cache.GetLocalToWorldTransform(prim)
            lines.append(f"local_translation={_format_vec3(local_transform.ExtractTranslation())}")
            lines.append(f"world_translation={_format_vec3(world_transform.ExtractTranslation())}")
            lines.append(f"resets_xform_stack={int(resets)}")
            try:
                world_bbox = bbox_cache.ComputeWorldBound(prim).ComputeAlignedBox()
                lines.append(f"world_bbox_min={_format_vec3(world_bbox.GetMin())}")
                lines.append(f"world_bbox_max={_format_vec3(world_bbox.GetMax())}")
            except Exception as exc:
                lines.append(f"world_bbox_error={exc}")
        for attr in prim.GetAttributes():
            name = attr.GetName()
            if name.startswith("xformOp:") or name in {"points", "faceVertexCounts"}:
                value = attr.Get()
                if name == "points" and value is not None:
                    lines.append(f"{name}_count={len(value)}")
                elif name == "faceVertexCounts" and value is not None:
                    lines.append(f"{name}_count={len(value)}")
                else:
                    lines.append(f"{name}={value}")
        lines.append("")
    try:
        Path(path).write_text("\n".join(lines), encoding="utf-8")
    except OSError as exc:
        carb.log_warn(f"Could not write D405 stage dump: {path}: {exc}")


async def _capture_d405_diagnostics(stage, viewport) -> None:
    dump_path = os.environ.get("A1Z_D405_STAGE_DUMP_PATH", "/workspace/A1Z/runtime/logs/d405-stage-dump.txt")
    _dump_d405_stage_state(stage, dump_path)
    if not _env_flag("A1Z_D405_VIEWPORT_CAPTURE_ENABLED", False):
        return
    if viewport is None:
        return
    capture_path = os.environ.get("A1Z_D405_VIEWPORT_CAPTURE_PATH", "/workspace/A1Z/runtime/logs/d405-viewport.png")
    try:
        await capture_viewport_to_file(viewport, file_path=capture_path, is_hdr=False).wait_for_result()
        carb.log_info(f"A1Z D405 viewport capture written: {capture_path}")
    except Exception as exc:
        carb.log_warn(f"A1Z D405 viewport capture failed: {exc}")


def parse_args():
    default_stage_path = os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd")
    isaac_defaults = get_control_defaults()["isaacsim"]
    parser = argparse.ArgumentParser(
        description="Open the prepared A1Z world USD and start the A1Z Isaac socket server."
    )
    parser.add_argument(
        "--stage-path",
        default=default_stage_path,
        help="Absolute path to the world USD.",
    )
    parser.add_argument(
        "--socket-path",
        default=os.environ.get("A1Z_SOCKET_PATH", get_socket_path()),
        help="Unix domain socket path for the A1Z server.",
    )
    parser.add_argument(
        "--articulation-root",
        default=os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", isaac_defaults["articulation_root_prim"]),
        help="Articulation root prim path inside the loaded stage.",
    )
    parser.add_argument(
        "--control-freq",
        type=int,
        default=int(os.environ.get("A1Z_ISAAC_CONTROL_FREQ_HZ", "60")),
        help="Control interpolation frequency for the Isaac backend.",
    )
    parser.add_argument(
        "--gravity-mode",
        dest="gravity_mode",
        action="store_true",
        help="Start Isaac arm backend in gravity-comp/effort mode.",
    )
    parser.add_argument(
        "--hold-mode",
        dest="gravity_mode",
        action="store_false",
        help="Start Isaac arm backend in position-hold mode.",
    )
    parser.add_argument(
        "--with-gripper",
        dest="with_gripper",
        action="store_true",
        help="Expose gripper control on the server.",
    )
    parser.add_argument(
        "--no-gripper",
        dest="with_gripper",
        action="store_false",
        help="Disable gripper control on the server.",
    )
    parser.set_defaults(
        with_gripper=_env_flag("A1Z_WITH_GRIPPER", True),
        gravity_mode=_env_flag("A1Z_ISAAC_GRAVITY_MODE", False),
    )
    args, extras = parser.parse_known_args()
    for token in extras:
        if token.endswith(".usd"):
            args.stage_path = token
            break
    return args


async def open_world(stage_path: str):
    _enable_local_d405_extension()
    attach_d405_asset, setup_d405_ros2_publishers = _load_d405_runtime_services()
    success, error = await omni.usd.get_context().open_stage_async(stage_path)
    if not success:
        raise RuntimeError(f"Failed to open stage {stage_path}: {error}")

    app = omni.kit.app.get_app()
    for _ in range(10):
        await app.next_update_async()

    stage = omni.usd.get_context().get_stage()
    d405_attachment = None
    if _env_flag("A1Z_D405_ENABLED", _viewport_enabled()):
        if attach_d405_asset is not None:
            d405_attachment = attach_d405_asset(stage)
        else:
            carb.log_warn("A1Z D405 runtime extension services unavailable; skipping D405 attachment.")
    else:
        carb.log_info("A1Z D405 attachment disabled for this startup.")

    viewport = None
    if _viewport_enabled():
        for _ in range(600):
            viewport = get_active_viewport()
            if viewport is not None and viewport.stage is not None:
                break
            await app.next_update_async()

    if not _viewport_enabled():
        carb.log_info("A1Z viewport operations disabled for headless startup.")
    elif viewport is None or viewport.stage is None:
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

    if _env_flag("A1Z_D405_ROS2_ENABLED", True):
        if setup_d405_ros2_publishers is not None:
            setup_d405_ros2_publishers(d405_attachment)
        else:
            carb.log_warn("A1Z D405 runtime extension services unavailable; skipping D405 ROS2 publishers.")
    else:
        carb.log_info("A1Z D405 ROS2 publishers disabled by A1Z_D405_ROS2_ENABLED.")

    carb.log_info(f"A1Z world opened: {stage_path}")
    return d405_attachment, viewport


async def startup():
    args = parse_args()
    app = omni.kit.app.get_app()
    server_thread = None
    server = None
    robot = None
    d405_attachment = None
    viewport = None
    d405_diagnostics_written = False

    try:
        d405_attachment, viewport = await open_world(args.stage_path)
        for _ in range(10):
            await app.next_update_async()

        timeline = omni.timeline.get_timeline_interface()
        if not timeline.is_playing():
            timeline.play()
            for _ in range(5):
                await app.next_update_async()

        robot = create_a1z_robot(
            backend="isaacsim",
            control_freq_hz=args.control_freq,
            with_gripper=args.with_gripper,
            articulation_root_prim=args.articulation_root,
            zero_gravity_mode=args.gravity_mode,
        )
        robot.start()

        server = RobotServer(robot, with_gripper=args.with_gripper)
        server_thread = threading.Thread(
            target=server.run,
            kwargs={"socket_path": args.socket_path},
            name="a1z_isaac_socket_server",
            daemon=True,
        )
        server_thread.start()

        carb.log_info(
            "A1Z Isaac server ready: "
            f"socket={args.socket_path} articulation={args.articulation_root} "
            f"gripper={'yes' if args.with_gripper else 'no'} "
            f"mode={'gravity_comp_effort' if args.gravity_mode else 'position_hold'}"
        )

        while not server._shutdown.is_set():
            try:
                robot.process_pending()
            except Exception as exc:
                carb.log_error(f"A1Z Isaac control loop failed: {exc}")
                raise
            if d405_attachment is not None:
                try:
                    d405_attachment.update(robot.get_joint_state()["pos"])
                    if not d405_diagnostics_written:
                        stage = omni.usd.get_context().get_stage()
                        await _capture_d405_diagnostics(stage, viewport)
                        d405_diagnostics_written = True
                except Exception as exc:
                    carb.log_error(f"A1Z D405 FK tracking disabled after update failure: {exc}")
                    d405_attachment = None
            await app.next_update_async()
    except Exception as exc:
        carb.log_error(f"A1Z Isaac startup failed: {exc}")
        raise
    finally:
        if server is not None:
            server._shutdown.set()
        if robot is not None:
            try:
                robot.stop()
            except Exception as exc:
                carb.log_warn(f"A1Z Isaac robot stop failed: {exc}")
        if server_thread is not None:
            server_thread.join(timeout=2.0)
        try:
            app.post_quit()
        except Exception as exc:
            carb.log_warn(f"A1Z Isaac app shutdown request failed: {exc}")
        carb.log_info("A1Z Isaac startup script finished.")


def main():
    omni.kit.async_engine.run_coroutine(startup())


main()
