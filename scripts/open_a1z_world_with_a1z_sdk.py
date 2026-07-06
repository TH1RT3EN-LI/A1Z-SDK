#!/usr/bin/env python3

import argparse
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

import carb
import numpy as np
import omni.kit.app
import omni.kit.async_engine
import omni.timeline
import omni.usd
from omni.kit.viewport.utility import capture_viewport_to_file, frame_viewport_prims, get_active_viewport
from omni.kit.viewport.utility.camera_state import ViewportCameraState
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.dirname(__file__)
SDK_DIR = os.path.join(ROOT_DIR, "vendor", "GALAXEA-A1Z")
RUNTIME_DIR = os.path.join(ROOT_DIR, "runtime")
RUNTIME_LOG_DIR = os.path.join(RUNTIME_DIR, "logs")
LOG_DIR = os.path.join(ROOT_DIR, "logs")
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

from a1z_ext.config import get_control_defaults  # noqa: E402
from a1z_ext.config import get_default_control_urdf_path  # noqa: E402
from a1z_ext.config import get_socket_path  # noqa: E402
from a1z_ext.config import get_tcp_host, get_tcp_port  # noqa: E402
from a1z_ext.runtime.d405 import attach_d405_wrist_camera  # noqa: E402
from a1z_ext.runtime.d405.session import D405CaptureSettings, D405FrameSession  # noqa: E402
from a1z_ext.robots.get_robot import create_a1z_robot  # noqa: E402
from a1z_ext.robots.server import RobotServer  # noqa: E402


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _viewport_enabled() -> bool:
    if "A1Z_VIEWPORT_ENABLED" in os.environ:
        return _env_flag("A1Z_VIEWPORT_ENABLED", False)
    return bool(os.environ.get("DISPLAY"))


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw


