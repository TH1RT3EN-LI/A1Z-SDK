#!/usr/bin/env python3

"""Collect runtime D405 and base-link diagnostics inside an Isaac headless session."""

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
from a1z_ext.runtime.d405.pose import camera_to_target_matrix_from_usd
from a1z_ext.robots.get_robot import get_a1z_isaacsim_robot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug the Isaac-hosted D405 runtime state.")
    parser.add_argument(
        "--stage-path",
        default=os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd"),
        help="World USD path to open.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("A1Z_D405_DEBUG_OUTPUT_DIR", "/workspace/A1Z/runtime/d405_runtime_debug"),
        help="Directory for runtime diagnostics.",
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


def _gf_matrix_to_np(matrix) -> np.ndarray:
    return np.array([[float(matrix[row][col]) for col in range(4)] for row in range(4)], dtype=np.float64).T


def _rigidize(transform: np.ndarray) -> np.ndarray:
    rigid = np.asarray(transform, dtype=np.float64).copy()
    rotation_scale = rigid[:3, :3]
    u, _, vh = np.linalg.svd(rotation_scale)
    rotation = u @ vh
    if np.linalg.det(rotation) < 0.0:
        u[:, -1] *= -1.0
        rotation = u @ vh
    rigid[:3, :3] = rotation
    rigid[3, :] = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return rigid


def _matrix_payload(transform: np.ndarray) -> dict[str, object]:
    t = np.asarray(transform, dtype=np.float64)
    rot = t[:3, :3]
    sy = math.hypot(float(rot[0, 0]), float(rot[1, 0]))
    singular = sy < 1e-9
    if not singular:
        roll = math.degrees(math.atan2(float(rot[2, 1]), float(rot[2, 2])))
        pitch = math.degrees(math.atan2(float(-rot[2, 0]), sy))
        yaw = math.degrees(math.atan2(float(rot[1, 0]), float(rot[0, 0])))
    else:
        roll = math.degrees(math.atan2(float(-rot[1, 2]), float(rot[1, 1])))
        pitch = math.degrees(math.atan2(float(-rot[2, 0]), sy))
        yaw = 0.0
    return {
        "matrix": [[float(v) for v in row] for row in t.tolist()],
        "xyz_m": [float(v) for v in t[:3, 3].tolist()],
        "rpy_deg": [roll, pitch, yaw],
    }


def _world_transform(stage, prim_path: str) -> dict[str, object]:
    from pxr import Usd, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return {"valid": False, "path": prim_path}
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    transform = _rigidize(_gf_matrix_to_np(cache.GetLocalToWorldTransform(prim)))
    payload = _matrix_payload(transform)
    payload["valid"] = True
    payload["path"] = prim_path
    payload["type_name"] = prim.GetTypeName()
    return payload


def _local_transform(stage, prim_path: str) -> dict[str, object]:
    from pxr import Usd, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return {"valid": False, "path": prim_path}
    xformable = UsdGeom.Xformable(prim)
    local = xformable.GetLocalTransformation(Usd.TimeCode.Default())
    payload = _matrix_payload(_rigidize(_gf_matrix_to_np(local)))
    payload["valid"] = True
    payload["path"] = prim_path
    payload["type_name"] = prim.GetTypeName()
    payload["resets_xform_stack"] = bool(xformable.GetResetXformStack())
    return payload


def _xform_ops(stage, prim_path: str) -> dict[str, object]:
    from pxr import Gf, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return {"valid": False, "path": prim_path}
    xformable = UsdGeom.Xformable(prim)
    ops_payload: list[dict[str, object]] = []
    for op in xformable.GetOrderedXformOps():
        value = op.Get()
        if isinstance(value, Gf.Matrix4d):
            serialized = _matrix_payload(_rigidize(_gf_matrix_to_np(value)))
        elif isinstance(value, (Gf.Quatd, Gf.Quatf, Gf.Quaternion)):
            imaginary = value.GetImaginary()
            serialized = {
                "real": float(value.GetReal()),
                "imaginary": [float(imaginary[0]), float(imaginary[1]), float(imaginary[2])],
            }
        elif hasattr(value, "__len__"):
            serialized = [float(v) for v in value]
        else:
            serialized = value
        ops_payload.append(
            {
                "name": op.GetOpName(),
                "type": str(op.GetOpType()),
                "value": serialized,
            }
        )
    return {
        "valid": True,
        "path": prim_path,
        "ops": ops_payload,
    }


def _edit_target_payload(stage) -> dict[str, object]:
    edit_target = stage.GetEditTarget()
    layer = edit_target.GetLayer()
    root_layer = stage.GetRootLayer()
    session_layer = stage.GetSessionLayer()
    return {
        "edit_target_identifier": "" if layer is None else str(layer.identifier),
        "root_layer_identifier": "" if root_layer is None else str(root_layer.identifier),
        "session_layer_identifier": "" if session_layer is None else str(session_layer.identifier),
    }


def _collect_base_link_candidates(stage) -> list[dict[str, object]]:
    from pxr import Usd

    results: list[dict[str, object]] = []
    for root_path in ("/World/A1Z_G1Z/Geometry", "/World/A1Z_G1Z", "/World"):
        root = stage.GetPrimAtPath(root_path)
        if not root.IsValid():
            continue
        for prim in Usd.PrimRange(root):
            if prim.GetName() != "base_link":
                continue
            path = prim.GetPath().pathString
            item = _world_transform(stage, path)
            item["search_root"] = root_path
            results.append(item)
    dedup: dict[str, dict[str, object]] = {}
    for item in results:
        dedup[item["path"]] = item
    return list(dedup.values())


async def _step_app(frames: int) -> None:
    app = omni.kit.app.get_app()
    for _ in range(max(0, int(frames))):
        await app.next_update_async()


async def startup() -> None:
    args, _extras = _build_parser().parse_known_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    error_path = output_dir / "error.txt"
    if error_path.exists():
        error_path.unlink()

    report: dict[str, object] = {
        "stage_path": args.stage_path,
        "articulation_root": args.articulation_root,
        "env": {
            key: os.environ.get(key, "")
            for key in (
                "A1Z_D405_PARENT_PRIM",
                "A1Z_D405_FALLBACK_PARENT_PRIM",
                "A1Z_D405_FK_FRAME",
                "A1Z_D405_STAGE_MOUNT_OFFSET_XYZ_M",
                "A1Z_D405_STAGE_MOUNT_RPY_DEG",
                "A1Z_D405_STAGE_RECTIFY_RPY_DEG",
                "A1Z_D405_STAGE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M",
                "A1Z_D405_STAGE_RECTIFIED_TO_OPTICAL_RPY_DEG",
            )
        },
    }

    robot = None
    camera = None
    try:
        success, error = await omni.usd.get_context().open_stage_async(args.stage_path)
        if not success:
            raise RuntimeError(f"Failed to open stage {args.stage_path}: {error}")
        await _step_app(args.warmup_frames)

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("No active stage after open_stage_async")
        report["edit_target_after_open"] = _edit_target_payload(stage)
        report["base_link_candidates_before_attach"] = _collect_base_link_candidates(stage)

        attachment = attach_d405_wrist_camera(stage)
        if attachment is None:
            raise RuntimeError("attach_d405_wrist_camera returned None")
        report["edit_target_after_attach"] = _edit_target_payload(stage)
        report["camera_paths"] = dict(attachment.camera_paths)
        report["base_link_candidates_after_attach"] = _collect_base_link_candidates(stage)

        from isaacsim.core.api import World
        from isaacsim.sensors.camera import Camera
        import omni.replicator.core as rep

        world = World(stage_units_in_meters=1.0)
        world.reset()
        report["edit_target_after_world_reset"] = _edit_target_payload(stage)
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
        joint_pos = robot.get_joint_state()["pos"]
        attachment.update(joint_pos)
        report["edit_target_after_attachment_update"] = _edit_target_payload(stage)
        mount_path = attachment.mount_path.pathString
        link_path = mount_path
        report["mount_world_immediate_after_update"] = _world_transform(stage, mount_path)
        report["mount_local_immediate_after_update"] = _local_transform(stage, mount_path)
        report["mount_ops_immediate_after_update"] = _xform_ops(stage, mount_path)
        report["link_world_immediate_after_update"] = _world_transform(stage, link_path)
        report["link_local_immediate_after_update"] = _local_transform(stage, link_path)
        report["link_ops_immediate_after_update"] = _xform_ops(stage, link_path)
        await _step_app(2)

        color_camera_path = str(attachment.camera_paths.get("color") or "")
        depth_camera_path = str(attachment.camera_paths.get("depth") or "")
        report["base_link_candidates_after_robot_start"] = _collect_base_link_candidates(stage)
        report["mount_world"] = _world_transform(stage, mount_path)
        report["mount_local"] = _local_transform(stage, mount_path)
        report["mount_ops"] = _xform_ops(stage, mount_path)
        report["link_world"] = _world_transform(stage, link_path)
        report["link_local"] = _local_transform(stage, link_path)
        report["link_ops"] = _xform_ops(stage, link_path)
        report["camera_world"] = _world_transform(stage, color_camera_path)
        report["depth_camera_world"] = _world_transform(stage, depth_camera_path)
        report["camera_to_robot_base_frame"] = _matrix_payload(
            camera_to_target_matrix_from_usd(
                camera_prim_path=color_camera_path,
                target_frame_id="robot_base_frame",
            )
        )
        report["camera_to_base_link"] = _matrix_payload(
            camera_to_target_matrix_from_usd(
                camera_prim_path=color_camera_path,
                target_frame_id="base_link",
            )
        )

        camera = Camera(
            prim_path=color_camera_path,
            resolution=(int(args.width), int(args.height)),
        )
        camera.initialize(attach_rgb_annotator=True)
        camera.add_distance_to_image_plane_to_frame()
        await _step_app(int(args.post_camera_warmup_frames))
        rgb = np.asarray(camera.get_rgb(), dtype=np.uint8)
        depth = np.asarray(camera.get_depth(), dtype=np.float64)
        if depth.ndim == 3 and depth.shape[2] == 1:
            depth = depth[:, :, 0]
        report["rgb_stats"] = {
            "shape": list(rgb.shape),
            "min": int(rgb.min()) if rgb.size else None,
            "max": int(rgb.max()) if rgb.size else None,
            "mean": float(rgb.mean()) if rgb.size else None,
        }
        finite = np.isfinite(depth)
        report["depth_stats"] = {
            "shape": list(depth.shape),
            "finite_ratio": float(finite.mean()) if depth.size else None,
            "min": float(depth[finite].min()) if finite.any() else None,
            "max": float(depth[finite].max()) if finite.any() else None,
        }
        render_product = rep.create.render_product(color_camera_path, (int(args.width), int(args.height)))
        rep_rgb_annot = rep.AnnotatorRegistry.get_annotator("rgb")
        rep_depth_annot = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
        rep_rgb_annot.attach(render_product)
        rep_depth_annot.attach(render_product)
        await rep.orchestrator.step_async()
        rep_rgb = rep_rgb_annot.get_data()
        rep_depth = rep_depth_annot.get_data()
        rep_rgb_annot.detach()
        rep_depth_annot.detach()
        render_product.destroy()
        rep_rgb_np = np.asarray(rep_rgb)
        rep_depth_np = np.asarray(rep_depth, dtype=np.float64)
        if rep_depth_np.ndim == 3 and rep_depth_np.shape[2] == 1:
            rep_depth_np = rep_depth_np[:, :, 0]
        rep_finite = np.isfinite(rep_depth_np)
        report["replicator_rgb_stats"] = {
            "shape": list(rep_rgb_np.shape),
            "min": int(rep_rgb_np.min()) if rep_rgb_np.size else None,
            "max": int(rep_rgb_np.max()) if rep_rgb_np.size else None,
            "mean": float(rep_rgb_np.mean()) if rep_rgb_np.size else None,
        }
        report["replicator_depth_stats"] = {
            "shape": list(rep_depth_np.shape),
            "finite_ratio": float(rep_finite.mean()) if rep_depth_np.size else None,
            "min": float(rep_depth_np[rep_finite].min()) if rep_finite.any() else None,
            "max": float(rep_depth_np[rep_finite].max()) if rep_finite.any() else None,
        }
        np.save(output_dir / "rgb.npy", rgb)
        np.save(output_dir / "depth.npy", depth)
        np.save(output_dir / "replicator_rgb.npy", rep_rgb_np)
        np.save(output_dir / "replicator_depth.npy", rep_depth_np)

        with (output_dir / "report.json").open("w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=True, indent=2)
        print(json.dumps(report, ensure_ascii=True, indent=2))
    except Exception as exc:
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        carb.log_error(f"D405 runtime debug failed: {exc}")
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
