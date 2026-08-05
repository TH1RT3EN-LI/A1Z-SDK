#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
import json
import math
import os
import shutil
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from a1z_ext.config.d405 import load_d405_config


ROBOT_PACKAGE_DIR = ROOT_DIR / "build" / "robot_packages" / "A1Z_G1Z"
ROBOT_URDF_DIR = ROBOT_PACKAGE_DIR / "urdf"
ROBOT_MESH_DIR = ROBOT_PACKAGE_DIR / "meshes"
DEFAULT_ENV_FILE = ROOT_DIR / "config" / "sim.env"
VENDOR_SOURCE_URDF = ROOT_DIR / "vendor" / "GALAXEA-A1Z" / "a1z" / "robot_models" / "a1z" / "A1Z_G1Z.urdf"
SOURCE_URDF = ROBOT_URDF_DIR / "A1Z_G1Z.urdf"
ISAAC_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_isaac.urdf"
CONTROL_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_control.urdf"
CAD_INERTIAL_SOURCE = ROBOT_URDF_DIR / "A1Z_nogripper.csv"
ASSET_D405_MESH = ROOT_DIR / "assets" / "realsense_d405" / "d405.stl"
PACKAGE_D405_MESH = ROBOT_MESH_DIR / "d405.stl"
CAMERA_BRACKET_CONFIG = ROOT_DIR / "config" / "camera_bracket.json"
ASSET_CAMERA_BRACKET_MESH = (
    ROOT_DIR / "assets" / "camera_bracket" / "camera_bracket.stl"
)
PACKAGE_CAMERA_BRACKET_MESH = ROBOT_MESH_DIR / "camera_bracket.stl"
D405_GUNMETAL_RGBA = (0.16, 0.16, 0.15, 1.0)
ROBOT_DARK_RGBA = (0.32, 0.32, 0.33, 1.0)
ROBOT_LIGHT_RGBA = (0.72, 0.74, 0.75, 1.0)

CONTROL_DEFAULTS = json.loads((ROOT_DIR / "a1z_ext" / "config" / "control_defaults.json").read_text(encoding="utf-8"))
ARM_JOINT_NAMES = CONTROL_DEFAULTS["isaacsim"]["arm_joint_names"]
ARM_JOINT_LIMITS = {
    joint_name: {
        "soft": CONTROL_DEFAULTS["arm_soft_joint_limits_deg"][idx],
        "hard": CONTROL_DEFAULTS["arm_hard_joint_limits_deg"][idx],
        "effort": CONTROL_DEFAULTS["arm_rated_torque_nm"][idx],
        "velocity": CONTROL_DEFAULTS["arm_rated_velocity_rad_s"][idx],
    }
    for idx, joint_name in enumerate(ARM_JOINT_NAMES)
}
GRIPPER_JOINT_NAMES = (
    "gripper_finger_left_joint",
    "gripper_finger_rIght_joint",
)
GRIPPER_JOINT_AXIS = "0 1 0"
GRIPPER_JOINT_LIMITS_M = {
    "gripper_finger_left_joint": (0.0, 0.048),
    "gripper_finger_rIght_joint": (-0.048, 0.0),
}
D405_LINK_XML = """
<link name="d405_link">
  <inertial>
    <origin xyz="{com_x} {com_y} {com_z}" rpy="0 0 0" />
    <mass value="{mass_kg}" />
    <inertia ixx="{ixx}" ixy="{ixy}" ixz="{ixz}" iyy="{iyy}" iyz="{iyz}" izz="{izz}" />
  </inertial>
  <visual>
    <origin xyz="0 0 0" rpy="{visual_roll} {visual_pitch} {visual_yaw}" />
    <geometry>
      <mesh filename="package://A1Z_G1Z/meshes/d405.stl" scale="{scale_x} {scale_y} {scale_z}" />
    </geometry>
    <material name="">
      <color rgba="0.16 0.16 0.15 1" />
    </material>
  </visual>
</link>
""".strip()

D405_COLLISION_XML = """
  <collision>
    <origin xyz="0.01465 0 0.021" rpy="0 0 0" />
    <geometry>
      <box size="0.023 0.042 0.042" />
    </geometry>
  </collision>
""".strip()