def _env_int(name: str, default: int) -> int:
    return int(_env_str(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(_env_str(name, str(default)))


def _env_vec3(name: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 3:
        raise ValueError(f"{name} must contain three comma-separated floats, got: {raw!r}")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def _normalize_stage_path(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).expanduser().resolve())
    except OSError:
        return os.path.abspath(os.path.expanduser(path))


def _get_current_stage_path() -> str | None:
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return None
    root_layer = stage.GetRootLayer()
    if root_layer is None:
        return None
    for candidate in (root_layer.realPath, root_layer.identifier):
        normalized = _normalize_stage_path(candidate)
        if normalized:
            return normalized
    return None


def _load_kinematics_class():
    try:
        from a1z.robots.kinematics import Kinematics
    except ImportError as exc:
        raise RuntimeError(
            "EE drag target requires Pinocchio/Kinematics support. "
            "Install the SDK dependencies or disable A1Z_EE_DRAG_TARGET_ENABLED."
        ) from exc
    return Kinematics


def _load_pinocchio_module():
    try:
        import pinocchio
    except ImportError as exc:
        raise RuntimeError(
            "EE drag target requires Pinocchio support. "
            "Install the SDK dependencies or disable A1Z_EE_DRAG_TARGET_ENABLED."
        ) from exc
    return pinocchio


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


def _apply_wrist_payload_collision_filters(stage) -> None:
    if stage is None:
        return
    base = Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6")
    wrist_paths = [base.AppendChild("d405_link")]
    for source_path in wrist_paths:
        source_prim = stage.GetPrimAtPath(source_path)
        if not source_prim.IsValid():
            continue
        api = UsdPhysics.FilteredPairsAPI.Apply(source_prim)
        existing = list(api.GetFilteredPairsRel().GetTargets() or [])
        merged = set(existing)
        merged.add(base)
        for target_path in wrist_paths:
            if target_path != source_path:
                merged.add(target_path)
        api.GetFilteredPairsRel().SetTargets(sorted(merged, key=str))


def _apply_adjacent_arm_collision_filters(stage) -> None:
    if stage is None:
        return
    pair_paths = [
        (
            Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link4_1"),
            Sdf.Path(
                "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link5_1"
            ),
        ),
        (
            Sdf.Path(
                "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link5_1"
            ),
            Sdf.Path(
                "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/arm_link6_1"
            ),
        ),
    ]
    for source_path, target_path in pair_paths:
        source_prim = stage.GetPrimAtPath(source_path)
        target_prim = stage.GetPrimAtPath(target_path)
        if not source_prim.IsValid() or not target_prim.IsValid():
            continue
        api = UsdPhysics.FilteredPairsAPI.Apply(source_prim)
        existing = list(api.GetFilteredPairsRel().GetTargets() or [])
        merged = set(existing)
        merged.add(target_path)
        api.GetFilteredPairsRel().SetTargets(sorted(merged, key=str))


def _apply_arm_internal_collision_filters(stage) -> None:
    if stage is None:
        return
    collision_paths = [
        Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/base_link_1"),
        Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link1_1"),
        Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link2_1"),
        Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link3_1"),
        Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link4_1"),
        Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link5_1"),
        Sdf.Path(
            "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/arm_link6_1"
        ),
    ]
    valid_paths = [path for path in collision_paths if stage.GetPrimAtPath(path).IsValid()]
    for source_path in valid_paths:
        source_prim = stage.GetPrimAtPath(source_path)
        api = UsdPhysics.FilteredPairsAPI.Apply(source_prim)
        existing = list(api.GetFilteredPairsRel().GetTargets() or [])
        merged = set(existing)
        for target_path in valid_paths:
            if target_path != source_path:
                merged.add(target_path)
        api.GetFilteredPairsRel().SetTargets(sorted(merged, key=str))


def _disable_wrist_payload_collisions(stage) -> None:
    if stage is None:
        return
    base = Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6")
    target_paths = [base.AppendChild("d405_link")]
    for prim_path in target_paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            continue
        prim.RemoveAPI(UsdPhysics.CollisionAPI)
        prim.RemoveAPI(UsdPhysics.MeshCollisionAPI)
        for child in Usd.PrimRange(prim):
            if child == prim:
                continue
            if child.IsA(UsdGeom.Gprim):
                child.RemoveAPI(UsdPhysics.CollisionAPI)
                child.RemoveAPI(UsdPhysics.MeshCollisionAPI)


def _lighten_wrist_payload_dynamics(stage) -> None:
    if stage is None:
        return
    base = Sdf.Path("/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6")
    target_paths = [base.AppendChild("d405_link")]
    for prim_path in target_paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            continue
        mass_api = UsdPhysics.MassAPI.Apply(prim)
        mass_api.CreateMassAttr().Set(1e-4)
        mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(1e-6, 1e-6, 1e-6))


def _set_or_create_attr(schema_obj, getter_name: str, creator_name: str, value) -> None:
    getter = getattr(schema_obj, getter_name, None)
    creator = getattr(schema_obj, creator_name, None)
    if getter is None or creator is None:
        return
    attr = getter()
    if not attr:
        attr = creator()
    attr.Set(value)


def _configure_arm_articulation_physics(stage) -> None:
    if stage is None:
        return
    articulation_root = stage.GetPrimAtPath("/World/A1Z_G1Z/Geometry")
    if not articulation_root.IsValid():
        return

    articulation_api = PhysxSchema.PhysxArticulationAPI.Apply(articulation_root)
    _set_or_create_attr(
        articulation_api,
        "GetEnabledSelfCollisionsAttr",
        "CreateEnabledSelfCollisionsAttr",
        False,
    )
    _set_or_create_attr(
        articulation_api,
        "GetSolverPositionIterationCountAttr",
        "CreateSolverPositionIterationCountAttr",
        64,
    )
    _set_or_create_attr(
        articulation_api,
        "GetSolverVelocityIterationCountAttr",
        "CreateSolverVelocityIterationCountAttr",
        4,
    )
    _set_or_create_attr(
        articulation_api,
        "GetSleepThresholdAttr",
        "CreateSleepThresholdAttr",
        0.0,
    )
    _set_or_create_attr(
        articulation_api,
        "GetStabilizationThresholdAttr",
        "CreateStabilizationThresholdAttr",
        0.0,
    )


def _configure_wrist_link_physics(stage) -> None:
    if stage is None:
        return
    link_paths = [
        "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5",
        "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6",
    ]
    for prim_path in link_paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            continue
        rigid_body_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        _set_or_create_attr(
            rigid_body_api,
            "GetLinearDampingAttr",
            "CreateLinearDampingAttr",
            0.05,
        )
        _set_or_create_attr(
            rigid_body_api,
            "GetAngularDampingAttr",
            "CreateAngularDampingAttr",
            0.2,
        )
        _set_or_create_attr(
            rigid_body_api,
            "GetSleepThresholdAttr",
            "CreateSleepThresholdAttr",
            0.0,
        )
        _set_or_create_attr(
            rigid_body_api,
            "GetStabilizationThresholdAttr",
            "CreateStabilizationThresholdAttr",
            0.0,
        )
        _set_or_create_attr(
            rigid_body_api,
            "GetSolverPositionIterationCountAttr",
            "CreateSolverPositionIterationCountAttr",
            32,
        )
        _set_or_create_attr(
            rigid_body_api,
            "GetSolverVelocityIterationCountAttr",
            "CreateSolverVelocityIterationCountAttr",
            4,
        )
        _set_or_create_attr(
            rigid_body_api,
            "GetMaxDepenetrationVelocityAttr",
            "CreateMaxDepenetrationVelocityAttr",
            2.0,
        )


def _configure_wrist_joint_physics(stage) -> None:
    if stage is None:
        return
    joint_paths = [
        "/World/A1Z_G1Z/Physics/arm_joint5",
        "/World/A1Z_G1Z/Physics/arm_joint6",
    ]
    drive_targets = {
        "/World/A1Z_G1Z/Physics/arm_joint5": {"stiffness": 18.0, "damping": 7.0, "max_force": 8.0, "max_velocity": 240.0},
        "/World/A1Z_G1Z/Physics/arm_joint6": {"stiffness": 22.0, "damping": 8.0, "max_force": 8.0, "max_velocity": 240.0},
    }
    for joint_path in joint_paths:
        prim = stage.GetPrimAtPath(joint_path)
        if not prim.IsValid():
            continue
        physx_joint_api = PhysxSchema.PhysxJointAPI.Apply(prim)
        _set_or_create_attr(
            physx_joint_api,
            "GetJointFrictionAttr",
            "CreateJointFrictionAttr",
            0.0,
        )
        _set_or_create_attr(
            physx_joint_api,
            "GetMaxJointVelocityAttr",
            "CreateMaxJointVelocityAttr",
            drive_targets[joint_path]["max_velocity"],
        )
        drive = UsdPhysics.DriveAPI.Get(prim, "angular")
        if not drive:
            drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
        if prim.HasAttribute("drive:angular:physics:type"):
            drive.GetTypeAttr().Set("acceleration")
        else:
            drive.CreateTypeAttr().Set("acceleration")
        if prim.HasAttribute("drive:angular:physics:stiffness"):
            drive.GetStiffnessAttr().Set(drive_targets[joint_path]["stiffness"])
        else:
            drive.CreateStiffnessAttr().Set(drive_targets[joint_path]["stiffness"])
        if prim.HasAttribute("drive:angular:physics:damping"):
            drive.GetDampingAttr().Set(drive_targets[joint_path]["damping"])
        else:
            drive.CreateDampingAttr().Set(drive_targets[joint_path]["damping"])
        if prim.HasAttribute("drive:angular:physics:maxForce"):
            drive.GetMaxForceAttr().Set(drive_targets[joint_path]["max_force"])
        else:
            drive.CreateMaxForceAttr().Set(drive_targets[joint_path]["max_force"])


def _enable_trashset_contact_reports(stage) -> None:
    if stage is None:
        return
    target_paths = [
        Sdf.Path("/World/GroundPlane"),
        Sdf.Path("/World/TrashSet"),
    ]
    trash_root = stage.GetPrimAtPath(Sdf.Path("/World/TrashSet"))
    if trash_root.IsValid():
        for prim in trash_root.GetChildren():
            target_paths.append(prim.GetPath())
    for prim_path in target_paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            continue
        if not (
            prim.HasAPI(UsdPhysics.RigidBodyAPI)
            or prim.GetAttribute("physics:rigidBodyEnabled").IsValid()
            or prim.HasAPI(UsdPhysics.CollisionAPI)
        ):
            continue
        report_api = PhysxSchema.PhysxContactReportAPI.Apply(prim)
        if report_api:
            report_api.CreateThresholdAttr().Set(0.0)


def _enforce_nested_rigid_body_reset_xforms(stage, root_prim_path: str) -> list[str]:
    if stage is None or not root_prim_path:
        return []
    root_prim = stage.GetPrimAtPath(root_prim_path)
    if not root_prim.IsValid():
        return []

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

    stop_prim = root_prim.GetParent()
    targets: list[tuple[Usd.Prim, Gf.Matrix4d]] = []
    patched_prims: list[str] = []
    for prim in Usd.PrimRange(root_prim):
        if not _is_rigid_body(prim):
            continue

        ancestor = prim.GetParent()
        has_rigid_body_ancestor = False
        while ancestor and ancestor.IsValid() and ancestor != stop_prim:
            if _is_rigid_body(ancestor):
                has_rigid_body_ancestor = True
                break
            ancestor = ancestor.GetParent()

        if not has_rigid_body_ancestor:
            continue

        xformable = UsdGeom.Xformable(prim)
        if not xformable:
            continue
        if xformable.GetResetXformStack():
            continue

        targets.append((prim, Gf.Matrix4d(xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default()))))

    for prim, world_transform in targets:
        _preserve_world_transform_with_reset(prim, world_transform)
        patched_prims.append(str(prim.GetPath()))

    return patched_prims


