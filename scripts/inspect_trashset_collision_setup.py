#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from isaacsim import SimulationApp


simulation_app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_WORLD_USD = ROOT_DIR / "build" / "scenes" / "A1Z_G1Z_world.usd"
TRASH_ROOT = Sdf.Path("/World/TrashSet")
GROUND_PATH = Sdf.Path("/World/GroundPlane")
DEFAULT_OUTPUT_PATH = ROOT_DIR / "runtime" / "logs" / "inspect-trashset-collision-summary.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect TrashSet collision setup in the generated world USD.")
    parser.add_argument("--world-usd", default=str(DEFAULT_WORLD_USD), help="World USD to inspect.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Summary output path.")
    return parser.parse_args()


def _format_vec3(value) -> str:
    if value is None:
        return "None"
    return f"({float(value[0]):.6f}, {float(value[1]):.6f}, {float(value[2]):.6f})"


def _format_bbox(min_vec, max_vec) -> str:
    if min_vec is None or max_vec is None:
        return "None"
    return f"min={_format_vec3(min_vec)} max={_format_vec3(max_vec)}"


def _local_bbox(prim: Usd.Prim) -> tuple[Gf.Vec3d | None, Gf.Vec3d | None]:
    if not prim.IsValid():
        return None, None
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
    )
    box = bbox_cache.ComputeLocalBound(prim).GetBox()
    return box.GetMin(), box.GetMax()


def _relative_bbox(prim: Usd.Prim, ancestor: Usd.Prim) -> tuple[Gf.Vec3d | None, Gf.Vec3d | None]:
    if not prim.IsValid() or not ancestor.IsValid():
        return None, None
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
    )
    box = bbox_cache.ComputeRelativeBound(prim, ancestor).GetBox()
    return box.GetMin(), box.GetMax()


def _collision_box_effective_local_bbox(prim: Usd.Prim) -> tuple[Gf.Vec3d | None, Gf.Vec3d | None]:
    if not prim.IsValid() or not prim.IsA(UsdGeom.Cube):
        return None, None
    cube = UsdGeom.Cube(prim)
    size = float(cube.GetSizeAttr().Get() or 1.0)
    half = 0.5 * size
    translate = np.zeros(3, dtype=float)
    scale = np.ones(3, dtype=float)
    for op in cube.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            value = op.Get()
            translate = np.asarray([float(value[i]) for i in range(3)], dtype=float)
        elif op.GetOpType() == UsdGeom.XformOp.TypeScale:
            value = op.Get()
            scale = np.asarray([float(value[i]) for i in range(3)], dtype=float)
    extent = half * scale
    min_vec = translate - extent
    max_vec = translate + extent
    return Gf.Vec3d(*min_vec.tolist()), Gf.Vec3d(*max_vec.tolist())


def _collision_summary(
    root_prim: Usd.Prim,
) -> tuple[int, int, int, set[str], list[tuple[float | None, float | None]], list[str]]:
    mesh_count = 0
    mesh_collider_count = 0
    collision_prim_count = 0
    approximations: set[str] = set()
    offsets: list[tuple[float | None, float | None]] = []
    collision_paths: list[str] = []
    for prim in Usd.PrimRange(root_prim):
        if prim.IsA(UsdGeom.Mesh):
            mesh_count += 1
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        collision_api = UsdPhysics.CollisionAPI(prim)
        enabled = collision_api.GetCollisionEnabledAttr().Get()
        if enabled is False:
            continue
        collision_prim_count += 1
        collision_paths.append(str(prim.GetPath()))
        if prim.IsA(UsdGeom.Mesh) and prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            mesh_collider_count += 1
            mesh_collision = UsdPhysics.MeshCollisionAPI(prim)
            approximations.add(str(mesh_collision.GetApproximationAttr().Get()))
        if prim.HasAPI(PhysxSchema.PhysxCollisionAPI):
            physx_collision = PhysxSchema.PhysxCollisionAPI(prim)
            offsets.append(
                (
                    physx_collision.GetContactOffsetAttr().Get(),
                    physx_collision.GetRestOffsetAttr().Get(),
                )
            )
    return mesh_count, mesh_collider_count, collision_prim_count, approximations, offsets, collision_paths


