#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import sys

from isaacsim import SimulationApp


def parse_args():
    parser = argparse.ArgumentParser(description="Import the A1Z_G1Z URDF into Isaac Sim and save robot/world USDs.")
    parser.add_argument(
        "--urdf",
        default="/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf",
        help="Absolute path to the source URDF.",
    )
    parser.add_argument(
        "--robot-usd",
        default="/workspace/A1Z/build/scenes/A1Z_G1Z_robot.usd",
        help="Absolute path to the generated robot USD.",
    )
    parser.add_argument(
        "--world-usd",
        default="/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd",
        help="Absolute path to the generated world USD.",
    )
    parser.add_argument(
        "--robot-prim",
        default="/World/A1Z_G1Z",
        help="Prim path used when referencing the robot into the world stage.",
    )
    args, _ = parser.parse_known_args()
    return args


simulation_app = SimulationApp({"headless": True})

import omni.kit.commands  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.utils.extensions import enable_extension  # noqa: E402
from isaacsim.core.utils.stage import save_stage  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade  # noqa: E402

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SDK_DIR = os.path.join(ROOT_DIR, "vendor", "GALAXEA-A1Z")
if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)

from a1z.config import get_control_defaults  # noqa: E402

ISAAC_CFG = get_control_defaults()["isaacsim"]
ARM_JOINT_NAMES = list(ISAAC_CFG["arm_joint_names"])
GRIPPER_JOINT_NAMES = list(ISAAC_CFG["gripper_joint_names"])
ARM_JOINT_DRIVE_STIFFNESS = dict(zip(ARM_JOINT_NAMES, ISAAC_CFG["position_hold_kp"], strict=True))
ARM_JOINT_DRIVE_DAMPING = dict(zip(ARM_JOINT_NAMES, ISAAC_CFG["position_hold_kd"], strict=True))
ARM_JOINT_MAX_FORCE = dict(zip(ARM_JOINT_NAMES, ISAAC_CFG["arm_max_effort"], strict=True))
GRIPPER_JOINT_DRIVE_STIFFNESS = dict(zip(GRIPPER_JOINT_NAMES, ISAAC_CFG["gripper_kp"], strict=True))
GRIPPER_JOINT_DRIVE_DAMPING = dict(zip(GRIPPER_JOINT_NAMES, ISAAC_CFG["gripper_kd"], strict=True))
GRIPPER_JOINT_MAX_FORCE = dict(zip(GRIPPER_JOINT_NAMES, ISAAC_CFG["gripper_max_effort"], strict=True))


def update_app(frames=5):
    for _ in range(frames):
        simulation_app.update()