async def _capture_d405_diagnostics(stage, viewport) -> None:
    dump_path = os.environ.get("A1Z_D405_STAGE_DUMP_PATH", os.path.join(RUNTIME_LOG_DIR, "d405-stage-dump.txt"))
    _dump_d405_stage_state(stage, dump_path)
    if not _env_flag("A1Z_D405_VIEWPORT_CAPTURE_ENABLED", False):
        return
    if viewport is None:
        return
    capture_path = os.environ.get("A1Z_D405_VIEWPORT_CAPTURE_PATH", os.path.join(RUNTIME_LOG_DIR, "d405-viewport.png"))
    try:
        await capture_viewport_to_file(viewport, file_path=capture_path, is_hdr=False).wait_for_result()
        carb.log_info(f"A1Z D405 viewport capture written: {capture_path}")
    except Exception as exc:
        carb.log_warn(f"A1Z D405 viewport capture failed: {exc}")


async def _capture_viewport_diagnostics_once(stage, viewport) -> bool:
    if viewport is None:
        return False
    warmup_frames = max(0, _env_int("A1Z_VIEWPORT_CAPTURE_WARMUP_FRAMES", 30))
    app = omni.kit.app.get_app()
    for _ in range(warmup_frames):
        await app.next_update_async()
    await _capture_d405_diagnostics(stage, viewport)
    return True


def _gf_matrix_to_np(matrix: Gf.Matrix4d) -> np.ndarray:
    # USD/Gf matrices use row-vector semantics, while the FK/IK code below uses
    # the conventional column-vector homogeneous transform layout.
    return np.array([[float(matrix[row][col]) for col in range(4)] for row in range(4)], dtype=np.float64).T


def _rotation_angle_rad(a_rot: np.ndarray, b_rot: np.ndarray) -> float:
    delta = a_rot.T @ b_rot
    cos_theta = np.clip((np.trace(delta) - 1.0) * 0.5, -1.0, 1.0)
    return float(math.acos(cos_theta))


def _rigidize_transform(transform: np.ndarray) -> np.ndarray:
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


def _matrix_to_quat(matrix: np.ndarray) -> Gf.Quatf:
    m = np.asarray(matrix, dtype=np.float64)
    trace = float(m[0, 0] + m[1, 1] + m[2, 2])
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s

    quat = Gf.Quatf(float(w), Gf.Vec3f(float(x), float(y), float(z)))
    return quat.GetNormalized()


def _pose_payload(transform: np.ndarray) -> dict[str, list[float]]:
    translation = transform[:3, 3]
    sy = math.hypot(float(transform[0, 0]), float(transform[1, 0]))
    singular = sy < 1e-9
    if not singular:
        roll = math.atan2(float(transform[2, 1]), float(transform[2, 2]))
        pitch = math.atan2(float(-transform[2, 0]), sy)
        yaw = math.atan2(float(transform[1, 0]), float(transform[0, 0]))
    else:
        roll = math.atan2(float(-transform[1, 2]), float(transform[1, 1]))
        pitch = math.atan2(float(-transform[2, 0]), sy)
        yaw = 0.0
    return {
        "xyz_m": [float(v) for v in translation.tolist()],
        "rpy_deg": [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)],
    }


