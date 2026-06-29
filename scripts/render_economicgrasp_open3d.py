#!/usr/bin/env python3

"""Render EconomicGrasp results with GraspNetAPI and Open3D."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import types
import sys
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render EconomicGrasp grasps with Open3D.")
    parser.add_argument("--points", required=True, help="Path to point cloud .npy in camera frame")
    parser.add_argument("--colors", required=True, help="Path to RGB .npy or colors .npy")
    parser.add_argument("--depth", default="", help="Optional depth_m.npy used to mask image colors to valid points")
    parser.add_argument("--mask", default="", help="Optional selected_mask.npy used to keep only target-object points")
    parser.add_argument("--intrinsics", default="", help="Optional intrinsics.json used for camera-view rendering")
    parser.add_argument("--predictions", required=True, help="Path to raw_predictions.npy [N,17]")
    parser.add_argument("--output-image", required=True, help="Output rendered image path")
    parser.add_argument("--output-json", default="", help="Optional render metadata JSON path")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--best-only", action="store_true")
    parser.add_argument("--no-grippers", action="store_true", help="Render only the point cloud without grasp geometries")
    parser.add_argument("--point-size", type=float, default=3.0)
    parser.add_argument("--gripper-color", default="[1.0, 0.0, 0.0]")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--crop-radius-m", type=float, default=0.0, help="Keep only points within this radius of selected grasp centers")
    parser.add_argument("--crop-padding-m", type=float, default=0.02, help="Extra padding added to auto crop radius")
    parser.add_argument("--max-points", type=int, default=120000, help="Randomly subsample cropped cloud to this many points")
    parser.add_argument("--camera-mode", choices=("auto_scene", "grasp_focus"), default="grasp_focus")
    parser.add_argument("--camera-view", action="store_true", help="Render from the original camera optical view using intrinsics")
    parser.add_argument("--gripper-wireframe", action="store_true", help="Render grippers as red wireframes")
    parser.add_argument("--gripper-line-width", type=float, default=3.0)
    parser.add_argument("--camera-lookat", default="", help="Optional [x,y,z]")
    parser.add_argument("--camera-front", default="", help="Optional [x,y,z]")
    parser.add_argument("--camera-up", default="", help="Optional [x,y,z]")
    parser.add_argument("--camera-zoom", type=float, default=0.7)
    parser.add_argument("--background", default="[0.10, 0.10, 0.12, 1.0]")
    return parser


def _parse_json_vector(raw: str, *, expected_len: int | None = None) -> list[float]:
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"expected JSON list: {raw}")
    result = [float(item) for item in value]
    if expected_len is not None and len(result) != expected_len:
        raise ValueError(f"expected length {expected_len}, got {len(result)} from {raw}")
    return result


def _load_points(path: str | Path) -> np.ndarray:
    points = np.load(Path(path)).astype(np.float64, copy=False)
    points = points.reshape(-1, 3)
    if points.shape[0] == 0:
        raise ValueError("points array is empty")
    return np.ascontiguousarray(points)


def _load_colors(path: str | Path) -> np.ndarray:
    colors = np.load(Path(path))
    if colors.ndim == 3:
        colors = colors.reshape(-1, colors.shape[2])
    colors = colors.reshape(-1, colors.shape[-1])
    if colors.shape[1] < 3:
        raise ValueError(f"colors must have at least 3 channels, got {colors.shape}")
    colors = colors[:, :3].astype(np.float64, copy=False)
    if colors.max() > 1.0:
        colors = colors / 255.0
    colors = np.clip(colors, 0.0, 1.0)
    return np.ascontiguousarray(colors)


def _flatten_image_colors(path: str | Path) -> np.ndarray:
    colors = np.load(Path(path))
    if colors.ndim != 3 or colors.shape[2] < 3:
        raise ValueError(f"image colors must have shape (H, W, >=3), got {colors.shape}")
    flat = colors[:, :, :3].reshape(-1, 3).astype(np.float64, copy=False)
    if flat.max() > 1.0:
        flat = flat / 255.0
    return np.ascontiguousarray(np.clip(flat, 0.0, 1.0))


def _depth_valid_mask(depth_path: str | Path) -> np.ndarray:
    depth = np.load(Path(depth_path)).astype(np.float64, copy=False)
    if depth.ndim != 2:
        raise ValueError(f"depth must be 2D, got {depth.shape}")
    valid = np.isfinite(depth) & (depth > 0.05)
    return valid.reshape(-1)


def _load_mask_flat(mask_path: str | Path) -> np.ndarray:
    mask = np.load(Path(mask_path))
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got {mask.shape}")
    return np.asarray(mask, dtype=bool).reshape(-1)


def _load_predictions(path: str | Path) -> np.ndarray:
    predictions = np.load(Path(path)).astype(np.float64, copy=False).reshape(-1, 17)
    if predictions.shape[0] == 0:
        raise ValueError("predictions array is empty")
    return predictions


def _load_intrinsics(path_arg: str) -> dict[str, float] | None:
    if not path_arg:
        return None
    payload = json.loads(Path(path_arg).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"intrinsics must be a JSON object: {path_arg}")
    return {
        "fx": float(payload["fx"]),
        "fy": float(payload["fy"]),
        "cx": float(payload["cx"]),
        "cy": float(payload["cy"]),
    }


def _resolve_camera(
    *,
    points: np.ndarray,
    focus_center: np.ndarray | None,
    focus_rotation: np.ndarray | None,
    mode: str,
    lookat_raw: str,
    front_raw: str,
    up_raw: str,
    zoom: float,
) -> dict[str, list[float] | float]:
    centroid = points.mean(axis=0)
    extent = np.maximum(points.max(axis=0) - points.min(axis=0), 1e-6)
    default_lookat = centroid.copy()
    default_front = np.array([-0.45, -0.35, -0.82], dtype=np.float64)
    default_up = np.array([0.0, -1.0, 0.0], dtype=np.float64)
    if mode == "grasp_focus" and focus_center is not None:
        default_lookat = focus_center.astype(np.float64).copy()
        if focus_rotation is not None and focus_rotation.shape == (3, 3):
            opening = focus_rotation[:, 1]
            approach = focus_rotation[:, 0]
            height = focus_rotation[:, 2]
            front_vec = -(0.75 * approach + 0.45 * height + 0.20 * opening)
            if np.linalg.norm(front_vec) > 1e-9:
                default_front = front_vec / np.linalg.norm(front_vec)
            up_vec = -height
            if np.linalg.norm(up_vec) > 1e-9:
                default_up = up_vec / np.linalg.norm(up_vec)
    return {
        "lookat": _parse_json_vector(lookat_raw, expected_len=3) if lookat_raw else [float(v) for v in default_lookat.tolist()],
        "front": _parse_json_vector(front_raw, expected_len=3) if front_raw else [float(v) for v in default_front.tolist()],
        "up": _parse_json_vector(up_raw, expected_len=3) if up_raw else [float(v) for v in default_up.tolist()],
        "zoom": float(zoom),
        "extent_xyz": [float(v) for v in extent.tolist()],
    }


def _crop_points_near_grasps(
    *,
    points: np.ndarray,
    colors: np.ndarray,
    grasp_array: np.ndarray,
    crop_radius_m: float,
    crop_padding_m: float,
    max_points: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if float(crop_radius_m) < 0.0:
        return points, colors, {"cropped": False, "crop_disabled": True}
    if grasp_array.shape[0] == 0:
        return points, colors, {"cropped": False}
    centers = grasp_array[:, 13:16].astype(np.float64, copy=False)
    widths = grasp_array[:, 1].astype(np.float64, copy=False)
    depths = grasp_array[:, 3].astype(np.float64, copy=False)
    auto_radius = float(max(np.max(widths) * 1.5, np.max(depths) * 4.0, 0.05) + float(crop_padding_m))
    radius = float(crop_radius_m) if float(crop_radius_m) > 0.0 else auto_radius
    deltas = points[:, None, :] - centers[None, :, :]
    distances = np.linalg.norm(deltas, axis=2)
    keep = np.min(distances, axis=1) <= radius
    points_kept = points[keep]
    colors_kept = colors[keep]
    if points_kept.shape[0] == 0:
        return points, colors, {
            "cropped": False,
            "crop_radius_m": radius,
            "crop_kept_points": 0,
            "crop_fallback": "empty_crop",
        }
    if int(max_points) > 0 and points_kept.shape[0] > int(max_points):
        rng = np.random.default_rng(0)
        indices = np.sort(rng.choice(points_kept.shape[0], size=int(max_points), replace=False))
        points_kept = points_kept[indices]
        colors_kept = colors_kept[indices]
    return points_kept, colors_kept, {
        "cropped": True,
        "crop_radius_m": radius,
        "crop_kept_points": int(points_kept.shape[0]),
        "crop_center_mean_xyz": [float(v) for v in centers.mean(axis=0).tolist()],
    }


def _load_grasp_group_class():
    try:
        from graspnetAPI.grasp import GraspGroup
        return GraspGroup
    except Exception:
        pass
    try:
        from graspnetAPI import GraspGroup
        return GraspGroup
    except Exception:
        pass

    candidates = []
    for prefix in sys.path:
        if not prefix:
            continue
        path = Path(prefix) / "graspnetAPI" / "grasp.py"
        if path.is_file():
            candidates.append(path)
    if not candidates:
        raise ImportError("unable to locate graspnetAPI/grasp.py for GraspGroup import")

    module_path = candidates[0]
    package_dir = module_path.parent
    package_name = "graspnetAPI"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_dir)]  # type: ignore[attr-defined]
        package.__file__ = str(package_dir / "__init__.py")
        sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(
        f"{package_name}.grasp",
        module_path,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"failed to load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.GraspGroup


def main() -> int:
    args = build_parser().parse_args()

    import open3d as o3d
    GraspGroup = _load_grasp_group_class()
    intrinsics = _load_intrinsics(args.intrinsics)
    if bool(args.camera_view) and intrinsics is None:
        raise ValueError("--camera-view requires --intrinsics")

    points = _load_points(args.points)
    colors_path = Path(args.colors)
    raw_colors = np.load(colors_path)
    if raw_colors.ndim == 3:
        colors = _flatten_image_colors(colors_path)
    else:
        colors = _load_colors(colors_path)
    valid_mask = None
    if args.depth:
        valid_mask = _depth_valid_mask(args.depth)
        if colors.shape[0] == valid_mask.shape[0]:
            colors = colors[valid_mask]
        elif colors.shape[0] != points.shape[0]:
            raise ValueError(
                "colors length does not match either full image pixels or point count: "
                f"{colors.shape[0]} vs valid_mask={valid_mask.shape[0]} vs points={points.shape[0]}"
            )
    if colors.shape[0] != points.shape[0]:
        raise ValueError(f"points/colors length mismatch: {points.shape[0]} vs {colors.shape[0]}")
    target_mask_meta: dict[str, Any] = {"mask_applied": False}
    if args.mask:
        if valid_mask is None:
            raise ValueError("--mask requires --depth so image-space mask can be aligned to valid points")
        mask_flat = _load_mask_flat(args.mask)
        if mask_flat.shape[0] != valid_mask.shape[0]:
            raise ValueError(f"mask/depth shape mismatch: {mask_flat.shape[0]} vs {valid_mask.shape[0]}")
        object_mask = mask_flat[valid_mask]
        if object_mask.shape[0] != points.shape[0]:
            raise ValueError(f"object mask/points mismatch: {object_mask.shape[0]} vs {points.shape[0]}")
        kept = int(np.count_nonzero(object_mask))
        target_mask_meta = {
            "mask_applied": True,
            "mask_path": str(Path(args.mask).resolve()),
            "mask_kept_points": kept,
            "mask_total_points": int(object_mask.shape[0]),
        }
        if kept > 0:
            points = points[object_mask]
            colors = colors[object_mask]
        else:
            target_mask_meta["mask_fallback"] = "empty_mask"
    predictions = _load_predictions(args.predictions)

    gg = GraspGroup(predictions)
    nms_used = False
    nms_error = ""
    if not bool(args.no_grippers):
        try:
            gg_nms = gg.nms()
        except Exception as exc:
            gg_nms = None
            nms_error = repr(exc)
        else:
            if gg_nms is not None:
                gg = gg_nms
                nms_used = True
        gg = gg.sort_by_score()
        if args.best_only:
            gg = gg[:1]
        elif int(args.top_k) > 0:
            gg = gg[: int(args.top_k)]
    else:
        gg = gg[:0]

    crop_meta: dict[str, Any] = {"cropped": False}
    points, colors, crop_meta = _crop_points_near_grasps(
        points=points,
        colors=colors,
        grasp_array=np.asarray(gg.grasp_group_array, dtype=np.float64).reshape(-1, 17),
        crop_radius_m=float(args.crop_radius_m),
        crop_padding_m=float(args.crop_padding_m),
        max_points=int(args.max_points),
    )

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.colors = o3d.utility.Vector3dVector(colors)

    grippers = [] if bool(args.no_grippers) else gg.to_open3d_geometry_list()
    gripper_color = _parse_json_vector(args.gripper_color, expected_len=3)
    for gripper in grippers:
        gripper.paint_uniform_color(gripper_color)
    gripper_geometries: list[Any] = []
    if bool(args.gripper_wireframe):
        for gripper in grippers:
            if isinstance(gripper, o3d.geometry.TriangleMesh):
                line = o3d.geometry.LineSet.create_from_triangle_mesh(gripper)
                line.paint_uniform_color(gripper_color)
                gripper_geometries.append(line)
            else:
                gripper_geometries.append(gripper)
    else:
        gripper_geometries = list(grippers)

    width = int(args.width)
    height = int(args.height)
    background = _parse_json_vector(args.background, expected_len=4)
    camera = _resolve_camera(
        points=points,
        focus_center=(None if len(gg) == 0 else np.asarray(gg.grasp_group_array[0, 13:16], dtype=np.float64)),
        focus_rotation=(None if len(gg) == 0 else np.asarray(gg.grasp_group_array[0, 4:13], dtype=np.float64).reshape(3, 3)),
        mode=args.camera_mode,
        lookat_raw=args.camera_lookat,
        front_raw=args.camera_front,
        up_raw=args.camera_up,
        zoom=float(args.camera_zoom),
    )

    geometries: list[Any] = [cloud, *gripper_geometries]
    output_image_path = Path(args.output_image).resolve()
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    ok = False
    render_backend = ""
    render_error = ""
    if hasattr(o3d.visualization, "rendering") and hasattr(o3d.visualization.rendering, "OffscreenRenderer"):
        try:
            renderer = o3d.visualization.rendering.OffscreenRenderer(width, height)
            scene = renderer.scene
            scene.set_background(np.asarray(background, dtype=np.float32))
            point_material = o3d.visualization.rendering.MaterialRecord()
            point_material.shader = "defaultUnlit"
            point_material.point_size = float(args.point_size)
            scene.add_geometry("cloud", cloud, point_material)
            line_material = o3d.visualization.rendering.MaterialRecord()
            line_material.shader = "unlitLine"
            line_material.line_width = float(args.gripper_line_width)
            mesh_material = o3d.visualization.rendering.MaterialRecord()
            mesh_material.shader = "defaultUnlit"
            mesh_material.base_color = np.asarray([gripper_color[0], gripper_color[1], gripper_color[2], 1.0], dtype=np.float32)
            for index, gripper in enumerate(gripper_geometries):
                material = line_material if isinstance(gripper, o3d.geometry.LineSet) else mesh_material
                scene.add_geometry(f"gripper_{index}", gripper, material)

            if bool(args.camera_view):
                fx = float(intrinsics["fx"])  # type: ignore[index]
                fy = float(intrinsics["fy"])  # type: ignore[index]
                cx = float(intrinsics["cx"])  # type: ignore[index]
                cy = float(intrinsics["cy"])  # type: ignore[index]
                intrinsic_matrix = np.array(
                    [
                        [fx, 0.0, cx],
                        [0.0, fy, cy],
                        [0.0, 0.0, 1.0],
                    ],
                    dtype=np.float64,
                )
                extrinsic = np.eye(4, dtype=np.float64)
                scene.camera.set_projection(
                    intrinsic_matrix,
                    0.01,
                    5.0,
                    float(width),
                    float(height),
                )
                eye = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                center = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                up = np.array([0.0, -1.0, 0.0], dtype=np.float32)
                scene.camera.look_at(center, eye, up)
            else:
                center = np.asarray(camera["lookat"], dtype=np.float32)
                front = np.asarray(camera["front"], dtype=np.float32)
                up = np.asarray(camera["up"], dtype=np.float32)
                extent = np.asarray(camera["extent_xyz"], dtype=np.float32)
                extent_scale = float(max(extent.max(), 1e-3))
                distance = max(0.08, 1.6 * extent_scale / max(float(camera["zoom"]), 1e-3))
                eye = center - front * distance
                scene.camera.look_at(center, eye, up)
            image = renderer.render_to_image()
            ok = bool(o3d.io.write_image(str(output_image_path), image))
            render_backend = "offscreen_renderer"
        except Exception as exc:
            render_error = repr(exc)
    if not ok:
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name="EconomicGrasp Results", width=width, height=height, visible=False)
        try:
            render_option = vis.get_render_option()
            if render_option is None:
                raise RuntimeError("Visualizer render option unavailable")
            render_option.background_color = np.asarray(background[:3], dtype=np.float64)
            render_option.point_size = float(args.point_size)
            for geometry in geometries:
                vis.add_geometry(geometry, reset_bounding_box=False)
            view = vis.get_view_control()
            if view is None:
                raise RuntimeError("Visualizer view control unavailable")
            view.set_front(np.asarray(camera["front"], dtype=np.float64))
            view.set_lookat(np.asarray(camera["lookat"], dtype=np.float64))
            view.set_up(np.asarray(camera["up"], dtype=np.float64))
            view.set_zoom(float(camera["zoom"]))
            vis.poll_events()
            vis.update_renderer()
            ok = bool(vis.capture_screen_image(str(output_image_path), do_render=True))
            render_backend = "visualizer"
        except Exception as exc:
            if not render_error:
                render_error = repr(exc)
        finally:
            vis.destroy_window()

    payload = {
        "points_path": str(Path(args.points).resolve()),
        "colors_path": str(Path(args.colors).resolve()),
        "depth_path": (str(Path(args.depth).resolve()) if args.depth else ""),
        "predictions_path": str(Path(args.predictions).resolve()),
        "output_image_path": str(output_image_path),
        "mask": target_mask_meta,
        "top_k": int(args.top_k),
        "best_only": bool(args.best_only),
        "no_grippers": bool(args.no_grippers),
        "camera_view": bool(args.camera_view),
        "intrinsics_path": (str(Path(args.intrinsics).resolve()) if args.intrinsics else ""),
        "selected_grasp_count": int(len(gg)),
        "point_count": int(points.shape[0]),
        "nms_used": bool(nms_used),
        "nms_error": nms_error,
        "camera": camera,
        "crop": crop_meta,
        "image_size": {"width": width, "height": height},
        "capture_ok": bool(ok),
        "render_backend": render_backend,
        "render_error": render_error,
    }
    if args.output_json:
        output_json_path = Path(args.output_json).resolve()
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
