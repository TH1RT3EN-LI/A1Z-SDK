#!/usr/bin/env python3

"""Render an EconomicGrasp candidate and derived end-effector pose on RGB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = REPO_ROOT / "vendor" / "GALAXEA-A1Z"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from a1z_ext.grasping.contact_graspnet_adapter import _invert_transform, _normalize, _rigidize_transform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render EconomicGrasp overlay on RGB.")
    parser.add_argument("--rgb", required=True, help="Path to RGB .npy array")
    parser.add_argument("--intrinsics", required=True, help="Path to intrinsics.json")
    parser.add_argument("--candidates-json", required=True, help="Path to EconomicGrasp grasp_candidates.json")
    parser.add_argument("--candidate-rank", type=int, default=0, help="Rank in candidates-json to render")
    parser.add_argument("--output", required=True, help="Output image path (.bmp)")
    parser.add_argument("--output-json", default="", help="Optional debug metadata JSON path")
    parser.add_argument("--axis-length-m", type=float, default=0.04)
    parser.add_argument("--jaw-depth-scale", type=float, default=1.0)
    parser.add_argument("--ee-grasp-origin-xyz-m", default="[0.0727, 0.0, 0.0]")
    parser.add_argument("--ee-opening-axis-xyz", default="[0.0, 1.0, 0.0]")
    parser.add_argument("--ee-approach-axis-xyz", default="[1.0, 0.0, 0.0]")
    return parser


def _parse_json_vector(raw: str, *, expected_len: int) -> np.ndarray:
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) != expected_len:
        raise ValueError(f"expected JSON list of length {expected_len}: {raw}")
    return np.asarray([float(item) for item in value], dtype=np.float64)


def _load_rgb(path: str | Path) -> np.ndarray:
    rgb = np.load(Path(path)).astype(np.uint8, copy=False)
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError(f"rgb must have shape (H, W, >=3), got {rgb.shape}")
    return np.ascontiguousarray(rgb[:, :, :3])


def _project_point(point_xyz: np.ndarray, intrinsics: dict[str, float]) -> tuple[int, int] | None:
    x, y, z = [float(v) for v in point_xyz.reshape(3)]
    if z <= 1e-6 or not np.isfinite(z):
        return None
    fx = float(intrinsics["fx"])
    fy = float(intrinsics["fy"])
    cx = float(intrinsics["cx"])
    cy = float(intrinsics["cy"])
    u = fx * x / z + cx
    v = fy * y / z + cy
    if not np.isfinite(u) or not np.isfinite(v):
        return None
    return int(round(u)), int(round(v))


def _set_pixel(image: np.ndarray, x: int, y: int, color: tuple[int, int, int]) -> None:
    height, width = image.shape[:2]
    if 0 <= x < width and 0 <= y < height:
        image[y, x, 0] = color[0]
        image[y, x, 1] = color[1]
        image[y, x, 2] = color[2]


def _draw_disc(image: np.ndarray, center_xy: tuple[int, int], radius_px: int, color: tuple[int, int, int]) -> None:
    cx, cy = center_xy
    radius_sq = int(radius_px) * int(radius_px)
    for dy in range(-radius_px, radius_px + 1):
        for dx in range(-radius_px, radius_px + 1):
            if dx * dx + dy * dy <= radius_sq:
                _set_pixel(image, cx + dx, cy + dy, color)


def _draw_line(
    image: np.ndarray,
    start_xy: tuple[int, int],
    end_xy: tuple[int, int],
    color: tuple[int, int, int],
    *,
    thickness: int = 1,
) -> None:
    x0, y0 = start_xy
    x1, y1 = end_xy
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _draw_disc(image, (x0, y0), max(0, thickness - 1), color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _write_bmp(path: str | Path, rgb: np.ndarray) -> None:
    image = np.asarray(rgb, dtype=np.uint8)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"expected RGB uint8 image, got {image.shape}")
    height, width = image.shape[:2]
    row_stride = width * 3
    row_padding = (4 - (row_stride % 4)) % 4
    pixel_bytes = bytearray()
    for row in image[::-1]:
        bgr = row[:, ::-1].tobytes()
        pixel_bytes.extend(bgr)
        pixel_bytes.extend(b"\x00" * row_padding)
    file_size = 14 + 40 + len(pixel_bytes)
    header = bytearray()
    header.extend(b"BM")
    header.extend(int(file_size).to_bytes(4, "little"))
    header.extend((0).to_bytes(2, "little"))
    header.extend((0).to_bytes(2, "little"))
    header.extend((54).to_bytes(4, "little"))
    header.extend((40).to_bytes(4, "little"))
    header.extend(int(width).to_bytes(4, "little", signed=True))
    header.extend(int(height).to_bytes(4, "little", signed=True))
    header.extend((1).to_bytes(2, "little"))
    header.extend((24).to_bytes(2, "little"))
    header.extend((0).to_bytes(4, "little"))
    header.extend(len(pixel_bytes).to_bytes(4, "little"))
    header.extend((2835).to_bytes(4, "little"))
    header.extend((2835).to_bytes(4, "little"))
    header.extend((0).to_bytes(4, "little"))
    header.extend((0).to_bytes(4, "little"))
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(header) + bytes(pixel_bytes))


def _ee_to_grasp_transform(
    *,
    ee_grasp_origin_xyz_m: np.ndarray,
    ee_opening_axis_xyz: np.ndarray,
    ee_approach_axis_xyz: np.ndarray,
) -> np.ndarray:
    opening = _normalize(ee_opening_axis_xyz)
    approach = ee_approach_axis_xyz - float(np.dot(ee_approach_axis_xyz, opening)) * opening
    approach = _normalize(approach)
    binormal = _normalize(np.cross(approach, opening))
    approach = _normalize(np.cross(opening, binormal))
    transform = np.eye(4, dtype=np.float64)
    transform[:3, 0] = opening
    transform[:3, 1] = binormal
    transform[:3, 2] = approach
    transform[:3, 3] = ee_grasp_origin_xyz_m
    return transform


def _candidate_to_grasp_pose(candidate: dict[str, Any]) -> np.ndarray:
    opening = _normalize(np.asarray(candidate["opening_axis_xyz"], dtype=np.float64).reshape(3))
    approach = np.asarray(candidate["approach_axis_xyz"], dtype=np.float64).reshape(3)
    approach = approach - float(np.dot(approach, opening)) * opening
    approach = _normalize(approach)
    height = np.asarray(candidate["height_axis_xyz"], dtype=np.float64).reshape(3)
    height = height - float(np.dot(height, opening)) * opening - float(np.dot(height, approach)) * approach
    if float(np.linalg.norm(height)) <= 1e-9:
        height = _normalize(np.cross(approach, opening))
    else:
        height = _normalize(height)
    approach = _normalize(np.cross(opening, height))
    grasp = np.eye(4, dtype=np.float64)
    grasp[:3, 0] = opening
    grasp[:3, 1] = height
    grasp[:3, 2] = approach
    grasp[:3, 3] = np.asarray(candidate["center_xyz_m"], dtype=np.float64).reshape(3)
    return _rigidize_transform(grasp)


def _collect_projected_points(
    *,
    intrinsics: dict[str, float],
    grasp_pose_cam: np.ndarray,
    tool_pose_cam: np.ndarray,
    width_m: float,
    depth_m: float,
    axis_length_m: float,
    jaw_depth_scale: float,
) -> dict[str, Any]:
    grasp_origin = grasp_pose_cam[:3, 3]
    opening_dir = _normalize(grasp_pose_cam[:3, 0])
    height_dir = _normalize(grasp_pose_cam[:3, 1])
    approach_dir = _normalize(grasp_pose_cam[:3, 2])
    tool_origin = tool_pose_cam[:3, 3]

    jaw_depth = max(0.0, float(depth_m) * float(jaw_depth_scale))
    left_tip = grasp_origin + opening_dir * (0.5 * float(width_m))
    right_tip = grasp_origin - opening_dir * (0.5 * float(width_m))
    left_back = left_tip - approach_dir * jaw_depth
    right_back = right_tip - approach_dir * jaw_depth

    points_3d = {
        "grasp_origin": grasp_origin,
        "tool_origin": tool_origin,
        "jaw_left_tip": left_tip,
        "jaw_right_tip": right_tip,
        "jaw_left_back": left_back,
        "jaw_right_back": right_back,
        "grasp_axis_opening": grasp_origin + opening_dir * float(axis_length_m),
        "grasp_axis_height": grasp_origin + height_dir * float(axis_length_m),
        "grasp_axis_approach": grasp_origin + approach_dir * float(axis_length_m),
        "tool_axis_x": tool_origin + tool_pose_cam[:3, 0] * float(axis_length_m),
        "tool_axis_y": tool_origin + tool_pose_cam[:3, 1] * float(axis_length_m),
        "tool_axis_z": tool_origin + tool_pose_cam[:3, 2] * float(axis_length_m),
    }
    projected = {
        name: _project_point(point, intrinsics)
        for name, point in points_3d.items()
    }
    return {
        "points_3d": {name: point.astype(float).tolist() for name, point in points_3d.items()},
        "points_px": {name: (None if point is None else [int(point[0]), int(point[1])]) for name, point in projected.items()},
    }


def _draw_overlay(image: np.ndarray, projected: dict[str, Any]) -> np.ndarray:
    overlay = image.copy()
    px = projected["points_px"]

    def line(a: str, b: str, color: tuple[int, int, int], thickness: int = 2) -> None:
        pa = px.get(a)
        pb = px.get(b)
        if pa is None or pb is None:
            return
        _draw_line(overlay, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), color, thickness=thickness)

    def dot(name: str, color: tuple[int, int, int], radius: int = 4) -> None:
        point = px.get(name)
        if point is None:
            return
        _draw_disc(overlay, (int(point[0]), int(point[1])), radius, color)

    line("jaw_left_tip", "jaw_right_tip", (255, 255, 0), thickness=2)
    line("jaw_left_tip", "jaw_left_back", (255, 200, 0), thickness=2)
    line("jaw_right_tip", "jaw_right_back", (255, 200, 0), thickness=2)
    line("jaw_left_back", "jaw_right_back", (255, 170, 0), thickness=2)
    line("tool_origin", "grasp_origin", (255, 255, 255), thickness=1)

    line("grasp_origin", "grasp_axis_opening", (255, 0, 0), thickness=2)
    line("grasp_origin", "grasp_axis_height", (0, 255, 0), thickness=2)
    line("grasp_origin", "grasp_axis_approach", (0, 128, 255), thickness=2)

    line("tool_origin", "tool_axis_x", (255, 0, 255), thickness=2)
    line("tool_origin", "tool_axis_y", (0, 255, 255), thickness=2)
    line("tool_origin", "tool_axis_z", (255, 255, 255), thickness=2)

    dot("grasp_origin", (255, 255, 0), radius=5)
    dot("tool_origin", (255, 0, 255), radius=5)
    dot("jaw_left_tip", (255, 255, 0), radius=3)
    dot("jaw_right_tip", (255, 255, 0), radius=3)
    return overlay


def main() -> int:
    args = build_parser().parse_args()
    rgb = _load_rgb(args.rgb)
    intrinsics = json.loads(Path(args.intrinsics).read_text(encoding="utf-8"))
    candidates = json.loads(Path(args.candidates_json).read_text(encoding="utf-8"))
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates-json must contain a non-empty list")
    if args.candidate_rank < 0 or args.candidate_rank >= len(candidates):
        raise ValueError(f"candidate-rank out of range: {args.candidate_rank}")

    candidate = dict(candidates[int(args.candidate_rank)])
    grasp_pose_cam = _candidate_to_grasp_pose(candidate)
    ee_to_grasp = _ee_to_grasp_transform(
        ee_grasp_origin_xyz_m=_parse_json_vector(args.ee_grasp_origin_xyz_m, expected_len=3),
        ee_opening_axis_xyz=_parse_json_vector(args.ee_opening_axis_xyz, expected_len=3),
        ee_approach_axis_xyz=_parse_json_vector(args.ee_approach_axis_xyz, expected_len=3),
    )
    tool_pose_cam = _rigidize_transform(grasp_pose_cam @ _invert_transform(ee_to_grasp))
    projected = _collect_projected_points(
        intrinsics=intrinsics,
        grasp_pose_cam=grasp_pose_cam,
        tool_pose_cam=tool_pose_cam,
        width_m=float(candidate["width_m"]),
        depth_m=float(candidate["depth_m"]),
        axis_length_m=float(args.axis_length_m),
        jaw_depth_scale=float(args.jaw_depth_scale),
    )
    overlay = _draw_overlay(rgb, projected)
    _write_bmp(args.output, overlay)

    payload = {
        "rgb_path": str(Path(args.rgb).resolve()),
        "intrinsics_path": str(Path(args.intrinsics).resolve()),
        "candidates_json_path": str(Path(args.candidates_json).resolve()),
        "candidate_rank": int(args.candidate_rank),
        "candidate_score": float(candidate["score"]),
        "candidate_width_m": float(candidate["width_m"]),
        "candidate_depth_m": float(candidate["depth_m"]),
        "grasp_pose_cam": grasp_pose_cam.astype(float).tolist(),
        "tool_pose_cam": tool_pose_cam.astype(float).tolist(),
        "projected": projected,
        "output_path": str(Path(args.output).resolve()),
    }
    if args.output_json:
        output_json_path = Path(args.output_json).resolve()
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
