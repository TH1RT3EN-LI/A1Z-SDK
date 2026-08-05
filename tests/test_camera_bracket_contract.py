from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "camera_bracket.json"
ASSET_DIR = ROOT / "assets" / "camera_bracket"
ROBOT_DIR = ROOT / "build" / "robot_packages" / "A1Z_G1Z"
ROBOT_USD = ROOT / "build" / "scenes" / "A1Z_G1Z_robot.usd"
ROBOT_BASE_USDA = (
    ROOT / "build" / "scenes" / "A1Z_G1Z_isaac" / "payloads" / "base.usda"
)


def test_camera_bracket_has_one_authoritative_mount_pose() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["enabled"] is True
    assert config["parent_link"] == "arm_link6"
    assert config["mount_offset_xyz_m"] == [0.06842, 0.0, 0.06546]
    assert config["mount_orient_deg"] == [-90.0, -90.0, 0.0]
    assert "mount_rpy_deg" not in config
    assert config["mesh_scale"] == [0.001, 0.001, 0.001]
    assert config["material_model"]["nominal_density_kg_m3"] == 1200.0
    assert config["material_model"]["density_range_kg_m3"] == [1000.0, 1400.0]
    assert math.isclose(config["mass_kg"], 0.029270651684159033)

    generator = (ROOT / "scripts" / "prepare_a1z_urdfs.py").read_text(
        encoding="utf-8"
    )
    assert "A1Z_CAMERA_BRACKET_MOUNT" not in generator
    assert "CAMERA_BRACKET_CONFIG" in generator


def test_camera_bracket_source_and_normalized_mesh_are_tracked_assets() -> None:
    source = ASSET_DIR / "camera_bracket.step"
    mesh = ASSET_DIR / "camera_bracket.stl"
    report = json.loads(
        (ASSET_DIR / "camera_bracket.conversion.json").read_text(encoding="utf-8")
    )
    assert source.stat().st_size > 100_000
    assert mesh.stat().st_size > 100_000
    assert report["source"] == "assets/camera_bracket/camera_bracket.step"
    assert report["output"] == "assets/camera_bracket/camera_bracket.stl"
    bounds = report["normalized_bbox_mm"]
    assert abs(bounds["min"][0] + bounds["max"][0]) < 1e-6
    assert abs(bounds["min"][1] + bounds["max"][1]) < 1e-6
    assert abs(bounds["min"][2]) < 1e-6


def test_control_and_isaac_urdfs_share_the_fixed_bracket_contract() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for filename in ("A1Z_G1Z_control.urdf", "A1Z_G1Z_isaac.urdf"):
        root = ET.parse(ROBOT_DIR / "urdf" / filename).getroot()
        links = root.findall("./link[@name='camera_bracket_link']")
        joints = root.findall("./joint[@name='camera_bracket_mount_joint']")
        assert len(links) == 1
        assert len(joints) == 1

        joint = joints[0]
        assert joint.get("type") == "fixed"
        assert joint.find("parent").get("link") == "arm_link6"
        assert joint.find("child").get("link") == "camera_bracket_link"
        assert joint.find("origin").get("xyz") == "0.06842 0 0.06546"
        actual_rpy = [
            float(value) for value in joint.find("origin").get("rpy").split()
        ]
        expected_rpy = [-1.570796326795, 0.0, 1.570796326795]
        assert all(
            abs(actual - expected) < 1e-10
            for actual, expected in zip(actual_rpy, expected_rpy, strict=True)
        )

        mesh = links[0].find("./visual/geometry/mesh")
        assert mesh.get("filename") == (
            "package://A1Z_G1Z/meshes/camera_bracket.stl"
        )
        assert mesh.get("scale") == "0.001 0.001 0.001"
        assert math.isclose(
            float(links[0].find("./inertial/mass").get("value")),
            config["mass_kg"],
            rel_tol=1e-10,
        )
        actual_com = [
            float(value)
            for value in links[0].find("./inertial/origin").get("xyz").split()
        ]
        expected_com = config["center_of_mass_xyz_m"]
        assert all(
            abs(actual - expected) < 1e-10
            for actual, expected in zip(actual_com, expected_com, strict=True)
        )
        actual_inertia = links[0].find("./inertial/inertia")
        assert actual_inertia is not None
        for key, expected in config["inertia_kg_m2"].items():
            assert math.isclose(
                float(actual_inertia.get(key)),
                expected,
                rel_tol=1e-10,
                abs_tol=1e-15,
            )


def test_packaged_mesh_matches_the_normalized_source_mesh() -> None:
    assert (ASSET_DIR / "camera_bracket.stl").read_bytes() == (
        ROBOT_DIR / "meshes" / "camera_bracket.stl"
    ).read_bytes()


def test_isaac_bracket_keeps_direct_local_inspector_transform() -> None:
    robot_usd = ROBOT_USD.read_text(encoding="utf-8")
    base_usda = ROBOT_BASE_USDA.read_text(encoding="utf-8")
    bracket_block = base_usda.split(
        'def Xform "camera_bracket_link"', maxsplit=1
    )[1].split('def Xform "d405_link"', maxsplit=1)[0]

    assert "resetXformStack" not in bracket_block
    assert "quatd xformOp:orient = (0.5, -0.5, -0.5, 0.5)" in bracket_block
    assert (
        'uniform token[] xformOpOrder = ["xformOp:translate", '
        '"xformOp:orient", "xformOp:scale"]'
    ) in bracket_block
    assert "xformOp:rotateXYZ" not in robot_usd


def test_runtime_preserves_the_fixed_camera_bracket_local_transform() -> None:
    runtime = (ROOT / "scripts" / "open_a1z_world_with_a1z_sdk.py").read_text(
        encoding="utf-8"
    )
    launcher = (ROOT / "scripts" / "open_workstation_ee_drag.sh").read_text(
        encoding="utf-8"
    )

    assert 'if prim.GetName() == "camera_bracket_link":' in runtime
    assert "CameraBracketEditWindow" not in runtime
    assert "A1Z_CAMERA_BRACKET_EDITOR_ENABLED" not in launcher
