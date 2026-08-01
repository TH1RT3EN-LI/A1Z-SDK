from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from a1z_ext.runtime.d405.settings import (
    D405AssetSettings,
    D405ComputeSettings,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "d405.json"
ROBOT_URDF_DIR = ROOT / "build" / "robot_packages" / "A1Z_G1Z" / "urdf"
CAD_INERTIAL_SOURCE = ROBOT_URDF_DIR / "A1Z_nogripper.csv"
REMOVED_POSE_ENV_KEYS = (
    "A1Z_D405_STAGE_MOUNT_OFFSET_XYZ_M",
    "A1Z_D405_STAGE_MOUNT_RPY_DEG",
    "A1Z_D405_STAGE_RECTIFY_RPY_DEG",
    "A1Z_D405_BODY_VISUAL_RPY_DEG",
    "A1Z_D405_STAGE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M",
    "A1Z_D405_STAGE_RECTIFIED_TO_OPTICAL_RPY_DEG",
    "A1Z_D405_COMPUTE_INSTALL_RPY_DEG",
    "A1Z_D405_COMPUTE_RECTIFY_RPY_DEG",
    "A1Z_D405_COMPUTE_RECTIFIED_TO_OPTICAL_OFFSET_XYZ_M",
    "A1Z_D405_MASS_KG",
)


def _matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [
            sum(left[row][inner] * right[inner][column] for inner in range(3))
            for column in range(3)
        ]
        for row in range(3)
    ]


def _matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [
        sum(matrix[row][column] * vector[column] for column in range(3))
        for row in range(3)
    ]


def _rpy_matrix(rpy_deg: list[float]) -> list[list[float]]:
    roll, pitch, yaw = (math.radians(value) for value in rpy_deg)
    rx = [
        [1.0, 0.0, 0.0],
        [0.0, math.cos(roll), -math.sin(roll)],
        [0.0, math.sin(roll), math.cos(roll)],
    ]
    ry = [
        [math.cos(pitch), 0.0, math.sin(pitch)],
        [0.0, 1.0, 0.0],
        [-math.sin(pitch), 0.0, math.cos(pitch)],
    ]
    rz = [
        [math.cos(yaw), -math.sin(yaw), 0.0],
        [math.sin(yaw), math.cos(yaw), 0.0],
        [0.0, 0.0, 1.0],
    ]
    return _matmul(_matmul(rz, ry), rx)


def _config() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _inertial_signature(inertial: ET.Element) -> dict[str, dict[str, str]]:
    return {
        child.tag: dict(child.attrib)
        for child in inertial
        if child.tag in {"origin", "mass", "inertia"}
    }


def _numeric_inertial_signature(
    inertial: ET.Element,
) -> dict[str, float | tuple[float, float, float]]:
    origin = inertial.find("origin")
    mass = inertial.find("mass")
    inertia = inertial.find("inertia")
    assert origin is not None
    assert mass is not None
    assert inertia is not None
    return {
        "origin_xyz": tuple(float(value) for value in origin.get("xyz").split()),
        "mass": float(mass.get("value")),
        **{
            key: float(inertia.get(key))
            for key in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")
        },
    }


def _cad_inertial_signature(
    link_name: str,
) -> dict[str, float | tuple[float, float, float]]:
    with CAD_INERTIAL_SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        matches = [
            row
            for row in csv.DictReader(stream)
            if row.get("Link Name") == link_name
        ]
    assert len(matches) == 1
    row = matches[0]
    return {
        "origin_xyz": (
            float(row["Center of Mass X"]),
            float(row["Center of Mass Y"]),
            float(row["Center of Mass Z"]),
        ),
        "mass": float(row["Mass"]),
        "ixx": float(row["Moment Ixx"]),
        "ixy": float(row["Moment Ixy"]),
        "ixz": float(row["Moment Ixz"]),
        "iyy": float(row["Moment Iyy"]),
        "iyz": float(row["Moment Iyz"]),
        "izz": float(row["Moment Izz"]),
    }


