"""Helpers to convert a selected 2D mask into AnyGrasp-ready 3D inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from a1z_ext.runtime.image_input import _encode_png


@dataclass(frozen=True, slots=True)
class MaskedPointCloudResult:
    mask_area_px: int
    valid_depth_count: int
    point_count: int
    depth_valid_ratio: float
    bbox_xyz_min: list[float]
    bbox_xyz_max: list[float]
    lims: list[float]
    points_path: str
    colors_path: str
    masked_rgb_path: str
    masked_depth_path: str
    summary_json_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AnyGraspPreflightResult:
    ready: bool
    sdk_dir: str
    checkpoint_path: str
    license_dir: str
    feature_id: str
    configured_license_feature_id: str
    detector_import_ok: bool
    graspnet_api_import_ok: bool
    checkpoint_exists: bool
    license_dir_exists: bool
    license_cfg_exists: bool
    detector_create_ok: bool
    missing: list[str]
    notes: list[str]
    detector_error: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AnyGraspDetectionResult:
    ran: bool
    grasp_count: int
    top_k: int
    lims: list[float]
    preflight: dict[str, Any]
    top_grasps: list[dict[str, Any]]
    result_json_path: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _write_rgb_png(path: Path, rgb: np.ndarray) -> None:
    array = np.ascontiguousarray(rgb.astype(np.uint8, copy=False))
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(f"rgb must have shape (H, W, 3), got {array.shape}")
    rows = [array[row_idx].tobytes() for row_idx in range(array.shape[0])]
    path.write_bytes(
        _encode_png(
            width=int(array.shape[1]),
            height=int(array.shape[0]),
            rows=rows,
            color_type=2,
        )
    )


def load_rgb_array(path: str | Path) -> np.ndarray:
    source = Path(path)
    if source.suffix.lower() == ".npy":
        array = np.load(source)
        if array.ndim != 3 or array.shape[2] < 3:
            raise ValueError(f"rgb npy must have shape (H, W, C>=3), got {array.shape}")
        return np.ascontiguousarray(array[:, :, :3].astype(np.uint8, copy=False))
    from PIL import Image

    return np.asarray(Image.open(source).convert("RGB"), dtype=np.uint8)


def load_mask_array(path: str | Path) -> np.ndarray:
    mask = np.load(Path(path))
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")
    return mask.astype(bool)


def build_anygrasp_inputs_from_mask(
    *,
    rgb: np.ndarray,
    depth_m: np.ndarray,
    intrinsics: dict[str, float],
    mask: np.ndarray,
    output_dir: str | Path,
    workspace_margin_m: float = 0.02,
    depth_min_m: float = 0.0,
    depth_max_m: float | None = 1.5,
    max_points: int | None = None,
    random_seed: int = 0,
) -> MaskedPointCloudResult:
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError(f"rgb must have shape (H, W, C>=3), got {rgb.shape}")
    if depth_m.ndim != 2:
        raise ValueError(f"depth_m must be 2D, got shape {depth_m.shape}")
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")
    if rgb.shape[:2] != depth_m.shape[:2]:
        raise ValueError(
            f"rgb/depth shape mismatch: rgb={rgb.shape[:2]} depth={depth_m.shape[:2]}"
        )
    if mask.shape != depth_m.shape:
        raise ValueError(
            f"mask/depth shape mismatch: mask={mask.shape} depth={depth_m.shape}"
        )

    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    fx = float(intrinsics["fx"])
    fy = float(intrinsics["fy"])
    cx = float(intrinsics["cx"])
    cy = float(intrinsics["cy"])

    valid = mask.astype(bool) & np.isfinite(depth_m) & (depth_m > float(depth_min_m))
    if depth_max_m is not None:
        valid &= depth_m < float(depth_max_m)

    mask_area_px = int(mask.sum())
    valid_depth_count = int(valid.sum())
    if valid_depth_count <= 0:
        raise ValueError("selected mask does not contain valid depth points")

    ys, xs = np.where(valid)
    z = depth_m[ys, xs].astype(np.float64)
    x = (xs.astype(np.float64) - cx) * z / fx
    y = (ys.astype(np.float64) - cy) * z / fy
    points = np.stack([x, y, z], axis=1).astype(np.float32)
    colors = (rgb[ys, xs, :3].astype(np.float32) / 255.0).astype(np.float32)

    point_count = int(points.shape[0])
    if max_points is not None and point_count > int(max_points):
        rng = np.random.default_rng(int(random_seed))
        keep = np.sort(rng.choice(point_count, size=int(max_points), replace=False))
        points = points[keep]
        colors = colors[keep]
        point_count = int(points.shape[0])

    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    margin = float(workspace_margin_m)
    lims = [
        float(mins[0] - margin),
        float(maxs[0] + margin),
        float(mins[1] - margin),
        float(maxs[1] + margin),
        float(max(depth_min_m, float(mins[2] - margin))),
        float(maxs[2] + margin),
    ]

    masked_rgb = np.zeros_like(rgb[:, :, :3], dtype=np.uint8)
    masked_rgb[mask] = rgb[:, :, :3][mask]
    masked_depth = np.full(depth_m.shape, np.nan, dtype=np.float32)
    masked_depth[valid] = depth_m[valid].astype(np.float32, copy=False)

    points_path = output_root / "points.npy"
    colors_path = output_root / "colors.npy"
    masked_rgb_path = output_root / "masked_rgb.png"
    masked_depth_path = output_root / "masked_depth_m.npy"
    summary_path = output_root / "masked_point_cloud.json"

    np.save(points_path, points)
    np.save(colors_path, colors)
    np.save(masked_depth_path, masked_depth)
    _write_rgb_png(masked_rgb_path, masked_rgb)

    result = MaskedPointCloudResult(
        mask_area_px=mask_area_px,
        valid_depth_count=valid_depth_count,
        point_count=point_count,
        depth_valid_ratio=float(valid_depth_count) / float(mask_area_px) if mask_area_px > 0 else 0.0,
        bbox_xyz_min=mins.astype(float).tolist(),
        bbox_xyz_max=maxs.astype(float).tolist(),
        lims=lims,
        points_path=str(points_path),
        colors_path=str(colors_path),
        masked_rgb_path=str(masked_rgb_path),
        masked_depth_path=str(masked_depth_path),
        summary_json_path=str(summary_path),
    )
    summary_path.write_text(json.dumps(result.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return result


def check_anygrasp_runtime(
    *,
    sdk_dir: str | Path,
    checkpoint_path: str | Path,
    license_dir: str | Path,
) -> AnyGraspPreflightResult:
    import os
    import sys
    import traceback

    sdk_root = Path(sdk_dir)
    checkpoint = Path(checkpoint_path)
    license_root = Path(license_dir)
    detection_dir = sdk_root / "grasp_detection"
    tracking_dir = sdk_root / "grasp_tracking"
    license_cfg_path = license_root / "licenseCfg.json"

    missing: list[str] = []
    notes: list[str] = []
    feature_id = ""
    configured_license_feature_id = ""
    detector_error = ""
    checkpoint_exists = checkpoint.is_file()
    license_dir_exists = license_root.is_dir()
    license_cfg_exists = license_cfg_path.is_file()
    detector_create_ok = False

    if not sdk_root.is_dir():
        missing.append(f"sdk_dir:{sdk_root}")
    if not detection_dir.is_dir():
        missing.append(f"grasp_detection_dir:{detection_dir}")
    if not tracking_dir.is_dir():
        missing.append(f"grasp_tracking_dir:{tracking_dir}")
    if not checkpoint_exists:
        missing.append(f"checkpoint:{checkpoint}")
    if not license_dir_exists:
        missing.append(f"license_dir:{license_root}")
    elif not license_cfg_exists:
        missing.append(f"license_cfg:{license_cfg_path}")

    if license_cfg_exists:
        try:
            payload = json.loads(license_cfg_path.read_text(encoding="utf-8"))
            configured_license_feature_id = str(payload.get("feature_id", "") or "")
        except Exception as exc:
            notes.append(f"license_cfg_read_error:{exc}")

    detector_import_ok = False
    graspnet_api_import_ok = False
    detection_path = str(detection_dir)
    tracking_path = str(tracking_dir)
    if detection_path not in sys.path:
        sys.path.insert(0, detection_path)
    if tracking_path not in sys.path:
        sys.path.insert(0, tracking_path)

    try:
        from graspnetAPI.grasp import GraspGroup  # noqa: F401

        graspnet_api_import_ok = True
    except Exception as exc:
        missing.append(f"graspnetAPI_import:{exc}")

    gsnet_module: Any | None = None
    if detection_dir.is_dir():
        try:
            import gsnet  # type: ignore

            gsnet_module = gsnet
            detector_import_ok = hasattr(gsnet, "create_detector")
            if hasattr(gsnet, "get_feature_id"):
                try:
                    feature_id = str(gsnet.get_feature_id())
                except Exception as exc:
                    notes.append(f"feature_id_error:{exc}")
            if not detector_import_ok:
                missing.append("gsnet.create_detector")
        except Exception as exc:
            missing.append(f"gsnet_import:{exc}")

    if detection_dir.is_dir() and not (detection_dir / "gsnet.so").is_file():
        notes.append(f"gsnet.so not found under {detection_dir}")
    if tracking_dir.is_dir() and not (tracking_dir / "tracker.so").is_file():
        notes.append(f"tracker.so not found under {tracking_dir}")

    if configured_license_feature_id and feature_id and configured_license_feature_id != feature_id:
        missing.append(f"license_feature_id_mismatch:{configured_license_feature_id}!={feature_id}")

    if detector_import_ok and gsnet_module is not None and checkpoint_exists and license_dir_exists and license_cfg_exists:
        current_detection_license = detection_dir / "license"
        current_tracking_license = tracking_dir / "license"
        previous_detection_license = None
        previous_tracking_license = None
        try:
            if current_detection_license.exists() or current_detection_license.is_symlink():
                previous_detection_license = os.readlink(current_detection_license) if current_detection_license.is_symlink() else None
            if current_tracking_license.exists() or current_tracking_license.is_symlink():
                previous_tracking_license = os.readlink(current_tracking_license) if current_tracking_license.is_symlink() else None
        except OSError:
            previous_detection_license = None
            previous_tracking_license = None

        try:
            if current_detection_license.exists() or current_detection_license.is_symlink():
                if current_detection_license.is_symlink() or current_detection_license.is_file():
                    current_detection_license.unlink()
                else:
                    import shutil

                    shutil.rmtree(current_detection_license)
            os.symlink(str(license_root), str(current_detection_license))

            if current_tracking_license.exists() or current_tracking_license.is_symlink():
                if current_tracking_license.is_symlink() or current_tracking_license.is_file():
                    current_tracking_license.unlink()
                else:
                    import shutil

                    shutil.rmtree(current_tracking_license)
            os.symlink(str(license_root), str(current_tracking_license))

            cfgs = SimpleNamespace(
                checkpoint_path=str(checkpoint),
                max_gripper_width=0.7,
                gripper_height=0.022,
                top_down_grasp=True,
                debug=False,
            )
            detector = gsnet_module.create_detector(cfgs)
            detector_create_ok = detector is not None
            if not detector_create_ok:
                detector_error = "create_detector returned a falsy detector"
                missing.append("detector_create")
        except Exception as exc:
            detector_error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            missing.append(f"detector_create:{detector_error}")
        finally:
            try:
                if current_detection_license.exists() or current_detection_license.is_symlink():
                    if current_detection_license.is_symlink() or current_detection_license.is_file():
                        current_detection_license.unlink()
                    else:
                        import shutil

                        shutil.rmtree(current_detection_license)
                if previous_detection_license:
                    os.symlink(previous_detection_license, str(current_detection_license))
            except OSError:
                pass
            try:
                if current_tracking_license.exists() or current_tracking_license.is_symlink():
                    if current_tracking_license.is_symlink() or current_tracking_license.is_file():
                        current_tracking_license.unlink()
                    else:
                        import shutil

                        shutil.rmtree(current_tracking_license)
                if previous_tracking_license:
                    os.symlink(previous_tracking_license, str(current_tracking_license))
            except OSError:
                pass

    return AnyGraspPreflightResult(
        ready=(len(missing) == 0 and detector_import_ok and graspnet_api_import_ok and detector_create_ok),
        sdk_dir=str(sdk_root),
        checkpoint_path=str(checkpoint),
        license_dir=str(license_root),
        feature_id=feature_id,
        configured_license_feature_id=configured_license_feature_id,
        detector_import_ok=detector_import_ok,
        graspnet_api_import_ok=graspnet_api_import_ok,
        checkpoint_exists=checkpoint_exists,
        license_dir_exists=license_dir_exists,
        license_cfg_exists=license_cfg_exists,
        detector_create_ok=detector_create_ok,
        missing=missing,
        notes=notes,
        detector_error=detector_error,
    )


def _serialize_grasp(grasp: Any, *, rank: int) -> dict[str, Any]:
    payload = {
        "rank": int(rank),
        "score": float(getattr(grasp, "score")),
        "width_m": float(getattr(grasp, "width")),
        "height_m": float(getattr(grasp, "height")),
        "depth_m": float(getattr(grasp, "depth")),
        "translation_xyz_m": np.asarray(getattr(grasp, "translation"), dtype=np.float64).reshape(3).tolist(),
        "rotation_matrix": np.asarray(getattr(grasp, "rotation_matrix"), dtype=np.float64).reshape(3, 3).tolist(),
    }
    object_id = getattr(grasp, "object_id", None)
    if object_id is not None:
        payload["object_id"] = int(object_id)
    return payload


def run_anygrasp_detection(
    *,
    points: np.ndarray,
    colors: np.ndarray,
    lims: list[float],
    output_dir: str | Path,
    sdk_dir: str | Path,
    checkpoint_path: str | Path,
    license_dir: str | Path,
    max_gripper_width: float = 0.7,
    gripper_height: float = 0.022,
    top_down_grasp: bool = True,
    collision_detection: bool = True,
    dense_grasp: bool = False,
    top_k: int = 20,
    minimum_point_count: int = 256,
) -> AnyGraspDetectionResult:
    import sys

    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    result_path = output_root / "anygrasp_result.json"

    points = np.asarray(points)
    colors = np.asarray(colors)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"points must have shape (N, 3), got {points.shape}")
    if colors.shape != points.shape:
        raise ValueError(
            f"colors must have the same shape as points: colors={colors.shape} points={points.shape}"
        )
    point_count = int(points.shape[0])
    required_points = max(1, int(minimum_point_count))
    if point_count < required_points:
        result = AnyGraspDetectionResult(
            ran=False,
            grasp_count=0,
            top_k=int(top_k),
            lims=[float(v) for v in lims],
            preflight={
                "ready": False,
                "skipped": "insufficient_masked_point_cloud",
            },
            top_grasps=[],
            result_json_path=str(result_path),
            error=(
                "insufficient masked point cloud: "
                f"{point_count} points, minimum {required_points}"
            ),
        )
        result_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return result

    preflight = check_anygrasp_runtime(
        sdk_dir=sdk_dir,
        checkpoint_path=checkpoint_path,
        license_dir=license_dir,
    )
    if not preflight.ready:
        result = AnyGraspDetectionResult(
            ran=False,
            grasp_count=0,
            top_k=int(top_k),
            lims=[float(v) for v in lims],
            preflight=preflight.to_dict(),
            top_grasps=[],
            result_json_path=str(result_path),
            error="AnyGrasp runtime is not ready",
        )
        result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
        return result

    detection_path = str(Path(sdk_dir) / "grasp_detection")
    tracking_path = str(Path(sdk_dir) / "grasp_tracking")
    if detection_path not in sys.path:
        sys.path.insert(0, detection_path)
    if tracking_path not in sys.path:
        sys.path.insert(0, tracking_path)

    try:
        from gsnet import create_detector  # type: ignore

        cfgs = SimpleNamespace(
            checkpoint_path=str(checkpoint_path),
            max_gripper_width=max(0.0, min(0.7, float(max_gripper_width))),
            gripper_height=float(gripper_height),
            top_down_grasp=bool(top_down_grasp),
            debug=False,
        )
        detector = create_detector(cfgs)
        if not detector:
            raise RuntimeError("create_detector returned a falsy detector")

        gg, _cloud = detector.get_grasp(
            points.astype(np.float32, copy=False),
            colors.astype(np.float32, copy=False),
            lims=[float(v) for v in lims],
            apply_object_mask=True,
            dense_grasp=bool(dense_grasp),
            collision_detection=bool(collision_detection),
        )

        grasp_count = 0 if gg is None else int(len(gg))
        if grasp_count <= 0:
            result = AnyGraspDetectionResult(
                ran=True,
                grasp_count=0,
                top_k=int(top_k),
                lims=[float(v) for v in lims],
                preflight=preflight.to_dict(),
                top_grasps=[],
                result_json_path=str(result_path),
                error="no grasp detected for selected target mask",
            )
            result_path.write_text(
                json.dumps(result.to_dict(), ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            return result

        gg = gg.nms().sort_by_score()
        take = min(int(top_k), int(len(gg)))
        top_grasps = [_serialize_grasp(gg[idx], rank=idx) for idx in range(take)]
        result = AnyGraspDetectionResult(
            ran=True,
            grasp_count=grasp_count,
            top_k=int(top_k),
            lims=[float(v) for v in lims],
            preflight=preflight.to_dict(),
            top_grasps=top_grasps,
            result_json_path=str(result_path),
            error="",
        )
    except Exception as exc:
        result = AnyGraspDetectionResult(
            ran=False,
            grasp_count=0,
            top_k=int(top_k),
            lims=[float(v) for v in lims],
            preflight=preflight.to_dict(),
            top_grasps=[],
            result_json_path=str(result_path),
            error=str(exc),
        )

    result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return result
