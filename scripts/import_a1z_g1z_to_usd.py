#!/usr/bin/env python3

import argparse
import math
import shutil
import os
from pathlib import Path
import sys

from isaacsim import SimulationApp


def parse_args():
    root_dir = Path(__file__).resolve().parent.parent
    default_urdf = root_dir / "build" / "robot_packages" / "A1Z_G1Z" / "urdf" / "A1Z_G1Z_isaac.urdf"
    default_robot_usd = root_dir / "build" / "scenes" / "A1Z_G1Z_robot.usd"
    default_world_usd = root_dir / "build" / "scenes" / "A1Z_G1Z_world.usd"
    parser = argparse.ArgumentParser(description="Import the A1Z_G1Z URDF into Isaac Sim and save robot/world USDs.")
    parser.add_argument(
        "--urdf",
        default=str(default_urdf),
        help="Absolute path to the source URDF.",
    )
    parser.add_argument(
        "--robot-usd",
        default=str(default_robot_usd),
        help="Absolute path to the generated robot USD.",
    )
    parser.add_argument(
        "--world-usd",
        default=str(default_world_usd),
        help="Absolute path to the generated world USD.",
    )
    parser.add_argument(
        "--robot-prim",
        default="/World/A1Z_G1Z",
        help="Prim path used when referencing the robot into the world stage.",
    )
    parser.add_argument(
        "--rebuild-world",
        action="store_true",
        help="Rebuild the world USD from scratch instead of preserving an existing world stage.",
    )
    args, _ = parser.parse_known_args()
    return args


simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import omni.usd  # noqa: E402
from isaacsim.asset.importer.urdf import URDFImporter, URDFImporterConfig  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade  # noqa: E402

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SDK_DIR = os.path.join(ROOT_DIR, "vendor", "GALAXEA-A1Z")
GROUND_WOOD_TEXTURE = (
    Path(ROOT_DIR)
    / ".."
    / "isaacsim_assets"
    / "Assets"
    / "Isaac"
    / "6.0"
    / "Isaac"
    / "Materials"
    / "Textures"
    / "Patterns"
    / "nv_wood_oak_flooring_stained.jpg"
)
GROUND_TEXTURE_FALLBACKS = (
    Path(ROOT_DIR)
    / "assets"
    / "trash_grasp_set"
    / "isaac_ycb"
    / "Axis_Aligned"
    / "Materials"
    / "Textures"
    / "036_wood_block_COLOR.png",
    Path(ROOT_DIR)
    / "assets"
    / "trash_grasp_set"
    / "isaac_ycb"
    / "Axis_Aligned"
    / "Materials"
    / "Textures"
    / "003_cracker_box_COLOR.png",
)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}

from a1z_ext.config import get_control_defaults  # noqa: E402

CONTROL_DEFAULTS = get_control_defaults()
ISAAC_CFG = CONTROL_DEFAULTS["isaacsim"]
ARM_JOINT_NAMES = list(ISAAC_CFG["arm_joint_names"])
GRIPPER_JOINT_NAMES = list(ISAAC_CFG["gripper_joint_names"])
ARM_JOINT_DRIVE_STIFFNESS = dict(zip(ARM_JOINT_NAMES, ISAAC_CFG["position_hold_kp"], strict=True))
ARM_JOINT_DRIVE_DAMPING = dict(zip(ARM_JOINT_NAMES, ISAAC_CFG["position_hold_kd"], strict=True))
ARM_JOINT_MAX_FORCE = dict(zip(ARM_JOINT_NAMES, ISAAC_CFG["arm_max_effort"], strict=True))
ARM_JOINT_HARD_LIMITS_DEG = dict(zip(ARM_JOINT_NAMES, CONTROL_DEFAULTS["arm_hard_joint_limits_deg"], strict=True))
ARM_JOINT_MAX_VELOCITY_DEG_S = dict(
    zip(
        ARM_JOINT_NAMES,
        [math.degrees(value) for value in ISAAC_CFG["arm_max_velocity"]],
        strict=True,
    )
)
GRIPPER_JOINT_DRIVE_STIFFNESS = dict(zip(GRIPPER_JOINT_NAMES, ISAAC_CFG["gripper_kp"], strict=True))
GRIPPER_JOINT_DRIVE_DAMPING = dict(zip(GRIPPER_JOINT_NAMES, ISAAC_CFG["gripper_kd"], strict=True))
GRIPPER_JOINT_MAX_FORCE = dict(zip(GRIPPER_JOINT_NAMES, ISAAC_CFG["gripper_max_effort"], strict=True))
GRIPPER_JOINT_MAX_VELOCITY = dict(zip(GRIPPER_JOINT_NAMES, ISAAC_CFG["gripper_max_velocity"], strict=True))
GRIPPER_JOINT_LIMITS_M = {
    "gripper_finger_left_joint": (0.0, 0.048),
    "gripper_finger_rIght_joint": (-0.048, 0.0),
}
GRIPPER_COLLISION_PRIM_PATHS = (
    "/Instances/gripper_finger_left_link_1/gripper_finger_left_link",
    "/Instances/gripper_finger_rIght_link_1/gripper_finger_rIght_link",
)
GRIPPER_LINK_NAMES = (
    "gripper_finger_left_link",
    "gripper_finger_rIght_link",
)
# Keep the bracket's authored local Translate/Orient/Scale visible in Isaac's
# Transform inspector instead of baking its default world pose into a matrix.
DIRECT_LOCAL_XFORM_LINK_NAMES = {
    "camera_bracket_link",
}
GRIPPER_INNER_INSTANCE_PRIM_PATHS = (
    "/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/"
    "gripper_finger_left_link/gripper_finger_left_link",
    "/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/"
    "gripper_finger_left_link/gripper_finger_left_link_1",
    "/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/"
    "gripper_finger_rIght_link/gripper_finger_rIght_link",
    "/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/"
    "gripper_finger_rIght_link/gripper_finger_rIght_link_1",
)
WITH_GRIPPER = _env_bool("A1Z_WITH_GRIPPER", True)

