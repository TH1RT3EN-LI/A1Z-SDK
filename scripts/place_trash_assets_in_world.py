#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

from isaacsim import SimulationApp


simulation_app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade  # noqa: E402


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_WORLD_USD = ROOT_DIR / "build" / "scenes" / "A1Z_G1Z_world.usd"
DEFAULT_MANIFEST = ROOT_DIR / "assets" / "trash_grasp_set" / "manifest_isaac_ycb.json"
DEFAULT_TRASH_ROOT = Sdf.Path("/World/TrashSet")
DEFAULT_MATERIALS_ROOT = Sdf.Path("/World/Looks/TrashSetMaterials")
DEFAULT_GLBS_DIR = ROOT_DIR / "assets" / "trash_grasp_set" / "raw" / "poly_pizza"
DEFAULT_USD_ASSET_ROOT = ROOT_DIR / "assets" / "trash_grasp_set" / "isaac_ycb"

# glTF assets are authored as Y-up. Rotate them so they sit on Isaac's Z-up ground.
Y_UP_TO_Z_UP = np.array(
    [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=np.float64,
)

OBJECT_LAYOUT = {
    "can_upright": {
        "position": (0.30, -0.12, 0.0),
        "yaw_deg": 0.0,
        "scale_mode": "height",
    },
    "can_crushed": {
        "position": (0.30, 0.00, 0.0),
        "yaw_deg": 28.0,
        "scale_mode": "horizontal_max",
    },
    "bottle_water": {
        "position": (0.30, 0.12, 0.0),
        "yaw_deg": -10.0,
        "scale_mode": "height",
    },
    "bottle_plastic": {
        "position": (0.42, -0.06, 0.0),
        "yaw_deg": 18.0,
        "scale_mode": "height",
    },
    "paper_debris": {
        "position": (0.42, 0.08, 0.0),
        "yaw_deg": -32.0,
        "scale_mode": "horizontal_max",
    },
}

CATEGORY_SURFACE = {
    "can": {"metallic": 0.72, "roughness": 0.36},
    "plastic_bottle": {"metallic": 0.02, "roughness": 0.48},
    "paper": {"metallic": 0.0, "roughness": 0.88},
    "tool": {"metallic": 0.08, "roughness": 0.58},
}

DEFAULT_COLLISION_APPROXIMATION = "convexHull"
DEFAULT_CONTACT_OFFSET_M = 0.0
DEFAULT_REST_OFFSET_M = 0.0
DEFAULT_GROUND_SURFACE_PAD_M = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bake the selected trash GLBs into the current Isaac world and place them on the ground."
    )
    parser.add_argument(
        "--world-usd",
        default=str(DEFAULT_WORLD_USD),
        help="Absolute path to the world USD to modify.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="Absolute path to the trash asset manifest JSON.",
    )
    parser.add_argument(
        "--trash-root",
        default=str(DEFAULT_TRASH_ROOT),
        help="Prim path where trash objects will be rebuilt.",
    )
    parser.add_argument(
        "--overlay-usda",
        default="",
        help="Optional USD layer path used to author TrashSet as a persistent overlay. Defaults next to the world USD.",
    )
    args, _ = parser.parse_known_args()
    return args


def _default_overlay_path(world_usd: Path) -> Path:
    return world_usd.with_name(f"{world_usd.stem}_trashset.usda")


def _make_relative_asset_path(path: Path, *, anchor_dir: Path) -> str:
    return os.path.relpath(path, start=anchor_dir).replace(os.sep, "/")


def _ensure_world_has_overlay(root_layer: Sdf.Layer, overlay_path: Path, *, world_usd: Path) -> bool:
    rel_overlay = _make_relative_asset_path(overlay_path, anchor_dir=world_usd.parent)
    if rel_overlay in root_layer.subLayerPaths:
        return False
    root_layer.subLayerPaths.append(rel_overlay)
    return True


def _remove_prim_from_layer(stage: Usd.Stage, layer: Sdf.Layer, prim_path: Sdf.Path) -> bool:
    if layer.GetPrimAtPath(str(prim_path)) is None:
        return False
    stage.SetEditTarget(layer)
    stage.RemovePrim(prim_path)
    return True


def _open_or_create_overlay_layer(path: Path) -> Sdf.Layer:
    path.parent.mkdir(parents=True, exist_ok=True)
    layer = Sdf.Layer.FindOrOpen(str(path))
    if layer is not None:
        return layer
    layer = Sdf.Layer.CreateNew(str(path))
    if layer is None:
        raise RuntimeError(f"Failed to create overlay layer: {path}")
    return layer


