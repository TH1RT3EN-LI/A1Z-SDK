"""Attach an approximate Intel RealSense D405 wrist camera to the A1Z stage."""

from __future__ import annotations

import math
import os
import struct
from pathlib import Path

import carb
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

from .settings import D405AssetSettings

D405_LINK_FRAME_NAME = "D405Link"
D405_RECTIFIED_FRAME_NAME = "RectifiedFrame"
D405_DEPTH_OPTICAL_FRAME_NAME = "DepthOpticalFrame"
D405_COLOR_OPTICAL_FRAME_NAME = "ColorOpticalFrame"
D405_DEPTH_CAMERA_NAME = "DepthCamera"
D405_COLOR_CAMERA_NAME = "ColorCamera"
USD_CAMERA_FROM_OPTICAL_RPY_DEG = (0.0, 0.0, 0.0)

D405_CAM_WIDTH_M = 0.042
D405_CAM_HEIGHT_M = 0.042
D405_CAM_DEPTH_M = 0.023
D405_CAM_MOUNT_FROM_CENTER_OFFSET_M = 0.01465
D405_GLASS_TO_FRONT_M = 0.0001
D405_ZERO_DEPTH_TO_GLASS_M = 0.0037
D405_COLLISION_OFFSET_IN_LINK = (
    D405_ZERO_DEPTH_TO_GLASS_M - (D405_CAM_DEPTH_M / 2.0),
    -0.009,
    0.0,
)


def _safe_path(path: str) -> Sdf.Path:
    sdf_path = Sdf.Path(path)
    if not sdf_path.IsAbsolutePath():
        raise ValueError(f"USD prim path must be absolute: {path}")
    return sdf_path


def _find_first_prim_path(stage: Usd.Stage, prim_name: str) -> Sdf.Path | None:
    for prim in stage.Traverse():
        if prim.GetName() == prim_name:
            return prim.GetPath()
    return None


def _find_descendant_prim_path(stage: Usd.Stage, *, root_path: str, prim_name: str) -> Sdf.Path | None:
    from pxr import Usd

    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        return None
    for prim in Usd.PrimRange(root):
        if prim.GetName() == prim_name:
            return prim.GetPath()
    return None


def _find_matching_child_link_path(stage: Usd.Stage, *, fk_prim_path: Sdf.Path, child_name: str) -> Sdf.Path | None:
    parent_prim = stage.GetPrimAtPath(fk_prim_path)
    if parent_prim.IsValid():
        direct_child = parent_prim.GetPath().AppendChild(child_name)
        if stage.GetPrimAtPath(direct_child).IsValid():
            return direct_child

    parent_path = fk_prim_path.GetParentPath()
    if parent_path and parent_path != Sdf.Path.absoluteRootPath:
        sibling_child = parent_path.AppendChild(child_name)
        if stage.GetPrimAtPath(sibling_child).IsValid():
            return sibling_child

    for prim in stage.Traverse():
        if prim.GetName() != child_name:
            continue
        path = prim.GetPath()
        if path.GetParentPath() in {fk_prim_path, parent_path}:
            return path
    return None


def _resolve_authorable_parent_path(stage: Usd.Stage, preferred_parent: str, fallback_parent: str) -> Sdf.Path:
    for candidate in (preferred_parent, fallback_parent, "/World"):
        if not candidate:
            continue
        path = _safe_path(candidate)
        prim = stage.GetPrimAtPath(path)
        if prim.IsValid():
            return path
    return _safe_path("/World")


def _unique_child_path(stage: Usd.Stage, parent_path: Sdf.Path, child_name: str) -> Sdf.Path:
    base_path = parent_path.AppendChild(child_name)
    if not stage.GetPrimAtPath(base_path).IsValid():
        return base_path
    suffix = 1
    while True:
        candidate = parent_path.AppendChild(f"{child_name}_{suffix}")
        if not stage.GetPrimAtPath(candidate).IsValid():
            return candidate
        suffix += 1


def _clear_xform_ops(xform: UsdGeom.Xform) -> None:
    for op in xform.GetOrderedXformOps():
        xform.GetPrim().RemoveProperty(op.GetOpName())
    xform.SetXformOpOrder([])


