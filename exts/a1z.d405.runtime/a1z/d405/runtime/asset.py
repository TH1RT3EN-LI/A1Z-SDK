"""Attach an approximate Intel RealSense D405 wrist camera to the A1Z stage."""

from __future__ import annotations

import math
import struct
from pathlib import Path

import carb
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

from .settings import D405AssetSettings

D405_XACRO_VISUAL_OFFSET = (0.0038, -0.009, 0.0)
D405_CENTERLINE_VISUAL_OFFSET = (0.0038, 0.0, 0.0)
D405_URDF_BODY_LINK_NAME = "d405_link"
D405_DEPTH_FRAME_OFFSET = (0.0, 0.0, 0.0)
D405_COLOR_FRAME_OFFSET = (0.0, 0.0, 0.0)
D405_CAMERA_OPTICAL_RPY_DEG = (0.0, 90.0, 0.0)
D405_DEPTH_FRAME_NAME = "DepthFrame"
D405_COLOR_FRAME_NAME = "ColorFrame"
D405_DEPTH_OPTICAL_FRAME_NAME = "DepthOpticalFrame"
D405_COLOR_OPTICAL_FRAME_NAME = "ColorOpticalFrame"
D405_DEPTH_CAMERA_NAME = "DepthCamera"
D405_COLOR_CAMERA_NAME = "ColorCamera"