def _sanitize_name(name: str) -> str:
    safe = []
    for char in name:
        if char.isalnum() or char == "_":
            safe.append(char)
        else:
            safe.append("_")
    value = "".join(safe).strip("_")
    if not value:
        value = "item"
    if value[0].isdigit():
        value = f"_{value}"
    return value


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw


def _env_float(name: str, default: float) -> float:
    return float(_env_str(name, str(default)))


def _load_manifest(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assets = list(data.get("direct_assets", []))
    if not assets:
        raise RuntimeError(f"No direct_assets found in manifest: {path}")
    return assets


def _resolve_usd_asset_path(raw_path: str) -> Path:
    expanded = Path(os.path.expandvars(os.path.expanduser(raw_path)))
    if expanded.is_absolute():
        return expanded
    return (ROOT_DIR / expanded).resolve()


def _is_remote_asset_path(raw_path: str) -> bool:
    lowered = raw_path.lower()
    return lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("omniverse://")


def _rgba_from_trimesh(mesh: trimesh.Trimesh) -> tuple[float, float, float, float]:
    material = getattr(getattr(mesh, "visual", None), "material", None)
    color = None
    if material is not None:
        color = getattr(material, "baseColorFactor", None)
        if color is None:
            color = getattr(material, "main_color", None)
    if color is None:
        return (0.65, 0.65, 0.65, 1.0)

    color_array = np.asarray(color, dtype=np.float64).reshape(-1)
    if color_array.size < 3:
        return (0.65, 0.65, 0.65, 1.0)
    if color_array.max() > 1.0:
        color_array = color_array / 255.0
    if color_array.size == 3:
        return (float(color_array[0]), float(color_array[1]), float(color_array[2]), 1.0)
    return (
        float(color_array[0]),
        float(color_array[1]),
        float(color_array[2]),
        float(color_array[3]),
    )


def _iter_scene_meshes(scene: trimesh.Scene) -> list[trimesh.Trimesh]:
    meshes: list[trimesh.Trimesh] = []
    for item in scene.dump():
        if isinstance(item, trimesh.Trimesh) and len(item.vertices) > 0 and len(item.faces) > 0:
            meshes.append(item)
    if not meshes:
        raise RuntimeError("Scene did not contain any triangle meshes after load.")
    return meshes


def _compute_scale(raw_dims: np.ndarray, target_dims: np.ndarray, scale_mode: str) -> float:
    if np.any(raw_dims <= 0.0):
        raise RuntimeError(f"Non-positive raw bbox dimensions: {raw_dims.tolist()}")

    if scale_mode == "height":
        return float(target_dims[2] / raw_dims[2])
    if scale_mode == "horizontal_max":
        raw_horizontal = float(max(raw_dims[0], raw_dims[1]))
        target_horizontal = float(max(target_dims[0], target_dims[1]))
        return target_horizontal / raw_horizontal
    if scale_mode == "bbox_fit":
        return float(np.min(target_dims / raw_dims))
    raise ValueError(f"Unsupported scale mode: {scale_mode}")


def _make_preview_material(
    stage: Usd.Stage,
    material_path: Sdf.Path,
    rgba: tuple[float, float, float, float],
    category: str,
) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, material_path)
    shader = UsdShade.Shader.Define(stage, material_path.AppendChild("Shader"))
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgba[:3]))

    surface = CATEGORY_SURFACE.get(category, {"metallic": 0.05, "roughness": 0.6})
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(float(surface["metallic"]))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(float(surface["roughness"]))

    opacity = max(0.0, min(1.0, float(rgba[3])))
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)

    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def _create_visual_mesh(
    stage: Usd.Stage,
    mesh_path: Sdf.Path,
    vertices: np.ndarray,
    faces: np.ndarray,
    rgba: tuple[float, float, float, float],
    material: UsdShade.Material,
) -> None:
    mesh = UsdGeom.Mesh.Define(stage, mesh_path)
    mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr().Set(True)
    mesh.CreatePointsAttr([Gf.Vec3f(*vertex.tolist()) for vertex in vertices])
    mesh.CreateFaceVertexCountsAttr([3] * int(len(faces)))
    mesh.CreateFaceVertexIndicesAttr([int(index) for index in faces.reshape(-1).tolist()])

    extent_min = vertices.min(axis=0)
    extent_max = vertices.max(axis=0)
    mesh.CreateExtentAttr(
        [
            Gf.Vec3f(*extent_min.tolist()),
            Gf.Vec3f(*extent_max.tolist()),
        ]
    )
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*rgba[:3])])
    UsdShade.MaterialBindingAPI(mesh.GetPrim()).Bind(material)