def _set_transform(
    xform: UsdGeom.Xformable,
    translate: tuple[float, float, float],
    rotate_deg: tuple[float, float, float],
    scale: tuple[float, float, float] | None = None,
) -> None:
    _clear_xform_ops(xform)
    xform.AddTranslateOp().Set(Gf.Vec3d(*translate))
    xform.AddRotateXYZOp().Set(Gf.Vec3f(*rotate_deg))
    if scale is not None:
        xform.AddScaleOp().Set(Gf.Vec3f(*scale))


def _rotation_matrix_to_quatf(rotation: np.ndarray) -> Gf.Quatf:
    rot = np.asarray(rotation, dtype=float)
    trace = float(rot[0, 0] + rot[1, 1] + rot[2, 2])
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (rot[2, 1] - rot[1, 2]) / s
        y = (rot[0, 2] - rot[2, 0]) / s
        z = (rot[1, 0] - rot[0, 1]) / s
    elif rot[0, 0] > rot[1, 1] and rot[0, 0] > rot[2, 2]:
        s = math.sqrt(1.0 + rot[0, 0] - rot[1, 1] - rot[2, 2]) * 2.0
        w = (rot[2, 1] - rot[1, 2]) / s
        x = 0.25 * s
        y = (rot[0, 1] + rot[1, 0]) / s
        z = (rot[0, 2] + rot[2, 0]) / s
    elif rot[1, 1] > rot[2, 2]:
        s = math.sqrt(1.0 + rot[1, 1] - rot[0, 0] - rot[2, 2]) * 2.0
        w = (rot[0, 2] - rot[2, 0]) / s
        x = (rot[0, 1] + rot[1, 0]) / s
        y = 0.25 * s
        z = (rot[1, 2] + rot[2, 1]) / s
    else:
        s = math.sqrt(1.0 + rot[2, 2] - rot[0, 0] - rot[1, 1]) * 2.0
        w = (rot[1, 0] - rot[0, 1]) / s
        x = (rot[0, 2] + rot[2, 0]) / s
        y = (rot[1, 2] + rot[2, 1]) / s
        z = 0.25 * s
    return Gf.Quatf(float(w), Gf.Vec3f(float(x), float(y), float(z)))


def _set_pose_from_np_matrix(xform: UsdGeom.Xformable, transform: np.ndarray) -> None:
    pose = np.asarray(transform, dtype=float)
    _clear_xform_ops(xform)
    xform.AddTranslateOp().Set(Gf.Vec3d(*pose[:3, 3].tolist()))
    xform.AddOrientOp().Set(_rotation_matrix_to_quatf(pose[:3, :3]))


def _set_trs_transform(
    xform: UsdGeom.Xformable,
    translate: tuple[float, float, float],
    rotate_deg: tuple[float, float, float],
    scale: tuple[float, float, float],
) -> None:
    _clear_xform_ops(xform)
    xform.AddTranslateOp().Set(Gf.Vec3d(*translate))
    xform.AddRotateXYZOp().Set(Gf.Vec3f(*rotate_deg))
    xform.AddScaleOp().Set(Gf.Vec3f(*scale))


def _matrix_from_np(transform) -> Gf.Matrix4d:
    # USD/Gf matrices use row-vector convention, with translation in row 3.
    # The FK math above uses the robotics column-vector convention, so transpose
    # before authoring the xformOp:transform.
    usd_transform = np.asarray(transform, dtype=float).T
    matrix = Gf.Matrix4d(1.0)
    for row in range(4):
        matrix.SetRow(
            row,
            Gf.Vec4d(
                float(usd_transform[row, 0]),
                float(usd_transform[row, 1]),
                float(usd_transform[row, 2]),
                float(usd_transform[row, 3]),
            ),
        )
    return matrix


def _gf_matrix_to_np(matrix) -> np.ndarray:
    return np.array([[float(matrix[row][col]) for col in range(4)] for row in range(4)], dtype=np.float64).T


def _world_transform_np(stage: Usd.Stage, prim_path: Sdf.Path) -> np.ndarray | None:
    from pxr import UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return None
    cache = UsdGeom.XformCache()
    return _gf_matrix_to_np(cache.GetLocalToWorldTransform(prim))