D405_JOINT_XML = """
<joint name="d405_mount_joint" type="fixed">
  <origin xyz="{mount_x} {mount_y} {mount_z}" rpy="{mount_roll} {mount_pitch} {mount_yaw}" />
  <parent link="{parent_link}" />
  <child link="d405_link" />
</joint>
""".strip()

D405_RECTIFIED_LINK_XML = """
<link name="d405_rectified_link" />
""".strip()

D405_RECTIFIED_JOINT_XML = """
<joint name="d405_rectified_joint" type="fixed">
  <origin xyz="0 0 0" rpy="{rectify_roll} {rectify_pitch} {rectify_yaw}" />
  <parent link="d405_link" />
  <child link="d405_rectified_link" />
</joint>
""".strip()

GRASP_TCP_LINK_XML = """
<link name="grasp_tcp" />
""".strip()

GRASP_TCP_JOINT_XML = """
<joint name="grasp_tcp_joint" type="fixed">
  <origin xyz="{tcp_x} {tcp_y} {tcp_z}" rpy="0 0 0" />
  <parent link="arm_link6" />
  <child link="grasp_tcp" />
</joint>
""".strip()

CAMERA_BRACKET_LINK_XML = """
<link name="camera_bracket_link">
  <inertial>
    <origin xyz="{com_x} {com_y} {com_z}" rpy="0 0 0" />
    <mass value="{mass_kg}" />
    <inertia ixx="{ixx}" ixy="{ixy}" ixz="{ixz}" iyy="{iyy}" iyz="{iyz}" izz="{izz}" />
  </inertial>
  <visual>
    <origin xyz="0 0 0" rpy="0 0 0" />
    <geometry>
      <mesh filename="package://A1Z_G1Z/meshes/camera_bracket.stl" scale="{scale_x} {scale_y} {scale_z}" />
    </geometry>
    <material name="camera_bracket_material">
      <color rgba="{color_r} {color_g} {color_b} {color_a}" />
    </material>
  </visual>
</link>
""".strip()

CAMERA_BRACKET_JOINT_XML = """
<joint name="camera_bracket_mount_joint" type="fixed">
  <origin xyz="{mount_x} {mount_y} {mount_z}" rpy="{mount_roll} {mount_pitch} {mount_yaw}" />
  <parent link="{parent_link}" />
  <child link="camera_bracket_link" />
</joint>
""".strip()


def _parse_urdf(path: Path) -> ET.ElementTree:
    if not path.is_file():
        raise FileNotFoundError(f"Base robot package URDF not found: {path}")
    return ET.parse(path)


def _write_tree(path: Path, tree: ET.ElementTree) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _find_named_child(root: ET.Element, tag: str, name: str) -> tuple[int, ET.Element] | None:
    for index, child in enumerate(root):
        if child.tag == tag and child.get("name") == name:
            return index, child
    return None


def _deg_to_rad_string(value_deg: float) -> str:
    return f"{_deg_to_rad(value_deg):.6f}".rstrip("0").rstrip(".")


def _deg_to_rad(value_deg: float) -> float:
    return float(value_deg) * 3.141592653589793 / 180.0


def _float_string(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _precise_float_string(value: float) -> str:
    """Keep small mass-property terms that six-decimal pose formatting loses."""
    return f"{float(value):.12g}"


def _isaac_orient_to_urdf_rpy_rad(
    orient_deg: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Convert Isaac's Orient editor angles to equivalent URDF fixed-axis RPY."""

    half_angles = [math.radians(value) * 0.5 for value in orient_deg]
    qx = (math.cos(half_angles[0]), math.sin(half_angles[0]), 0.0, 0.0)
    qy = (math.cos(half_angles[1]), 0.0, math.sin(half_angles[1]), 0.0)
    qz = (math.cos(half_angles[2]), 0.0, 0.0, math.sin(half_angles[2]))

    def multiply(
        left: tuple[float, float, float, float],
        right: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        lw, lx, ly, lz = left
        rw, rx, ry, rz = right
        return (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        )

    # Isaac's GfQuatEulerAttributeModel composes Orient as Rz * Ry * Rx in
    # Gf's row-vector convention, equivalent to qx * qy * qz here.
    w, x, y, z = multiply(multiply(qx, qy), qz)
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2.0 * (w * y - z * x))))
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return tuple(0.0 if abs(value) < 1.0e-12 else value for value in (roll, pitch, yaw))


