#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.config import get_socket_path, get_tcp_host, get_tcp_port
from a1z_ext.control_client import send_control_request


SEMANTIC_ID_TO_PRIM_NAMES = {
    "can_crushed": ("can_crushed", "pudding_box"),
    "marker_upright": ("marker_upright", "large_marker"),
    "bottle_plastic": ("bottle_plastic", "cracker_box"),
    "bottle_water": ("bottle_water", "sugar_box"),
    "paper_debris": ("paper_debris", "gelatin_box"),
}

DEFAULT_CANDIDATE_IDS = tuple(SEMANTIC_ID_TO_PRIM_NAMES)
DEFAULT_BASE_LINK_PRIM_CANDIDATES = (
    "/World/A1Z_G1Z/Geometry/base_link",
    "/DOG/A1Z_PAYLOAD_MOUNT/A1Z_G1Z/Geometry/base_link",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve the live TrashSet prim path for the selected mask.")
    parser.add_argument("--selection-json", required=True)
    parser.add_argument("--depth-npy", required=True)
    parser.add_argument("--intrinsics-json", required=True)
    parser.add_argument("--extrinsic-camera-to-base", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--trash-root", default="/World/TrashSet")
    parser.add_argument(
        "--base-link-prim",
        default="",
        help="Optional explicit base_link prim. Defaults to discovery from the live articulation root.",
    )
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--tcp-host", default=get_tcp_host())
    parser.add_argument("--tcp-port", type=int, default=get_tcp_port())
    return parser


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _as_matrix(payload: dict[str, Any], *, field: str, label: str) -> np.ndarray:
    value = payload.get(field)
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (4, 4):
        raise ValueError(f"{label} missing valid {field}: {payload}")
    return matrix


def _rotation_translation_from_row_major_world_matrix(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(matrix, dtype=np.float64).reshape(4, 4)
    rotation = matrix[:3, :3]
    translation = matrix[3, :3]
    return rotation, translation


def _camera_point_from_mask(
    *,
    selection_payload: dict[str, Any],
    depth_m: np.ndarray,
    intrinsics_payload: dict[str, Any],
) -> dict[str, Any]:
    selected_mask = selection_payload.get("selected_mask") or {}
    mask_path = str(selected_mask.get("mask_npy_path") or "")
    if not mask_path:
        raise ValueError("selection json missing selected_mask.mask_npy_path")
    mask = np.load(mask_path).astype(bool)
    if mask.shape != depth_m.shape:
        raise ValueError(f"mask/depth shape mismatch: {mask.shape} vs {depth_m.shape}")
    valid = mask & np.isfinite(depth_m) & (depth_m > 0.0)
    ys, xs = np.nonzero(valid)
    if xs.size == 0:
        raise RuntimeError("selected mask has no valid depth samples")

    center_x = float(np.median(xs))
    center_y = float(np.median(ys))
    depth_value = float(np.median(depth_m[valid]))
    fx = float(intrinsics_payload["intrinsics"]["fx"])
    fy = float(intrinsics_payload["intrinsics"]["fy"])
    cx = float(intrinsics_payload["intrinsics"]["cx"])
    cy = float(intrinsics_payload["intrinsics"]["cy"])
    point_camera = np.asarray(
        [
            (center_x - cx) * depth_value / fx,
            (center_y - cy) * depth_value / fy,
            depth_value,
            1.0,
        ],
        dtype=np.float64,
    )
    bbox_xywh = list((selected_mask.get("bbox_xywh") or [])[:4])
    return {
        "point_camera_h": point_camera,
        "mask_center_xy": [center_x, center_y],
        "bbox_xywh": bbox_xywh,
        "valid_depth_count": int(xs.size),
    }


def _semantic_hint(instruction: str) -> str:
    text = str(instruction or "")
    hints = (
        (("白板笔", "记号笔", "marker"), "marker_upright"),
        (("零食盒", "零食盒子", "饼干盒", "盒子", "snack", "pudding", "box"), "can_crushed"),
        (("塑料瓶", "高盒", "cracker"), "bottle_plastic"),
        (("糖盒", "水瓶", "sugar"), "bottle_water"),
        (("纸", "碎片", "gelatin"), "paper_debris"),
    )
    for keys, candidate_id in hints:
        if any(key in text for key in keys):
            return candidate_id
    return ""


def _semantic_score(label_text: str, hinted_id: str) -> float:
    text = str(label_text or "").lower()
    if not hinted_id:
        return 0.0
    lookup = {
        "marker_upright": ("marker", "白板笔", "large_marker", "040_"),
        "can_crushed": ("snack", "pudding", "零食", "盒", "008_"),
        "bottle_plastic": ("cracker", "plastic", "003_"),
        "bottle_water": ("sugar", "water", "004_"),
        "paper_debris": ("gelatin", "paper", "009_"),
    }
    keys = lookup.get(hinted_id, ())
    return -0.25 if any(key.lower() in text for key in keys) else 0.0


def _hinted_prim_names(hinted_id: str) -> tuple[str, ...]:
    return tuple(SEMANTIC_ID_TO_PRIM_NAMES.get(str(hinted_id or ""), ()))


def _query_prim_debug(args: argparse.Namespace, prim_path: str) -> dict[str, Any]:
    return send_control_request(
        "prim_debug",
        {"prim_path": prim_path},
        socket_path=args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
    )


def _query_robot_info(args: argparse.Namespace) -> dict[str, Any]:
    return send_control_request(
        "info",
        {},
        socket_path=args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
    )


def _resolve_base_link_debug(args: argparse.Namespace) -> tuple[str, dict[str, Any], list[dict[str, str]]]:
    candidates: list[str] = []
    requested = str(args.base_link_prim or "").strip()
    if requested:
        candidates.append(requested)

    discovery_errors: list[dict[str, str]] = []
    try:
        robot_info = _query_robot_info(args)
        articulation_root = str(robot_info.get("articulation_root_prim", "") or "").rstrip("/")
        if articulation_root:
            candidates.append(f"{articulation_root}/base_link")
            try:
                root_debug = _query_prim_debug(args, articulation_root)
                candidates.extend(
                    str(path)
                    for path in (root_debug.get("child_paths") or [])
                    if Path(str(path)).name == "base_link"
                )
            except Exception as exc:
                discovery_errors.append({"prim_path": articulation_root, "error": str(exc)})
    except Exception as exc:
        discovery_errors.append({"prim_path": "<robot_info>", "error": str(exc)})

    candidates.extend(DEFAULT_BASE_LINK_PRIM_CANDIDATES)
    attempted: list[dict[str, str]] = list(discovery_errors)
    seen: set[str] = set()
    for prim_path in candidates:
        if not prim_path or prim_path in seen:
            continue
        seen.add(prim_path)
        try:
            return prim_path, _query_prim_debug(args, prim_path), attempted
        except Exception as exc:
            attempted.append({"prim_path": prim_path, "error": str(exc)})

    details = "; ".join(f"{item['prim_path']}: {item['error']}" for item in attempted)
    raise RuntimeError(f"failed to resolve live base_link prim ({details})")


def main() -> int:
    args = build_parser().parse_args()
    selection_payload = _load_json(args.selection_json)
    depth_m = np.load(Path(args.depth_npy)).astype(np.float64, copy=False)
    intrinsics_payload = _load_json(args.intrinsics_json)
    extrinsic_camera_to_base = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError(f"extrinsic_camera_to_base must be 4x4, got {extrinsic_camera_to_base.shape}")

    camera_sample = _camera_point_from_mask(
        selection_payload=selection_payload,
        depth_m=depth_m,
        intrinsics_payload=intrinsics_payload,
    )
    point_base_h = extrinsic_camera_to_base @ camera_sample["point_camera_h"]

    base_link_prim, base_debug, base_link_resolution_attempts = _resolve_base_link_debug(args)
    world_from_base = _as_matrix(base_debug, field="world_matrix", label="base_link")
    base_rotation_world, base_translation_world = _rotation_translation_from_row_major_world_matrix(world_from_base)
    point_base_xyz = np.asarray(point_base_h[:3], dtype=np.float64)
    point_world_xyz = point_base_xyz @ base_rotation_world + base_translation_world

    hinted_id = _semantic_hint(str(selection_payload.get("decision", {}).get("instruction", "")))
    hinted_prim_names = _hinted_prim_names(hinted_id)
    root_debug = _query_prim_debug(args, str(args.trash_root))
    child_paths = [str(path) for path in (root_debug.get("child_paths") or []) if str(path or "").strip()]
    if not child_paths:
        child_paths = [f"{str(args.trash_root).rstrip('/')}/{candidate_id}" for candidate_id in DEFAULT_CANDIDATE_IDS]

    candidates: list[dict[str, Any]] = []
    for prim_path in child_paths:
        try:
            debug = _query_prim_debug(args, prim_path)
        except Exception as exc:
            candidates.append(
                {
                    "prim_path": prim_path,
                    "candidate_id": Path(prim_path).name,
                    "available": False,
                    "error": str(exc),
                }
            )
            continue
        world_matrix = _as_matrix(debug, field="world_matrix", label=prim_path)
        _, candidate_world_xyz = _rotation_translation_from_row_major_world_matrix(world_matrix)
        candidate_base_xyz = (candidate_world_xyz - base_translation_world) @ base_rotation_world.T
        delta_base = candidate_base_xyz - point_base_xyz
        distance_base_m = float(np.linalg.norm(delta_base))
        candidate_label_text = " ".join(
            [
                Path(prim_path).name,
                str(debug.get("first_collision_descendant_path") or ""),
                str(debug.get("resolved_rigid_body_path") or ""),
            ]
        )
        semantic_bonus = _semantic_score(candidate_label_text, hinted_id)
        score = distance_base_m + semantic_bonus
        candidates.append(
            {
                "prim_path": prim_path,
                "candidate_id": Path(prim_path).name,
                "available": True,
                "distance_base_m": distance_base_m,
                "semantic_bonus": float(semantic_bonus),
                "score": float(score),
                "object_center_base_xyz_m": [float(v) for v in candidate_base_xyz.tolist()],
                "object_center_world_xyz_m": [float(v) for v in candidate_world_xyz.tolist()],
                "first_collision_descendant_path": str(debug.get("first_collision_descendant_path") or ""),
                "resolved_rigid_body_path": str(debug.get("resolved_rigid_body_path") or ""),
            }
        )

    available = [candidate for candidate in candidates if candidate.get("available")]
    if not available:
        raise RuntimeError("failed to resolve any live TrashSet candidate prim")
    selected = None
    if hinted_prim_names:
        exact_semantic_matches = [
            candidate for candidate in available if str(candidate.get("candidate_id")) in hinted_prim_names
        ]
        if exact_semantic_matches:
            selected = min(
                exact_semantic_matches,
                key=lambda item: (float(item["distance_base_m"]), str(item["prim_path"])),
            )
    if selected is None:
        selected = min(
            available,
            key=lambda item: (float(item["score"]), float(item["distance_base_m"]), str(item["prim_path"])),
        )

    payload = {
        "target_prim_path": str(selected["prim_path"]),
        "candidate_id": str(selected["candidate_id"]),
        "semantic_hint_id": hinted_id or None,
        "semantic_hint_prim_name": hinted_prim_names[0] if hinted_prim_names else None,
        "semantic_hint_prim_names": list(hinted_prim_names),
        "mask_center_xy": list(camera_sample["mask_center_xy"]),
        "bbox_xywh": list(camera_sample["bbox_xywh"]),
        "valid_depth_count": int(camera_sample["valid_depth_count"]),
        "selected_point_base_xyz_m": [float(v) for v in point_base_xyz.tolist()],
        "selected_point_world_xyz_m": [float(v) for v in point_world_xyz.tolist()],
        "base_link_prim": base_link_prim,
        "requested_base_link_prim": str(args.base_link_prim or ""),
        "base_link_resolution_attempts": base_link_resolution_attempts,
        "trash_root": str(args.trash_root),
        "candidates": candidates,
    }
    output_path = Path(args.output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
