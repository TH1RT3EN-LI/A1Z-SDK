#!/usr/bin/env python3

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT_DIR = Path(__file__).resolve().parent.parent
ROBOT_PACKAGE_DIR = ROOT_DIR / "build" / "robot_packages" / "A1Z_G1Z"
ROBOT_URDF_DIR = ROBOT_PACKAGE_DIR / "urdf"
ROBOT_MESH_DIR = ROBOT_PACKAGE_DIR / "meshes"
DEFAULT_ENV_FILE = ROOT_DIR / "config" / "sim.env"
VENDOR_SOURCE_URDF = ROOT_DIR / "vendor" / "GALAXEA-A1Z" / "a1z" / "robot_models" / "a1z" / "A1Z_G1Z.urdf"
SOURCE_URDF = ROBOT_URDF_DIR / "A1Z_G1Z.urdf"
ISAAC_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_isaac.urdf"
CONTROL_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_control.urdf"
ASSET_D405_MESH = ROOT_DIR / "assets" / "realsense_d405" / "d405.stl"
PACKAGE_D405_MESH = ROBOT_MESH_DIR / "d405.stl"
DEFAULT_D405_STAGE_MOUNT_OFFSET_XYZ_M = (0.08, 0.0, 0.08623718)
DEFAULT_D405_STAGE_MOUNT_RPY_DEG = (0.0, 0.0, 0.0)
DEFAULT_D405_MASS_KG = 0.001
D405_BASE_MASS_KG = 0.072
DEFAULT_GRIPPER_FINGER_MASS_KG = 0.02
D405_BASE_INERTIA = (
    0.003881243,
    0.0,
    0.0,
    0.00049894,
    0.0,
    0.003879257,
)
D405_GUNMETAL_RGBA = (0.16, 0.16, 0.15, 1.0)

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
LINK3_INERTIA_OVERRIDE = {
    "mass": 0.93954481,
    "origin_xyz": (0.16216028, -6.8e-06, 0.05497523),
    "ixx": 0.0006646,
    "ixy": -5.769e-05,
    "ixz": -0.00070446,
    "iyy": 0.00871203,
    "iyz": -1.192e-05,
    "izz": 0.00879503,
}
LINK4_INERTIA_OVERRIDE = {
    "mass": 0.17709874,
    "origin_xyz": (0.03970651, 0.00298658, 0.03093312),
    "ixx": 0.00025509,
    "ixy": 1.994e-05,
    "ixz": -9.986e-05,
    "iyy": 0.00027975,
    "iyz": 1.559e-05,
    "izz": 0.00029767,
}
LINK5_INERTIA_OVERRIDE = {
    "mass": 0.36875049,
    "origin_xyz": (-0.00366248, -2.724e-05, -0.03904971),
    "ixx": 0.00010146,
    "ixy": -7.0e-08,
    "ixz": 5.55e-06,
    "iyy": 0.00011993,
    "iyz": 0.0,
    "izz": 8.271e-05,
}
LINK6_INERTIA_OVERRIDE = {
    "mass": 0.42335647,
    "origin_xyz": (0.05514353, -2.867e-05, -0.00013152),
    "ixx": 0.00028807,
    "ixy": -6.5e-07,
    "ixz": -2.8e-06,
    "iyy": 0.00050989,
    "iyz": 1.432e-05,
    "izz": 0.00062848,
}