ARM_JOINT_ORIGINS = (
    (0.0, 0.0, 0.075),
    (0.02, 0.0, 0.043),
    (-0.264, 0.0, 0.0),
    (0.245, 0.0, 0.06),
    (0.074, 0.0, 0.042),
    (0.0235, 0.0, -0.042),
)
ARM_JOINT_AXES = (
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (1.0, 0.0, 0.0),
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
        for col in range(4):
            matrix[row][col] = float(usd_transform[row, col])
    return matrix


def _translation_matrix(offset: tuple[float, float, float]) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(offset, dtype=float)
    return matrix


def _scale_matrix(scale: tuple[float, float, float]) -> np.ndarray:
    matrix = np.eye(4)
    matrix[0, 0] = scale[0]
    matrix[1, 1] = scale[1]
    matrix[2, 2] = scale[2]
    return matrix


def _axis_angle_matrix(axis: tuple[float, float, float], angle: float) -> np.ndarray:
    axis_arr = np.asarray(axis, dtype=float)
    axis_arr = axis_arr / np.linalg.norm(axis_arr)
    x, y, z = axis_arr
    c = math.cos(angle)
    s = math.sin(angle)
    one_c = 1.0 - c
    rot = np.array(
        [
            [c + x * x * one_c, x * y * one_c - z * s, x * z * one_c + y * s],
            [y * x * one_c + z * s, c + y * y * one_c, y * z * one_c - x * s],
            [z * x * one_c - y * s, z * y * one_c + x * s, c + z * z * one_c],
        ],
        dtype=float,
    )
    matrix = np.eye(4)
    matrix[:3, :3] = rot
    return matrix


def _rpy_np_matrix(rpy_deg: tuple[float, float, float]) -> np.ndarray:
    rx, ry, rz = (math.radians(v) for v in rpy_deg)
    return (
        _axis_angle_matrix((1.0, 0.0, 0.0), rx)
        @ _axis_angle_matrix((0.0, 1.0, 0.0), ry)
        @ _axis_angle_matrix((0.0, 0.0, 1.0), rz)
    )


def _pose_np_matrix(
    translate: tuple[float, float, float],
    rotate_deg: tuple[float, float, float],
) -> np.ndarray:
    return _translation_matrix(translate) @ _rpy_np_matrix(rotate_deg)


def _arm_link6_fk(joint_pos) -> np.ndarray:
    q = np.asarray(joint_pos, dtype=float).reshape(-1)[:6]
    transform = np.eye(4)
    for origin, axis, angle in zip(ARM_JOINT_ORIGINS, ARM_JOINT_AXES, q):
        transform = transform @ _translation_matrix(origin) @ _axis_angle_matrix(axis, angle)
    return transform


def _look_at_rotation(eye: tuple[float, float, float], target: tuple[float, float, float]) -> np.ndarray:
    eye_arr = np.asarray(eye, dtype=float)
    target_arr = np.asarray(target, dtype=float)
    forward = target_arr - eye_arr
    forward = forward / np.linalg.norm(forward)
    world_up = np.array([0.0, 0.0, 1.0], dtype=float)
    right = np.cross(forward, world_up)
    if np.linalg.norm(right) < 1e-6:
        right = np.array([0.0, 1.0, 0.0], dtype=float)
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)
    up = up / np.linalg.norm(up)

    matrix = np.eye(4)
    matrix[:3, 0] = forward
    matrix[:3, 1] = right
    matrix[:3, 2] = up
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
        mount_offset: tuple[float, float, float],
        mount_rpy_deg: tuple[float, float, float],
        fk_frame: str,
        target_world_transform: np.ndarray | None = None,
        target_pose_applies_to: str = "body",
        body_visual_transform: np.ndarray | None = None,
        authored_scale: tuple[float, float, float] | None = None,
        static_pose: bool = False,
        status_path: str | None = None,
    ) -> None:
        self.mount_path = mount_path
        self.mount_offset = mount_offset
        self.mount_rpy_deg = mount_rpy_deg
        self.target_offset = (0.085, 0.0, -0.020)
        self.fk_frame = fk_frame
        self.camera_paths: dict[str, str] = {}
        self._target_world_transform = target_world_transform
        self._target_pose_applies_to = target_pose_applies_to
        self._body_visual_transform = body_visual_transform
        self._authored_scale = authored_scale
        self._static_pose = static_pose
        self._link_mount_transform: np.ndarray | None = None
        self._mount_xform: UsdGeom.Xformable | None = None
        self._mount_transform_op = None
        self._status_path = status_path or D405AssetSettings.from_env().status_path
        self._tracking_written = False

    def bind_stage(self, stage: Usd.Stage) -> None:
        if self._static_pose:
            return
        self._mount_xform = UsdGeom.Xformable(stage.GetPrimAtPath(self.mount_path))
        existing_ops = self._mount_xform.GetOrderedXformOps()
        transform_ops = [op for op in existing_ops if op.GetOpName() == "xformOp:transform"]
        if transform_ops:
            self._mount_transform_op = transform_ops[0]
        else:
            _clear_xform_ops(self._mount_xform)
            self._mount_transform_op = self._mount_xform.AddTransformOp()

    def update(self, joint_pos) -> None:
        if self._static_pose:
            if not self._tracking_written:
                self._append_tracking_status(
                    self._target_world_transform if self._target_world_transform is not None else np.eye(4)
                )
                self._tracking_written = True
            return
        if self._mount_transform_op is None:
            return
        if self.fk_frame != "arm_link6":
            raise ValueError(f"Unsupported D405 FK frame: {self.fk_frame}")
        t_world_link = _arm_link6_fk(joint_pos)
        if self._link_mount_transform is None:
            if self._target_world_transform is not None:
                t_world_mount = self._target_world_transform
                if self._target_pose_applies_to == "body":
                    if self._body_visual_transform is None:
                        raise ValueError("D405 body target pose requires a body visual transform")
                    t_world_mount = t_world_mount @ np.linalg.inv(self._body_visual_transform)
                elif self._target_pose_applies_to != "mount":
                    raise ValueError(
                        "A1Z_D405_TARGET_WORLD_POSE_APPLIES_TO must be 'body' or 'mount'"
                    )
                self._link_mount_transform = np.linalg.inv(t_world_link) @ t_world_mount
            else:
                self._link_mount_transform = (
                    _translation_matrix(self.mount_offset)
                    @ _look_at_rotation(self.mount_offset, self.target_offset)
                    @ _rpy_np_matrix(self.mount_rpy_deg)
                )
        t_link_mount = self._link_mount_transform
        t_world_mount = t_world_link @ t_link_mount
        authored_transform = t_world_mount
        if self._authored_scale is not None:
            authored_transform = authored_transform @ _scale_matrix(self._authored_scale)
        self._mount_transform_op.Set(_matrix_from_np(authored_transform))
        if not self._tracking_written:
            self._append_tracking_status(t_world_mount)
            self._tracking_written = True

    def _append_tracking_status(self, t_world_mount: np.ndarray) -> None:
        try:
            with Path(self._status_path).open("a", encoding="utf-8") as fh:
                fh.write("tracking=1\n")
                fh.write("tracking_source=urdf_fk:arm_link6\n")
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
    camera.CreateClippingRangeAttr(Gf.Vec2f(0.07, 0.50))
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

    The D405 mount is tracked from the A1Z URDF FK so it follows arm_link6
    motion when the articulation is driven. This intentionally does not alter
    the robot articulation or SDK DOF mapping.
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

    body_link_path = _find_first_prim_path(stage, D405_URDF_BODY_LINK_NAME)
    parent_path = settings.parent_prim
    mount_name = settings.mount_name
    mesh_path = Path(settings.mesh_path).expanduser()
    mount_offset = settings.mount_offset
    target_offset = settings.target_offset
    mount_rpy_deg = settings.mount_rpy_deg
    camera_optical_rpy_deg = settings.camera_optical_rpy_deg
    center_on_axis = settings.center_on_axis
    target_world_translate = settings.target_world_translate
    target_world_rotate_deg = settings.target_world_rotate_deg
    target_pose_applies_to = settings.target_world_pose_applies_to
    target_world_scale = settings.target_world_scale
    target_world_transform = None
    if (target_world_translate is None) != (target_world_rotate_deg is None):
        raise ValueError(
            "A1Z_D405_TARGET_WORLD_TRANSLATE and "
            "A1Z_D405_TARGET_WORLD_ROTATE_DEG must be set together"
        )
    if target_world_translate is not None and target_world_rotate_deg is not None:
        target_world_transform = _pose_np_matrix(target_world_translate, target_world_rotate_deg)
    fk_frame = settings.fk_frame

    if body_link_path is not None:
        mount_path = body_link_path
        parent_path = str(body_link_path.GetParentPath())
        body_kind = "urdf_link"
        body_triangles = 0
        body_visual_offset = (0.0, 0.0, 0.0)
        attachment_body_visual_transform = None
        attachment_authored_scale = None
        carb.log_info(f"A1Z D405 URDF link detected: {body_link_path}")
    else:
        parent = stage.GetPrimAtPath(parent_path)
        if not parent.IsValid():
            fallback_path = settings.fallback_parent_prim
            fallback = stage.GetPrimAtPath(fallback_path)
            if not fallback.IsValid():
                carb.log_warn(
                    "A1Z D405 parent prim not found, skipping wrist camera: "
                    f"parent={parent_path} fallback={fallback_path}"
                )
                return None
            carb.log_warn(
                "A1Z D405 requested parent prim not found; using fallback parent. "
                f"requested={parent_path} fallback={fallback_path}"
            )
            parent_path = fallback_path
            parent = fallback
        if not mesh_path.is_file():
            carb.log_warn(f"A1Z D405 mesh not found, skipping wrist camera body: {mesh_path}")

        mount_path = _safe_path(f"{parent_path}/{mount_name}")
        mount = UsdGeom.Xform.Define(stage, mount_path)
        mount_matrix = _translation_matrix(mount_offset) @ _look_at_rotation(mount_offset, target_offset)
        _clear_xform_ops(UsdGeom.Xformable(mount.GetPrim()))
        mount.AddTransformOp().Set(_matrix_from_np(mount_matrix))

        body_kind = "fallback"
        body_triangles = 0
        body_visual_offset = (
            D405_CENTERLINE_VISUAL_OFFSET if center_on_axis else D405_XACRO_VISUAL_OFFSET
        )
        body_visual_transform = _pose_np_matrix(body_visual_offset, (90.0, 0.0, 90.0))
        attachment_body_visual_transform = body_visual_transform
        attachment_authored_scale = None
        if mesh_path.is_file():
            points, indices, counts = _read_binary_stl(mesh_path)
            if settings.center_mesh_y:
                points = _center_d405_mesh_points(points)
            body_triangles = len(counts)
            body = _define_mesh(stage, mount_path.AppendChild("D405BodyMesh"), points, indices, counts)
            body_kind = "mesh"
            _set_transform(
                UsdGeom.Xformable(body.GetPrim()),
                body_visual_offset,
                (90.0, 0.0, 90.0),
                (0.001, 0.001, 0.001),
            )
            UsdShade.MaterialBindingAPI(body.GetPrim()).Bind(_make_material(stage))
        else:
            body = UsdGeom.Cube.Define(stage, mount_path.AppendChild("D405BodyFallback"))
            body.CreateSizeAttr(1.0)
            _set_transform(
                UsdGeom.Xformable(body.GetPrim()),
                (0.00315, 0.0, 0.021),
                (0.0, 0.0, 0.0),
                (0.023, 0.042, 0.042),
            )
            UsdShade.MaterialBindingAPI(body.GetPrim()).Bind(_make_material(stage))

    cameras_enabled = settings.camera_prims_enabled
    if cameras_enabled:
        camera_parent_path = mount_path
        h_aperture_mm = 2.0
        v_aperture_mm = h_aperture_mm / (16.0 / 9.0)
        focal_mm = h_aperture_mm / (2.0 * math.tan(math.radians(87.0 / 2.0)))
        camera_specs = (
            (
                D405_DEPTH_FRAME_NAME,
                D405_DEPTH_FRAME_OFFSET,
                D405_DEPTH_OPTICAL_FRAME_NAME,
                D405_DEPTH_CAMERA_NAME,
            ),
            (
                D405_COLOR_FRAME_NAME,
                D405_COLOR_FRAME_OFFSET,
                D405_COLOR_OPTICAL_FRAME_NAME,
                D405_COLOR_CAMERA_NAME,
            ),
        )
        for frame_name, frame_offset, optical_frame_name, camera_name in camera_specs:
            sensor_frame = _define_xform(stage, camera_parent_path.AppendChild(frame_name), frame_offset, (0.0, 0.0, 0.0))
            optical_frame_path = sensor_frame.GetPath().AppendChild(optical_frame_name)
            _define_xform(stage, optical_frame_path, (0.0, 0.0, 0.0), camera_optical_rpy_deg)
            camera = _define_camera(
                stage,
                optical_frame_path.AppendChild(camera_name),
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                h_aperture_mm,
                v_aperture_mm,
            )
            camera.CreateFocalLengthAttr(focal_mm)
            camera.GetPrim().CreateAttribute("a1z:d405:resolution", Sdf.ValueTypeNames.Int2).Set(
                Gf.Vec2i(1280, 720)
            )
            camera.GetPrim().CreateAttribute("a1z:d405:fps", Sdf.ValueTypeNames.Int).Set(30)

    carb.log_info(
        "A1Z D405 wrist camera attached: "
        f"mount={mount_path} parent={parent_path} source_mesh={mesh_path} "
        f"fk_frame={fk_frame} offset={mount_offset} target={target_offset} "
        f"center_on_axis={center_on_axis} body_visual_offset={body_visual_offset} "
        f"rpy_deg={mount_rpy_deg}"
    )
    attachment = D405WristCameraAttachment(
        mount_path,
        mount_offset,
        mount_rpy_deg,
        fk_frame,
        target_world_transform=target_world_transform,
        target_pose_applies_to=target_pose_applies_to,
        body_visual_transform=attachment_body_visual_transform,
        authored_scale=attachment_authored_scale,
        static_pose=body_link_path is not None,
        status_path=status_path,
    )
    attachment.target_offset = target_offset
    if cameras_enabled:
        attachment.camera_paths = {
            "depth": str(
                camera_parent_path.AppendChild(D405_DEPTH_FRAME_NAME)
                .AppendChild(D405_DEPTH_OPTICAL_FRAME_NAME)
                .AppendChild(D405_DEPTH_CAMERA_NAME)
            ),
            "color": str(
                camera_parent_path.AppendChild(D405_COLOR_FRAME_NAME)
                .AppendChild(D405_COLOR_OPTICAL_FRAME_NAME)
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
                    f"parent={parent_path}",
                    f"fk_frame={fk_frame}",
                    f"source_mesh={mesh_path}",
                    f"body={body_kind}",
                    f"body_triangles={body_triangles}",
                    f"offset={mount_offset}",
                    f"target_offset={target_offset}",
                    f"rpy_deg={mount_rpy_deg}",
                    f"center_on_axis={int(center_on_axis)}",
                    f"body_visual_offset={body_visual_offset}",
                    f"target_world_translate={target_world_translate or ''}",
                    f"target_world_rotate_deg={target_world_rotate_deg or ''}",
                    f"target_world_scale={target_world_scale}",
                    f"target_world_pose_applies_to={target_pose_applies_to}",
                    "direct_body_pose=0",
                    f"camera_prims_enabled={int(cameras_enabled)}",
                    f"depth_camera={'DepthCamera' if cameras_enabled else ''}",
                    f"color_camera={'ColorCamera' if cameras_enabled else ''}",
                    "resolution=1280x720",
                    "fps=30",
                    "clip_range_m=0.07,0.50",
                    "tracking=0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        carb.log_warn(f"Could not write A1Z D405 status file: {status_path}: {exc}")
    return attachment