ROBOT_MATERIAL_PRESETS = {
    "silver_shell": {
        "base_color_srgb": (0.78, 0.78, 0.78),
        "metallic": 0.72,
        "roughness": 0.42,
        "specular": 0.52,
    },
    "gunmetal": {
        "base_color_srgb": (0.16, 0.16, 0.15),
        "metallic": 0.72,
        "roughness": 0.46,
        "specular": 0.72,
    },
}


def update_app(frames=5):
    for _ in range(frames):
        simulation_app.update()


def _resolve_ground_texture() -> Path:
    candidates = (GROUND_WOOD_TEXTURE, *GROUND_TEXTURE_FALLBACKS)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(
        "No ground texture found. Checked: " + ", ".join(str(path) for path in candidates)
    )


def _configure_ground_material(stage: Usd.Stage, ground_prim: Usd.Prim) -> None:
    ground_texture_path = _resolve_ground_texture()
    material_path = Sdf.Path("/World/Looks/GroundMaterial")
    shader_path = material_path.AppendPath("Shader")
    primvar_reader_path = material_path.AppendPath("PrimvarReader")
    transform_path = material_path.AppendPath("TextureTransform")
    texture_path = material_path.AppendPath("WoodTexture")

    ground_material = UsdShade.Material.Define(stage, material_path)
    shader = UsdShade.Shader.Define(stage, shader_path)
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.50, 0.38, 0.27))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.72)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("specularColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.18, 0.14, 0.10))

    primvar_reader = UsdShade.Shader.Define(stage, primvar_reader_path)
    primvar_reader.CreateIdAttr("UsdPrimvarReader_float2")
    primvar_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

    texture_transform = UsdShade.Shader.Define(stage, transform_path)
    texture_transform.CreateIdAttr("UsdTransform2d")
    texture_transform.CreateInput("scale", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(4.0, 4.0))
    texture_transform.CreateInput("in", Sdf.ValueTypeNames.Float2).ConnectToSource(
        primvar_reader.ConnectableAPI(), "result"
    )

    wood_texture = UsdShade.Shader.Define(stage, texture_path)
    wood_texture.CreateIdAttr("UsdUVTexture")
    stage_path = Path(stage.GetRootLayer().realPath).resolve()
    texture_asset_path = os.path.relpath(ground_texture_path, start=stage_path.parent)
    wood_texture.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(texture_asset_path))
    wood_texture.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
    wood_texture.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
    wood_texture.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
    wood_texture.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
        texture_transform.ConnectableAPI(), "result"
    )

    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
        wood_texture.ConnectableAPI(), "rgb"
    )
    ground_material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    primvars_api = UsdGeom.PrimvarsAPI(ground_prim)
    st = primvars_api.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
    st.Set(
        [
            Gf.Vec2f(0.0, 0.0),
            Gf.Vec2f(1.0, 0.0),
            Gf.Vec2f(1.0, 1.0),
            Gf.Vec2f(0.0, 1.0),
        ]
        * 6
    )

    UsdShade.MaterialBindingAPI(ground_prim).Bind(ground_material)


def _create_ground_visual(stage: Usd.Stage) -> Usd.Prim:
    mesh = UsdGeom.Mesh.Define(stage, Sdf.Path("/World/GroundVisual"))
    half_extent = 4.0
    z = 0.0005
    mesh.CreatePointsAttr(
        [
            Gf.Vec3f(-half_extent, -half_extent, z),
            Gf.Vec3f(half_extent, -half_extent, z),
            Gf.Vec3f(half_extent, half_extent, z),
            Gf.Vec3f(-half_extent, half_extent, z),
        ]
    )
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateExtentAttr([Gf.Vec3f(-half_extent, -half_extent, z), Gf.Vec3f(half_extent, half_extent, z)])
    mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)

    primvars_api = UsdGeom.PrimvarsAPI(mesh)
    st = primvars_api.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    st.Set(
        [
            Gf.Vec2f(0.0, 0.0),
            Gf.Vec2f(4.0, 0.0),
            Gf.Vec2f(4.0, 4.0),
            Gf.Vec2f(0.0, 4.0),
        ]
    )
    normals = primvars_api.CreatePrimvar("normals", Sdf.ValueTypeNames.Normal3fArray, UsdGeom.Tokens.vertex)
    normals.Set([Gf.Vec3f(0.0, 0.0, 1.0)] * 4)
    return mesh.GetPrim()