def ensure_parent_dir(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def cleanup_generated_usd(robot_usd_path: str, world_usd_path: str) -> None:
    robot_path = Path(robot_usd_path)
    world_path = Path(world_usd_path)
    config_dir = robot_path.parent / "configuration"
    robot_stem = robot_path.stem

    for path in (robot_path, world_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    if config_dir.is_dir():
        for child in config_dir.glob(f"{robot_stem}_*.usd"):
            try:
                child.unlink()
            except FileNotFoundError:
                pass


def _set_joint_drive(
    stage,
    joint_path: str,
    drive_type: str,
    stiffness: float,
    damping: float,
    max_force: float | None = None,
):
    prim = stage.GetPrimAtPath(joint_path)
    if not prim.IsValid():
        raise RuntimeError(f"Joint prim not found in imported USD: {joint_path}")

    drive = UsdPhysics.DriveAPI.Get(prim, drive_type)
    if not drive:
        drive = UsdPhysics.DriveAPI.Apply(prim, drive_type)

    drive.CreateTypeAttr().Set("acceleration")
    drive.CreateTargetPositionAttr().Set(0.0)
    drive.CreateTargetVelocityAttr().Set(0.0)
    drive.CreateStiffnessAttr().Set(float(stiffness))
    drive.CreateDampingAttr().Set(float(damping))
    if max_force is not None:
        drive.CreateMaxForceAttr().Set(float(max_force))


def patch_imported_joint_drives(stage, root_prim_path: str):
    candidates = [
        f"{root_prim_path}/joints",
        f"{root_prim_path}/root_joint/joints",
        "/A1Z_G1Z/root_joint/joints",
        "/World/A1Z_G1Z/root_joint/joints",
    ]
    joints_root = None
    for candidate in candidates:
        if stage.GetPrimAtPath(candidate).IsValid():
            joints_root = candidate
            break
    if joints_root is None:
        raise RuntimeError(
            f"Could not locate imported joints root for {root_prim_path}. "
            f"Tried: {candidates}"
        )

    for joint_name, stiffness in ARM_JOINT_DRIVE_STIFFNESS.items():
        _set_joint_drive(
            stage=stage,
            joint_path=f"{joints_root}/{joint_name}",
            drive_type="angular",
            stiffness=stiffness,
            damping=ARM_JOINT_DRIVE_DAMPING[joint_name],
            max_force=ARM_JOINT_MAX_FORCE[joint_name],
        )

    for joint_name, stiffness in GRIPPER_JOINT_DRIVE_STIFFNESS.items():
        _set_joint_drive(
            stage=stage,
            joint_path=f"{joints_root}/{joint_name}",
            drive_type="linear",
            stiffness=stiffness,
            damping=GRIPPER_JOINT_DRIVE_DAMPING[joint_name],
            max_force=GRIPPER_JOINT_MAX_FORCE[joint_name],
        )


def patch_imported_robot_usd(robot_usd_path: str, root_prim_path: str):
    stage = Usd.Stage.Open(robot_usd_path)
    if stage is None:
        raise RuntimeError(f"Failed to reopen generated robot USD: {robot_usd_path}")
    patch_imported_joint_drives(stage, root_prim_path)
    stage.GetRootLayer().Save()


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
    ground.AddScaleOp().Set(Gf.Vec3f(4.0, 4.0, 0.02))
    ground.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, -0.01))
    UsdPhysics.CollisionAPI.Apply(ground.GetPrim())

    ground_material = UsdShade.Material.Define(stage, Sdf.Path("/World/Looks/GroundMaterial"))
    shader = UsdShade.Shader.Define(stage, Sdf.Path("/World/Looks/GroundMaterial/Shader"))
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.18, 0.18, 0.18))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.6)
    ground_material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI(ground.GetPrim()).Bind(ground_material)

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

    status, import_config = omni.kit.commands.execute("URDFCreateImportConfig")
    if not status:
        raise RuntimeError("Failed to create URDF import config.")

    import_config.merge_fixed_joints = False
    import_config.convex_decomp = False
    import_config.import_inertia_tensor = True
    import_config.fix_base = True
    import_config.make_default_prim = True
    import_config.create_physics_scene = False
    import_config.distance_scale = 1.0
    import_config.override_joint_dynamics = True
    import_config.default_drive_strength = float(max(ISAAC_CFG["position_hold_kp"]))
    import_config.default_position_drive_damping = float(max(ISAAC_CFG["position_hold_kd"]))

    status, robot_prim_path = omni.kit.commands.execute(
        "URDFParseAndImportFile",
        urdf_path=urdf_path,
        import_config=import_config,
        dest_path=robot_usd_path,
        get_articulation_root=True,
    )
    update_app(20)

    if not status:
        raise RuntimeError(f"Failed to import URDF: {urdf_path}")

    update_app(10)
    patch_imported_robot_usd(robot_usd_path, robot_prim_path)

    return robot_prim_path


def build_world(robot_usd_path, world_usd_path, robot_prim_path):
    omni.usd.get_context().new_stage()
    update_app(5)

    stage = omni.usd.get_context().get_stage()
    configure_world_stage(stage)

    robot_prim = stage.DefinePrim(robot_prim_path, "Xform")
    robot_prim.GetReferences().AddReference(robot_usd_path)
    update_app(10)

    save_stage(world_usd_path, save_and_reload_in_place=False)
    update_app(5)


def main():
    args = parse_args()

    for path in (args.urdf,):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

    for path in (args.robot_usd, args.world_usd):
        ensure_parent_dir(path)

    cleanup_generated_usd(args.robot_usd, args.world_usd)

    enable_extension("isaacsim.asset.importer.urdf")
    update_app(20)

    robot_prim_path = import_robot_asset(args.urdf, args.robot_usd)
    build_world(args.robot_usd, args.world_usd, args.robot_prim)

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