class EndEffectorDragTarget:
    _TARGET_SIZE_M = 0.05
    _READY_COLOR = Gf.Vec3f(0.17, 0.82, 0.37)
    _ERROR_COLOR = Gf.Vec3f(0.92, 0.28, 0.24)

    def __init__(
        self,
        *,
        stage: Usd.Stage,
        robot,
        articulation_root_prim: str,
        viewport,
        target_prim_path: str,
        end_effector_frame: str,
        control_urdf: str,
        pos_epsilon_m: float,
        ori_epsilon_deg: float,
        ik_dt: float,
        ik_damping: float,
        ik_max_iters: int,
        position_only: bool,
        posture_weight: float,
        initial_offset_base_m: tuple[float, float, float],
        status_path: str,
    ) -> None:
        self._stage = stage
        self._robot = robot
        self._articulation_root_prim = articulation_root_prim
        self._viewport = viewport
        self._target_prim_path = target_prim_path
        self._end_effector_frame = end_effector_frame
        self._control_urdf = control_urdf
        self._pos_epsilon_m = float(pos_epsilon_m)
        self._ori_epsilon_rad = math.radians(float(ori_epsilon_deg))
        self._ik_dt = float(ik_dt)
        self._ik_damping = float(ik_damping)
        self._ik_max_iters = int(ik_max_iters)
        self._position_only = bool(position_only)
        self._posture_weight = max(0.0, float(posture_weight))
        self._initial_offset_base = np.asarray(initial_offset_base_m, dtype=np.float64).reshape(3)
        self._status_path = Path(status_path)

        Kinematics = _load_kinematics_class()
        self._pinocchio = _load_pinocchio_module()
        self._kinematics = Kinematics(control_urdf, end_effector_frame=end_effector_frame)
        self._joint_lower = np.asarray(self._kinematics._model.lowerPositionLimit, dtype=np.float64).reshape(-1)
        self._joint_upper = np.asarray(self._kinematics._model.upperPositionLimit, dtype=np.float64).reshape(-1)
        self._joint_names = [f"J{i + 1}" for i in range(self._joint_lower.size)]

        self._base_link_prim_path = self._resolve_descendant_prim_path("base_link")
        try:
            self._ee_link_prim_path = self._resolve_descendant_prim_path(end_effector_frame)
        except RuntimeError:
            # Some end-effector frames exist only in the control URDF for FK/IK and do not
            # correspond to a concrete rigid prim inside the Isaac stage.
            self._ee_link_prim_path = self._resolve_descendant_prim_path("arm_link6")
        self._target_geom: UsdGeom.Cube | None = None
        self._translate_op = None
        self._orient_op = None

        self._last_target_world: np.ndarray | None = None
        self._last_ik_q: np.ndarray | None = None
        self._last_status_sig: tuple[object, ...] | None = None

    def initialize(self) -> None:
        target_geom = UsdGeom.Cube.Define(self._stage, self._target_prim_path)
        target_geom.CreateSizeAttr(self._TARGET_SIZE_M)
        target_geom.CreateDisplayColorAttr([self._READY_COLOR])
        target_geom.CreateDisplayOpacityAttr([0.92])

        xformable = UsdGeom.Xformable(target_geom.GetPrim())
        xformable.ClearXformOpOrder()
        self._translate_op = xformable.AddTranslateOp()
        self._orient_op = xformable.AddOrientOp()

        current_world = self._current_end_effector_world_from_fk()
        initial_world = self._pick_initial_target_world(current_world)
        self._set_target_world_transform(initial_world)
        self._last_target_world = initial_world.copy()
        self._target_geom = target_geom

        selection = omni.usd.get_context().get_selection()
        selection.set_selected_prim_paths([self._target_prim_path], False)
        if self._viewport is not None:
            try:
                frame_viewport_prims(self._viewport, [self._target_prim_path])
            except Exception as exc:
                carb.log_warn(f"A1Z EE drag target framing skipped: {exc}")

        self._write_status(
            state="ready",
            last_error=None,
            transform=initial_world,
            debug=self._joint_debug_payload(),
        )
        carb.log_info(
            "A1Z EE drag target ready: "
            f"path={self._target_prim_path} base={self._base_link_prim_path} ee={self._ee_link_prim_path} "
            f"mode={'position_only' if self._position_only else 'full_pose'} "
            "Drag this target with the viewport transform gizmo."
        )

    def update(self) -> None:
        target_world = self._world_transform(self._target_prim_path)
        if self._last_target_world is not None:
            pos_delta = np.linalg.norm(target_world[:3, 3] - self._last_target_world[:3, 3])
            ori_delta = (
                0.0
                if self._position_only
                else _rotation_angle_rad(self._last_target_world[:3, :3], target_world[:3, :3])
            )
            if pos_delta < self._pos_epsilon_m and ori_delta < self._ori_epsilon_rad:
                return

        base_world = self._world_transform(self._base_link_prim_path)
        target_in_base = np.linalg.inv(base_world) @ target_world
        seed_q = np.asarray(self._robot.get_joint_state()["pos"], dtype=np.float64).copy()
        converged, ik_q = self._solve_ik(target_in_base, seed_q)
        debug = self._joint_debug_payload(seed_q=seed_q, ik_q=ik_q)

        self._last_target_world = target_world.copy()
        if not converged:
            self._set_target_color(self._ERROR_COLOR)
            self._hold_current_joint_position()
            self._write_status(
                state="ik_failed",
                last_error="IK did not converge for the requested target pose.",
                transform=target_world,
                debug=debug,
            )
            return

        tol = 1e-6
        if np.any(ik_q < self._joint_lower - tol) or np.any(ik_q > self._joint_upper + tol):
            self._set_target_color(self._ERROR_COLOR)
            self._hold_current_joint_position()
            self._write_status(
                state="joint_limit_violation",
                last_error="IK solution violates control URDF joint limits.",
                transform=target_world,
                debug=debug,
            )
            return

        ik_q = np.clip(ik_q, self._joint_lower, self._joint_upper)
        self._robot.command_joint_pos(ik_q)
        self._last_ik_q = ik_q.copy()
        self._set_target_color(self._READY_COLOR)
        self._write_status(state="tracking", last_error=None, transform=target_world, debug=debug)

    def _resolve_descendant_prim_path(self, prim_name: str) -> str:
        root = self._stage.GetPrimAtPath(self._articulation_root_prim)
        if not root.IsValid():
            raise RuntimeError(f"Invalid articulation root prim: {self._articulation_root_prim}")
        for prim in Usd.PrimRange(root):
            if prim.GetName() == prim_name:
                return prim.GetPath().pathString
        raise RuntimeError(f"Could not resolve prim '{prim_name}' under root {self._articulation_root_prim}")

    def _world_transform(self, prim_path: str) -> np.ndarray:
        prim = self._stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid stage prim: {prim_path}")
        cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        return _rigidize_transform(_gf_matrix_to_np(cache.GetLocalToWorldTransform(prim)))

    def _current_end_effector_world_from_fk(self) -> np.ndarray:
        base_world = self._world_transform(self._base_link_prim_path)
        current_q = self._robot.get_joint_state()["pos"]
        ee_in_base = self._kinematics.fk(current_q, frame_name=self._end_effector_frame)
        return base_world @ ee_in_base

    def _pick_initial_target_world(self, current_world: np.ndarray) -> np.ndarray:
        base_world = self._world_transform(self._base_link_prim_path)
        current_q = np.asarray(self._robot.get_joint_state()["pos"], dtype=np.float64)
        offset_candidates = [
            self._initial_offset_base,
            np.array([self._initial_offset_base[0], -self._initial_offset_base[1], self._initial_offset_base[2]]),
            self._initial_offset_base * np.array([0.6, 0.6, 1.0], dtype=np.float64),
            np.array([max(0.04, abs(self._initial_offset_base[0]) * 0.5), 0.0, max(0.03, self._initial_offset_base[2])]),
            np.array([0.0, math.copysign(max(0.05, abs(self._initial_offset_base[1]) * 0.5), self._initial_offset_base[1] or 1.0), max(0.03, self._initial_offset_base[2])]),
        ]

        seen_offsets: set[tuple[float, float, float]] = set()
        for offset_base in offset_candidates:
            offset_base = np.asarray(offset_base, dtype=np.float64).reshape(3)
            offset_key = tuple(float(v) for v in np.round(offset_base, 6).tolist())
            if offset_key in seen_offsets:
                continue
            seen_offsets.add(offset_key)

            candidate_world = current_world.copy()
            candidate_world[:3, 3] = current_world[:3, 3] + (base_world[:3, :3] @ offset_base)
            if self._target_world_is_reachable(candidate_world, seed_q=current_q, base_world=base_world):
                carb.log_info(
                    "A1Z EE drag target initial offset selected "
                    f"(base frame meters): {offset_key}"
                )
                return candidate_world

        carb.log_warn(
            "A1Z EE drag target could not find a reachable offset pose; falling back to the current end-effector pose."
        )
        return current_world.copy()

    def _target_world_is_reachable(
        self,
        target_world: np.ndarray,
        *,
        seed_q: np.ndarray,
        base_world: np.ndarray | None = None,
    ) -> bool:
        if base_world is None:
            base_world = self._world_transform(self._base_link_prim_path)
        target_in_base = np.linalg.inv(base_world) @ target_world
        converged, ik_q = self._solve_ik(target_in_base, np.asarray(seed_q, dtype=np.float64).copy())
        if not converged:
            return False
        tol = 1e-6
        return not (np.any(ik_q < self._joint_lower - tol) or np.any(ik_q > self._joint_upper + tol))

    def _solve_ik(self, target_in_base: np.ndarray, seed_q: np.ndarray) -> tuple[bool, np.ndarray]:
        pos_threshold = max(5e-4, self._pos_epsilon_m * 0.5)
        if self._position_only:
            return self._ik_position_only(
                target_in_base,
                init_q=seed_q,
                pos_threshold=pos_threshold,
                damping=self._ik_damping,
                max_iters=self._ik_max_iters,
            )
        return self._kinematics.ik(
            target_in_base,
            init_q=seed_q,
            frame_name=self._end_effector_frame,
            dt=self._ik_dt,
            pos_threshold=pos_threshold,
            ori_threshold=max(math.radians(1.0), self._ori_epsilon_rad * 0.5),
            damping=self._ik_damping,
            max_iters=self._ik_max_iters,
        )

    def _ik_position_only(
        self,
        target_pose: np.ndarray,
        *,
        init_q: np.ndarray,
        pos_threshold: float,
        damping: float,
        max_iters: int,
    ) -> tuple[bool, np.ndarray]:
        model = self._kinematics._model
        data = self._kinematics._data
        pinocchio = self._pinocchio
        frame_id = model.getFrameId(self._end_effector_frame)

        lower = self._joint_lower
        upper = self._joint_upper
        seed_q = np.clip(np.asarray(init_q, dtype=np.float64).reshape(-1).copy(), lower, upper)
        q = seed_q.copy()
        target_pos = np.asarray(target_pose[:3, 3], dtype=np.float64).reshape(3)

        eye = np.eye(model.nv, dtype=np.float64)
        posture_weight = self._posture_weight
        damping = max(float(damping), 1e-9)
        for _ in range(max_iters):
            pinocchio.forwardKinematics(model, data, q)
            pinocchio.updateFramePlacements(model, data)

            current_pos = np.asarray(data.oMf[frame_id].translation, dtype=np.float64).reshape(3)
            err = target_pos - current_pos
            if float(np.linalg.norm(err)) <= pos_threshold:
                return True, np.clip(q, lower, upper)

            jacobian = pinocchio.computeFrameJacobian(
                model,
                data,
                q,
                frame_id,
                pinocchio.LOCAL_WORLD_ALIGNED,
            )[:3, :]
            lhs = jacobian.T @ jacobian + damping * eye
            rhs = jacobian.T @ err
            if posture_weight > 0.0:
                lhs = lhs + posture_weight * eye
                rhs = rhs + posture_weight * (seed_q - q)

            try:
                dq = np.linalg.solve(lhs, rhs)
            except np.linalg.LinAlgError:
                dq = np.linalg.lstsq(lhs, rhs, rcond=None)[0]
            dq = np.clip(dq, -0.25, 0.25)
            q = pinocchio.integrate(model, q, dq * self._ik_dt)
            q = np.clip(q, lower, upper)

        return False, q

    def _hold_current_joint_position(self) -> None:
        current_q = np.asarray(self._robot.get_joint_state()["pos"], dtype=np.float64).reshape(-1)
        self._robot.command_joint_pos(np.clip(current_q, self._joint_lower, self._joint_upper))

    def _set_target_world_transform(self, transform: np.ndarray) -> None:
        self._translate_op.Set(Gf.Vec3d(*transform[:3, 3].tolist()))
        self._orient_op.Set(_matrix_to_quat(transform[:3, :3]))

    def _set_target_color(self, color: Gf.Vec3f) -> None:
        if self._target_geom is not None:
            self._target_geom.GetDisplayColorAttr().Set([color])

    def _joint_vector_payload(self, q: np.ndarray | None) -> dict[str, list[float]] | None:
        if q is None:
            return None
        vec = np.asarray(q, dtype=np.float64).reshape(-1)
        return {
            "rad": [round(float(v), 6) for v in vec.tolist()],
            "deg": [round(math.degrees(float(v)), 3) for v in vec.tolist()],
        }

    def _joint_limit_margins_deg(self, q: np.ndarray | None) -> list[float] | None:
        if q is None:
            return None
        vec = np.asarray(q, dtype=np.float64).reshape(-1)
        if vec.size != self._joint_lower.size:
            return None
        margins = np.minimum(vec - self._joint_lower, self._joint_upper - vec)
        return [round(math.degrees(float(v)), 3) for v in margins.tolist()]

    def _violating_joints_payload(self, q: np.ndarray | None, tol: float = 1e-6) -> list[dict[str, object]]:
        if q is None:
            return []
        vec = np.asarray(q, dtype=np.float64).reshape(-1)
        if vec.size != self._joint_lower.size:
            return []

        violations = []
        for index, value in enumerate(vec):
            lower = float(self._joint_lower[index])
            upper = float(self._joint_upper[index])
            value = float(value)
            if value < lower - tol:
                violations.append(
                    {
                        "joint": self._joint_names[index],
                        "side": "lower",
                        "q_deg": round(math.degrees(value), 3),
                        "limit_deg": round(math.degrees(lower), 3),
                        "excess_deg": round(math.degrees(lower - value), 3),
                    }
                )
            elif value > upper + tol:
                violations.append(
                    {
                        "joint": self._joint_names[index],
                        "side": "upper",
                        "q_deg": round(math.degrees(value), 3),
                        "limit_deg": round(math.degrees(upper), 3),
                        "excess_deg": round(math.degrees(value - upper), 3),
                    }
                )
        return violations

    def _joint_debug_payload(
        self,
        *,
        seed_q: np.ndarray | None = None,
        ik_q: np.ndarray | None = None,
    ) -> dict[str, object]:
        current_q = np.asarray(self._robot.get_joint_state()["pos"], dtype=np.float64).reshape(-1)
        last_accepted_q = self._last_ik_q.copy() if self._last_ik_q is not None else None
        return {
            "joint_order": self._joint_names,
            "ik_mode": "position_only" if self._position_only else "full_pose",
            "joint_angle_reference": (
                "Control URDF / Isaac articulation joint coordinates, radians internally; "
                "deg values are direct rad-to-deg conversions in J1..J6 order."
            ),
            "current_q": self._joint_vector_payload(current_q),
            "seed_q": self._joint_vector_payload(seed_q),
            "ik_q": self._joint_vector_payload(ik_q),
            "last_accepted_ik_q": self._joint_vector_payload(last_accepted_q),
            "lower_limit": self._joint_vector_payload(self._joint_lower),
            "upper_limit": self._joint_vector_payload(self._joint_upper),
            "ik_limit_margin_deg": self._joint_limit_margins_deg(ik_q),
            "violating_joints": self._violating_joints_payload(ik_q),
        }

    def _write_status(
        self,
        *,
        state: str,
        last_error: str | None,
        transform: np.ndarray,
        debug: dict[str, object] | None = None,
    ) -> None:
        debug_sig = None if debug is None else json.dumps(debug, sort_keys=True, separators=(",", ":"))
        sig = (
            state,
            last_error,
            tuple(float(v) for v in np.round(transform[:3, 3], 6).tolist()),
            tuple(float(v) for v in np.round(transform[:3, :3].reshape(-1), 5).tolist()),
            debug_sig,
        )
        if sig == self._last_status_sig and self._status_path.exists():
            return
        payload = {
            "enabled": True,
            "state": state,
            "target_prim_path": self._target_prim_path,
            "base_link_prim_path": self._base_link_prim_path,
            "end_effector_link_prim_path": self._ee_link_prim_path,
            "end_effector_frame": self._end_effector_frame,
            "control_urdf": self._control_urdf,
            "ik_mode": "position_only" if self._position_only else "full_pose",
            "last_error": last_error,
            "pose": _pose_payload(transform),
            "timestamp_s": time.time(),
        }
        if debug is not None:
            payload["joint_debug"] = debug
        self._status_path.parent.mkdir(parents=True, exist_ok=True)
        self._status_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        self._last_status_sig = sig


