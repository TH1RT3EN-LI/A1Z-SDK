"""Run GR-ConvNet on RGB-D inputs and return reusable grasp-map artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class GRConvNetInferenceResult:
    ran: bool
    checkpoint_path: str
    vendor_repo_dir: str
    use_depth: bool
    use_rgb: bool
    input_crop_top_left_rc: list[int]
    input_crop_bottom_right_rc: list[int]
    quality_map_path: str
    angle_map_rad_path: str
    width_map_px_path: str
    grasp_candidates_json_path: str
    preview_json_path: str
    candidate_count: int
    top_candidates: list[dict[str, Any]]
    error: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _compute_crop_bounds(
    *,
    height: int,
    width: int,
    crop_size: int,
    mask: np.ndarray | None,
) -> tuple[int, int, int, int]:
    if crop_size <= 0:
        raise ValueError(f"crop_size must be positive, got {crop_size}")
    if crop_size > height or crop_size > width:
        raise ValueError(
            f"crop_size {crop_size} must fit inside image shape {(height, width)}"
        )

    if mask is not None:
        mask_bool = np.asarray(mask, dtype=bool)
        ys, xs = np.where(mask_bool)
        if ys.size > 0:
            center_row = int(round(float(ys.min() + ys.max()) * 0.5))
            center_col = int(round(float(xs.min() + xs.max()) * 0.5))
        else:
            center_row = height // 2
            center_col = width // 2
    else:
        center_row = height // 2
        center_col = width // 2

    top = int(center_row - (crop_size // 2))
    left = int(center_col - (crop_size // 2))
    top = max(0, min(top, height - crop_size))
    left = max(0, min(left, width - crop_size))
    bottom = top + crop_size
    right = left + crop_size
    return top, left, bottom, right


def run_grconvnet_inference(
    *,
    rgb: np.ndarray,
    depth_m: np.ndarray,
    checkpoint_path: str | Path,
    vendor_repo_dir: str | Path,
    output_dir: str | Path,
    mask: np.ndarray | None = None,
    use_depth: bool = True,
    use_rgb: bool = True,
    top_k: int = 20,
    force_cpu: bool = False,
    peak_local_max_min_distance: int = 12,
    min_quality: float = 0.1,
) -> GRConvNetInferenceResult:
    vendor_dir = Path(vendor_repo_dir).resolve()
    checkpoint = Path(checkpoint_path).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    if not checkpoint.is_file():
        raise FileNotFoundError(f"GR-ConvNet checkpoint not found: {checkpoint}")
    if not vendor_dir.is_dir():
        raise FileNotFoundError(f"GR-ConvNet vendor repo not found: {vendor_dir}")

    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError(f"rgb must have shape (H, W, 3), got {rgb.shape}")
    if depth_m.ndim != 2:
        raise ValueError(f"depth_m must be 2D, got {depth_m.shape}")
    if rgb.shape[:2] != depth_m.shape:
        raise ValueError("rgb/depth shape mismatch")

    vendor_str = str(vendor_dir)
    if vendor_str not in sys.path:
        sys.path.insert(0, vendor_str)

    import torch
    from skimage.filters import gaussian

    crop_size = 224
    top, left, bottom, right = _compute_crop_bounds(
        height=int(rgb.shape[0]),
        width=int(rgb.shape[1]),
        crop_size=crop_size,
        mask=mask,
    )
    rgb_crop = np.ascontiguousarray(rgb[top:bottom, left:right, :3])
    depth_crop = np.ascontiguousarray(depth_m[top:bottom, left:right])
    mask_crop = None if mask is None else np.asarray(mask, dtype=bool)[top:bottom, left:right]
    depth_crop_for_net = depth_crop.copy()
    depth_crop_for_net[~np.isfinite(depth_crop_for_net)] = 0.0

    x = _build_network_input(
        rgb_crop=rgb_crop,
        depth_crop=depth_crop_for_net,
        use_depth=bool(use_depth),
        use_rgb=bool(use_rgb),
    )

    device = torch.device("cpu")
    if torch.cuda.is_available() and not force_cpu:
        device = torch.device("cuda")

    try:
        net = torch.load(checkpoint, map_location=device, weights_only=False)
    except TypeError:
        net = torch.load(checkpoint, map_location=device)
    net = net.to(device)
    net.eval()

    with torch.no_grad():
        xc = x.to(device)
        pred = net.predict(xc)
        q_img = pred["pos"].detach().cpu().numpy().squeeze().astype(np.float32)
        ang_img = (
            (torch.atan2(pred["sin"], pred["cos"]) / 2.0)
            .detach()
            .cpu()
            .numpy()
            .squeeze()
            .astype(np.float32)
        )
        width_img = (
            pred["width"].detach().cpu().numpy().squeeze().astype(np.float32) * 150.0
        )

    q_img = gaussian(q_img, 2.0, preserve_range=True).astype(np.float32)
    ang_img = gaussian(ang_img, 2.0, preserve_range=True).astype(np.float32)
    width_img = gaussian(width_img, 1.0, preserve_range=True).astype(np.float32)

    if mask_crop is not None:
        q_img = q_img.copy()
        q_img[~mask_crop] = 0.0

    from skimage.feature import peak_local_max

    peaks = peak_local_max(
        q_img,
        min_distance=max(1, int(peak_local_max_min_distance)),
        threshold_abs=float(min_quality),
        num_peaks=max(1, int(top_k)),
    )
    top_candidates: list[dict[str, Any]] = []
    for rank, (row_px, col_px) in enumerate(peaks[:top_k]):
        top_candidates.append(
            {
                "rank": rank,
                "row_px_crop": int(row_px),
                "col_px_crop": int(col_px),
                "row_px_full": int(top + row_px),
                "col_px_full": int(left + col_px),
                "quality": float(q_img[row_px, col_px]),
                "angle_rad": float(ang_img[row_px, col_px]),
                "width_px": float(width_img[row_px, col_px]),
            }
        )

    quality_map_path = output_root / "quality_map.npy"
    angle_map_path = output_root / "angle_map_rad.npy"
    width_map_path = output_root / "width_map_px.npy"
    candidates_path = output_root / "grasp_candidates.json"
    preview_path = output_root / "grconvnet_result.json"
    np.save(quality_map_path, q_img)
    np.save(angle_map_path, ang_img)
    np.save(width_map_path, width_img)
    candidates_path.write_text(json.dumps(top_candidates, ensure_ascii=True, indent=2), encoding="utf-8")

    result = GRConvNetInferenceResult(
        ran=True,
        checkpoint_path=str(checkpoint),
        vendor_repo_dir=str(vendor_dir),
        use_depth=bool(use_depth),
        use_rgb=bool(use_rgb),
        input_crop_top_left_rc=[int(top), int(left)],
        input_crop_bottom_right_rc=[int(bottom), int(right)],
        quality_map_path=str(quality_map_path),
        angle_map_rad_path=str(angle_map_path),
        width_map_px_path=str(width_map_path),
        grasp_candidates_json_path=str(candidates_path),
        preview_json_path=str(preview_path),
        candidate_count=len(top_candidates),
        top_candidates=top_candidates,
        error="",
    )
    preview_path.write_text(json.dumps(result.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return result


def _build_network_input(
    *,
    rgb_crop: np.ndarray,
    depth_crop: np.ndarray,
    use_depth: bool,
    use_rgb: bool,
):
    import torch

    if not use_depth and not use_rgb:
        raise ValueError("at least one of use_depth or use_rgb must be enabled")

    channels: list[np.ndarray] = []
    if use_depth:
        depth_norm = depth_crop.astype(np.float32, copy=True)
        depth_norm -= float(depth_norm.mean())
        depth_norm = np.clip(depth_norm, -1.0, 1.0)
        channels.append(depth_norm[None, :, :])

    if use_rgb:
        rgb_norm = rgb_crop.astype(np.float32, copy=True) / 255.0
        rgb_norm -= float(rgb_norm.mean())
        channels.append(np.transpose(rgb_norm, (2, 0, 1)))

    stacked = np.concatenate(channels, axis=0).astype(np.float32, copy=False)
    return torch.from_numpy(stacked[None, ...])
