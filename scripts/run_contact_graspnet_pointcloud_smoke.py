#!/usr/bin/env python3

"""Minimal Contact-GraspNet point-cloud smoke test runner."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import tensorflow.compat.v1 as tf

tf.disable_eager_execution()
if os.environ.get("CGN_DISABLE_RESOURCE_VARIABLES") == "1":
    tf.disable_resource_variables()


REPO_ROOT = Path(__file__).resolve().parents[1]
CGN_ROOT = REPO_ROOT / "vendor" / "vision" / "contact_graspnet"


def _add_contact_graspnet_paths() -> None:
    paths = [
        CGN_ROOT,
        CGN_ROOT / "contact_graspnet",
        CGN_ROOT / "pointnet2" / "utils",
        CGN_ROOT / "pointnet2" / "tf_ops" / "sampling",
        CGN_ROOT / "pointnet2" / "tf_ops" / "grouping",
        CGN_ROOT / "pointnet2" / "tf_ops" / "3d_interpolation",
    ]
    for path in paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a minimal Contact-GraspNet point-cloud smoke test.")
    parser.add_argument(
        "--checkpoint-dir",
        default=str(CGN_ROOT / "checkpoints" / "scene_test_2048_bs3_hor_sigma_001"),
        help="Contact-GraspNet checkpoint directory.",
    )
    parser.add_argument(
        "--points",
        default=str(
            REPO_ROOT
            / "runtime"
            / "target_mask_to_anygrasp"
            / "from_ros_live"
            / "anygrasp_from_mask"
            / "masked_point_cloud"
            / "points.npy"
        ),
        help="Nx3 point cloud .npy file in meters.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(
            REPO_ROOT
            / "runtime"
            / "target_mask_to_anygrasp"
            / "from_ros_live"
            / "contact_graspnet_pointcloud_smoke"
        ),
        help="Directory for summary and optional outputs.",
    )
    parser.add_argument("--raw-num-points", type=int, default=2048)
    parser.add_argument("--max-farthest-points", type=int, default=32)
    parser.add_argument("--num-samples", type=int, default=32)
    parser.add_argument("--forward-passes", type=int, default=1)
    parser.add_argument(
        "--keep-is-training-placeholder",
        action="store_true",
        help="Keep the dynamic is_training placeholder instead of compiling an inference-only graph.",
    )
    parser.add_argument(
        "--arg-config",
        action="append",
        default=[],
        help="Additional Contact-GraspNet config override like MODEL.pointnet_sa_modules_msg.0.npoint:1024",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _add_contact_graspnet_paths()

    from contact_grasp_estimator import GraspEstimator
    import config_utils
    from data import preprocess_pc_for_inference

    checkpoint_dir = Path(args.checkpoint_dir).resolve()
    points_path = Path(args.points).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    points = np.load(points_path).astype(np.float32, copy=False)
    print(f"loaded points {points.shape}", flush=True)

    arg_configs = [
        f"DATA.raw_num_points:{int(args.raw_num_points)}",
        f"DATA.ndataset_points:{int(args.raw_num_points)}",
        f"TEST.max_farthest_points:{int(args.max_farthest_points)}",
        f"TEST.num_samples:{int(args.num_samples)}",
    ]
    arg_configs.extend(args.arg_config)
    cfg = config_utils.load_config(
        str(checkpoint_dir),
        batch_size=int(args.forward_passes),
        arg_configs=arg_configs,
    )
    print(f"config raw_num_points={cfg['DATA']['raw_num_points']}", flush=True)

    start = time.time()
    estimator = GraspEstimator(cfg)
    print(f"after estimator {time.time() - start:.3f}s", flush=True)
    if not args.keep_is_training_placeholder:
        estimator.placeholders["is_training_pl"] = False
    estimator.build_network()
    print(f"after build_network {time.time() - start:.3f}s", flush=True)

    saver = tf.train.Saver(save_relative_paths=True)
    session_config = tf.ConfigProto()
    session_config.gpu_options.allow_growth = True
    session_config.allow_soft_placement = True
    sess = tf.Session(config=session_config)
    try:
        estimator.load_weights(sess, saver, str(checkpoint_dir), mode="test")
        print(f"after load_weights {time.time() - start:.3f}s", flush=True)

        pc, _pc_mean = preprocess_pc_for_inference(
            points.squeeze(),
            estimator._num_input_points,
            return_mean=True,
            convert_to_internal_coords=True,
        )
        print(f"after preprocess {time.time() - start:.3f}s {pc.shape}", flush=True)

        pc_batch = pc[np.newaxis, :, :]
        if int(args.forward_passes) > 1:
            pc_batch = np.tile(pc_batch, (int(args.forward_passes), 1, 1))

        feed_dict = {
            estimator.placeholders["pointclouds_pl"]: pc_batch,
        }
        if hasattr(estimator.placeholders["is_training_pl"], "dtype"):
            feed_dict[estimator.placeholders["is_training_pl"]] = False
        print(f"before sess.run {time.time() - start:.3f}s", flush=True)
        pred_grasps_cam, pred_scores, pred_points, offset_pred = sess.run(
            estimator.inference_ops,
            feed_dict=feed_dict,
        )
        print(f"after sess.run {time.time() - start:.3f}s", flush=True)

        pred_grasps_cam = pred_grasps_cam.reshape(-1, *pred_grasps_cam.shape[-2:])
        pred_points = pred_points.reshape(-1, pred_points.shape[-1])
        pred_scores = pred_scores.reshape(-1)
        offset_pred = offset_pred.reshape(-1)

        selection_idcs = estimator.select_grasps(
            pred_points[:, :3],
            pred_scores,
            cfg["TEST"]["max_farthest_points"],
            cfg["TEST"]["num_samples"],
            cfg["TEST"]["first_thres"],
            cfg["TEST"]["second_thres"],
            with_replacement=cfg["TEST"].get("with_replacement", False),
        )
        print(f"after select_grasps {time.time() - start:.3f}s", flush=True)

        summary = {
            "checkpoint_dir": str(checkpoint_dir),
            "points_path": str(points_path),
            "input_point_count": int(points.shape[0]),
            "raw_num_points": int(cfg["DATA"]["raw_num_points"]),
            "forward_passes": int(args.forward_passes),
            "selected_grasp_count": int(len(selection_idcs)),
            "raw_prediction_count": int(pred_grasps_cam.shape[0]),
            "duration_s": time.time() - start,
            "score_max": float(np.max(pred_scores)) if len(pred_scores) else None,
            "score_mean": float(np.mean(pred_scores)) if len(pred_scores) else None,
        }
        if len(selection_idcs):
            top_idx = int(selection_idcs[0])
            summary["top_grasp_translation_xyz_m"] = (
                np.asarray(pred_grasps_cam[top_idx][:3, 3], dtype=float).tolist()
            )
            summary["top_contact_point_xyz_m"] = np.asarray(
                pred_points[top_idx][:3],
                dtype=float,
            ).tolist()
            summary["top_opening_m"] = float(offset_pred[top_idx])

        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=True), flush=True)
    finally:
        sess.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