def _create_collision_box(
    stage: Usd.Stage,
    object_path: Sdf.Path,
    dims: np.ndarray,
) -> None:
    collider = UsdGeom.Cube.Define(stage, object_path.AppendChild("CollisionBox"))
    collider.CreateSizeAttr(1.0)
    collider.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, float(dims[2] * 0.5)))
    collider.AddScaleOp().Set(Gf.Vec3f(*dims.tolist()))
    collider.MakeInvisible()
    UsdPhysics.CollisionAPI.Apply(collider.GetPrim())


def _set_collision_offsets(prim: Usd.Prim, *, contact_offset_m: float, rest_offset_m: float) -> None:
    physx_collision = PhysxSchema.PhysxCollisionAPI.Apply(prim)
    physx_collision.CreateContactOffsetAttr(float(contact_offset_m))
    physx_collision.CreateRestOffsetAttr(float(rest_offset_m))


def _apply_mesh_collision(
    prim: Usd.Prim,
    *,
    approximation: str,
    contact_offset_m: float,
    rest_offset_m: float,
) -> None:
    UsdPhysics.CollisionAPI.Apply(prim)
    mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
    mesh_collision.CreateApproximationAttr().Set(approximation)
    _set_collision_offsets(
        prim,
        contact_offset_m=contact_offset_m,
        rest_offset_m=rest_offset_m,
    )


def _iter_mesh_descendants(root_prim: Usd.Prim) -> list[Usd.Prim]:
    meshes: list[Usd.Prim] = []
    for prim in Usd.PrimRange(root_prim):
        if prim.IsA(UsdGeom.Mesh):
            meshes.append(prim)
    return meshes


def _configure_reference_mesh_collisions(stage: Usd.Stage, object_path: Sdf.Path) -> int:
    root_prim = stage.GetPrimAtPath(object_path)
    if not root_prim or not root_prim.IsValid():
        return 0

    approximation = _env_str("A1Z_TRASH_COLLISION_APPROXIMATION", DEFAULT_COLLISION_APPROXIMATION)
    contact_offset_m = _env_float("A1Z_TRASH_CONTACT_OFFSET_M", DEFAULT_CONTACT_OFFSET_M)
    rest_offset_m = _env_float("A1Z_TRASH_REST_OFFSET_M", DEFAULT_REST_OFFSET_M)

    configured = 0
    for mesh_prim in _iter_mesh_descendants(root_prim):
        _apply_mesh_collision(
            mesh_prim,
            approximation=approximation,
            contact_offset_m=contact_offset_m,
            rest_offset_m=rest_offset_m,
        )
        configured += 1
    return configured


def _align_ground_surface(stage: Usd.Stage) -> None:
    ground_prim = stage.GetPrimAtPath("/World/GroundPlane")
    if not ground_prim or not ground_prim.IsValid() or not ground_prim.IsA(UsdGeom.Cube):
        return

    ground = UsdGeom.Cube(ground_prim)
    pad_m = _env_float("A1Z_GROUND_SURFACE_PAD_M", DEFAULT_GROUND_SURFACE_PAD_M)
    contact_offset_m = _env_float("A1Z_GROUND_CONTACT_OFFSET_M", DEFAULT_CONTACT_OFFSET_M)
    rest_offset_m = _env_float("A1Z_GROUND_REST_OFFSET_M", DEFAULT_REST_OFFSET_M)

    UsdPhysics.CollisionAPI.Apply(ground_prim)
    _set_collision_offsets(
        ground_prim,
        contact_offset_m=contact_offset_m,
        rest_offset_m=rest_offset_m,
    )

    if abs(pad_m) <= 1e-9:
        return

    translate_op = None
    scale_op = None
    for op in ground.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            translate_op = op
        elif op.GetOpType() == UsdGeom.XformOp.TypeScale:
            scale_op = op

    if translate_op is None or scale_op is None:
        return

    translate = Gf.Vec3f(translate_op.Get())
    scale = Gf.Vec3f(scale_op.Get())
    scale[2] = float(scale[2] + 2.0 * pad_m)
    translate[2] = float(translate[2] + pad_m)
    scale_op.Set(scale)
    translate_op.Set(translate)