def _scale_matrix(scale: tuple[float, float, float]) -> np.ndarray:
    matrix = np.eye(4)
    matrix[0, 0] = scale[0]
    matrix[1, 1] = scale[1]
    matrix[2, 2] = scale[2]
    return matrix


def _read_binary_stl(path: Path) -> tuple[list[Gf.Vec3f], list[int], list[int]]:
    with path.open("rb") as fh:
        fh.read(80)
        tri_count = struct.unpack("<I", fh.read(4))[0]
        points: list[Gf.Vec3f] = []
        indices: list[int] = []
        counts: list[int] = []
        for _ in range(tri_count):
            data = fh.read(50)
            if len(data) != 50:
                raise ValueError(f"Unexpected EOF while reading STL: {path}")
            values = struct.unpack("<12fH", data)
            base = len(points)
            for idx in (3, 6, 9):
                points.append(Gf.Vec3f(values[idx], values[idx + 1], values[idx + 2]))
            indices.extend((base, base + 1, base + 2))
            counts.append(3)
    return points, indices, counts


def _define_mesh(
    stage: Usd.Stage,
    path: Sdf.Path,
    points: list[Gf.Vec3f],
    indices: list[int],
    counts: list[int],
) -> UsdGeom.Mesh:
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexIndicesAttr(indices)
    mesh.CreateFaceVertexCountsAttr(counts)
    mesh.CreateSubdivisionSchemeAttr("none")
    return mesh


def _center_d405_mesh_points(points: list[Gf.Vec3f]) -> list[Gf.Vec3f]:
    if not points:
        return points
    min_y = min(float(p[1]) for p in points)
    max_y = max(float(p[1]) for p in points)
    center_y = 0.5 * (min_y + max_y)
    return [Gf.Vec3f(float(p[0]), float(p[1]) - center_y, float(p[2])) for p in points]