def _env_vec3(name: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = os.environ.get(name)
    if not raw:
        return default
    parts = [part.strip() for part in raw.replace(",", " ").split()]
    if len(parts) != 3:
        raise ValueError(f"{name} must contain exactly 3 numbers, got: {raw}")
    return float(parts[0]), float(parts[1]), float(parts[2])


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return float(default)
    return float(raw.strip())


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return bool(default)
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean-like value, got: {raw}")


def _load_project_env_defaults(env_path: Path) -> None:
    env_path = env_path.expanduser()
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _set_visual_material_rgba(visual: ET.Element, rgba: tuple[float, float, float, float]) -> None:
    material = visual.find("material")
    if material is None:
        material = ET.SubElement(visual, "material", {"name": ""})
    color = material.find("color")
    if color is None:
        color = ET.SubElement(material, "color")
    color.set("rgba", " ".join(_float_string(value) for value in rgba))


def _apply_robot_visual_palette(root: ET.Element) -> None:
    for link in root.findall("link"):
        link_name = link.get("name", "")
        if link_name in {"d405_link", "camera_bracket_link"}:
            continue
        rgba = ROBOT_LIGHT_RGBA if link_name == "arm_link3" else ROBOT_DARK_RGBA
        for visual in link.findall("visual"):
            _set_visual_material_rgba(visual, rgba)


def _upsert_d405(root: ET.Element) -> None:
    for tag, name in (
        ("link", "d405_link"),
        ("link", "d405_rectified_link"),
        ("joint", "d405_mount_joint"),
        ("joint", "d405_rectified_joint"),
    ):
        match = _find_named_child(root, tag, name)
        if match is not None:
            _, element = match
            root.remove(element)

    config = load_d405_config()
    if not bool(config["enabled"]) or not _env_bool("A1Z_D405_ENABLED", True):
        return

    parent_link = str(config["parent_link"])
    if _find_named_child(root, "link", parent_link) is None:
        raise ValueError(f"D405 parent link does not exist: {parent_link}")

    gripper_link = _find_named_child(root, "link", "gripper_finger_left_link")
    insert_index = gripper_link[0] if gripper_link is not None else len(root)
    d405_mass_kg = float(config["mass_kg"])
    com_x, com_y, com_z = (
        float(value) for value in config["center_of_mass_xyz_m"]
    )
    inertia = dict(config["inertia_kg_m2"])
    ixx, ixy, ixz, iyy, iyz, izz = (
        float(inertia[key])
        for key in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")
    )
    visual_roll_deg, visual_pitch_deg, visual_yaw_deg = (
        float(value) for value in config["body_visual_rpy_deg"]
    )
    scale_x, scale_y, scale_z = (
        float(value) for value in config["mesh_scale"]
    )
    d405_link = ET.fromstring(
        D405_LINK_XML.format(
            mass_kg=_precise_float_string(d405_mass_kg),
            com_x=_precise_float_string(com_x),
            com_y=_precise_float_string(com_y),
            com_z=_precise_float_string(com_z),
            ixx=_precise_float_string(ixx),
            ixy=_precise_float_string(ixy),
            ixz=_precise_float_string(ixz),
            iyy=_precise_float_string(iyy),
            iyz=_precise_float_string(iyz),
            izz=_precise_float_string(izz),
            visual_roll=_deg_to_rad_string(visual_roll_deg),
            visual_pitch=_deg_to_rad_string(visual_pitch_deg),
            visual_yaw=_deg_to_rad_string(visual_yaw_deg),
            scale_x=_precise_float_string(scale_x),
            scale_y=_precise_float_string(scale_y),
            scale_z=_precise_float_string(scale_z),
        )
    )
    if _env_bool("A1Z_D405_COLLISION_ENABLED", False):
        d405_link.append(ET.fromstring(D405_COLLISION_XML))
    root.insert(
        insert_index,
        d405_link,
    )
    mount_x, mount_y, mount_z = (
        float(value) for value in config["mount_offset_xyz_m"]
    )
    mount_roll_deg, mount_pitch_deg, mount_yaw_deg = (
        float(value) for value in config["mount_rpy_deg"]
    )
    stage_frames = dict(config["stage_frames"])
    rectify_roll_deg, rectify_pitch_deg, rectify_yaw_deg = (
        float(value) for value in stage_frames["rectify_rpy_deg"]
    )
    root.insert(
        insert_index + 1,
        ET.fromstring(
            D405_JOINT_XML.format(
                mount_x=_precise_float_string(mount_x),
                mount_y=_precise_float_string(mount_y),
                mount_z=_precise_float_string(mount_z),
                mount_roll=_precise_float_string(_deg_to_rad(mount_roll_deg)),
                mount_pitch=_precise_float_string(_deg_to_rad(mount_pitch_deg)),
                mount_yaw=_precise_float_string(_deg_to_rad(mount_yaw_deg)),
                parent_link=parent_link,
            )
        ),
    )
    root.insert(insert_index + 2, ET.fromstring(D405_RECTIFIED_LINK_XML))
    root.insert(
        insert_index + 3,
        ET.fromstring(
            D405_RECTIFIED_JOINT_XML.format(
                rectify_roll=_deg_to_rad_string(rectify_roll_deg),
                rectify_pitch=_deg_to_rad_string(rectify_pitch_deg),
                rectify_yaw=_deg_to_rad_string(rectify_yaw_deg),
            )
        ),
    )


def _upsert_grasp_tcp(root: ET.Element) -> None:
    for tag, name in (("link", "grasp_tcp"), ("joint", "grasp_tcp_joint")):
        match = _find_named_child(root, tag, name)
        if match is not None:
            _, element = match
            root.remove(element)

    left_finger = _find_named_child(root, "link", "gripper_finger_left_link")
    insert_index = left_finger[0] if left_finger is not None else len(root)
    root.insert(insert_index, ET.fromstring(GRASP_TCP_LINK_XML))
    root.insert(
        insert_index + 1,
        ET.fromstring(
            GRASP_TCP_JOINT_XML.format(
                tcp_x=_float_string(0.08),
                tcp_y=_float_string(0.0),
                tcp_z=_float_string(0.0),
            )
        ),
    )


def _load_camera_bracket_config() -> dict[str, object]:
    if not CAMERA_BRACKET_CONFIG.is_file():
        raise FileNotFoundError(
            f"Camera bracket config not found: {CAMERA_BRACKET_CONFIG}"
        )
    payload = json.loads(CAMERA_BRACKET_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("camera_bracket.json must contain a JSON object")

    for key, count in (
        ("mount_offset_xyz_m", 3),
        ("mount_orient_deg", 3),
        ("mesh_scale", 3),
        ("material_rgba", 4),
        ("center_of_mass_xyz_m", 3),
    ):
        values = payload.get(key)
        if (
            not isinstance(values, list)
            or len(values) != count
            or any(not isinstance(value, (int, float)) for value in values)
        ):
            raise ValueError(f"camera_bracket.json {key} must contain {count} numbers")
    parent_link = payload.get("parent_link")
    if not isinstance(parent_link, str) or not parent_link:
        raise ValueError("camera_bracket.json parent_link must be a non-empty string")
    if not isinstance(payload.get("enabled"), bool):
        raise ValueError("camera_bracket.json enabled must be a boolean")
    mass_kg = payload.get("mass_kg")
    if not isinstance(mass_kg, (int, float)) or float(mass_kg) <= 0.0:
        raise ValueError("camera_bracket.json mass_kg must be a positive number")
    inertia = payload.get("inertia_kg_m2")
    inertia_keys = ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")
    if (
        not isinstance(inertia, dict)
        or any(
            not isinstance(inertia.get(key), (int, float))
            for key in inertia_keys
        )
        or any(float(inertia[key]) <= 0.0 for key in ("ixx", "iyy", "izz"))
    ):
        raise ValueError(
            "camera_bracket.json inertia_kg_m2 must contain a valid inertia tensor"
        )
    return payload


def _upsert_camera_bracket(root: ET.Element) -> None:
    for tag, name in (
        ("link", "camera_bracket_link"),
        ("joint", "camera_bracket_mount_joint"),
    ):
        match = _find_named_child(root, tag, name)
        if match is not None:
            _, element = match
            root.remove(element)

    config = _load_camera_bracket_config()
    if not config["enabled"]:
        return

    parent_link = str(config["parent_link"])
    if _find_named_child(root, "link", parent_link) is None:
        raise ValueError(f"camera bracket parent link does not exist: {parent_link}")

    mount_x, mount_y, mount_z = (
        float(value) for value in config["mount_offset_xyz_m"]
    )
    mount_roll, mount_pitch, mount_yaw = _isaac_orient_to_urdf_rpy_rad(
        tuple(float(value) for value in config["mount_orient_deg"])
    )
    scale_x, scale_y, scale_z = (
        float(value) for value in config["mesh_scale"]
    )
    color_r, color_g, color_b, color_a = (
        float(value) for value in config["material_rgba"]
    )
    mass_kg = float(config["mass_kg"])
    com_x, com_y, com_z = (
        float(value) for value in config["center_of_mass_xyz_m"]
    )
    inertia = {
        key: float(value)
        for key, value in dict(config["inertia_kg_m2"]).items()
    }
    if any(value <= 0.0 for value in (scale_x, scale_y, scale_z)):
        raise ValueError("camera bracket mesh_scale values must be positive")
    if any(value < 0.0 or value > 1.0 for value in (color_r, color_g, color_b, color_a)):
        raise ValueError("camera bracket material_rgba values must be between 0 and 1")

    left_finger = _find_named_child(root, "link", "gripper_finger_left_link")
    insert_index = left_finger[0] if left_finger is not None else len(root)
    root.insert(
        insert_index,
        ET.fromstring(
            CAMERA_BRACKET_LINK_XML.format(
                mass_kg=_precise_float_string(mass_kg),
                com_x=_precise_float_string(com_x),
                com_y=_precise_float_string(com_y),
                com_z=_precise_float_string(com_z),
                ixx=_precise_float_string(inertia["ixx"]),
                ixy=_precise_float_string(inertia["ixy"]),
                ixz=_precise_float_string(inertia["ixz"]),
                iyy=_precise_float_string(inertia["iyy"]),
                iyz=_precise_float_string(inertia["iyz"]),
                izz=_precise_float_string(inertia["izz"]),
                scale_x=_float_string(scale_x),
                scale_y=_float_string(scale_y),
                scale_z=_float_string(scale_z),
                color_r=_float_string(color_r),
                color_g=_float_string(color_g),
                color_b=_float_string(color_b),
                color_a=_float_string(color_a),
            )
        ),
    )
    root.insert(
        insert_index + 1,
        ET.fromstring(
            CAMERA_BRACKET_JOINT_XML.format(
                mount_x=_float_string(mount_x),
                mount_y=_float_string(mount_y),
                mount_z=_float_string(mount_z),
                mount_roll=_precise_float_string(mount_roll),
                mount_pitch=_precise_float_string(mount_pitch),
                mount_yaw=_precise_float_string(mount_yaw),
                parent_link=parent_link,
            )
        ),
    )


def _apply_arm_joint_limits(root: ET.Element, *, limit_kind: str) -> None:
    for joint in root.findall("joint"):
        joint_name = joint.get("name")
        if joint_name not in ARM_JOINT_LIMITS:
            continue
        limit = joint.find("limit")
        if limit is None:
            raise RuntimeError(f"Joint {joint_name} is missing a <limit> node.")
        overrides = ARM_JOINT_LIMITS[joint_name]
        lower_deg, upper_deg = overrides[limit_kind]
        limit.set("lower", _deg_to_rad_string(lower_deg))
        limit.set("upper", _deg_to_rad_string(upper_deg))
        limit.set("effort", _float_string(overrides["effort"]))
        limit.set("velocity", _float_string(overrides["velocity"]))


def _set_gripper_joint_mode(root: ET.Element, *, fixed: bool) -> None:
    for joint in root.findall("joint"):
        joint_name = joint.get("name")
        if joint_name not in GRIPPER_JOINT_NAMES:
            continue
        if fixed:
            joint.set("type", "fixed")
            for tag in ("axis", "limit", "mimic"):
                child = joint.find(tag)
                if child is not None:
                    joint.remove(child)
        else:
            joint.set("type", "prismatic")
            axis = joint.find("axis")
            if axis is None:
                axis = ET.SubElement(joint, "axis")
            axis.set("xyz", GRIPPER_JOINT_AXIS)
            limit = joint.find("limit")
            if limit is None:
                limit = ET.SubElement(joint, "limit")
            lower_m, upper_m = GRIPPER_JOINT_LIMITS_M[joint_name]
            limit.set("lower", _float_string(lower_m))
            limit.set("upper", _float_string(upper_m))
            limit.set(
                "effort",
                _float_string(CONTROL_DEFAULTS["isaacsim"]["gripper_max_effort"][0]),
            )
            limit.set(
                "velocity",
                _float_string(CONTROL_DEFAULTS["isaacsim"]["gripper_max_velocity"][0]),
            )


def _load_cad_link_inertial(
    link_name: str,
) -> dict[str, float | tuple[float, float, float]]:
    if not CAD_INERTIAL_SOURCE.is_file():
        raise FileNotFoundError(f"CAD inertial source not found: {CAD_INERTIAL_SOURCE}")

    with CAD_INERTIAL_SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        matches = [
            row
            for row in csv.DictReader(stream)
            if row.get("Link Name") == link_name
        ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one CAD inertial row for {link_name}, found {len(matches)}"
        )

    row = matches[0]
    inertial = {
        "mass": float(row["Mass"]),
        "origin_xyz": (
            float(row["Center of Mass X"]),
            float(row["Center of Mass Y"]),
            float(row["Center of Mass Z"]),
        ),
        "ixx": float(row["Moment Ixx"]),
        "ixy": float(row["Moment Ixy"]),
        "ixz": float(row["Moment Ixz"]),
        "iyy": float(row["Moment Iyy"]),
        "iyz": float(row["Moment Iyz"]),
        "izz": float(row["Moment Izz"]),
    }
    if inertial["mass"] <= 0.0:
        raise ValueError(f"CAD link {link_name} has non-positive mass")
    if any(inertial[key] <= 0.0 for key in ("ixx", "iyy", "izz")):
        raise ValueError(f"CAD link {link_name} has non-positive diagonal inertia")
    return inertial


def _override_link_inertial(
    root: ET.Element,
    link_name: str,
    inertial_values: dict[str, float | tuple[float, float, float]],
) -> None:
    match = _find_named_child(root, "link", link_name)
    if match is None:
        raise ValueError(f"Required link not found in vendor URDF: {link_name}")
    _, link = match
    inertial = link.find("inertial")
    if inertial is None:
        raise ValueError(f"Required inertial element missing for link: {link_name}")
    origin = inertial.find("origin")
    mass = inertial.find("mass")
    inertia = inertial.find("inertia")
    if origin is None or mass is None or inertia is None:
        raise ValueError(f"Incomplete inertial element for link: {link_name}")

    origin.set(
        "xyz",
        " ".join(
            _precise_float_string(value)
            for value in inertial_values["origin_xyz"]
        ),
    )
    mass.set("value", _precise_float_string(inertial_values["mass"]))
    for attribute in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"):
        inertia.set(
            attribute,
            _precise_float_string(inertial_values[attribute]),
        )


def _scale_link_inertial_mass(root: ET.Element, link_name: str, target_mass_kg: float) -> None:
    match = _find_named_child(root, "link", link_name)
    if match is None:
        return
    _, link = match
    inertial = link.find("inertial")
    if inertial is None:
        return
    mass = inertial.find("mass")
    inertia = inertial.find("inertia")
    if mass is None or inertia is None:
        return

    source_mass_kg = float(mass.get("value", "0"))
    if source_mass_kg <= 0:
        raise ValueError(f"Link {link_name} has non-positive source mass: {source_mass_kg}")

    target_mass_kg = max(target_mass_kg, 1e-6)
    inertia_scale = target_mass_kg / source_mass_kg
    mass.set("value", _float_string(target_mass_kg))
    for attribute in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"):
        inertia.set(attribute, _float_string(float(inertia.get(attribute, "0")) * inertia_scale))


def _remove_gripper_subtree(root: ET.Element) -> None:
    gripper_link_names = {"gripper_finger_left_link", "gripper_finger_rIght_link"}
    gripper_joint_names = set(GRIPPER_JOINT_NAMES)
    to_remove = []
    for child in root:
        name = child.get("name")
        if child.tag == "link" and name in gripper_link_names:
            to_remove.append(child)
        elif child.tag == "joint" and name in gripper_joint_names:
            to_remove.append(child)
    for element in to_remove:
        root.remove(element)


def _build_variant(*, fixed_gripper: bool, limit_kind: str) -> ET.ElementTree:
    # The vendored SDK model is the canonical input.  A1Z_G1Z.urdf in the
    # generated package is a legacy, human-readable snapshot whose display
    # palette must not be overwritten every time derived variants are rebuilt.
    base_tree = _parse_urdf(VENDOR_SOURCE_URDF)
    variant_root = deepcopy(base_tree.getroot())
    _apply_robot_visual_palette(variant_root)
    _apply_arm_joint_limits(variant_root, limit_kind=limit_kind)
    # The vendored arm_link6 tensor violates the rigid-body principal-inertia
    # triangle inequality. Use the traceable CAD export for this link only.
    _override_link_inertial(
        variant_root,
        "arm_link6",
        _load_cad_link_inertial("arm_link6"),
    )
    _upsert_grasp_tcp(variant_root)
    _upsert_camera_bracket(variant_root)
    _upsert_d405(variant_root)
    if _env_bool("A1Z_WITH_GRIPPER", True):
        finger_mass_override = os.environ.get("A1Z_GRIPPER_FINGER_MASS_KG")
        if finger_mass_override is not None and finger_mass_override.strip():
            finger_mass_kg = float(finger_mass_override)
            _scale_link_inertial_mass(
                variant_root, "gripper_finger_left_link", finger_mass_kg
            )
            _scale_link_inertial_mass(
                variant_root, "gripper_finger_rIght_link", finger_mass_kg
            )
        _set_gripper_joint_mode(variant_root, fixed=fixed_gripper)
    else:
        _remove_gripper_subtree(variant_root)
    return ET.ElementTree(variant_root)


def prepare_robot_package_urdfs() -> None:
    ROBOT_URDF_DIR.mkdir(parents=True, exist_ok=True)
    _write_tree(ISAAC_URDF, _build_variant(fixed_gripper=False, limit_kind="hard"))
    _write_tree(CONTROL_URDF, _build_variant(fixed_gripper=True, limit_kind="soft"))


def sync_d405_mesh() -> None:
    if not ASSET_D405_MESH.is_file():
        raise FileNotFoundError(f"D405 mesh not found: {ASSET_D405_MESH}")
    ROBOT_MESH_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSET_D405_MESH, PACKAGE_D405_MESH)


def sync_camera_bracket_mesh() -> None:
    if not ASSET_CAMERA_BRACKET_MESH.is_file():
        raise FileNotFoundError(
            f"Camera bracket mesh not found: {ASSET_CAMERA_BRACKET_MESH}"
        )
    ROBOT_MESH_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSET_CAMERA_BRACKET_MESH, PACKAGE_CAMERA_BRACKET_MESH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate A1Z control and Isaac URDFs.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    args = parser.parse_args()
    _load_project_env_defaults(args.env_file)
    sync_d405_mesh()
    sync_camera_bracket_mesh()
    prepare_robot_package_urdfs()
    print(f"Prepared: {ISAAC_URDF}")
    print(f"Prepared: {CONTROL_URDF}")
    print(f"Synced:   {PACKAGE_D405_MESH}")
    print(f"Synced:   {PACKAGE_CAMERA_BRACKET_MESH}")


if __name__ == "__main__":
    main()