def ensure_parent_dir(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def default_trashset_overlay_usda_path(world_usd_path: str) -> str:
    world_path = Path(world_usd_path)
    return str(world_path.with_name(f"{world_path.stem}_trashset.usda"))


def ensure_world_sublayer(world_usd_path: str, layer_path: str) -> bool:
    world_path = Path(world_usd_path).resolve()
    overlay_path = Path(layer_path).resolve()
    if not overlay_path.is_file():
        return False

    stage = Usd.Stage.Open(str(world_path))
    if stage is None:
        raise RuntimeError(f"Failed to reopen world USD for sublayer patch: {world_path}")

    root_layer = stage.GetRootLayer()
    rel_overlay_path = os.path.relpath(overlay_path, start=world_path.parent).replace(os.sep, "/")
    if rel_overlay_path in root_layer.subLayerPaths:
        return False

    root_layer.subLayerPaths.append(rel_overlay_path)
    root_layer.Save()
    print(f"Attached world sublayer: {rel_overlay_path}")
    return True


def cleanup_generated_usd(robot_usd_path: str, world_usd_path: str, *, rebuild_world: bool) -> None:
    robot_path = Path(robot_usd_path)
    world_path = Path(world_usd_path)
    config_dir = robot_path.parent / "configuration"
    robot_stem = robot_path.stem

    for path in (robot_path,):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    if rebuild_world:
        try:
            world_path.unlink()
        except FileNotFoundError:
            pass

    if config_dir.is_dir():
        for child in config_dir.glob(f"{robot_stem}_*.usd"):
            try:
                child.unlink()
            except FileNotFoundError:
                pass

    for generated_dir in robot_path.parent.glob("A1Z_G1Z_isaac*"):
        if generated_dir.is_dir():
            shutil.rmtree(generated_dir, ignore_errors=True)


def _set_joint_drive(
    stage,
    joint_path: str,
    drive_type: str,
    stiffness: float,
    damping: float,
    max_force: float | None = None,
    effort_type: str = "acceleration",
):
    prim = stage.GetPrimAtPath(joint_path)
    if not prim.IsValid():
        raise RuntimeError(f"Joint prim not found in imported USD: {joint_path}")

    drive = UsdPhysics.DriveAPI.Get(prim, drive_type)
    if not drive:
        drive = UsdPhysics.DriveAPI.Apply(prim, drive_type)

    drive.CreateTypeAttr().Set(effort_type)
    drive.CreateTargetPositionAttr().Set(0.0)
    drive.CreateTargetVelocityAttr().Set(0.0)
    if drive_type == "angular":
        # Runtime/controller gains are per radian; USD angular DriveAPI
        # stiffness and damping are stored per degree.
        stiffness = math.radians(float(stiffness))
        damping = math.radians(float(damping))
    drive.CreateStiffnessAttr().Set(float(stiffness))
    drive.CreateDampingAttr().Set(float(damping))
    if max_force is not None:
        drive.CreateMaxForceAttr().Set(float(max_force))


def _set_revolute_joint_limits(
    stage,
    joint_path: str,
    lower_deg: float,
    upper_deg: float,
    max_velocity_deg_s: float,
) -> None:
    prim = stage.GetPrimAtPath(joint_path)
    if not prim.IsValid():
        raise RuntimeError(f"Joint prim not found in imported USD: {joint_path}")

    joint = UsdPhysics.RevoluteJoint.Get(stage, joint_path)
    if not joint:
        raise RuntimeError(f"Expected a PhysicsRevoluteJoint prim at: {joint_path}")
    joint.CreateLowerLimitAttr().Set(float(lower_deg))
    joint.CreateUpperLimitAttr().Set(float(upper_deg))

    physx_joint = PhysxSchema.PhysxJointAPI(prim)
    if not physx_joint:
        physx_joint = PhysxSchema.PhysxJointAPI.Apply(prim)
    physx_joint.CreateMaxJointVelocityAttr().Set(float(max_velocity_deg_s))


def _set_prismatic_joint_limits(
    stage,
    joint_path: str,
    lower_m: float,
    upper_m: float,
    max_velocity_m_s: float,
) -> None:
    prim = stage.GetPrimAtPath(joint_path)
    if not prim.IsValid():
        raise RuntimeError(f"Joint prim not found in imported USD: {joint_path}")

    joint = UsdPhysics.PrismaticJoint.Get(stage, joint_path)
    if not joint:
        raise RuntimeError(f"Expected a PhysicsPrismaticJoint prim at: {joint_path}")
    joint.CreateLowerLimitAttr().Set(float(lower_m))
    joint.CreateUpperLimitAttr().Set(float(upper_m))

    physx_joint = PhysxSchema.PhysxJointAPI(prim)
    if not physx_joint:
        physx_joint = PhysxSchema.PhysxJointAPI.Apply(prim)
    physx_joint.CreateMaxJointVelocityAttr().Set(float(max_velocity_m_s))


def _patch_gripper_joint_drives(stage, joints_root: str) -> list[str]:
    patched_joints = []
    for joint_name, stiffness in GRIPPER_JOINT_DRIVE_STIFFNESS.items():
        lower_m, upper_m = GRIPPER_JOINT_LIMITS_M[joint_name]
        joint_path = f"{joints_root}/{joint_name}"
        if not stage.GetPrimAtPath(joint_path).IsValid():
            continue
        _set_prismatic_joint_limits(
            stage=stage,
            joint_path=joint_path,
            lower_m=lower_m,
            upper_m=upper_m,
            max_velocity_m_s=GRIPPER_JOINT_MAX_VELOCITY[joint_name],
        )
        _set_joint_drive(
            stage=stage,
            joint_path=joint_path,
            drive_type="linear",
            stiffness=stiffness,
            damping=GRIPPER_JOINT_DRIVE_DAMPING[joint_name],
            max_force=GRIPPER_JOINT_MAX_FORCE[joint_name],
        )
        patched_joints.append(joint_path)
    return patched_joints


def _find_joint_container(stage, root_prim_path: str, joint_names: list[str]) -> str:
    candidates = [
        f"{root_prim_path}/Physics",
        f"{root_prim_path}/joints",
        f"{root_prim_path}/root_joint/joints",
        "/A1Z_G1Z/Physics",
        "/A1Z_G1Z/joints",
        "/A1Z_G1Z/root_joint/joints",
        "/World/A1Z_G1Z/Physics",
        "/World/A1Z_G1Z/root_joint/joints",
    ]

    best_candidate = None
    best_match_count = 0
    for candidate in candidates:
        prim = stage.GetPrimAtPath(candidate)
        if not prim.IsValid():
            continue
        match_count = sum(stage.GetPrimAtPath(f"{candidate}/{joint_name}").IsValid() for joint_name in joint_names)
        if match_count > best_match_count:
            best_candidate = candidate
            best_match_count = match_count
        if match_count == len(joint_names):
            return candidate

    root_prim = stage.GetPrimAtPath(root_prim_path)
    if root_prim.IsValid():
        discovered_parents = {}
        for prim in Usd.PrimRange(root_prim):
            prim_name = prim.GetName()
            if prim_name not in joint_names:
                continue
            parent_path = str(prim.GetPath().GetParentPath())
            discovered_parents[parent_path] = discovered_parents.get(parent_path, 0) + 1
        if discovered_parents:
            return max(discovered_parents.items(), key=lambda item: item[1])[0]

    if best_candidate is not None:
        return best_candidate

    raise RuntimeError(
        f"Could not locate imported joint container for {root_prim_path}. "
        f"Tried: {candidates}"
    )


def patch_imported_joint_drives(stage, root_prim_path: str):
    joint_names = list(ARM_JOINT_NAMES)
    if WITH_GRIPPER:
        joint_names.extend(GRIPPER_JOINT_NAMES)
    joints_root = _find_joint_container(stage, root_prim_path, joint_names)

    for joint_name, stiffness in ARM_JOINT_DRIVE_STIFFNESS.items():
        lower_deg, upper_deg = ARM_JOINT_HARD_LIMITS_DEG[joint_name]
        _set_revolute_joint_limits(
            stage=stage,
            joint_path=f"{joints_root}/{joint_name}",
            lower_deg=lower_deg,
            upper_deg=upper_deg,
            max_velocity_deg_s=ARM_JOINT_MAX_VELOCITY_DEG_S[joint_name],
        )
        _set_joint_drive(
            stage=stage,
            joint_path=f"{joints_root}/{joint_name}",
            drive_type="angular",
            stiffness=stiffness,
            damping=ARM_JOINT_DRIVE_DAMPING[joint_name],
            max_force=ARM_JOINT_MAX_FORCE[joint_name],
            effort_type=str(ISAAC_CFG.get("arm_drive_type", "force")),
        )

    if WITH_GRIPPER:
        _patch_gripper_joint_drives(stage, joints_root)


def _relativize_internal_relationship_targets(stage, root_prim_path: str) -> None:
    root_prim = stage.GetPrimAtPath(root_prim_path)
    if not root_prim.IsValid():
        raise RuntimeError(f"Invalid imported robot root prim: {root_prim_path}")

    root_path = root_prim.GetPath()
    # The generated robot asset keeps helper scopes such as /visuals and /colliders
    # outside the robot root prim. Their bindings still target materials under the
    # robot root, so they must be relativized too before the whole asset is referenced
    # under /World/... in the final stage.
    for prim in stage.Traverse():
        owner_path = prim.GetPath()
        for rel in prim.GetRelationships():
            targets = rel.GetTargets()
            if not targets:
                continue
            new_targets = []
            changed = False
            for target in targets:
                if target.IsAbsolutePath() and target.HasPrefix(root_path):
                    relative_target = target.MakeRelativePath(owner_path)
                    new_targets.append(relative_target)
                    changed = changed or relative_target != target
                else:
                    new_targets.append(target)
            if changed:
                rel.SetTargets(new_targets)
        for attr in prim.GetAttributes():
            connections = attr.GetConnections()
            if not connections:
                continue
            new_connections = []
            changed = False
            for connection in connections:
                if connection.IsAbsolutePath() and connection.HasPrefix(root_path):
                    relative_connection = connection.MakeRelativePath(owner_path)
                    new_connections.append(relative_connection)
                    changed = changed or relative_connection != connection
                else:
                    new_connections.append(connection)
            if changed:
                attr.SetConnections(new_connections)


def _reset_nested_rigid_body_xforms(stage, root_prim_path: str) -> None:
    root_prim = stage.GetPrimAtPath(root_prim_path)
    if not root_prim.IsValid():
        raise RuntimeError(f"Invalid imported robot root prim: {root_prim_path}")

    def _preserve_world_transform_with_reset(prim: Usd.Prim, world_transform: Gf.Matrix4d) -> None:
        xformable = UsdGeom.Xformable(prim)
        if not xformable:
            return
        for op in list(xformable.GetOrderedXformOps()):
            prim.RemoveProperty(op.GetOpName())
        xformable.ClearXformOpOrder()
        xformable.AddTransformOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Matrix4d(world_transform))
        xformable.SetResetXformStack(True)

    def _is_rigid_body(prim: Usd.Prim) -> bool:
        if not prim.IsValid():
            return False
        enabled_attr = prim.GetAttribute("physics:rigidBodyEnabled")
        if enabled_attr.IsValid():
            return bool(enabled_attr.Get())
        return bool(prim.HasAPI(UsdPhysics.RigidBodyAPI))

    targets: list[tuple[Usd.Prim, Gf.Matrix4d]] = []
    patched_prims: list[str] = []
    for prim in Usd.PrimRange(root_prim):
        if not _is_rigid_body(prim):
            continue
        if prim.GetName() in DIRECT_LOCAL_XFORM_LINK_NAMES:
            continue

        ancestor = prim.GetParent()
        has_rigid_body_ancestor = False
        while ancestor and ancestor.IsValid() and ancestor != root_prim.GetParent():
            if _is_rigid_body(ancestor):
                has_rigid_body_ancestor = True
                break
            ancestor = ancestor.GetParent()

        if not has_rigid_body_ancestor:
            continue

        xformable = UsdGeom.Xformable(prim)
        if not xformable:
            continue
        if not xformable.GetResetXformStack():
            targets.append((prim, Gf.Matrix4d(xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default()))))

    for prim, world_transform in targets:
        _preserve_world_transform_with_reset(prim, world_transform)
        patched_prims.append(str(prim.GetPath()))

    if patched_prims:
        print(
            "Patched nested rigid-body resetXformStack with preserved world poses: "
            + ", ".join(patched_prims)
        )