class D405WristCameraAttachment:
    def __init__(
        self,
        mount_path: Sdf.Path,
        tracked_mount_path: Sdf.Path,
        body_visual_transform: np.ndarray | None = None,
        authored_scale: tuple[float, float, float] | None = None,
        static_pose: bool = False,
        status_path: str | None = None,
    ) -> None:
        self.mount_path = mount_path
        self.tracked_mount_path = tracked_mount_path
        self.camera_paths: dict[str, str] = {}
        self._body_visual_transform = body_visual_transform
        self._authored_scale = authored_scale
        self._static_pose = static_pose
        self._mount_xform: UsdGeom.Xformable | None = None
        self._mount_transform_op = None
        self._status_path = status_path or D405AssetSettings.from_env().status_path
        self._tracking_written = False

    def _tracked_mount_world_transform(self) -> np.ndarray | None:
        try:
            import omni.usd

            stage = omni.usd.get_context().get_stage()
        except Exception:
            stage = None
        if stage is None:
            return None
        return _world_transform_np(stage, self.tracked_mount_path)

    def _mount_parent_world_transform(self) -> np.ndarray | None:
        try:
            import omni.usd

            stage = omni.usd.get_context().get_stage()
        except Exception:
            stage = None
        if stage is None:
            return None
        parent_path = self.mount_path.GetParentPath()
        if not parent_path or parent_path == Sdf.Path.absoluteRootPath:
            return np.eye(4, dtype=float)
        parent_world = _world_transform_np(stage, parent_path)
        if parent_world is None:
            return None
        return parent_world

    def _ensure_mount_transform_op(self):
        if self._static_pose:
            return None
        try:
            import omni.usd

            stage = omni.usd.get_context().get_stage()
        except Exception:
            stage = None
        if stage is None:
            return self._mount_transform_op
        prim = stage.GetPrimAtPath(self.mount_path)
        if not prim.IsValid():
            self._mount_xform = None
            self._mount_transform_op = None
            return None
        xformable = UsdGeom.Xformable(prim)
        existing_ops = xformable.GetOrderedXformOps()
        transform_ops = [op for op in existing_ops if op.GetOpName() == "xformOp:transform"]
        if transform_ops:
            op = transform_ops[0]
        else:
            _clear_xform_ops(xformable)
            op = xformable.AddTransformOp()
        self._mount_xform = xformable
        self._mount_transform_op = op
        return op

    def bind_stage(self, stage: Usd.Stage) -> None:
        if self._static_pose:
            return
        self._mount_xform = UsdGeom.Xformable(stage.GetPrimAtPath(self.mount_path))
        self._ensure_mount_transform_op()

    def update(self, joint_pos) -> None:
        if self._static_pose:
            if not self._tracking_written:
                try:
                    import omni.usd

                    stage = omni.usd.get_context().get_stage()
                    t_world_mount = _world_transform_np(stage, self.mount_path) if stage is not None else None
                except Exception:
                    t_world_mount = None
                self._append_tracking_status(np.eye(4) if t_world_mount is None else t_world_mount)
                self._tracking_written = True
            return
        mount_transform_op = self._ensure_mount_transform_op()
        if mount_transform_op is None:
            return
        tracked_mount_world = self._tracked_mount_world_transform()
        if tracked_mount_world is None:
            raise RuntimeError(f"Tracked D405 mount prim is unavailable: {self.tracked_mount_path}")
        t_world_mount = tracked_mount_world
        authored_transform = t_world_mount
        parent_world = self._mount_parent_world_transform()
        if parent_world is not None:
            authored_transform = np.linalg.inv(parent_world) @ authored_transform
        if self._authored_scale is not None:
            authored_transform = authored_transform @ _scale_matrix(self._authored_scale)
        mount_transform_op.Set(_matrix_from_np(authored_transform))
        if not self._tracking_written:
            self._append_tracking_status(t_world_mount)
            self._tracking_written = True

    def _append_tracking_status(self, t_world_mount: np.ndarray) -> None:
        try:
            with Path(self._status_path).open("a", encoding="utf-8") as fh:
                fh.write("tracking=1\n")
                fh.write(f"tracking_source=model_world:{self.tracked_mount_path}\n")
                xyz = tuple(float(v) for v in t_world_mount[:3, 3])
                fh.write(f"world_translation={xyz}\n")
                if self._body_visual_transform is not None:
                    t_world_body = t_world_mount @ self._body_visual_transform
                    body_xyz = tuple(float(v) for v in t_world_body[:3, 3])
                    fh.write(f"body_world_translation={body_xyz}\n")
        except OSError as exc:
            carb.log_warn(f"Could not update A1Z D405 status file: {self._status_path}: {exc}")


def _make_material(stage: Usd.Stage) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, Sdf.Path("/World/Looks/D405Aluminum"))
    shader = UsdShade.Shader.Define(stage, Sdf.Path("/World/Looks/D405Aluminum/Shader"))
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.16, 0.16, 0.15))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.42)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.8)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def _define_camera(
    stage: Usd.Stage,
    path: Sdf.Path,
    translate: tuple[float, float, float],
    rotate_deg: tuple[float, float, float],
    horizontal_aperture_mm: float,
    vertical_aperture_mm: float,
) -> UsdGeom.Camera:
    camera = UsdGeom.Camera.Define(stage, path)
    _set_transform(UsdGeom.Xformable(camera.GetPrim()), translate, rotate_deg)
    camera.CreateProjectionAttr("perspective")
    camera.CreateFocalLengthAttr(1.93)
    camera.CreateHorizontalApertureAttr(horizontal_aperture_mm)
    camera.CreateVerticalApertureAttr(vertical_aperture_mm)
    camera.CreateClippingRangeAttr(Gf.Vec2f(0.02, 0.50))
    camera.CreateFocusDistanceAttr(0.22)
    return camera


def _define_xform(
    stage: Usd.Stage,
    path: Sdf.Path,
    translate: tuple[float, float, float],
    rotate_deg: tuple[float, float, float],
) -> UsdGeom.Xform:
    xform = UsdGeom.Xform.Define(stage, path)
    _set_transform(UsdGeom.Xformable(xform.GetPrim()), translate, rotate_deg)
    return xform