def _reference_usd_asset(
    stage: Usd.Stage,
    asset: dict,
    trash_root: Sdf.Path,
) -> dict:
    asset_id = str(asset["id"])
    layout = OBJECT_LAYOUT.get(asset_id)
    if layout is None:
        raise RuntimeError(f"No placement config found for asset '{asset_id}'")

    usd_path_value = asset.get("usd_path")
    if not usd_path_value:
        raise RuntimeError(f"USD asset entry '{asset_id}' is missing 'usd_path'")
    usd_path_str = str(usd_path_value)
    if _is_remote_asset_path(usd_path_str):
        resolved_reference = usd_path_str
    else:
        usd_path = _resolve_usd_asset_path(usd_path_str)
        if not usd_path.is_file():
            raise FileNotFoundError(usd_path)
        resolved_reference = str(usd_path)

    object_path = trash_root.AppendChild(_sanitize_name(asset_id))
    object_xform = UsdGeom.Xform.Define(stage, object_path)
    object_xform.AddTranslateOp().Set(Gf.Vec3d(*layout["position"]))
    object_xform.AddRotateZOp().Set(float(layout["yaw_deg"]))

    if "scale" in asset:
        scale = float(asset["scale"])
        object_xform.AddScaleOp().Set(Gf.Vec3f(scale, scale, scale))
    elif "scale_xyz" in asset:
        scale_xyz = asset["scale_xyz"]
        if len(scale_xyz) != 3:
            raise RuntimeError(f"USD asset '{asset_id}' scale_xyz must have 3 values")
        object_xform.AddScaleOp().Set(Gf.Vec3f(*[float(v) for v in scale_xyz]))

    references = object_xform.GetPrim().GetReferences()
    references.AddReference(resolved_reference)

    if asset.get("rigid_body", True):
        UsdPhysics.RigidBodyAPI.Apply(object_xform.GetPrim()).CreateRigidBodyEnabledAttr(True)
    if "suggested_mass_kg" in asset:
        UsdPhysics.MassAPI.Apply(object_xform.GetPrim()).CreateMassAttr(float(asset["suggested_mass_kg"]))
    mesh_collider_count = _configure_reference_mesh_collisions(stage=stage, object_path=object_path)

    return {
        "id": asset_id,
        "usd": resolved_reference,
        "position": tuple(layout["position"]),
        "yaw_deg": float(layout["yaw_deg"]),
        "scale": float(asset.get("scale", 1.0)),
        "mesh_collider_count": mesh_collider_count,
        "target_bbox_m": tuple(float(v) for v in asset.get("target_bbox_m", [])),
    }


def _build_asset(
    stage: Usd.Stage,
    asset: dict,
    trash_root: Sdf.Path,
    materials_root: Sdf.Path,
) -> dict:
    asset_id = str(asset["id"])
    layout = OBJECT_LAYOUT.get(asset_id)
    if layout is None:
        raise RuntimeError(f"No placement config found for asset '{asset_id}'")

    glb_path = DEFAULT_GLBS_DIR / f"{asset_id}.glb"
    if not glb_path.is_file():
        raise FileNotFoundError(glb_path)

    scene = trimesh.load(glb_path, force="scene")
    scene_meshes = _iter_scene_meshes(scene)

    rotated_meshes: list[tuple[str, trimesh.Trimesh, np.ndarray]] = []
    mins = []
    maxs = []
    for index, mesh in enumerate(scene_meshes):
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        rotated_vertices = vertices @ Y_UP_TO_Z_UP.T
        rotated_meshes.append((f"mesh_{index}", mesh, rotated_vertices))
        mins.append(rotated_vertices.min(axis=0))
        maxs.append(rotated_vertices.max(axis=0))

    overall_min = np.min(np.stack(mins, axis=0), axis=0)
    overall_max = np.max(np.stack(maxs, axis=0), axis=0)
    raw_dims = overall_max - overall_min

    target_bbox = np.asarray(asset["target_bbox_m"], dtype=np.float64).reshape(3)
    scale = _compute_scale(raw_dims, target_bbox, str(layout["scale_mode"]))

    center_xy = 0.5 * (overall_min[:2] + overall_max[:2])
    object_path = trash_root.AppendChild(_sanitize_name(asset_id))
    object_xform = UsdGeom.Xform.Define(stage, object_path)
    object_xform.AddTranslateOp().Set(Gf.Vec3d(*layout["position"]))
    object_xform.AddRotateZOp().Set(float(layout["yaw_deg"]))

    UsdPhysics.RigidBodyAPI.Apply(object_xform.GetPrim()).CreateRigidBodyEnabledAttr(True)
    UsdPhysics.MassAPI.Apply(object_xform.GetPrim()).CreateMassAttr(float(asset["suggested_mass_kg"]))

    visuals_path = object_path.AppendChild("Visuals")
    UsdGeom.Xform.Define(stage, visuals_path)

    for mesh_name, mesh, rotated_vertices in rotated_meshes:
        local_vertices = rotated_vertices.copy()
        local_vertices[:, 0] -= center_xy[0]
        local_vertices[:, 1] -= center_xy[1]
        local_vertices[:, 2] -= overall_min[2]
        local_vertices *= scale

        rgba = _rgba_from_trimesh(mesh)
        material_name = _sanitize_name(f"{asset_id}_{mesh_name}_mat")
        material = _make_preview_material(
            stage=stage,
            material_path=materials_root.AppendChild(material_name),
            rgba=rgba,
            category=str(asset["category"]),
        )
        _create_visual_mesh(
            stage=stage,
            mesh_path=visuals_path.AppendChild(_sanitize_name(mesh_name)),
            vertices=local_vertices,
            faces=np.asarray(mesh.faces, dtype=np.int64),
            rgba=rgba,
            material=material,
        )

    _create_collision_box(stage=stage, object_path=object_path, dims=target_bbox)

    return {
        "id": asset_id,
        "glb": str(glb_path),
        "position": tuple(layout["position"]),
        "yaw_deg": float(layout["yaw_deg"]),
        "scale": scale,
        "target_bbox_m": tuple(float(value) for value in target_bbox.tolist()),
    }