def parse_args():
    default_stage_path = os.environ.get("A1Z_WORLD_USD", os.path.join(ROOT_DIR, "build", "scenes", "A1Z_G1Z_world.usd"))
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
        "--tcp-host",
        default=os.environ.get("A1Z_TCP_HOST", get_tcp_host()),
        help="Optional TCP bind host for the A1Z server.",
    )
    parser.add_argument(
        "--tcp-port",
        type=int,
        default=int(os.environ.get("A1Z_TCP_PORT", str(get_tcp_port()))),
        help="Optional TCP bind port for the A1Z server. Set <=0 to disable.",
    )
    parser.add_argument(
        "--articulation-root",
        default=os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", isaac_defaults["articulation_root_prim"]),
        help="Articulation root prim path inside the loaded stage.",
    )
    parser.add_argument(
        "--control-freq",
        type=int,
        default=_env_int("A1Z_ISAAC_CONTROL_FREQ_HZ", 60),
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
    parser.add_argument(
        "--ee-drag-target",
        dest="ee_drag_target",
        action="store_true",
        help="Spawn a draggable end-effector target prim and continuously follow it with IK.",
    )
    parser.add_argument(
        "--no-ee-drag-target",
        dest="ee_drag_target",
        action="store_false",
        help="Disable the draggable end-effector target.",
    )
    parser.add_argument(
        "--ee-target-prim-path",
        default=_env_str("A1Z_EE_TARGET_PRIM_PATH", "/World/A1Z_EE_Target"),
        help="Stage prim path for the draggable end-effector target.",
    )
    parser.add_argument(
        "--ee-frame",
        default=_env_str("A1Z_EE_FRAME", "grasp_tcp"),
        help="Control URDF frame used as the IK end effector.",
    )
    parser.add_argument(
        "--control-urdf",
        default=_env_str("A1Z_CONTROL_URDF", get_default_control_urdf_path()),
        help="Control URDF path used for FK/IK.",
    )
    parser.add_argument(
        "--ee-pos-epsilon-mm",
        type=float,
        default=_env_float("A1Z_EE_POS_EPSILON_MM", 2.0),
        help="Ignore drag target updates smaller than this translation threshold.",
    )
    parser.add_argument(
        "--ee-ori-epsilon-deg",
        type=float,
        default=_env_float("A1Z_EE_ORI_EPSILON_DEG", 1.5),
        help="Ignore drag target updates smaller than this orientation threshold.",
    )
    parser.add_argument(
        "--ee-ik-dt",
        type=float,
        default=_env_float("A1Z_EE_IK_DT", 0.12),
        help="IK integration step for draggable target following.",
    )
    parser.add_argument(
        "--ee-ik-damping",
        type=float,
        default=_env_float("A1Z_EE_IK_DAMPING", 1e-6),
        help="IK damping factor for draggable target following.",
    )
    parser.add_argument(
        "--ee-ik-max-iters",
        type=int,
        default=_env_int("A1Z_EE_IK_MAX_ITERS", 240),
        help="Maximum IK iterations per draggable target update.",
    )
    parser.add_argument(
        "--ee-position-only",
        dest="ee_position_only",
        action="store_true",
        help="Make the draggable target follow only XYZ position, ignoring target orientation.",
    )
    parser.add_argument(
        "--ee-full-pose",
        dest="ee_position_only",
        action="store_false",
        help="Make the draggable target follow XYZ plus orientation, matching the previous behavior.",
    )
    parser.add_argument(
        "--ee-posture-weight",
        type=float,
        default=_env_float("A1Z_EE_POSTURE_WEIGHT", 1e-4),
        help="Small posture regularization weight used by position-only IK.",
    )
    parser.add_argument(
        "--ee-target-offset-x-m",
        type=float,
        default=_env_float("A1Z_EE_TARGET_OFFSET_X_M", 0.08),
        help="Default initial target offset along the base-frame X axis.",
    )
    parser.add_argument(
        "--ee-target-offset-y-m",
        type=float,
        default=_env_float("A1Z_EE_TARGET_OFFSET_Y_M", -0.10),
        help="Default initial target offset along the base-frame Y axis.",
    )
    parser.add_argument(
        "--ee-target-offset-z-m",
        type=float,
        default=_env_float("A1Z_EE_TARGET_OFFSET_Z_M", 0.05),
        help="Default initial target offset along the base-frame Z axis.",
    )
    parser.add_argument(
        "--ee-status-path",
        default=_env_str("A1Z_EE_TARGET_STATUS_PATH", os.path.join(RUNTIME_LOG_DIR, "a1z-ee-drag-target.json")),
        help="Status JSON written by the draggable target follower.",
    )
    parser.set_defaults(
        with_gripper=_env_flag("A1Z_WITH_GRIPPER", True),
        gravity_mode=_env_flag("A1Z_ISAAC_GRAVITY_MODE", False),
        ee_drag_target=_env_flag("A1Z_EE_DRAG_TARGET_ENABLED", False),
        ee_position_only=_env_flag("A1Z_EE_POSITION_ONLY", True),
    )
    args, extras = parser.parse_known_args()
    for token in extras:
        if token.endswith(".usd"):
            args.stage_path = token
            break
    return args


async def open_world(stage_path: str):
    requested_stage_path = _normalize_stage_path(stage_path)
    current_stage_path = _get_current_stage_path()
    if requested_stage_path and current_stage_path == requested_stage_path:
        carb.log_info(f"A1Z world already loaded by Kit: {requested_stage_path}")
    else:
        carb.log_info(f"A1Z opening world stage: {requested_stage_path or stage_path}")
        success, error = await omni.usd.get_context().open_stage_async(stage_path)
        if not success:
            raise RuntimeError(f"Failed to open stage {stage_path}: {error}")

    app = omni.kit.app.get_app()
    for _ in range(10):
        await app.next_update_async()

    stage = omni.usd.get_context().get_stage()
    _apply_wrist_payload_collision_filters(stage)
    _apply_adjacent_arm_collision_filters(stage)
    _apply_arm_internal_collision_filters(stage)
    _disable_wrist_payload_collisions(stage)
    _lighten_wrist_payload_dynamics(stage)
    _configure_arm_articulation_physics(stage)
    _configure_wrist_link_physics(stage)
    _configure_wrist_joint_physics(stage)
    _enable_trashset_contact_reports(stage)
    d405_attachment = None
    if _env_flag("A1Z_D405_ENABLED", _viewport_enabled()):
        d405_attachment = attach_d405_wrist_camera(stage)
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
            camera_state = ViewportCameraState(viewport=viewport)
            focus_prim = _env_str("A1Z_VIEWPORT_FOCUS_PRIM", "/World/A1Z_G1Z")
            framed = frame_viewport_prims(viewport, [focus_prim])
            camera_position = _env_vec3("A1Z_VIEWPORT_CAMERA_POSITION", (1.4, -1.6, 1.1))
            camera_target = _env_vec3("A1Z_VIEWPORT_CAMERA_TARGET", (0.0, 0.0, 0.35))
            camera_state.set_position_world(Gf.Vec3d(*camera_position), True)
            camera_state.set_target_world(Gf.Vec3d(*camera_target), True)
            carb.log_info(
                "A1Z viewport framing applied: "
                f"framed={framed} focus={focus_prim} camera={viewport.camera_path} "
                f"position={camera_position} target={camera_target}"
            )
        except Exception as exc:
            carb.log_warn(f"Viewport camera framing skipped: {exc}")

    carb.log_info(f"A1Z world opened: {stage_path}")
    return d405_attachment, viewport


async def startup():
    args = parse_args()
    app = omni.kit.app.get_app()
    server_thread = None
    server = None
    robot = None
    resolved_articulation_root = None
    d405_attachment = None
    d405_session = None
    viewport = None
    d405_diagnostics_written = False
    ee_drag_target = None
    repaired_reset_paths: set[str] = set()

    try:
        d405_attachment, viewport = await open_world(args.stage_path)
        stage = omni.usd.get_context().get_stage()
        initial_patched = _enforce_nested_rigid_body_reset_xforms(stage, args.articulation_root)
        repaired_reset_paths.update(initial_patched)
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
        try:
            resolved_articulation_root = robot.get_robot_info().get("articulation_root_prim")
        except Exception:
            resolved_articulation_root = None
        if not resolved_articulation_root:
            resolved_articulation_root = args.articulation_root
        for _ in range(2):
            await app.next_update_async()
        stage = omni.usd.get_context().get_stage()
        patched_prims = _enforce_nested_rigid_body_reset_xforms(stage, resolved_articulation_root)
        new_patched = [path for path in patched_prims if path not in repaired_reset_paths]
        if new_patched:
            repaired_reset_paths.update(new_patched)
            carb.log_warn(
                "A1Z repaired nested rigid-body resetXformStack after articulation start: "
                + ", ".join(new_patched)
            )

        if not d405_diagnostics_written:
            stage = omni.usd.get_context().get_stage()
            d405_diagnostics_written = await _capture_viewport_diagnostics_once(stage, viewport)

        if args.ee_drag_target:
            try:
                stage = omni.usd.get_context().get_stage()
                ee_drag_target = EndEffectorDragTarget(
                    stage=stage,
                    robot=robot,
                    articulation_root_prim=resolved_articulation_root,
                    viewport=viewport,
                    target_prim_path=args.ee_target_prim_path,
                    end_effector_frame=args.ee_frame,
                    control_urdf=args.control_urdf,
                    pos_epsilon_m=max(1e-4, args.ee_pos_epsilon_mm / 1000.0),
                    ori_epsilon_deg=max(0.1, args.ee_ori_epsilon_deg),
                    ik_dt=args.ee_ik_dt,
                    ik_damping=args.ee_ik_damping,
                    ik_max_iters=max(20, args.ee_ik_max_iters),
                    position_only=args.ee_position_only,
                    posture_weight=args.ee_posture_weight,
                    initial_offset_base_m=(
                        args.ee_target_offset_x_m,
                        args.ee_target_offset_y_m,
                        args.ee_target_offset_z_m,
                    ),
                    status_path=args.ee_status_path,
                )
                ee_drag_target.initialize()
            except Exception as exc:
                carb.log_warn(f"A1Z EE drag target disabled: {exc}")
                ee_drag_target = None

        if d405_attachment is not None:
            color_path = str(d405_attachment.camera_paths.get("color") or "")
            depth_path = str(d405_attachment.camera_paths.get("depth") or "")
            if color_path:
                d405_session = D405FrameSession(
                    attachment=d405_attachment,
                    color_camera_path=color_path,
                    depth_camera_path=depth_path or color_path,
                    settings=D405CaptureSettings(),
                    stage_path=args.stage_path,
                )
            else:
                carb.log_warn("A1Z D405 attachment exists but no color camera path was found.")

        server = RobotServer(robot, with_gripper=args.with_gripper, camera_session=d405_session)
        server_thread = threading.Thread(
            target=server.run,
            kwargs={
                "socket_path": args.socket_path,
                "tcp_host": args.tcp_host,
                "tcp_port": args.tcp_port,
            },
            name="a1z_isaac_socket_server",
            daemon=True,
        )
        server_thread.start()

        carb.log_info(
            "A1Z Isaac server ready: "
            f"socket={args.socket_path} tcp={args.tcp_host}:{args.tcp_port} "
            f"articulation={args.articulation_root} "
            f"gripper={'yes' if args.with_gripper else 'no'} "
            f"mode={'gravity_comp_effort' if args.gravity_mode else 'position_hold'}"
        )

        while not server._shutdown.is_set():
            try:
                robot.process_pending()
            except Exception as exc:
                carb.log_error(f"A1Z Isaac control loop failed: {exc}")
                raise
            if ee_drag_target is not None:
                try:
                    ee_drag_target.update()
                except Exception as exc:
                    carb.log_warn(f"A1Z EE drag target disabled after update failure: {exc}")
                    ee_drag_target = None
            if d405_attachment is not None:
                try:
                    if d405_session is not None:
                        d405_session.update(robot.get_joint_state()["pos"])
                    else:
                        d405_attachment.update(robot.get_joint_state()["pos"])
                    if not d405_diagnostics_written:
                        stage = omni.usd.get_context().get_stage()
                        d405_diagnostics_written = await _capture_viewport_diagnostics_once(stage, viewport)
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


if __name__ == "__main__":
    main()
