"""Depth + mask fusion for the initial non-grasping docker loop."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from a1z_ext.interfaces.schemas import MaskCandidate, Object3DDescriptor, PrincipalAxes


def _load_mask(path: str | Path) -> np.ndarray:
    mask = np.load(Path(path))
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")
    return mask.astype(bool)


def _principal_axes(points: np.ndarray) -> PrincipalAxes:
    centered = points - points.mean(axis=0, keepdims=True)
    if centered.shape[0] < 3:
        return PrincipalAxes([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    axes = eigvecs[:, order]
    return PrincipalAxes(
        axis_1=axes[:, 0].astype(float).tolist(),
        axis_2=axes[:, 1].astype(float).tolist(),
        axis_3=axes[:, 2].astype(float).tolist(),
    )


def recover_object_descriptors(
    *,
    depth_m: np.ndarray,
    intrinsics: dict[str, float],
    extrinsic_camera_to_base: np.ndarray,
    mask_candidates: list[MaskCandidate],
    frame_id: str = "robot_base_frame",
) -> list[Object3DDescriptor]:
    if depth_m.ndim != 2:
        raise ValueError(f"depth_m must be 2D, got shape {depth_m.shape}")
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError("extrinsic_camera_to_base must be 4x4")

    fx = float(intrinsics["fx"])
    fy = float(intrinsics["fy"])
    cx = float(intrinsics["cx"])
    cy = float(intrinsics["cy"])

    descriptors: list[Object3DDescriptor] = []
    for candidate in mask_candidates:
        mask = _load_mask(candidate.mask_path)
        valid = mask & np.isfinite(depth_m) & (depth_m > 0.0)
        ys, xs = np.where(valid)
        if xs.size == 0:
            continue

        z = depth_m[ys, xs]
        x = (xs.astype(np.float64) - cx) * z / fx
        y = (ys.astype(np.float64) - cy) * z / fy
        points_cam = np.stack([x, y, z, np.ones_like(z)], axis=1)
        points_base = (extrinsic_camera_to_base @ points_cam.T).T[:, :3]

        centroid = points_base.mean(axis=0)
        top_idx = int(np.argmax(points_base[:, 2]))
        top_point = points_base[top_idx]
        mins = points_base.min(axis=0)
        maxs = points_base.max(axis=0)
        extents = maxs - mins
        support_height = float(mins[2])
        support_normal = [0.0, 0.0, 1.0]
        local_normal = [0.0, 0.0, 1.0]
        quality = min(1.0, float(points_base.shape[0]) / max(1.0, float(candidate.mask_area_px)))

        descriptors.append(
            Object3DDescriptor(
                object_id=f"{candidate.mask_id}-object",
                mask_id=candidate.mask_id,
                frame_id=frame_id,
                point_count=int(points_base.shape[0]),
                centroid_xyz=centroid.astype(float).tolist(),
                top_point_xyz=top_point.astype(float).tolist(),
                support_plane_height_m=support_height,
                support_plane_normal_xyz=support_normal,
                local_surface_normal_xyz=local_normal,
                principal_axes=_principal_axes(points_base),
                bbox_extent_xyz_m=extents.astype(float).tolist(),
                workspace_margin_ok=True,
                point_cloud_quality=float(quality),
                pose_confidence=float(min(candidate.mask_score, quality)),
            )
        )
    return descriptors