def _srgb_channel_to_linear(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _linear_channel_to_srgb(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value <= 0.0031308:
        return value * 12.92
    return 1.055 * (value ** (1.0 / 2.4)) - 0.055


def _vec3_to_tuple(value) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (IndexError, TypeError, ValueError):
        return None


def _classify_robot_material(linear_color: tuple[float, float, float]) -> str | None:
    srgb_color = tuple(_linear_channel_to_srgb(channel) for channel in linear_color)
    average = sum(srgb_color) / len(srgb_color)
    spread = max(srgb_color) - min(srgb_color)

    if average >= 0.55 and spread <= 0.16:
        return "silver_shell"
    if average <= 0.48 and spread <= 0.10:
        return "gunmetal"
    return None


def _get_material_input(material: UsdShade.Material, name: str, value_type):
    material_input = material.GetInput(name)
    if material_input:
        return material_input
    return material.CreateInput(name, value_type)


def _get_preview_shader(stage, material_prim):
    shader_path = material_prim.GetPath().AppendChild("PreviewSurface")
    shader = UsdShade.Shader.Get(stage, shader_path)
    if not shader:
        shader = UsdShade.Shader.Define(stage, shader_path)
    shader.CreateIdAttr("UsdPreviewSurface")
    return shader


def _connect_preview_input(shader: UsdShade.Shader, material: UsdShade.Material, name: str, value_type) -> None:
    _get_material_input(material, name, value_type)
    shader_input = shader.CreateInput(name, value_type)
    shader_input.ConnectToSource(material.ConnectableAPI(), name, UsdShade.AttributeType.Input)


def _apply_preview_material_preset(stage, material_prim, preset: dict) -> None:
    material = UsdShade.Material(material_prim)
    shader = _get_preview_shader(stage, material_prim)

    linear_base_color = tuple(_srgb_channel_to_linear(channel) for channel in preset["base_color_srgb"])
    specular_color = (preset["specular"], preset["specular"], preset["specular"])

    _get_material_input(material, "diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*linear_base_color))
    _get_material_input(material, "metallic", Sdf.ValueTypeNames.Float).Set(float(preset["metallic"]))
    _get_material_input(material, "roughness", Sdf.ValueTypeNames.Float).Set(float(preset["roughness"]))
    _get_material_input(material, "specular", Sdf.ValueTypeNames.Float).Set(float(preset["specular"]))
    _get_material_input(material, "specularColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*specular_color))

    _connect_preview_input(shader, material, "diffuseColor", Sdf.ValueTypeNames.Color3f)
    _connect_preview_input(shader, material, "metallic", Sdf.ValueTypeNames.Float)
    _connect_preview_input(shader, material, "roughness", Sdf.ValueTypeNames.Float)
    _connect_preview_input(shader, material, "specularColor", Sdf.ValueTypeNames.Color3f)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")


def _apply_omnipbr_material_preset(stage, material_prim, preset: dict) -> None:
    shader_path = material_prim.GetPath().AppendChild("OmniPBR")
    shader = UsdShade.Shader.Get(stage, shader_path)
    if not shader:
        shader = UsdShade.Shader.Define(stage, shader_path)

    linear_base_color = tuple(_srgb_channel_to_linear(channel) for channel in preset["base_color_srgb"])

    shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
    shader.SetSourceAsset("OmniPBR.mdl", "mdl")
    shader.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    shader.CreateOutput("out", Sdf.ValueTypeNames.Token).SetRenderType("material")
    shader.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*linear_base_color))
    shader.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(float(preset["metallic"]))
    shader.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(float(preset["roughness"]))
    shader.CreateInput("specular_level", Sdf.ValueTypeNames.Float).Set(float(preset["specular"]))

    material = UsdShade.Material(material_prim)
    material.CreateSurfaceOutput("mdl").ConnectToSource(shader.ConnectableAPI(), "out")
    material.CreateDisplacementOutput("mdl").ConnectToSource(shader.ConnectableAPI(), "out")
    material.CreateVolumeOutput("mdl").ConnectToSource(shader.ConnectableAPI(), "out")


def patch_imported_robot_materials(materials_usd_path: str) -> None:
    stage = Usd.Stage.Open(materials_usd_path)
    if stage is None:
        raise RuntimeError(f"Failed to reopen generated materials USD: {materials_usd_path}")

    patched_materials = []
    for prim in stage.Traverse():
        if prim.GetTypeName() != "Material":
            continue
        material = UsdShade.Material(prim)
        diffuse_input = material.GetInput("diffuseColor")
        diffuse_color = _vec3_to_tuple(diffuse_input.Get() if diffuse_input else None)
        if diffuse_color is None:
            continue

        preset_name = _classify_robot_material(diffuse_color)
        if preset_name is None:
            continue

        _apply_preview_material_preset(stage, prim, ROBOT_MATERIAL_PRESETS[preset_name])
        _apply_omnipbr_material_preset(stage, prim, ROBOT_MATERIAL_PRESETS[preset_name])
        patched_materials.append(f"{prim.GetPath()}:{preset_name}")

    if not patched_materials:
        raise RuntimeError(f"No A1Z robot materials matched the expected color groups in {materials_usd_path}")

    stage.GetRootLayer().Save()
    print(f"Patched robot materials: {', '.join(patched_materials)}")


def patch_imported_gripper_collision_meshes(stage, root_prim_path: str) -> None:
    if not WITH_GRIPPER:
        print("Skipping gripper collision mesh patch because A1Z_WITH_GRIPPER=0.")
        return
    root_prim = stage.GetPrimAtPath(root_prim_path)
    if not root_prim.IsValid():
        raise RuntimeError(f"Invalid imported robot root prim: {root_prim_path}")
    patched_prims = []
    for prim in Usd.PrimRange(root_prim):
        prim_path = str(prim.GetPath())
        if "gripper_finger_left_link" not in prim_path and "gripper_finger_rIght_link" not in prim_path:
            continue
        mesh_collision = UsdPhysics.MeshCollisionAPI(prim)
        if not mesh_collision:
            continue

        mesh_collision.CreateApproximationAttr().Set(UsdPhysics.Tokens.convexDecomposition)
        patched_prims.append(prim_path)

    if not patched_prims:
        print("Warning: no gripper collision mesh prims were found to patch on the imported robot stage.")
        return

    _apply_gripper_pad_physics_material(
        stage,
        patched_prims,
        f"{root_prim_path}/PhysicsMaterials/A1ZGripperPad",
    )
    print(f"Patched gripper collision meshes: {', '.join(patched_prims)}")


def _apply_gripper_pad_physics_material(
    stage,
    collision_prim_paths: list[str],
    material_path: str,
) -> None:
    UsdGeom.Scope.Define(stage, str(Sdf.Path(material_path).GetParentPath()))
    material = UsdShade.Material.Define(stage, material_path)
    material_api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    material_api.CreateStaticFrictionAttr().Set(2.0)
    material_api.CreateDynamicFrictionAttr().Set(1.5)
    material_api.CreateRestitutionAttr().Set(0.0)
    physx_material_api = PhysxSchema.PhysxMaterialAPI.Apply(material.GetPrim())
    physx_material_api.CreateFrictionCombineModeAttr().Set("max")
    physx_material_api.CreateRestitutionCombineModeAttr().Set("min")
    for prim_path in collision_prim_paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid gripper collision prim while binding friction: {prim_path}")
        UsdShade.MaterialBindingAPI.Apply(prim)
        prim.CreateRelationship("material:binding:physics", custom=False).SetTargets(
            [Sdf.Path(material_path)]
        )


def patch_imported_gripper_visual_instanceability(base_usd_path: str) -> bool:
    if not WITH_GRIPPER:
        print("Skipping gripper instanceability patch because A1Z_WITH_GRIPPER=0.")
        return False
    stage = Usd.Stage.Open(str(base_usd_path))
    if stage is None:
        raise RuntimeError(f"Failed to reopen generated base payload USD: {base_usd_path}")

    patched_paths: list[str] = []
    for prim_path in GRIPPER_INNER_INSTANCE_PRIM_PATHS:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            continue
        if prim.IsInstanceable():
            prim.SetInstanceable(False)
            patched_paths.append(prim_path)

    if not patched_paths:
        print("Warning: no gripper inner instance prims were found to de-instance in base.usda.")
        return False

    stage.GetRootLayer().Save()
    print(f"Disabled gripper inner instanceability: {', '.join(patched_paths)}")
    return True


def filter_gripper_finger_pair(stage, root_prim_path: str) -> None:
    if not WITH_GRIPPER:
        print("Skipping gripper collision filtering because A1Z_WITH_GRIPPER=0.")
        return
    root_prim = stage.GetPrimAtPath(root_prim_path)
    if not root_prim.IsValid():
        raise RuntimeError(f"Invalid imported robot root prim: {root_prim_path}")

    link_prims = {}
    for prim in Usd.PrimRange(root_prim):
        name = prim.GetName()
        if name not in GRIPPER_LINK_NAMES:
            continue
        current = link_prims.get(name)
        if current is None or prim.GetPath().pathElementCount < current.GetPath().pathElementCount:
            link_prims[name] = prim
    missing = [name for name in GRIPPER_LINK_NAMES if name not in link_prims]
    if missing:
        print(f"Warning: skipping gripper collision filtering because these links are absent: {missing}")
        return

    left_prim = link_prims[GRIPPER_LINK_NAMES[0]]
    right_path = link_prims[GRIPPER_LINK_NAMES[1]].GetPath()
    filtered_pairs = UsdPhysics.FilteredPairsAPI.Apply(left_prim)
    filtered_pairs.CreateFilteredPairsRel().AddTarget(right_path)
    print(f"Filtered gripper finger collision pair: {left_prim.GetPath()} <-> {right_path}")


def patch_imported_gripper_collision_meshes_in_physics_layer(robot_usd_path: str) -> bool:
    if not WITH_GRIPPER:
        print("Skipping gripper physics patch because A1Z_WITH_GRIPPER=0.")
        return False
    robot_path = Path(robot_usd_path)
    physics_layer_path = robot_path.parent / "configuration" / f"{robot_path.stem}_physics.usd"
    if not physics_layer_path.is_file():
        return False

    stage = Usd.Stage.Open(str(physics_layer_path))
    if stage is None:
        raise RuntimeError(f"Failed to reopen generated physics USD: {physics_layer_path}")

    patched_joint_paths = _patch_gripper_joint_drives(stage, "/A1Z_G1Z/joints")
    prim_roots = (
        "/colliders/gripper_finger_left_link",
        "/colliders/gripper_finger_rIght_link",
    )
    patched_prims = []
    for prim_root in prim_roots:
        root_prim = stage.GetPrimAtPath(prim_root)
        if not root_prim.IsValid():
            continue
        for prim in Usd.PrimRange(root_prim):
            mesh_collision = UsdPhysics.MeshCollisionAPI(prim)
            if not mesh_collision:
                continue
            mesh_collision.CreateApproximationAttr().Set(UsdPhysics.Tokens.convexDecomposition)
            patched_prims.append(str(prim.GetPath()))

    if not patched_joint_paths and not patched_prims:
        print("Warning: gripper physics patch skipped because no gripper joints or collision prims were found.")
        return False

    if not patched_prims:
        print(
            "Warning: no gripper PhysicsMeshCollisionAPI prims were found "
            f"under the expected physics USD subtrees: {prim_roots}"
        )
        stage.GetRootLayer().Save()
        return False

    _apply_gripper_pad_physics_material(
        stage,
        patched_prims,
        "/PhysicsMaterials/A1ZGripperPad",
    )
    stage.GetRootLayer().Save()
    print(
        "Patched gripper physics in physics USD: "
        f"joints={', '.join(patched_joint_paths)} collisions={', '.join(patched_prims)}"
    )
    return True


def resolve_imported_payload_usd_path(
    imported_usd_path: str,
    robot_usd_path: str,
    payload_filename: str,
    *,
    required: bool = True,
) -> str | None:
    imported_path = Path(imported_usd_path)
    robot_path = Path(robot_usd_path)
    candidates = [
        imported_path.parent / "payloads" / payload_filename,
        robot_path.parent / imported_path.stem / "payloads" / payload_filename,
    ]
    candidates.extend(sorted(robot_path.parent.glob(f"A1Z_G1Z_isaac*/payloads/{payload_filename}")))

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return str(candidate)

    if not required:
        return None

    searched = "\n  ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Could not locate generated {payload_filename}. Searched:\n  {searched}")


def patch_imported_robot_usd(
    robot_usd_path: str,
    root_prim_path: str,
    materials_usd_path: str | None,
    base_usd_path: str | None,
):
    if materials_usd_path:
        patch_imported_robot_materials(materials_usd_path)
    if base_usd_path:
        patch_imported_gripper_visual_instanceability(base_usd_path)

    physics_layer_patched = patch_imported_gripper_collision_meshes_in_physics_layer(robot_usd_path)

    stage = Usd.Stage.Open(robot_usd_path)
    if stage is None:
        raise RuntimeError(f"Failed to reopen generated robot USD: {robot_usd_path}")
    _relativize_internal_relationship_targets(stage, root_prim_path)
    _reset_nested_rigid_body_xforms(stage, root_prim_path)
    if not physics_layer_patched:
        patch_imported_joint_drives(stage, root_prim_path)
        patch_imported_gripper_collision_meshes(stage, root_prim_path)
    filter_gripper_finger_pair(stage, root_prim_path)
    stage.GetRootLayer().Save()


def relocate_robot_root_usd(imported_usd_path: str, robot_usd_path: str) -> None:
    imported_path = Path(imported_usd_path)
    target_path = Path(robot_usd_path)
    ensure_parent_dir(str(target_path))

    content = imported_path.read_text(encoding="utf-8")
    payload_prefix = f"./{imported_path.parent.name}/payloads/"
    content = content.replace("@./payloads/", f"@{payload_prefix}")
    target_path.write_text(content, encoding="utf-8")
    imported_path.unlink()


def configure_world_stage(stage):
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    world = UsdGeom.Xform.Define(stage, Sdf.Path("/World"))
    stage.SetDefaultPrim(world.GetPrim())

    scene = UsdPhysics.Scene.Define(stage, Sdf.Path("/physicsScene"))
    scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
    scene.CreateGravityMagnitudeAttr().Set(9.81)

    physx_scene = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/physicsScene"))
    physx_scene.CreateEnableCCDAttr(True)
    physx_scene.CreateEnableStabilizationAttr(True)
    physx_scene.CreateEnableGPUDynamicsAttr(False)
    physx_scene.CreateBroadphaseTypeAttr("MBP")
    physx_scene.CreateSolverTypeAttr("TGS")

    ground = UsdGeom.Cube.Define(stage, Sdf.Path("/World/GroundPlane"))
    ground.CreateSizeAttr(1.0)
    ground.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, -0.01))
    ground.AddScaleOp().Set(Gf.Vec3f(4.0, 4.0, 0.02))
    UsdPhysics.CollisionAPI.Apply(ground.GetPrim())
    ground_visual_prim = _create_ground_visual(stage)
    _configure_ground_material(stage, ground_visual_prim)

    distant_light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/DistantLight"))
    distant_light.CreateIntensityAttr(900.0)
    distant_light.AddRotateXYZOp().Set(Gf.Vec3f(35.0, 0.0, 35.0))

    dome_light = UsdLux.DomeLight.Define(stage, Sdf.Path("/World/DomeLight"))
    dome_light.CreateIntensityAttr(350.0)


