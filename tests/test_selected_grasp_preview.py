from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest


def test_selected_grasp_preview_writes_png_and_base_pose(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    from scripts.render_selected_grasp_preview import render_preview

    points = np.asarray(
        [
            [-0.03, -0.02, 0.30],
            [-0.03, 0.02, 0.30],
            [0.03, -0.02, 0.30],
            [0.03, 0.02, 0.30],
            [0.0, 0.0, 0.36],
        ],
        dtype=np.float32,
    )
    colors = np.asarray(
        [[220, 220, 220], [20, 20, 20], [200, 80, 40], [40, 100, 220], [80, 220, 120]],
        dtype=np.uint8,
    )
    points_path = tmp_path / "points.npy"
    colors_path = tmp_path / "colors.npy"
    extrinsic_path = tmp_path / "extrinsic.npy"
    np.save(points_path, points)
    np.save(colors_path, colors)
    np.save(extrinsic_path, np.eye(4, dtype=np.float64))

    pose = np.eye(4, dtype=np.float64)
    pose[:3, 3] = [0.40, -0.05, 0.20]
    planner_result_path = tmp_path / "anygrasp_adapter_result.json"
    planner_result_path.write_text(
        json.dumps(
            {
                "summary": {
                    "active_camera_correction_label": "identity",
                    "active_extrinsic_correction_label": "identity",
                },
                "candidates": [
                    {
                        "candidate_id": "candidate-1",
                        "rank": 2,
                        "raw_score": 0.75,
                        "overall_score": 0.70,
                        "gripper_opening_m": 0.04,
                        "gripper_command_open": 0.5,
                        "gripper_command_close": 0.0,
                        "grasp_pose": {
                            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]
                        },
                        "tool_grasp_pose_matrix": pose.tolist(),
                        "metadata": {"tool_front_extent_m": 0.10},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    selected_plan_path = tmp_path / "selected_plan.json"
    selected_plan_path.write_text(
        json.dumps(
            {
                "selected_grasp_candidate_id": "candidate-1",
                "candidate_rank": 2,
                "frame_id": "base_link",
            }
        ),
        encoding="utf-8",
    )

    output_png = tmp_path / "selected_grasp_point_cloud.png"
    output_json = tmp_path / "selected_grasp_preview.json"
    payload = render_preview(
        points_path=points_path,
        colors_path=colors_path,
        extrinsic_path=extrinsic_path,
        planner_result_path=planner_result_path,
        selected_plan_path=selected_plan_path,
        output_png=output_png,
        output_json=output_json,
    )

    assert output_png.is_file()
    assert Image.open(output_png).size == (1400, 900)
    assert output_json.is_file()
    assert payload["candidate_id"] == "candidate-1"
    assert payload["point_cloud"]["rendered_point_count"] == 5
    assert payload["gripper_pose_6dof"]["position_xyz_m"] == [0.4, -0.05, 0.2]
    assert payload["gripper_pose_6dof"]["rpy_deg"] == pytest.approx([0.0, 0.0, 0.0])