def _determinant_3x3(matrix: tuple[tuple[float, ...], ...]) -> float:
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _assert_physically_realizable_inertia(
    values: dict[str, float | tuple[float, float, float]],
) -> None:
    inertia = (
        (values["ixx"], values["ixy"], values["ixz"]),
        (values["ixy"], values["iyy"], values["iyz"]),
        (values["ixz"], values["iyz"], values["izz"]),
    )
    trace = values["ixx"] + values["iyy"] + values["izz"]
    covariance = tuple(
        tuple(
            (0.5 * trace if row == column else 0.0) - inertia[row][column]
            for column in range(3)
        )
        for row in range(3)
    )
    tolerance = 1e-15
    assert all(covariance[index][index] >= -tolerance for index in range(3))
    assert all(
        covariance[first][first] * covariance[second][second]
        - covariance[first][second] ** 2
        >= -tolerance
        for first, second in ((0, 1), (0, 2), (1, 2))
    )
    assert _determinant_3x3(covariance) >= -tolerance


def test_d405_rear_holes_and_bracket_holes_are_coincident() -> None:
    config = _config()
    mount_rotation = _rpy_matrix(config["mount_rpy_deg"])
    body_rotation = _rpy_matrix(config["body_visual_rpy_deg"])
    mesh_to_parent = _matmul(mount_rotation, body_rotation)
    mount_translation = config["mount_offset_xyz_m"]
    scale = config["mesh_scale"]
    rear = config["rear_mount_datum"]
    target = config["target_bracket_datum"]

    actual_holes = []
    for point_mm in rear["hole_centers_mesh_mm"]:
        point_m = [point_mm[index] * scale[index] for index in range(3)]
        rotated = _matvec(mesh_to_parent, point_m)
        actual_holes.append(
            [rotated[index] + mount_translation[index] for index in range(3)]
        )

    for actual, expected in zip(
        actual_holes, target["hole_centers_parent_m"], strict=True
    ):
        assert max(abs(a - e) for a, e in zip(actual, expected, strict=True)) < 1e-12

    hole_axis = [
        actual_holes[1][index] - actual_holes[0][index] for index in range(3)
    ]
    assert abs(hole_axis[0]) < 1e-12
    assert abs(hole_axis[1] - 0.02) < 1e-12
    assert abs(hole_axis[2]) < 1e-12

    actual_back_normal = _matvec(
        mesh_to_parent, rear["outward_normal_mesh"]
    )
    bracket_down_normal = target["downward_outward_normal_parent"]
    assert max(
        abs(actual_back_normal[index] + bracket_down_normal[index])
        for index in range(3)
    ) < 1e-12


def test_control_and_isaac_urdfs_share_d405_mount_and_frame_tree() -> None:
    config = _config()
    expected_xyz = config["mount_offset_xyz_m"]
    expected_rpy = [math.radians(value) for value in config["mount_rpy_deg"]]

    for filename in ("A1Z_G1Z_control.urdf", "A1Z_G1Z_isaac.urdf"):
        root = ET.parse(ROBOT_URDF_DIR / filename).getroot()
        mount = root.find("./joint[@name='d405_mount_joint']")
        rectified = root.find("./joint[@name='d405_rectified_joint']")
        assert mount is not None
        assert rectified is not None
        assert mount.get("type") == "fixed"
        assert mount.find("parent").get("link") == config["parent_link"]
        assert mount.find("child").get("link") == "d405_link"
        assert rectified.find("parent").get("link") == "d405_link"
        assert rectified.find("child").get("link") == "d405_rectified_link"

        actual_xyz = [float(value) for value in mount.find("origin").get("xyz").split()]
        actual_rpy = [float(value) for value in mount.find("origin").get("rpy").split()]
        assert max(abs(a - e) for a, e in zip(actual_xyz, expected_xyz, strict=True)) < 1e-12
        assert max(abs(a - e) for a, e in zip(actual_rpy, expected_rpy, strict=True)) < 1e-12