def _place_asset(
    stage: Usd.Stage,
    asset: dict,
    trash_root: Sdf.Path,
    materials_root: Sdf.Path,
) -> dict:
    source_type = str(asset.get("source_type", "glb_bake"))
    if source_type == "glb_bake":
        return _build_asset(stage=stage, asset=asset, trash_root=trash_root, materials_root=materials_root)
    if source_type == "usd_reference":
        return _reference_usd_asset(stage=stage, asset=asset, trash_root=trash_root)
    raise RuntimeError(f"Unsupported asset source_type '{source_type}' for asset '{asset.get('id')}'")


def main() -> int:
    args = parse_args()

    world_usd = Path(args.world_usd).resolve()
    manifest_path = Path(args.manifest).resolve()
    overlay_usda = Path(args.overlay_usda).resolve() if args.overlay_usda else _default_overlay_path(world_usd)
    trash_root = Sdf.Path(args.trash_root)
    materials_root = DEFAULT_MATERIALS_ROOT

    if not world_usd.is_file():
        raise FileNotFoundError(world_usd)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    assets = _load_manifest(manifest_path)

    stage = Usd.Stage.Open(str(world_usd))
    if stage is None:
        raise RuntimeError(f"Failed to open world stage: {world_usd}")

    root_layer = stage.GetRootLayer()
    overlay_layer = _open_or_create_overlay_layer(overlay_usda)
    root_layer_changed = _ensure_world_has_overlay(root_layer, overlay_usda, world_usd=world_usd)

    removed_inline = False
    removed_inline = _remove_prim_from_layer(stage, root_layer, trash_root) or removed_inline
    removed_inline = _remove_prim_from_layer(stage, root_layer, materials_root) or removed_inline

    stage.SetEditTarget(overlay_layer)
    if overlay_layer.GetPrimAtPath(str(trash_root)) is not None:
        stage.RemovePrim(trash_root)
    if overlay_layer.GetPrimAtPath(str(materials_root)) is not None:
        stage.RemovePrim(materials_root)

    UsdGeom.Xform.Define(stage, trash_root)
    UsdGeom.Scope.Define(stage, materials_root)

    placed_assets = []
    for asset in assets:
        placed_assets.append(
            _place_asset(
                stage=stage,
                asset=asset,
                trash_root=trash_root,
                materials_root=materials_root,
            )
        )

    _align_ground_surface(stage)

    overlay_layer.Save()
    if root_layer_changed or removed_inline:
        root_layer.Save()

    print(f"World USD: {world_usd}")
    print(f"Trash overlay: {overlay_usda}")
    print(f"Trash root: {trash_root}")
    for placed in placed_assets:
        x, y, z = placed["position"]
        print(
            "Placed "
            f"{placed['id']} at ({x:.3f}, {y:.3f}, {z:.3f}) m, "
            f"yaw={placed['yaw_deg']:.1f} deg, scale={placed['scale']:.5f}, "
            f"target_bbox={placed['target_bbox_m']}"
        )
    return 0


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
