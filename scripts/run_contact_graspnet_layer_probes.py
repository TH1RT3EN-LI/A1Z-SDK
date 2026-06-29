#!/usr/bin/env python3

"""Run focused PointNet++ layer probes inside the Contact-GraspNet stack."""

import argparse
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


def _add_paths():
    for path in (
        CGN_ROOT,
        CGN_ROOT / "contact_graspnet",
        CGN_ROOT / "pointnet2" / "utils",
        CGN_ROOT / "pointnet2" / "tf_ops" / "sampling",
        CGN_ROOT / "pointnet2" / "tf_ops" / "grouping",
        CGN_ROOT / "pointnet2" / "tf_ops" / "3d_interpolation",
    ):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def build_parser():
    parser = argparse.ArgumentParser(description="Probe Contact-GraspNet PointNet++ sublayers.")
    parser.add_argument(
        "--mode",
        choices=["fps", "query_group", "conv_only", "conv_only_bn", "msg1", "msg1_bn", "sa_nobn", "sa", "fp"],
        required=True,
    )
    parser.add_argument("--device", default="/gpu:0")
    return parser


def _session_config():
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config.allow_soft_placement = True
    return config


def _format_shapes(values):
    if not isinstance(values, (list, tuple)):
        values = [values]

    parts = []
    for value in values:
        shape = getattr(value, "shape", None)
        if shape is None:
            parts.append(type(value).__name__)
        else:
            parts.append(str(tuple(shape)))
    return ", ".join(parts)


def _run_fetches(fetches):
    print("graph ready", flush=True)
    wall_start = time.time()
    with tf.Session(config=_session_config()) as sess:
        print("before init", flush=True)
        init_start = time.time()
        sess.run(tf.global_variables_initializer())
        print(f"after init {time.time() - init_start:.3f}s", flush=True)

        for name, tensors in fetches:
            stage_start = time.time()
            print(f"before {name}", flush=True)
            values = sess.run(tensors)
            print(f"after {name} {time.time() - stage_start:.3f}s {_format_shapes(values)}", flush=True)
    print(f"done {time.time() - wall_start:.3f}s", flush=True)


def run_fps(device):
    from tf_sampling import farthest_point_sample

    xyz_np = np.random.rand(1, 256, 3).astype("float32")

    with tf.device(device):
        xyz = tf.constant(xyz_np)
        fps_idx = farthest_point_sample(128, xyz)

    _run_fetches([("fps", fps_idx)])


def run_query_group(device):
    from tf_grouping import group_point, query_ball_point

    xyz_np = np.random.rand(1, 256, 3).astype("float32")
    new_xyz_np = xyz_np[:, :128, :]

    with tf.device(device):
        xyz = tf.constant(xyz_np)
        new_xyz = tf.constant(new_xyz_np)
        idx, pts_cnt = query_ball_point(0.04, 64, xyz, new_xyz)
        grouped_xyz = group_point(xyz, idx)

    _run_fetches(
        [
            ("query_ball", [idx, pts_cnt]),
            ("group", grouped_xyz),
        ]
    )


def run_conv_only(device, use_bn):
    import tf_util

    grouped_xyz_np = np.random.rand(1, 128, 64, 3).astype("float32")

    with tf.device(device):
        grouped_points = tf.constant(grouped_xyz_np)
        for layer_idx, num_out_channel in enumerate([32, 32, 64]):
            grouped_points = tf_util.conv2d(
                grouped_points,
                num_out_channel,
                [1, 1],
                padding="VALID",
                stride=[1, 1],
                bn=use_bn,
                is_training=False,
                bn_decay=None,
                scope=f"conv_only_{'bn' if use_bn else 'plain'}_{layer_idx}",
            )
        reduced_points = tf.reduce_max(grouped_points, axis=[2])

    _run_fetches([("conv_reduce", reduced_points)])


def run_msg1(device, use_bn):
    from tf_grouping import group_point, query_ball_point
    from tf_sampling import farthest_point_sample, gather_point
    import tf_util

    xyz_np = np.random.rand(1, 256, 3).astype("float32")

    with tf.device(device):
        xyz = tf.constant(xyz_np)
        fps_idx = farthest_point_sample(128, xyz)
        new_xyz = gather_point(xyz, fps_idx)
        idx, pts_cnt = query_ball_point(0.04, 64, xyz, new_xyz)
        grouped_xyz = group_point(xyz, idx)
        centered_grouped_xyz = grouped_xyz - tf.tile(tf.expand_dims(new_xyz, 2), [1, 1, 64, 1])

        grouped_points = centered_grouped_xyz
        for layer_idx, num_out_channel in enumerate([32, 32, 64]):
            grouped_points = tf_util.conv2d(
                grouped_points,
                num_out_channel,
                [1, 1],
                padding="VALID",
                stride=[1, 1],
                bn=use_bn,
                is_training=False,
                bn_decay=None,
                scope=f"msg1_conv{layer_idx}",
            )
        reduced_points = tf.reduce_max(grouped_points, axis=[2])

    _run_fetches(
        [
            ("fps", fps_idx),
            ("fps_gather", new_xyz),
            ("query_ball", [idx, pts_cnt]),
            ("group", centered_grouped_xyz),
            ("conv_reduce", reduced_points),
        ]
    )


def run_sa(device, use_bn):
    from pointnet_util import pointnet_sa_module_msg

    xyz_np = np.random.rand(1, 256, 3).astype("float32")

    with tf.device(device):
        xyz = tf.constant(xyz_np)
        new_xyz, new_points = pointnet_sa_module_msg(
            xyz,
            None,
            128,
            [0.02, 0.04, 0.08],
            [32, 64, 128],
            [[32, 32, 64], [64, 64, 128], [64, 96, 128]],
            is_training=False,
            bn_decay=None,
            scope="layer1_probe",
            bn=use_bn,
        )

    _run_fetches([("sa_run", [new_xyz, new_points])])


def run_fp(device):
    from pointnet_util import pointnet_fp_module

    xyz1_np = np.random.rand(1, 128, 3).astype("float32")
    xyz2_np = np.random.rand(1, 32, 3).astype("float32")
    pts1_np = np.random.rand(1, 128, 32).astype("float32")
    pts2_np = np.random.rand(1, 32, 64).astype("float32")

    with tf.device(device):
        xyz1 = tf.constant(xyz1_np)
        xyz2 = tf.constant(xyz2_np)
        pts1 = tf.constant(pts1_np)
        pts2 = tf.constant(pts2_np)
        out = pointnet_fp_module(
            xyz1,
            xyz2,
            pts1,
            pts2,
            [64, 64],
            is_training=False,
            bn_decay=None,
            scope="fp_probe",
        )

    _run_fetches([("fp_run", out)])


def main():
    args = build_parser().parse_args()
    _add_paths()
    if args.mode == "fps":
        run_fps(args.device)
    elif args.mode == "query_group":
        run_query_group(args.device)
    elif args.mode == "conv_only":
        run_conv_only(args.device, use_bn=False)
    elif args.mode == "conv_only_bn":
        run_conv_only(args.device, use_bn=True)
    elif args.mode == "msg1":
        run_msg1(args.device, use_bn=False)
    elif args.mode == "msg1_bn":
        run_msg1(args.device, use_bn=True)
    elif args.mode == "sa_nobn":
        run_sa(args.device, use_bn=False)
    elif args.mode == "sa":
        run_sa(args.device, use_bn=True)
    else:
        run_fp(args.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