def test_generated_urdfs_preserve_expected_g1z_inertials_and_d405_mass() -> None:
    config = _config()
    assert config["mass_kg"] == 0.072

    official = ET.parse(
        ROOT
        / "vendor"
        / "GALAXEA-A1Z"
        / "a1z"
        / "robot_models"
        / "a1z"
        / "A1Z_G1Z.urdf"
    ).getroot()
    official_links = {
        link.get("name"): link
        for link in official.findall("link")
    }
    dynamic_links = (
        "arm_link3",
        "arm_link4",
        "arm_link5",
        "gripper_finger_left_link",
        "gripper_finger_rIght_link",
    )
    expected_link6 = _cad_inertial_signature("arm_link6")
    _assert_physically_realizable_inertia(expected_link6)

    for filename in ("A1Z_G1Z_control.urdf", "A1Z_G1Z_isaac.urdf"):
        generated = ET.parse(ROBOT_URDF_DIR / filename).getroot()
        generated_links = {
            link.get("name"): link
            for link in generated.findall("link")
        }
        for link_name in dynamic_links:
            expected = official_links[link_name].find("inertial")
            actual = generated_links[link_name].find("inertial")
            assert _inertial_signature(actual) == _inertial_signature(expected)

        actual_link6 = _numeric_inertial_signature(
            generated_links["arm_link6"].find("inertial")
        )
        assert actual_link6 == expected_link6
        _assert_physically_realizable_inertia(actual_link6)

        d405_mass = generated.find("./link[@name='d405_link']/inertial/mass")
        assert d405_mass is not None
        assert float(d405_mass.get("value")) == config["mass_kg"]


def test_sim_profile_does_not_override_official_gripper_inertials() -> None:
    assignments = {
        line.split("=", 1)[0].strip()
        for line in (ROOT / "config" / "sim.env").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    assert "A1Z_GRIPPER_FINGER_MASS_KG" not in assignments


def test_d405_pose_values_have_one_project_source(monkeypatch) -> None:
    config = _config()
    project_sources = [
        ROOT / "config" / "sim.env",
        ROOT / "config" / "real.env",
        ROOT / "scripts" / "prepare_a1z_urdfs.py",
        ROOT / "scripts" / "a1z_isaac_python_in_container.sh",
        ROOT / "scripts" / "a1z_sdk_python_in_container.sh",
        ROOT / "scripts" / "start_a1z_webrtc_streaming_host.sh",
        ROOT / "scripts" / "run_a1z_ros2_stack_in_container.sh",
    ]
    for path in project_sources:
        text = path.read_text(encoding="utf-8")
        for key in REMOVED_POSE_ENV_KEYS:
            assert key not in text

    for key in REMOVED_POSE_ENV_KEYS:
        monkeypatch.setenv(key, "999,999,999")
    asset = D405AssetSettings.from_env()
    compute = D405ComputeSettings.from_env()
    assert asset.body_visual_rpy_deg == tuple(config["body_visual_rpy_deg"])
    assert asset.rectify_rpy_deg == tuple(config["stage_frames"]["rectify_rpy_deg"])
    assert asset.rectified_to_optical_rpy_deg == tuple(
        config["stage_frames"]["rectified_to_optical_rpy_deg"]
    )
    assert compute.install_rpy_deg == tuple(config["compute_frames"]["install_rpy_deg"])


def test_runtime_camera_frames_follow_imported_d405_link() -> None:
    asset_source = (
        ROOT / "a1z_ext" / "runtime" / "d405" / "asset.py"
    ).read_text(encoding="utf-8")
    pose_source = (
        ROOT / "a1z_ext" / "runtime" / "d405" / "pose.py"
    ).read_text(encoding="utf-8")

    assert 'child_name="d405_link"' in asset_source
    assert "Use the imported robot model's d405_link as the only D405 prim." in asset_source
    assert "D405_RECTIFIED_FRAME_NAME = \"RectifiedFrame\"" in asset_source
    assert "D405_DEPTH_OPTICAL_FRAME_NAME = \"DepthOpticalFrame\"" in asset_source
    assert "D405_COLOR_OPTICAL_FRAME_NAME = \"ColorOpticalFrame\"" in asset_source
    assert "live imported stage already carries the authoritative" in pose_source
