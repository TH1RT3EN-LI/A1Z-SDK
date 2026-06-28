"""Run EconomicGrasp on RGB-D input and export raw grasp candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class EconomicGraspSmokeResult:
    ran: bool
    checkpoint_path: str
    vendor_repo_dir: str
    camera: str
    checkpoint_loaded: bool
    forced_smoke_mode: bool
    voxel_size_m: float
    num_points: int
    valid_point_count: int
    sampled_point_count: int
    quantized_point_count: int
    graspable_point_count: int
    prediction_count: int
    points_path: str
    sampled_points_path: str
    coordinates_path: str
    raw_predictions_path: str
    candidates_json_path: str
    summary_json_path: str
    model_load_notes: dict[str, Any]
    top_candidates: list[dict[str, Any]]
    error: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _create_point_cloud_from_depth_image(depth_m: np.ndarray, *, fx: float, fy: float, cx: float, cy: float) -> np.ndarray:
    if depth_m.ndim != 2:
        raise ValueError(f"depth_m must be 2D, got shape {depth_m.shape}")
    height, width = depth_m.shape
    xmap = np.arange(width, dtype=np.float64)
    ymap = np.arange(height, dtype=np.float64)
    xmap, ymap = np.meshgrid(xmap, ymap)
    points_z = depth_m.astype(np.float64, copy=False)
    points_x = (xmap - float(cx)) * points_z / float(fx)
    points_y = (ymap - float(cy)) * points_z / float(fy)
    return np.stack([points_x, points_y, points_z], axis=-1).astype(np.float32)


def _matrix_to_quaternion_xyzw(rotation: np.ndarray) -> list[float]:
    matrix = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    trace = float(matrix[0, 0] + matrix[1, 1] + matrix[2, 2])
    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (matrix[2, 1] - matrix[1, 2]) / s
        y = (matrix[0, 2] - matrix[2, 0]) / s
        z = (matrix[1, 0] - matrix[0, 1]) / s
    elif matrix[0, 0] > matrix[1, 1] and matrix[0, 0] > matrix[2, 2]:
        s = np.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
        w = (matrix[2, 1] - matrix[1, 2]) / s
        x = 0.25 * s
        y = (matrix[0, 1] + matrix[1, 0]) / s
        z = (matrix[0, 2] + matrix[2, 0]) / s
    elif matrix[1, 1] > matrix[2, 2]:
        s = np.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
        w = (matrix[0, 2] - matrix[2, 0]) / s
        x = (matrix[0, 1] + matrix[1, 0]) / s
        y = 0.25 * s
        z = (matrix[1, 2] + matrix[2, 1]) / s
    else:
        s = np.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
        w = (matrix[1, 0] - matrix[0, 1]) / s
        x = (matrix[0, 2] + matrix[2, 0]) / s
        y = (matrix[1, 2] + matrix[2, 1]) / s
        z = 0.25 * s
    quaternion = np.array([x, y, z, w], dtype=np.float64)
    norm = float(np.linalg.norm(quaternion))
    if norm > 1e-12:
        quaternion /= norm
    return quaternion.astype(float).tolist()


def _prediction_to_candidate(row: np.ndarray, *, rank: int) -> dict[str, Any]:
    row = np.asarray(row, dtype=np.float64).reshape(-1)
    if row.shape[0] < 17:
        raise ValueError(f"prediction row must contain at least 17 values, got {row.shape[0]}")
    score = float(row[0])
    width_m = float(row[1])
    height_m = float(row[2])
    depth_m = float(row[3])
    rotation = row[4:13].reshape(3, 3)
    center_xyz = row[13:16].tolist()
    approach_axis = np.asarray(rotation, dtype=np.float64)[:, 0]
    opening_axis = np.asarray(rotation, dtype=np.float64)[:, 1]
    height_axis = np.asarray(rotation, dtype=np.float64)[:, 2]
    return {
        "rank": int(rank),
        "score": score,
        "width_m": width_m,
        "height_m": height_m,
        "depth_m": depth_m,
        "center_xyz_m": [float(v) for v in center_xyz],
        "rotation_matrix": np.asarray(rotation, dtype=np.float64).astype(float).tolist(),
        "quaternion_xyzw": _matrix_to_quaternion_xyzw(rotation),
        "opening_axis_xyz": opening_axis.astype(float).tolist(),
        "approach_axis_xyz": approach_axis.astype(float).tolist(),
        "height_axis_xyz": height_axis.astype(float).tolist(),
    }


def run_economicgrasp_smoke(
    *,
    rgb: np.ndarray,
    depth_m: np.ndarray,
    intrinsics: dict[str, float],
    checkpoint_path: str | Path,
    vendor_repo_dir: str | Path,
    output_dir: str | Path,
    camera: str = "realsense",
    num_points: int = 20000,
    voxel_size_m: float = 0.005,
    depth_min_m: float = 0.05,
    depth_max_m: float = 1.5,
    random_seed: int = 0,
    top_k: int = 20,
    force_cpu: bool = False,
    allow_random_weights: bool = False,
    force_all_graspable: bool = False,
) -> EconomicGraspSmokeResult:
    vendor_dir = Path(vendor_repo_dir).resolve()
    checkpoint = Path(checkpoint_path).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    if not vendor_dir.is_dir():
        raise FileNotFoundError(f"EconomicGrasp vendor repo not found: {vendor_dir}")
    if not checkpoint.is_file():
        raise FileNotFoundError(f"EconomicGrasp checkpoint not found: {checkpoint}")
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError(f"rgb must have shape (H, W, 3), got {rgb.shape}")
    if depth_m.ndim != 2:
        raise ValueError(f"depth_m must be 2D, got {depth_m.shape}")
    if rgb.shape[:2] != depth_m.shape:
        raise ValueError(f"rgb/depth shape mismatch: rgb={rgb.shape[:2]} depth={depth_m.shape[:2]}")

    vendor_str = str(vendor_dir)
    import sys

    if vendor_str not in sys.path:
        sys.path.insert(0, vendor_str)

    import torch
    import MinkowskiEngine as ME

    sys.argv = [
        "economicgrasp_smoke",
        "--dataset_root",
        "/tmp/graspnet_stub",
        "--camera",
        camera,
        "--graspness_threshold",
        "0.0",
        "--num_point",
        str(int(num_points)),
    ]
    from models.economicgrasp import economicgrasp, pred_decode
    from utils.arguments import cfgs

    fx = float(intrinsics["fx"])
    fy = float(intrinsics["fy"])
    cx = float(intrinsics["cx"])
    cy = float(intrinsics["cy"])

    cloud = _create_point_cloud_from_depth_image(depth_m.astype(np.float32, copy=False), fx=fx, fy=fy, cx=cx, cy=cy)
    valid = np.isfinite(depth_m) & (depth_m > float(depth_min_m))
    if depth_max_m is not None:
        valid &= depth_m < float(depth_max_m)
    valid_point_count = int(valid.sum())
    if valid_point_count <= 0:
        raise ValueError("depth image does not contain any valid points")

    cloud_valid = cloud[valid]
    colors_valid = rgb[valid][:, :3].astype(np.float32, copy=False) / 255.0
    rng = np.random.default_rng(int(random_seed))
    if cloud_valid.shape[0] >= int(num_points):
        sample_idx = np.sort(rng.choice(cloud_valid.shape[0], size=int(num_points), replace=False))
    else:
        sample_idx = np.concatenate(
            [
                np.arange(cloud_valid.shape[0]),
                rng.choice(cloud_valid.shape[0], size=int(num_points) - cloud_valid.shape[0], replace=True),
            ]
        )
    cloud_sampled = np.ascontiguousarray(cloud_valid[sample_idx].astype(np.float32, copy=False))
    colors_sampled = np.ascontiguousarray(colors_valid[sample_idx].astype(np.float32, copy=False))

    points_path = output_root / "points.npy"
    sampled_points_path = output_root / "sampled_points.npy"
    coordinates_path = output_root / "coordinates_for_voxel.npy"
    raw_predictions_path = output_root / "raw_predictions.npy"
    candidates_json_path = output_root / "grasp_candidates.json"
    summary_json_path = output_root / "economicgrasp_result.json"

    np.save(points_path, cloud_valid.astype(np.float32, copy=False))
    np.save(sampled_points_path, cloud_sampled)
    np.save(coordinates_path, (cloud_sampled / float(voxel_size_m)).astype(np.float32, copy=False))

    device = torch.device("cpu")
    if torch.cuda.is_available() and not force_cpu:
        device = torch.device("cuda")

    model = economicgrasp(seed_feat_dim=512, is_training=False)
    model = model.to(device)
    checkpoint_loaded = False
    forced_smoke_mode = bool(force_all_graspable or allow_random_weights)
    load_state_notes: dict[str, Any] = {}
    try:
        try:
            checkpoint_obj = torch.load(checkpoint, map_location=device, weights_only=False)
        except TypeError:
            checkpoint_obj = torch.load(checkpoint, map_location=device)

        if isinstance(checkpoint_obj, dict) and "model_state_dict" in checkpoint_obj:
            state_dict = checkpoint_obj["model_state_dict"]
        else:
            state_dict = checkpoint_obj
        missing_keys, unexpected_keys = model.load_state_dict(state_dict, strict=False)
        checkpoint_loaded = True
        if missing_keys or unexpected_keys:
            load_state_notes = {
                "missing_keys": list(missing_keys),
                "unexpected_keys": list(unexpected_keys),
            }
    except Exception as exc:
        if not allow_random_weights:
            raise
        load_state_notes = {
            "checkpoint_load_error": repr(exc),
            "used_random_weights": True,
        }

    if force_all_graspable:
        def _force_graspable(seed_features: torch.Tensor, end_points: dict[str, Any]) -> dict[str, Any]:
            batch_size = int(seed_features.shape[0])
            num_points_local = int(seed_features.shape[2])
            objectness_score = torch.zeros(
                (batch_size, 2, num_points_local),
                device=seed_features.device,
                dtype=seed_features.dtype,
            )
            objectness_score[:, 1, :] = 1.0
            graspness_score = torch.ones(
                (batch_size, num_points_local),
                device=seed_features.device,
                dtype=seed_features.dtype,
            )
            end_points["objectness_score"] = objectness_score
            end_points["graspness_score"] = graspness_score
            return end_points

        model.graspable.forward = _force_graspable  # type: ignore[method-assign]
        load_state_notes["forced_all_graspable"] = True

    end_points = {
        "point_clouds": torch.from_numpy(cloud_sampled[None, ...]).to(device=device, dtype=torch.float32),
        "coordinates_for_voxel": torch.from_numpy(
            np.ascontiguousarray((cloud_sampled / float(voxel_size_m))[None, ...], dtype=np.float32)
        ),
    }

    with torch.no_grad():
        end_points = model(end_points)
        grasp_preds = pred_decode(end_points)

    grasp_preds_cam = grasp_preds[0].detach().cpu().numpy().astype(np.float32, copy=False)
    pred_scores = grasp_preds_cam[:, 0]
    order = np.argsort(pred_scores)[::-1]
    top_candidates = [_prediction_to_candidate(grasp_preds_cam[idx], rank=rank) for rank, idx in enumerate(order[: int(top_k)])]

    objectness_score = end_points["objectness_score"].detach().cpu()
    graspness_score = end_points["graspness_score"].detach().cpu().squeeze(1)
    objectness_pred = torch.argmax(objectness_score, 1)
    graspable_mask = (objectness_pred == 1) & (graspness_score > float(cfgs.graspness_threshold))
    graspable_point_count = int(graspable_mask.sum().item())

    np.save(raw_predictions_path, grasp_preds_cam)
    candidates_json_path.write_text(json.dumps(top_candidates, ensure_ascii=True, indent=2), encoding="utf-8")

    summary = {
        "checkpoint_path": str(checkpoint),
        "vendor_repo_dir": str(vendor_dir),
        "camera": str(camera),
        "checkpoint_loaded": bool(checkpoint_loaded),
        "forced_smoke_mode": bool(forced_smoke_mode),
        "voxel_size_m": float(voxel_size_m),
        "num_points": int(num_points),
        "valid_point_count": int(valid_point_count),
        "sampled_point_count": int(cloud_sampled.shape[0]),
        "quantized_point_count": int(end_points["quantize2original"].shape[0]),
        "graspable_point_count": int(graspable_point_count),
        "prediction_count": int(grasp_preds_cam.shape[0]),
        "score_max": float(pred_scores.max()) if pred_scores.size else None,
        "score_mean": float(pred_scores.mean()) if pred_scores.size else None,
        "top_candidates": top_candidates,
        "model_load_notes": load_state_notes,
    }
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    return EconomicGraspSmokeResult(
        ran=True,
        checkpoint_path=str(checkpoint),
        vendor_repo_dir=str(vendor_dir),
        camera=str(camera),
        checkpoint_loaded=bool(checkpoint_loaded),
        forced_smoke_mode=bool(forced_smoke_mode),
        voxel_size_m=float(voxel_size_m),
        num_points=int(num_points),
        valid_point_count=int(valid_point_count),
        sampled_point_count=int(cloud_sampled.shape[0]),
        quantized_point_count=int(end_points["quantize2original"].shape[0]),
        graspable_point_count=int(graspable_point_count),
        prediction_count=int(grasp_preds_cam.shape[0]),
        points_path=str(points_path),
        sampled_points_path=str(sampled_points_path),
        coordinates_path=str(coordinates_path),
        raw_predictions_path=str(raw_predictions_path),
        candidates_json_path=str(candidates_json_path),
        summary_json_path=str(summary_json_path),
        model_load_notes=load_state_notes,
        top_candidates=top_candidates,
        error="",
    )