def import_robot_asset(urdf_path, robot_usd_path):
    omni.usd.get_context().new_stage()
    update_app(5)

    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    importer = URDFImporter(
        URDFImporterConfig(
            urdf_path=urdf_path,
            usd_path=os.path.dirname(robot_usd_path),
            merge_fixed_joints=False,
            merge_mesh=False,
            fix_base=True,
            robot_type="Manipulator",
            joint_drive_type=str(ISAAC_CFG.get("arm_drive_type", "force")),
            joint_target_type="position",
            override_joint_stiffness=float(max(ISAAC_CFG["position_hold_kp"])),
            override_joint_damping=float(max(ISAAC_CFG["position_hold_kd"])),
            run_asset_transformer=True,
            run_multi_physics_conversion=True,
        )
    )
    imported_usd_path = importer.import_urdf()
    update_app(20)

    if not imported_usd_path or not os.path.isfile(imported_usd_path):
        raise RuntimeError(f"Failed to import URDF with the Isaac Sim 6 importer: {urdf_path}")

    if os.path.abspath(imported_usd_path) != os.path.abspath(robot_usd_path):
        relocate_robot_root_usd(imported_usd_path, robot_usd_path)

    robot_prim_path = "/A1Z_G1Z"
    payload_locator_path = imported_usd_path

    materials_usd_path = resolve_imported_payload_usd_path(
        payload_locator_path,
        robot_usd_path,
        "materials.usda",
        required=False,
    )
    base_usd_path = resolve_imported_payload_usd_path(
        payload_locator_path,
        robot_usd_path,
        "base.usda",
        required=False,
    )
    update_app(10)
    patch_imported_robot_usd(robot_usd_path, robot_prim_path, materials_usd_path, base_usd_path)

    return robot_prim_path


