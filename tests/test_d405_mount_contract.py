from __future__ import annotations

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