def attach_d405_wrist_camera(stage: Usd.Stage) -> D405WristCameraAttachment | None:
    """Attach a visual D405 body and approximate RGB/depth cameras.

    The runtime D405 rig follows the imported robot model's d405_link prim.
    Mechanical truth comes from the generated URDF/USD, not from a runtime FK fallback.
    """

    settings = D405AssetSettings.from_env()
    if not settings.enabled:
        carb.log_info("A1Z D405 wrist camera attachment disabled by A1Z_D405_ENABLED.")
        return None

    status_path = settings.status_path
    try:
        Path(status_path).write_text("attached=0\n", encoding="utf-8")
    except OSError:
        pass

    parent_search_root = settings.parent_prim
    mesh_path = Path(settings.mesh_path).expanduser()
    rectify_rpy_deg = settings.rectify_rpy_deg
    rectified_to_optical_offset = settings.rectified_to_optical_offset_xyz_m
    rectified_to_optical_rpy_deg = settings.rectified_to_optical_rpy_deg
    body_visual_rpy_deg = settings.body_visual_rpy_deg
    center_on_axis = settings.center_on_axis
    fk_frame = settings.fk_frame

    fk_prim_path = _find_descendant_prim_path(stage, root_path=parent_search_root, prim_name=fk_frame)
    if fk_prim_path is None:
        carb.log_warn(
            "A1Z D405 FK parent prim not found, skipping wrist camera: "
            f"fk_frame={fk_frame} search_root={parent_search_root}"
        )
        return None
    if not mesh_path.is_file():
        carb.log_warn(f"A1Z D405 mesh not found, skipping wrist camera body: {mesh_path}")

    tracked_mount_path = _find_matching_child_link_path(stage, fk_prim_path=fk_prim_path, child_name="d405_link")
    if tracked_mount_path is None:
        tracked_mount_path = fk_prim_path.AppendChild("d405_link")
    mount_prim = stage.GetPrimAtPath(tracked_mount_path)
    if not mount_prim.IsValid():
        carb.log_warn(
            "A1Z D405 stage prim not found under FK parent, skipping wrist camera: "
            f"path={tracked_mount_path}"
        )
        return None
    # Use the imported robot model's d405_link as the only D405 prim.
    # Do not author a second runtime mount under /World.
    mount_path = tracked_mount_path
    static_pose = True

    body_kind = "existing"
    body_triangles = 0
    body_visual_offset = (0.0, 0.0, 0.0)
    collision_offset = D405_COLLISION_OFFSET_IN_LINK
    attachment_body_visual_transform = None
    attachment_authored_scale = None
    link_frame_path = mount_path
    rectified_frame_path = link_frame_path.AppendChild(D405_RECTIFIED_FRAME_NAME)
    if not stage.GetPrimAtPath(rectified_frame_path).IsValid():
        _define_xform(stage, rectified_frame_path, (0.0, 0.0, 0.0), rectify_rpy_deg)

    # The imported USD already contains the D405 body mesh under d405_link.
    # Runtime only authors semantic rectified/optical/camera frames.

    cameras_enabled = settings.camera_prims_enabled
    if cameras_enabled:
        capture_width = max(1, int(os.environ.get("A1Z_D405_WIDTH", "320")))
        capture_height = max(1, int(os.environ.get("A1Z_D405_HEIGHT", "240")))
        capture_hz = max(1, int(os.environ.get("A1Z_D405_CAPTURE_HZ", "10")))
        camera_specs = (
            (D405_DEPTH_OPTICAL_FRAME_NAME, D405_DEPTH_CAMERA_NAME),
            (D405_COLOR_OPTICAL_FRAME_NAME, D405_COLOR_CAMERA_NAME),
        )
        h_aperture_mm = 2.0
        v_aperture_mm = h_aperture_mm / (16.0 / 9.0)
        focal_mm = h_aperture_mm / (2.0 * math.tan(math.radians(87.0 / 2.0)))
        for optical_frame_name, camera_name in camera_specs:
            optical_frame_path = rectified_frame_path.AppendChild(optical_frame_name)
            if stage.GetPrimAtPath(optical_frame_path).IsValid():
                _set_transform(
                    UsdGeom.Xformable(stage.GetPrimAtPath(optical_frame_path)),
                    rectified_to_optical_offset,
                    rectified_to_optical_rpy_deg,
                )
            else:
                _define_xform(
                    stage,
                    optical_frame_path,
                    rectified_to_optical_offset,
                    rectified_to_optical_rpy_deg,
                )
            camera = _define_camera(
                stage,
                optical_frame_path.AppendChild(camera_name),
                (0.0, 0.0, 0.0),
                USD_CAMERA_FROM_OPTICAL_RPY_DEG,
                h_aperture_mm,
                v_aperture_mm,
            )
            camera.CreateFocalLengthAttr(focal_mm)
            camera_prim = camera.GetPrim()
            if "OmniSensorAPI" not in camera_prim.GetAppliedSchemas():
                camera_prim.ApplyAPI("OmniSensorAPI")
            tick_rate_attr = camera_prim.GetAttribute("omni:sensor:tickRate")
            if not tick_rate_attr.IsValid():
                raise RuntimeError(f"D405 camera does not expose omni:sensor:tickRate: {camera_prim.GetPath()}")
            tick_rate_attr.Set(float(capture_hz))
            camera_prim.CreateAttribute("a1z:d405:resolution", Sdf.ValueTypeNames.Int2).Set(
                Gf.Vec2i(capture_width, capture_height)
            )
            camera_prim.CreateAttribute("a1z:d405:fps", Sdf.ValueTypeNames.Int).Set(capture_hz)

    carb.log_info(
        "A1Z D405 camera attached: "
        f"mount={mount_path} tracked_mount={tracked_mount_path} parent={fk_prim_path} source_mesh={mesh_path} "
        f"fk_frame={fk_frame} "
        f"rectify_rpy_deg={rectify_rpy_deg} "
        f"rectified_to_optical_offset={rectified_to_optical_offset} "
        f"center_on_axis={center_on_axis} body_visual_offset={body_visual_offset} "
        f"rectified_to_optical_rpy_deg={rectified_to_optical_rpy_deg}"
    )
    attachment = D405WristCameraAttachment(
        mount_path,
        tracked_mount_path,
        body_visual_transform=attachment_body_visual_transform,
        authored_scale=attachment_authored_scale,
        static_pose=static_pose,
        status_path=status_path,
    )
    if cameras_enabled:
        attachment.camera_paths = {
            "depth": str(
                rectified_frame_path.AppendChild(D405_DEPTH_OPTICAL_FRAME_NAME)
                .AppendChild(D405_DEPTH_CAMERA_NAME)
            ),
            "color": str(
                rectified_frame_path.AppendChild(D405_COLOR_OPTICAL_FRAME_NAME)
                .AppendChild(D405_COLOR_CAMERA_NAME)
            ),
        }
    attachment.bind_stage(stage)
    try:
        Path(status_path).write_text(
            "\n".join(
                [
                    "attached=1",
                    f"mount={mount_path}",
                    f"tracked_mount={tracked_mount_path}",
                    f"parent={fk_prim_path}",
                    f"fk_frame={fk_frame}",
                    f"source_mesh={mesh_path}",
                    f"body={body_kind}",
                    f"body_triangles={body_triangles}",
                    f"runtime_link_path={link_frame_path}",
                    f"runtime_rectified_frame_path={rectified_frame_path}",
                    f"rectify_rpy_deg={rectify_rpy_deg}",
                    f"rectified_to_optical_offset={rectified_to_optical_offset}",
                    f"rectified_to_optical_rpy_deg={rectified_to_optical_rpy_deg}",
                    f"body_visual_rpy_deg={body_visual_rpy_deg}",
                    f"center_on_axis={int(center_on_axis)}",
                    f"body_visual_offset={body_visual_offset}",
                    f"collision_offset={collision_offset}",
                    "direct_body_pose=1",
                    "mechanical_mount_source=model:d405_link",
                    f"camera_prims_enabled={int(cameras_enabled)}",
                    f"depth_camera={'DepthCamera' if cameras_enabled else ''}",
                    f"color_camera={'ColorCamera' if cameras_enabled else ''}",
                    f"resolution={capture_width}x{capture_height}" if cameras_enabled else "resolution=",
                    f"fps={capture_hz}" if cameras_enabled else "fps=",
                    "clip_range_m=0.02,0.50",
                    "tracking=0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        carb.log_warn(f"Could not write A1Z D405 status file: {status_path}: {exc}")
    return attachment
