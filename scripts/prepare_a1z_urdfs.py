#!/usr/bin/env python3

from __future__ import annotations

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
VENDOR_SOURCE_URDF = ROOT_DIR / "vendor" / "GALAXEA-A1Z" / "a1z" / "robot_models" / "a1z" / "A1Z_G1Z.urdf"
SOURCE_URDF = ROBOT_URDF_DIR / "A1Z_G1Z.urdf"
ISAAC_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_isaac.urdf"
CONTROL_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_control.urdf"
ASSET_D405_MESH = ROOT_DIR / "assets" / "realsense_d405" / "d405.stl"
PACKAGE_D405_MESH = ROBOT_MESH_DIR / "d405.stl"
DEFAULT_D405_MOUNT_OFFSET = (0.0, 0.0, 0.05623718)
DEFAULT_D405_MOUNT_RPY_DEG = (0.0, 0.0, 0.0)
DEFAULT_D405_MASS_KG = 0.001
D405_BASE_MASS_KG = 0.072
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

D405_LINK_XML = """
<link name="d405_link">
  <inertial>
    <origin xyz="0 0 0" rpy="0 0 0" />
    <mass value="{mass_kg}" />
    <inertia ixx="{ixx}" ixy="{ixy}" ixz="{ixz}" iyy="{iyy}" iyz="{iyz}" izz="{izz}" />
  </inertial>
  <visual>
    <origin xyz="0 0 0" rpy="0 0 0" />
    <geometry>
      <mesh filename="package://A1Z_G1Z/meshes/d405.stl" scale="0.001 0.001 0.001" />
    </geometry>
    <material name="">
      <color rgba="0.16 0.16 0.15 1" />
    </material>
  </visual>
  <collision>
    <origin xyz="0.01465 0 0.021" rpy="0 0 0" />
    <geometry>
      <box size="0.023 0.042 0.042" />
    </geometry>
  </collision>
</link>
""".strip()

D405_JOINT_XML = """
<joint name="d405_mount_joint" type="fixed">
  <origin xyz="{mount_x} {mount_y} {mount_z}" rpy="{mount_roll} {mount_pitch} {mount_yaw}" />
  <parent link="arm_link6" />
  <child link="d405_link" />
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


def _set_visual_material_rgba(visual: ET.Element, rgba: tuple[float, float, float, float]) -> None:
    material = visual.find("material")
    if material is None:
        material = ET.SubElement(visual, "material", {"name": ""})
    color = material.find("color")
    if color is None:
        color = ET.SubElement(material, "color")
    color.set("rgba", " ".join(_float_string(value) for value in rgba))


def _upsert_d405(root: ET.Element) -> None:
    for tag, name in (("link", "d405_link"), ("joint", "d405_mount_joint")):
        match = _find_named_child(root, tag, name)
        if match is not None:
            _, element = match
            root.remove(element)

    gripper_link = _find_named_child(root, "link", "gripper_finger_left_link")
    insert_index = gripper_link[0] if gripper_link is not None else len(root)
    d405_mass_kg = max(_env_float("A1Z_D405_MASS_KG", DEFAULT_D405_MASS_KG), 1e-6)
    inertia_scale = d405_mass_kg / D405_BASE_MASS_KG
    ixx, ixy, ixz, iyy, iyz, izz = (value * inertia_scale for value in D405_BASE_INERTIA)
    root.insert(
        insert_index,
        ET.fromstring(
            D405_LINK_XML.format(
                mass_kg=_float_string(d405_mass_kg),
                ixx=_float_string(ixx),
                ixy=_float_string(ixy),
                ixz=_float_string(ixz),
                iyy=_float_string(iyy),
                iyz=_float_string(iyz),
                izz=_float_string(izz),
            )
        ),
    )
    mount_x, mount_y, mount_z = _env_vec3("A1Z_D405_MOUNT_OFFSET", DEFAULT_D405_MOUNT_OFFSET)
    mount_roll_deg, mount_pitch_deg, mount_yaw_deg = _env_vec3(
        "A1Z_D405_MOUNT_RPY_DEG",
        DEFAULT_D405_MOUNT_RPY_DEG,
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


def _build_variant(*, fixed_gripper: bool, limit_kind: str) -> ET.ElementTree:
    base_tree = _parse_urdf(SOURCE_URDF)
    variant_root = deepcopy(base_tree.getroot())
    _apply_arm_joint_limits(variant_root, limit_kind=limit_kind)
    _upsert_d405(variant_root)
    _set_gripper_joint_mode(variant_root, fixed=fixed_gripper)
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
    sync_d405_mesh()
    prepare_robot_package_urdfs()
    print(f"Prepared: {ISAAC_URDF}")
    print(f"Prepared: {CONTROL_URDF}")
    print(f"Synced:   {PACKAGE_D405_MESH}")


if __name__ == "__main__":
    main()