D405_LINK_XML = """
<link name="d405_link">
  <inertial>
    <origin xyz="0 0 0" rpy="0 0 0" />
    <mass value="{mass_kg}" />
    <inertia ixx="{ixx}" ixy="{ixy}" ixz="{ixz}" iyy="{iyy}" iyz="{iyz}" izz="{izz}" />
  </inertial>
  <visual>
    <origin xyz="0 0 0" rpy="{visual_roll} {visual_pitch} {visual_yaw}" />
    <geometry>
      <mesh filename="package://A1Z_G1Z/meshes/d405.stl" scale="0.001 0.001 0.001" />
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
  <parent link="arm_link6" />
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

    if not _env_bool("A1Z_D405_ENABLED", True):
        return

    gripper_link = _find_named_child(root, "link", "gripper_finger_left_link")
    insert_index = gripper_link[0] if gripper_link is not None else len(root)
    d405_mass_kg = max(_env_float("A1Z_D405_MASS_KG", DEFAULT_D405_MASS_KG), 1e-6)
    inertia_scale = d405_mass_kg / D405_BASE_MASS_KG
    ixx, ixy, ixz, iyy, iyz, izz = (value * inertia_scale for value in D405_BASE_INERTIA)
    visual_roll_deg, visual_pitch_deg, visual_yaw_deg = _env_vec3(
        "A1Z_D405_BODY_VISUAL_RPY_DEG",
        (0.0, 0.0, 0.0),
    )
    d405_link = ET.fromstring(
        D405_LINK_XML.format(
            mass_kg=_float_string(d405_mass_kg),
            ixx=_float_string(ixx),
            ixy=_float_string(ixy),
            ixz=_float_string(ixz),
            iyy=_float_string(iyy),
            iyz=_float_string(iyz),
            izz=_float_string(izz),
            visual_roll=_deg_to_rad_string(visual_roll_deg),
            visual_pitch=_deg_to_rad_string(visual_pitch_deg),
            visual_yaw=_deg_to_rad_string(visual_yaw_deg),
        )
    )
    if _env_bool("A1Z_D405_COLLISION_ENABLED", False):
        d405_link.append(ET.fromstring(D405_COLLISION_XML))
    root.insert(
        insert_index,
        d405_link,
    )
    mount_x, mount_y, mount_z = _env_vec3(
        "A1Z_D405_STAGE_MOUNT_OFFSET_XYZ_M",
        DEFAULT_D405_STAGE_MOUNT_OFFSET_XYZ_M,
    )
    mount_roll_deg, mount_pitch_deg, mount_yaw_deg = _env_vec3(
        "A1Z_D405_STAGE_MOUNT_RPY_DEG",
        DEFAULT_D405_STAGE_MOUNT_RPY_DEG,
    )
    rectify_roll_deg, rectify_pitch_deg, rectify_yaw_deg = _env_vec3(
        "A1Z_D405_STAGE_RECTIFY_RPY_DEG",
        (0.0, 0.0, 0.0),
    )
    root.insert(
        insert_index + 1,
        ET.fromstring(
            D405_JOINT_XML.format(
                mount_x=_float_string(mount_x),
                mount_y=_float_string(mount_y),
                mount_z=_float_string(mount_z),
                mount_roll=_deg_to_rad_string(mount_roll_deg),
                mount_pitch=_deg_to_rad_string(mount_pitch_deg),
                mount_yaw=_deg_to_rad_string(mount_yaw_deg),
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


def _override_link_inertial(root: ET.Element, link_name: str, override: dict[str, float | tuple[float, float, float]]) -> None:
    match = _find_named_child(root, "link", link_name)
    if match is None:
        return
    _, link = match
    inertial = link.find("inertial")
    if inertial is None:
        return
    origin = inertial.find("origin")
    if origin is not None:
        origin.set(
            "xyz",
            " ".join(_float_string(value) for value in override["origin_xyz"]),
        )
    mass = inertial.find("mass")
    if mass is not None:
        mass.set("value", _float_string(override["mass"]))
    inertia = inertial.find("inertia")
    if inertia is not None:
        inertia.set("ixx", _float_string(override["ixx"]))
        inertia.set("ixy", _float_string(override["ixy"]))
        inertia.set("ixz", _float_string(override["ixz"]))
        inertia.set("iyy", _float_string(override["iyy"]))
        inertia.set("iyz", _float_string(override["iyz"]))
        inertia.set("izz", _float_string(override["izz"]))


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
    base_tree = _parse_urdf(SOURCE_URDF)
    variant_root = deepcopy(base_tree.getroot())
    _apply_arm_joint_limits(variant_root, limit_kind=limit_kind)
    _override_link_inertial(variant_root, "arm_link3", LINK3_INERTIA_OVERRIDE)
    _override_link_inertial(variant_root, "arm_link4", LINK4_INERTIA_OVERRIDE)
    _override_link_inertial(variant_root, "arm_link5", LINK5_INERTIA_OVERRIDE)
    _override_link_inertial(variant_root, "arm_link6", LINK6_INERTIA_OVERRIDE)
    _upsert_grasp_tcp(variant_root)
    _upsert_d405(variant_root)
    if _env_bool("A1Z_WITH_GRIPPER", True):
        finger_mass_kg = _env_float("A1Z_GRIPPER_FINGER_MASS_KG", DEFAULT_GRIPPER_FINGER_MASS_KG)
        _scale_link_inertial_mass(variant_root, "gripper_finger_left_link", finger_mass_kg)
        _scale_link_inertial_mass(variant_root, "gripper_finger_rIght_link", finger_mass_kg)
        _set_gripper_joint_mode(variant_root, fixed=fixed_gripper)
    else:
        _remove_gripper_subtree(variant_root)
    return ET.ElementTree(variant_root)


def prepare_robot_package_urdfs() -> None:
    ROBOT_URDF_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VENDOR_SOURCE_URDF, SOURCE_URDF)
    _write_tree(ISAAC_URDF, _build_variant(fixed_gripper=False, limit_kind="hard"))
    _write_tree(CONTROL_URDF, _build_variant(fixed_gripper=True, limit_kind="soft"))


def sync_d405_mesh() -> None:
    if not ASSET_D405_MESH.is_file():
        raise FileNotFoundError(f"D405 mesh not found: {ASSET_D405_MESH}")
    ROBOT_MESH_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSET_D405_MESH, PACKAGE_D405_MESH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate A1Z control and Isaac URDFs.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    args = parser.parse_args()
    _load_project_env_defaults(args.env_file)
    sync_d405_mesh()
    prepare_robot_package_urdfs()
    print(f"Prepared: {ISAAC_URDF}")
    print(f"Prepared: {CONTROL_URDF}")
    print(f"Synced:   {PACKAGE_D405_MESH}")


if __name__ == "__main__":
    main()
