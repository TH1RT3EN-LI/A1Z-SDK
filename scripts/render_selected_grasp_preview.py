#!/usr/bin/env python3
"""Render the selected object cloud and gripper 6-DoF pose in the base frame."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


CANVAS_SIZE = (1400, 900)
BACKGROUND = np.asarray([12, 18, 28], dtype=np.uint8)
PANEL_BACKGROUND = np.asarray([20, 29, 43], dtype=np.uint8)
AXIS_COLORS = {
    "x": (255, 82, 82),
    "y": (72, 218, 132),
    "z": (77, 151, 255),
}
GRIPPER_COLOR = (255, 194, 72)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", required=True, help="Selected object points.npy in camera frame")
    parser.add_argument("--colors", required=True, help="Selected object colors.npy")
    parser.add_argument("--extrinsic-camera-to-base", required=True)
    parser.add_argument("--planner-result", required=True)
    parser.add_argument("--selected-plan", required=True)
    parser.add_argument("--output-png", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--max-points", type=int, default=50000)
    return parser


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _axis_vector(label: str) -> np.ndarray:
    sign = -1.0 if label.startswith("-") else 1.0
    axis_name = label[-1:].lower()
    if axis_name not in {"x", "y", "z"}:
        raise ValueError(f"invalid correction axis: {label}")
    result = np.zeros(3, dtype=np.float64)
    result[{"x": 0, "y": 1, "z": 2}[axis_name]] = sign
    return result


def _correction_transform(label: str) -> np.ndarray:
    transform = np.eye(4, dtype=np.float64)
    if not label or label == "identity":
        return transform
    assignments: dict[str, np.ndarray] = {}
    for item in label.split(","):
        name, separator, value = item.strip().partition("=")
        if not separator or name not in {"x", "y", "z"}:
            raise ValueError(f"invalid camera correction label: {label}")
        assignments[name] = _axis_vector(value)
    if set(assignments) != {"x", "y", "z"}:
        raise ValueError(f"incomplete camera correction label: {label}")
    rotation = np.column_stack(
        [assignments["x"], assignments["y"], assignments["z"]]
    )
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8):
        raise ValueError(f"non-orthogonal camera correction label: {label}")
    if float(np.linalg.det(rotation)) < 0.999:
        raise ValueError(f"left-handed camera correction label: {label}")
    transform[:3, :3] = rotation
    return transform


def _selected_grasp(
    planner_result: dict[str, Any],
    selected_plan: dict[str, Any],
) -> dict[str, Any]:
    candidate_id = str(selected_plan.get("selected_grasp_candidate_id", ""))
    candidates = planner_result.get("candidates")
    if isinstance(candidates, list):
        candidate = next(
            (
                item
                for item in candidates
                if isinstance(item, dict)
                and str(item.get("candidate_id", "")) == candidate_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError(f"selected candidate {candidate_id!r} is absent from planner result")
        summary = planner_result.get("summary", {})
        summary = summary if isinstance(summary, dict) else {}
        metadata = candidate.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        return {
            "candidate_id": candidate_id,
            "rank": int(candidate.get("rank", selected_plan.get("candidate_rank", 0))),
            "score": float(candidate.get("raw_score", candidate.get("overall_score", 0.0))),
            "overall_score": float(candidate.get("overall_score", 0.0)),
            "opening_m": float(candidate.get("gripper_opening_m", 0.0)),
            "open_command": float(candidate.get("gripper_command_open", 0.0)),
            "close_command": float(candidate.get("gripper_command_close", 0.0)),
            "pose_matrix": candidate.get("tool_grasp_pose_matrix"),
            "quaternion_xyzw": dict(candidate.get("grasp_pose", {}) or {}).get(
                "quaternion_xyzw", []
            ),
            "front_extent_m": float(metadata.get("tool_front_extent_m", 0.1032)),
            "camera_correction_label": str(
                summary.get("active_camera_correction_label", "identity")
            ),
            "extrinsic_correction_label": str(
                summary.get("active_extrinsic_correction_label", "identity")
            ),
        }

    # The direct-best planner stores one selected grasp directly at the top level.
    metadata = planner_result.get("metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    pose_summary = planner_result.get("pose_summary", {})
    pose_summary = pose_summary if isinstance(pose_summary, dict) else {}
    tool_pose = pose_summary.get("tool_grasp_pose", {})
    tool_pose = tool_pose if isinstance(tool_pose, dict) else {}
    return {
        "candidate_id": candidate_id,
        "rank": int(planner_result.get("selected_rank", selected_plan.get("candidate_rank", 0))),
        "score": float(planner_result.get("raw_score", 0.0)),
        "overall_score": float(planner_result.get("raw_score", 0.0)),
        "opening_m": float(planner_result.get("width_m", 0.0)),
        "open_command": float(
            dict(selected_plan.get("gripper_commands", {}) or {}).get(
                "open_before_grasp", 0.0
            )
        ),
        "close_command": float(
            dict(selected_plan.get("gripper_commands", {}) or {}).get(
                "close_after_approach", 0.0
            )
        ),
        "pose_matrix": planner_result.get("tool_grasp_pose_matrix"),
        "quaternion_xyzw": tool_pose.get("quaternion_xyzw", []),
        "front_extent_m": float(metadata.get("tool_front_extent_m", 0.1032)),
        "camera_correction_label": str(
            planner_result.get("active_camera_correction_label", "identity")
        ),
        "extrinsic_correction_label": str(
            planner_result.get("active_extrinsic_correction_label", "identity")
        ),
    }


def _rotation_to_rpy_deg(rotation: np.ndarray) -> list[float]:
    # R = Rz(yaw) * Ry(pitch) * Rx(roll).
    sy = math.hypot(float(rotation[0, 0]), float(rotation[1, 0]))
    if sy > 1e-9:
        roll = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        pitch = math.atan2(-float(rotation[2, 0]), sy)
        yaw = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    else:
        roll = math.atan2(-float(rotation[1, 2]), float(rotation[1, 1]))
        pitch = math.atan2(-float(rotation[2, 0]), sy)
        yaw = 0.0
    return [math.degrees(value) for value in (roll, pitch, yaw)]


def _rotation_to_quaternion_xyzw(rotation: np.ndarray) -> list[float]:
    trace = float(np.trace(rotation))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * scale
        qx = (float(rotation[2, 1]) - float(rotation[1, 2])) / scale
        qy = (float(rotation[0, 2]) - float(rotation[2, 0])) / scale
        qz = (float(rotation[1, 0]) - float(rotation[0, 1])) / scale
    else:
        diagonal = np.diag(rotation)
        index = int(np.argmax(diagonal))
        if index == 0:
            scale = math.sqrt(1.0 + float(rotation[0, 0]) - float(rotation[1, 1]) - float(rotation[2, 2])) * 2.0
            qw = (float(rotation[2, 1]) - float(rotation[1, 2])) / scale
            qx = 0.25 * scale
            qy = (float(rotation[0, 1]) + float(rotation[1, 0])) / scale
            qz = (float(rotation[0, 2]) + float(rotation[2, 0])) / scale
        elif index == 1:
            scale = math.sqrt(1.0 + float(rotation[1, 1]) - float(rotation[0, 0]) - float(rotation[2, 2])) * 2.0
            qw = (float(rotation[0, 2]) - float(rotation[2, 0])) / scale
            qx = (float(rotation[0, 1]) + float(rotation[1, 0])) / scale
            qy = 0.25 * scale
            qz = (float(rotation[1, 2]) + float(rotation[2, 1])) / scale
        else:
            scale = math.sqrt(1.0 + float(rotation[2, 2]) - float(rotation[0, 0]) - float(rotation[1, 1])) * 2.0
            qw = (float(rotation[1, 0]) - float(rotation[0, 1])) / scale
            qx = (float(rotation[0, 2]) + float(rotation[2, 0])) / scale
            qy = (float(rotation[1, 2]) + float(rotation[2, 1])) / scale
            qz = 0.25 * scale
    quaternion = np.asarray([qx, qy, qz, qw], dtype=np.float64)
    quaternion /= np.linalg.norm(quaternion)
    return quaternion.astype(float).tolist()


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


def _geometry_points(pose: np.ndarray, opening_m: float, front_extent_m: float) -> tuple[np.ndarray, list[tuple[np.ndarray, np.ndarray, tuple[int, int, int], int]]]:
    origin = pose[:3, 3]
    x_axis, y_axis, z_axis = (pose[:3, index] for index in range(3))
    axis_length = max(0.055, min(0.085, float(front_extent_m) * 0.7))
    half_opening = max(0.006, float(opening_m) * 0.5)
    front = origin + x_axis * float(front_extent_m)
    jaw_a = y_axis * half_opening
    palm_half = y_axis * (half_opening + 0.012)
    segments = [
        (origin, origin + x_axis * axis_length, AXIS_COLORS["x"], 5),
        (origin, origin + y_axis * axis_length, AXIS_COLORS["y"], 5),
        (origin, origin + z_axis * axis_length, AXIS_COLORS["z"], 5),
        (origin - palm_half, origin + palm_half, GRIPPER_COLOR, 6),
        (origin - jaw_a, front - jaw_a, GRIPPER_COLOR, 6),
        (origin + jaw_a, front + jaw_a, GRIPPER_COLOR, 6),
        (front - jaw_a, front - jaw_a + z_axis * 0.018, GRIPPER_COLOR, 5),
        (front + jaw_a, front + jaw_a + z_axis * 0.018, GRIPPER_COLOR, 5),
    ]
    points = np.vstack([np.vstack((start, end)) for start, end, _, _ in segments])
    return points, segments


def _project_panel(
    canvas: np.ndarray,
    cloud: np.ndarray,
    colors: np.ndarray,
    geometry: np.ndarray,
    segments: list[tuple[np.ndarray, np.ndarray, tuple[int, int, int], int]],
    bounds: tuple[int, int, int, int],
    u_axis: np.ndarray,
    v_axis: np.ndarray,
) -> list[tuple[tuple[int, int], tuple[int, int], tuple[int, int, int], int]]:
    x0, y0, x1, y1 = bounds
    canvas[y0:y1, x0:x1] = PANEL_BACKGROUND
    u_axis = u_axis / np.linalg.norm(u_axis)
    v_axis = v_axis / np.linalg.norm(v_axis)
    combined = np.vstack((cloud, geometry))
    projected = np.column_stack((combined @ u_axis, combined @ v_axis))
    low = projected.min(axis=0)
    high = projected.max(axis=0)
    span = np.maximum(high - low, 1e-4)
    padding = 30.0
    scale = min(
        (x1 - x0 - 2.0 * padding) / float(span[0]),
        (y1 - y0 - 2.0 * padding) / float(span[1]),
    )
    center_world = (low + high) * 0.5
    center_pixel = np.asarray([(x0 + x1) * 0.5, (y0 + y1) * 0.5])

    def pixels(points: np.ndarray) -> np.ndarray:
        uv = np.column_stack((points @ u_axis, points @ v_axis))
        result = (uv - center_world) * scale + center_pixel
        result[:, 1] = 2.0 * center_pixel[1] - result[:, 1]
        return np.rint(result).astype(np.int32)

    cloud_pixels = pixels(cloud)
    valid = (
        (cloud_pixels[:, 0] >= x0 + 1)
        & (cloud_pixels[:, 0] < x1 - 1)
        & (cloud_pixels[:, 1] >= y0 + 1)
        & (cloud_pixels[:, 1] < y1 - 1)
    )
    px = cloud_pixels[valid, 0]
    py = cloud_pixels[valid, 1]
    rgb = colors[valid]
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        canvas[py + dy, px + dx] = rgb

    projected_segments = []
    for start, end, color, width in segments:
        pair = pixels(np.vstack((start, end)))
        projected_segments.append(
            (
                (int(pair[0, 0]), int(pair[0, 1])),
                (int(pair[1, 0]), int(pair[1, 1])),
                color,
                width,
            )
        )
    return projected_segments


def render_preview(
    *,
    points_path: Path,
    colors_path: Path,
    extrinsic_path: Path,
    planner_result_path: Path,
    selected_plan_path: Path,
    output_png: Path,
    output_json: Path,
    max_points: int = 50000,
) -> dict[str, Any]:
    points_camera = np.asarray(np.load(points_path), dtype=np.float64).reshape(-1, 3)
    raw_colors = np.asarray(np.load(colors_path)).reshape(-1, 3)
    if points_camera.shape[0] != raw_colors.shape[0] or not points_camera.shape[0]:
        raise ValueError("selected object points and colors must have the same non-zero length")
    finite = np.all(np.isfinite(points_camera), axis=1)
    points_camera = points_camera[finite]
    raw_colors = raw_colors[finite]
    if not points_camera.shape[0]:
        raise ValueError("selected object point cloud contains no finite points")
    if points_camera.shape[0] > max(1, int(max_points)):
        indices = np.linspace(
            0,
            points_camera.shape[0] - 1,
            num=max(1, int(max_points)),
            dtype=np.int64,
        )
        points_camera = points_camera[indices]
        raw_colors = raw_colors[indices]
    if np.issubdtype(raw_colors.dtype, np.floating) and float(np.nanmax(raw_colors)) <= 1.0:
        raw_colors = raw_colors * 255.0
    colors = np.clip(raw_colors, 0.0, 255.0).astype(np.uint8)
    # Keep black/dark objects visible on the review panel without losing their hue.
    colors = np.maximum(colors, np.asarray([48, 48, 48], dtype=np.uint8))

    planner_result = _load_object(planner_result_path)
    selected_plan = _load_object(selected_plan_path)
    selected = _selected_grasp(planner_result, selected_plan)
    pose = np.asarray(selected.get("pose_matrix"), dtype=np.float64)
    if pose.shape != (4, 4) or not np.all(np.isfinite(pose)):
        raise ValueError("selected planner result has no finite 4x4 tool_grasp_pose_matrix")

    extrinsic = np.asarray(np.load(extrinsic_path), dtype=np.float64)
    if extrinsic.shape != (4, 4) or not np.all(np.isfinite(extrinsic)):
        raise ValueError("extrinsic_camera_to_base must be a finite 4x4 matrix")
    camera_to_base = (
        extrinsic
        @ _correction_transform(str(selected["extrinsic_correction_label"]))
        @ _correction_transform(str(selected["camera_correction_label"]))
    )
    points_h = np.column_stack((points_camera, np.ones(points_camera.shape[0])))
    points_base = (camera_to_base @ points_h.T).T[:, :3]

    geometry, segments = _geometry_points(
        pose,
        float(selected["opening_m"]),
        float(selected["front_extent_m"]),
    )
    canvas = np.empty((CANVAS_SIZE[1], CANVAS_SIZE[0], 3), dtype=np.uint8)
    canvas[:] = BACKGROUND
    panels = [
        (
            "ISOMETRIC / BASE",
            (26, 124, 688, 714),
            np.asarray([1.0, -1.0, 0.0]),
            np.asarray([-0.45, -0.45, 0.9]),
        ),
        (
            "TOP / BASE XY",
            (712, 124, 1374, 404),
            np.asarray([1.0, 0.0, 0.0]),
            np.asarray([0.0, 1.0, 0.0]),
        ),
        (
            "SIDE / BASE XZ",
            (712, 434, 1374, 714),
            np.asarray([1.0, 0.0, 0.0]),
            np.asarray([0.0, 0.0, 1.0]),
        ),
    ]
    projected_lines = []
    for label, bounds, u_axis, v_axis in panels:
        lines = _project_panel(
            canvas,
            points_base,
            colors,
            geometry,
            segments,
            bounds,
            u_axis,
            v_axis,
        )
        projected_lines.append((label, bounds, lines))

    image = Image.fromarray(canvas, mode="RGB")
    draw = ImageDraw.Draw(image)
    title_font = _font(28, bold=True)
    body_font = _font(19)
    label_font = _font(16, bold=True)
    small_font = _font(15)
    draw.text(
        (26, 24),
        "SELECTED OBJECT POINT CLOUD + GRIPPER 6-DOF",
        fill=(242, 246, 252),
        font=title_font,
    )
    draw.text(
        (27, 70),
        f"Candidate #{selected['rank']}  score {selected['score']:.4f}  frame {selected_plan.get('frame_id', 'base')}",
        fill=(164, 177, 197),
        font=body_font,
    )
    for label, bounds, lines in projected_lines:
        x0, y0, x1, y1 = bounds
        draw.rectangle((x0, y0, x1, y1), outline=(54, 72, 96), width=2)
        draw.rectangle((x0 + 12, y0 + 10, x0 + 188, y0 + 38), fill=(12, 18, 28))
        draw.text((x0 + 20, y0 + 15), label, fill=(204, 216, 232), font=label_font)
        for start, end, color, width in lines:
            draw.line((start, end), fill=color, width=width)
        origin = lines[0][0]
        draw.ellipse(
            (origin[0] - 6, origin[1] - 6, origin[0] + 6, origin[1] + 6),
            fill=(255, 255, 255),
            outline=(12, 18, 28),
            width=2,
        )

    rpy_deg = _rotation_to_rpy_deg(pose[:3, :3])
    xyz = pose[:3, 3].astype(float).tolist()
    draw.text(
        (28, 750),
        "BASE XYZ [m]   " + "   ".join(f"{axis} {value:+.4f}" for axis, value in zip("XYZ", xyz)),
        fill=(238, 242, 248),
        font=body_font,
    )
    draw.text(
        (28, 788),
        "BASE RPY [deg] " + "   ".join(f"{axis} {value:+.1f}" for axis, value in zip("RPY", rpy_deg)),
        fill=(238, 242, 248),
        font=body_font,
    )
    draw.text(
        (28, 832),
        f"Opening {float(selected['opening_m']) * 1000.0:.1f} mm   |   X approach   Y opening   Z tool-up",
        fill=(255, 194, 72),
        font=small_font,
    )
    legend_x = 820
    for index, (axis, color) in enumerate(AXIS_COLORS.items()):
        x = legend_x + index * 150
        draw.line((x, 790, x + 34, 790), fill=color, width=6)
        draw.text((x + 44, 780), f"Tool {axis.upper()}", fill=(210, 220, 234), font=small_font)
    draw.line((legend_x, 836, legend_x + 34, 836), fill=GRIPPER_COLOR, width=6)
    draw.text((legend_x + 44, 826), "Gripper jaws", fill=(210, 220, 234), font=small_font)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_png, format="PNG", optimize=True)

    quaternion = selected.get("quaternion_xyzw", [])
    if not isinstance(quaternion, list) or len(quaternion) != 4:
        quaternion = _rotation_to_quaternion_xyzw(pose[:3, :3])
    payload = {
        "schema_name": "SelectedGraspPreview",
        "schema_version": "v1",
        "candidate_id": str(selected["candidate_id"]),
        "candidate_rank": int(selected["rank"]),
        "score": float(selected["score"]),
        "overall_score": float(selected["overall_score"]),
        "frame_id": str(selected_plan.get("frame_id", "")),
        "point_cloud": {
            "source_frame": "camera",
            "display_frame": str(selected_plan.get("frame_id", "base")),
            "source_point_count": int(np.count_nonzero(finite)),
            "rendered_point_count": int(points_base.shape[0]),
            "points_path": str(points_path.resolve()),
            "colors_path": str(colors_path.resolve()),
        },
        "gripper_pose_6dof": {
            "position_xyz_m": xyz,
            "rpy_deg": [float(value) for value in rpy_deg],
            "quaternion_xyzw": [float(value) for value in quaternion],
            "transform_matrix": pose.astype(float).tolist(),
            "axis_convention": {
                "x": "approach",
                "y": "opening",
                "z": "tool_up",
            },
        },
        "gripper": {
            "opening_m": float(selected["opening_m"]),
            "open_command": float(selected["open_command"]),
            "close_command": float(selected["close_command"]),
            "front_extent_m": float(selected["front_extent_m"]),
        },
        "camera_to_base_matrix": camera_to_base.astype(float).tolist(),
        "preview_png": str(output_png.resolve()),
    }
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    args = _build_parser().parse_args()
    payload = render_preview(
        points_path=Path(args.points).resolve(),
        colors_path=Path(args.colors).resolve(),
        extrinsic_path=Path(args.extrinsic_camera_to_base).resolve(),
        planner_result_path=Path(args.planner_result).resolve(),
        selected_plan_path=Path(args.selected_plan).resolve(),
        output_png=Path(args.output_png).resolve(),
        output_json=Path(args.output_json).resolve(),
        max_points=int(args.max_points),
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
