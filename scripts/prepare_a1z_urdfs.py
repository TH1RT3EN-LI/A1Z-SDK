#!/usr/bin/env python3

from __future__ import annotations

import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
ROBOT_PACKAGE_DIR = ROOT_DIR / "build" / "robot_packages" / "A1Z_G1Z"
ROBOT_URDF_DIR = ROBOT_PACKAGE_DIR / "urdf"
ROBOT_MESH_DIR = ROBOT_PACKAGE_DIR / "meshes"
SDK_URDF_DIR = ROOT_DIR / "vendor" / "GALAXEA-A1Z" / "a1z" / "robot_models" / "a1z"
SDK_CONTROL_URDF = SDK_URDF_DIR / "A1Z_G1Z_control.urdf"
ISAAC_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_isaac.urdf"
CONTROL_URDF = ROBOT_URDF_DIR / "A1Z_G1Z_control.urdf"
ASSET_D405_MESH = ROOT_DIR / "assets" / "realsense_d405" / "d405.stl"
PACKAGE_D405_MESH = ROBOT_MESH_DIR / "d405.stl"

D405_URDF_BLOCK = """
  <link
    name="d405_link">
    <inertial>
      <origin
        xyz="0 0 0"
        rpy="0 0 0" />
      <mass
        value="0.072" />
      <inertia
        ixx="0.003881243"
        ixy="0"
        ixz="0"
        iyy="0.00049894"
        iyz="0"
        izz="0.003879257" />
    </inertial>
    <visual>
      <origin
        xyz="0 0 0"
        rpy="0 0 0" />
      <geometry>
        <mesh
          filename="package://A1Z_G1Z/meshes/d405.stl"
          scale="0.001 0.001 0.001" />
      </geometry>
      <material
        name="">
        <color
          rgba="0.16 0.16 0.15 1" />
      </material>
    </visual>
    <collision>
      <origin
        xyz="0.01465 0 0.021"
        rpy="0 0 0" />
      <geometry>
        <box
          size="0.023 0.042 0.042" />
      </geometry>
    </collision>
  </link>
  <joint
    name="d405_mount_joint"
    type="fixed">
    <origin
      xyz="0.09238 0 0.09625"
      rpy="2.2724490548256018 0 1.5707963267948966" />
    <parent
      link="arm_link6" />
    <child
      link="d405_link" />
  </joint>
""".strip("\n")


def _strip_existing_d405_block(text: str) -> str:
    start_marker = '  <link\n    name="d405_link">'
    end_marker = '  <link\n   name="gripper_finger_left_link">'
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return text
    end_idx = text.find(end_marker, start_idx)
    if end_idx == -1:
        raise RuntimeError("Could not locate end of existing D405 block in URDF.")
    return text[:start_idx] + text[end_idx:]


def _inject_d405_block(text: str) -> str:
    text = _strip_existing_d405_block(text)
    marker = '  <link\n   name="gripper_finger_left_link">'
    idx = text.find(marker)
    if idx == -1:
        raise RuntimeError("Could not locate gripper insertion point in URDF.")
    return text[:idx] + D405_URDF_BLOCK + "\n" + text[idx:]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def prepare_robot_package_urdfs() -> None:
    source_isaac = ROBOT_URDF_DIR / "A1Z_G1Z.urdf"
    if not source_isaac.is_file():
        raise FileNotFoundError(f"Base robot package URDF not found: {source_isaac}")
    isaac_text = source_isaac.read_text(encoding="utf-8")
    isaac_with_d405 = _inject_d405_block(isaac_text)
    _write_text(ISAAC_URDF, isaac_with_d405)

    if not SDK_CONTROL_URDF.is_file():
        raise FileNotFoundError(f"SDK control URDF not found: {SDK_CONTROL_URDF}")
    control_text = SDK_CONTROL_URDF.read_text(encoding="utf-8")
    control_with_d405 = _inject_d405_block(control_text)
    _write_text(CONTROL_URDF, control_with_d405)


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