def _ground_summary(stage: Usd.Stage) -> None:
    prim = stage.GetPrimAtPath(GROUND_PATH)
    print(f"ground.valid={prim.IsValid()}")
    if not prim.IsValid():
        return

    print(f"ground.has_collision={prim.HasAPI(UsdPhysics.CollisionAPI)}")
    print(f"ground.has_physx_collision={prim.HasAPI(PhysxSchema.PhysxCollisionAPI)}")
    if prim.HasAPI(PhysxSchema.PhysxCollisionAPI):
        physx_collision = PhysxSchema.PhysxCollisionAPI(prim)
        print(f"ground.contact_offset={physx_collision.GetContactOffsetAttr().Get()}")
        print(f"ground.rest_offset={physx_collision.GetRestOffsetAttr().Get()}")

    cube = UsdGeom.Cube(prim)
    translate = None
    scale = None
    for op in cube.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            translate = op.Get()
        elif op.GetOpType() == UsdGeom.XformOp.TypeScale:
            scale = op.Get()
    print(f"ground.translate={_format_vec3(translate)}")
    print(f"ground.scale={_format_vec3(scale)}")


def main() -> int:
    args = parse_args()
    world_usd = Path(args.world_usd).resolve()
    output_path = Path(args.output).resolve()
    stage = Usd.Stage.Open(str(world_usd))
    if stage is None:
        raise RuntimeError(f"Failed to open stage: {world_usd}")

    lines: list[str] = []
    lines.append(f"world_usd={world_usd}")
    lines.append(f"trash_root.valid={stage.GetPrimAtPath(TRASH_ROOT).IsValid()}")

    for child in stage.GetPrimAtPath(TRASH_ROOT).GetChildren():
        mesh_count, mesh_collider_count, collision_prim_count, approximations, offsets, collision_paths = (
            _collision_summary(child)
        )
        visual_min, visual_max = _local_bbox(child)
        collision_box_prim = child.GetPrimAtPath(child.GetPath().AppendChild("CollisionBox"))
        collision_min, collision_max = (
            _collision_box_effective_local_bbox(collision_box_prim) if collision_box_prim.IsValid() else (None, None)
        )
        lines.append(f"asset={child.GetName()}")
        lines.append(f"  mesh_count={mesh_count}")
        lines.append(f"  mesh_collider_count={mesh_collider_count}")
        lines.append(f"  collision_prim_count={collision_prim_count}")
        lines.append(f"  collision_paths={collision_paths[:3]}")
        lines.append(f"  approximations={sorted(approximations)}")
        lines.append(f"  offset_samples={offsets[:3]}")
        lines.append(f"  visual_local_bbox={_format_bbox(visual_min, visual_max)}")
        lines.append(f"  collision_box_local_bbox={_format_bbox(collision_min, collision_max)}")

    prim = stage.GetPrimAtPath(GROUND_PATH)
    lines.append(f"ground.valid={prim.IsValid()}")
    if prim.IsValid():
        lines.append(f"ground.has_collision={prim.HasAPI(UsdPhysics.CollisionAPI)}")
        lines.append(f"ground.has_physx_collision={prim.HasAPI(PhysxSchema.PhysxCollisionAPI)}")
        if prim.HasAPI(PhysxSchema.PhysxCollisionAPI):
            physx_collision = PhysxSchema.PhysxCollisionAPI(prim)
            lines.append(f"ground.contact_offset={physx_collision.GetContactOffsetAttr().Get()}")
            lines.append(f"ground.rest_offset={physx_collision.GetRestOffsetAttr().Get()}")
        cube = UsdGeom.Cube(prim)
        translate = None
        scale = None
        for op in cube.GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                translate = op.Get()
            elif op.GetOpType() == UsdGeom.XformOp.TypeScale:
                scale = op.Get()
        lines.append(f"ground.translate={_format_vec3(translate)}")
        lines.append(f"ground.scale={_format_vec3(scale)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"summary_written={output_path}")
    return 0


if __name__ == "__main__":
    code = 0
    try:
        code = main()
    finally:
        simulation_app.close()
    raise SystemExit(code)