def build_world(robot_usd_path, world_usd_path, robot_prim_path):
    omni.usd.get_context().new_stage()
    update_app(5)

    stage = omni.usd.get_context().get_stage()
    configure_world_stage(stage)

    robot_prim = stage.DefinePrim(robot_prim_path, "Xform")
    robot_reference = os.path.relpath(
        os.path.abspath(robot_usd_path),
        start=os.path.dirname(os.path.abspath(world_usd_path)),
    ).replace(os.sep, "/")
    robot_prim.GetReferences().AddReference(robot_reference)
    update_app(10)

    if not stage.GetRootLayer().Export(world_usd_path):
        raise RuntimeError(f"Failed to export generated world stage: {world_usd_path}")
    update_app(5)


def main():
    args = parse_args()

    for path in (args.urdf,):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

    for path in (args.robot_usd, args.world_usd):
        ensure_parent_dir(path)

    world_exists = os.path.isfile(args.world_usd)
    rebuild_world = args.rebuild_world or not world_exists
    trashset_overlay_usda = default_trashset_overlay_usda_path(args.world_usd)

    cleanup_generated_usd(args.robot_usd, args.world_usd, rebuild_world=rebuild_world)

    robot_prim_path = import_robot_asset(args.urdf, args.robot_usd)
    if rebuild_world:
        build_world(args.robot_usd, args.world_usd, args.robot_prim)
        ensure_world_sublayer(args.world_usd, trashset_overlay_usda)
    else:
        print(f"Preserved existing world USD: {args.world_usd}")

    print(f"URDF source: {args.urdf}")
    print(f"Robot USD:   {args.robot_usd}")
    print(f"World USD:   {args.world_usd}")
    print(f"Robot prim:  {robot_prim_path}")


if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        simulation_app.close()
    sys.exit(exit_code)
