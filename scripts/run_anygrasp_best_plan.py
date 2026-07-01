#!/usr/bin/env python3

"""Build a direct execution attempt from a single AnyGrasp top grasp."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = REPO_ROOT / "vendor" / "GALAXEA-A1Z"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from a1z_ext.config import get_socket_path
from a1z_ext.grasping import (
    ANYGRASP_ACTIVE_BINDING_LABEL,
    ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL,
    ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL,
    ExecutablePlan,
    JointTrajectorySegment,
    KeepoutSphere,
    anygrasp_extrinsic_correction_transform,
    anygrasp_item_to_grasp_pose_with_binding_label,
    write_json,
)
from a1z_ext.grasping.contact_graspnet_adapter import (
    ContactGraspNetA1ZAdapter,
    ContactGraspNetA1ZAdapterConfig,
    _invert_transform,
    _joint_margin_score,
    _matrix_to_list,
    _matrix_to_pose,
    _normalize,
    _rigidize_transform,
)
from a1z_ext.grasping.types import to_dict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a direct top-rank AnyGrasp execution plan.")
    parser.add_argument("--result-json", required=True, help="Path to anygrasp_result.json")
    parser.add_argument("--extrinsic-camera-to-base", required=True, help="Path to 4x4 extrinsic_camera_to_base.npy")
    parser.add_argument("--current-joints-rad", default="")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--binding-label", default=ANYGRASP_ACTIVE_BINDING_LABEL, help="How to interpret AnyGrasp raw rotation columns.")
    parser.add_argument("--camera-correction-label", default=ANYGRASP_ACTIVE_CAMERA_CORRECTION_LABEL, help="Additional camera-frame correction applied before camera-to-base extrinsic.")
    parser.add_argument("--extrinsic-correction-label", default=ANYGRASP_ACTIVE_EXTRINSIC_CORRECTION_LABEL, help="Additional correction applied inside extrinsic_camera_to_base before projecting grasps into base frame.")
    parser.add_argument("--task-id", default="anygrasp-best-pick")
    parser.add_argument("--object-id", default="target-object")
    parser.add_argument("--backend", default="anygrasp_best_direct")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "runtime" / "anygrasp_best_direct"))
    parser.add_argument("--frame-id", default="robot_base_frame")
    parser.add_argument("--transform-source", default="extrinsic_camera_to_base")
    parser.add_argument("--end-effector-frame", default="arm_link6")
    parser.add_argument("--pregrasp-offset-m", type=float, default=0.08)
    parser.add_argument("--lift-offset-m", type=float, default=0.10)
    parser.add_argument("--retreat-offset-m", type=float, default=0.04)
    parser.add_argument("--table-height-m", type=float, default=0.0)
    parser.add_argument("--min-tool-height-above-table-m", type=float, default=0.005)
    parser.add_argument("--max-approach-deviation-deg", type=float, default=85.0)
    parser.add_argument("--max-gripper-opening-m", type=float, default=0.096)
    parser.add_argument("--pregrasp-opening-margin-m", type=float, default=0.008)
    parser.add_argument("--min-joint-margin-deg", type=float, default=5.0)
    parser.add_argument("--max-waypoint-delta-rad", type=float, default=2.5)
    parser.add_argument("--ik-dt", type=float, default=0.01)
    parser.add_argument("--ik-pos-threshold-m", type=float, default=5e-4)
    parser.add_argument("--ik-ori-threshold-rad", type=float, default=5e-3)
    parser.add_argument("--ik-damping", type=float, default=1e-6)
    parser.add_argument("--ik-max-iters", type=int, default=800)
    parser.add_argument("--approach-linear-waypoint-count", type=int, default=0)
    parser.add_argument("--ee-grasp-origin-xyz-m", default="[0.04, 0.0, 0.0]")
    parser.add_argument("--ee-opening-axis-xyz", default="[0.0, 0.0, 1.0]")
    parser.add_argument("--ee-approach-axis-xyz", default="[0.0, -1.0, 0.0]")
    parser.add_argument("--keepout-sphere", action="append", default=[])
    parser.add_argument("--grasp-rank", type=int, default=0, help="Rank inside AnyGrasp top_grasps to use directly.")
    parser.add_argument(
        "--require-approach-downward",
        action="store_true",
        help="Require approach axis to point generally downward in base frame.",
    )
    return parser


def _parse_json_value(raw: str, *, expected_len: int | None = None) -> list[float]:
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"expected JSON list, got: {raw}")
    result = [float(item) for item in value]
    if expected_len is not None and len(result) != expected_len:
        raise ValueError(f"expected length {expected_len}, got {len(result)} from {raw}")
    return result


def _send_socket_request(socket_path: str, cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    request = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    try:
        sock.connect(socket_path)
        sock.sendall(request.encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        sock.close()
    if not data:
        raise RuntimeError(f"no response from A1Z server on {socket_path}")
    payload = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("error", "unknown server error")))
    return dict(payload.get("data", {}))


def _load_current_joints(value: str, *, socket_path: str) -> np.ndarray:
    if value:
        candidate = Path(value)
        if candidate.is_file():
            if candidate.suffix.lower() == ".npy":
                joints = np.load(candidate)
            else:
                joints = np.asarray(json.loads(candidate.read_text(encoding="utf-8")), dtype=np.float64)
        else:
            joints = np.asarray(json.loads(value), dtype=np.float64)
        joints = joints.reshape(-1)
        if joints.shape[0] != 6:
            raise ValueError(f"expected 6 current joints, got shape {joints.shape}")
        return joints.astype(np.float64)

    status = _send_socket_request(socket_path, "status")
    pos_deg = status.get("pos_deg")
    if not isinstance(pos_deg, list) or len(pos_deg) < 6:
        raise RuntimeError(f"unexpected status payload: {status}")
    return np.deg2rad(np.asarray(pos_deg[:6], dtype=np.float64))


def _parse_keepout_spheres(raw_values: list[str]) -> list[KeepoutSphere]:
    spheres: list[KeepoutSphere] = []
    for raw in raw_values:
        payload = json.loads(raw)
        center = payload.get("center_xyz")
        radius = payload.get("radius_m")
        if not isinstance(center, list) or len(center) != 3 or radius is None:
            raise ValueError(f"invalid keepout sphere: {raw}")
        spheres.append(
            KeepoutSphere(
                center_xyz=(float(center[0]), float(center[1]), float(center[2])),
                radius_m=float(radius),
                label=str(payload.get("label", "keepout")),
            )
        )
    return spheres


def _load_anygrasp_top_grasp(
    path: str | Path,
    rank: int,
    *,
    binding_label: str,
    camera_correction_label: str,
) -> tuple[dict[str, Any], np.ndarray]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"AnyGrasp result must be a JSON object: {path}")
    if not payload.get("ran", False):
        raise ValueError(f"AnyGrasp result did not run successfully: {payload.get('error', '')}")
    top_grasps = payload.get("top_grasps")
    if not isinstance(top_grasps, list) or not top_grasps:
        raise ValueError(f"AnyGrasp result missing top_grasps: {path}")
    if rank < 0 or rank >= len(top_grasps):
        raise ValueError(f"grasp-rank out of range: {rank} for {len(top_grasps)} grasps")
    item = dict(top_grasps[rank])
    return item, anygrasp_item_to_grasp_pose_with_binding_label(
        item,
        binding_label=binding_label,
        camera_correction_label=camera_correction_label,
    )


def _build_poses(grasp_base: np.ndarray, config: ContactGraspNetA1ZAdapterConfig) -> dict[str, np.ndarray]:
    grasp_to_ee = _invert_transform(config.ee_to_grasp_transform())
    tool_grasp = _rigidize_transform(grasp_base @ grasp_to_ee)
    approach = _normalize(grasp_base[:3, 2])
    retreat = -approach
    table_normal = _normalize(np.asarray(config.table_normal_base, dtype=np.float64))
    tool_pregrasp = tool_grasp.copy()
    tool_pregrasp[:3, 3] += retreat * float(config.pregrasp_offset_m)
    tool_lift = tool_grasp.copy()
    tool_lift[:3, 3] += table_normal * float(config.lift_offset_m)
    tool_retreat = tool_lift.copy()
    tool_retreat[:3, 3] += retreat * float(config.retreat_offset_m)
    return {
        "grasp": _rigidize_transform(tool_grasp),
        "pregrasp": _rigidize_transform(tool_pregrasp),
        "lift": _rigidize_transform(tool_lift),
        "retreat": _rigidize_transform(tool_retreat),
    }


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    top_grasp, grasp_cam = _load_anygrasp_top_grasp(
        args.result_json,
        int(args.grasp_rank),
        binding_label=str(args.binding_label),
        camera_correction_label=str(args.camera_correction_label),
    )
    current_q = _load_current_joints(args.current_joints_rad, socket_path=args.socket_path)
    extrinsic_camera_to_base = np.load(Path(args.extrinsic_camera_to_base)).astype(np.float64, copy=False)
    if extrinsic_camera_to_base.shape != (4, 4):
        raise ValueError(f"extrinsic_camera_to_base must be 4x4, got {extrinsic_camera_to_base.shape}")
    extrinsic_camera_to_base = (
        np.asarray(extrinsic_camera_to_base, dtype=np.float64).reshape(4, 4)
        @ anygrasp_extrinsic_correction_transform(correction_label=str(args.extrinsic_correction_label))
    )

    config = ContactGraspNetA1ZAdapterConfig(
        end_effector_frame=args.end_effector_frame,
        frame_id=args.frame_id,
        transform_source=args.transform_source,
        pregrasp_offset_m=args.pregrasp_offset_m,
        lift_offset_m=args.lift_offset_m,
        retreat_offset_m=args.retreat_offset_m,
        table_height_m=args.table_height_m,
        min_tool_height_above_table_m=args.min_tool_height_above_table_m,
        require_approach_downward=bool(args.require_approach_downward),
        max_approach_deviation_deg=args.max_approach_deviation_deg,
        max_gripper_opening_m=args.max_gripper_opening_m,
        pregrasp_opening_margin_m=args.pregrasp_opening_margin_m,
        min_joint_margin_deg=args.min_joint_margin_deg,
        max_waypoint_delta_rad=args.max_waypoint_delta_rad,
        ik_dt=args.ik_dt,
        ik_pos_threshold_m=args.ik_pos_threshold_m,
        ik_ori_threshold_rad=args.ik_ori_threshold_rad,
        ik_damping=args.ik_damping,
        ik_max_iters=args.ik_max_iters,
        approach_linear_waypoint_count=args.approach_linear_waypoint_count,
        ee_grasp_origin_xyz_m=tuple(_parse_json_value(args.ee_grasp_origin_xyz_m, expected_len=3)),
        ee_opening_axis_xyz=tuple(_parse_json_value(args.ee_opening_axis_xyz, expected_len=3)),
        ee_approach_axis_xyz=tuple(_parse_json_value(args.ee_approach_axis_xyz, expected_len=3)),
        keepout_spheres=_parse_keepout_spheres(args.keepout_sphere),
    )
    contact_adapter = ContactGraspNetA1ZAdapter(config=config)
    assert contact_adapter._kinematics is not None

    grasp_base = _rigidize_transform(extrinsic_camera_to_base @ grasp_cam)
    poses = _build_poses(grasp_base, config)
    lower = np.asarray(contact_adapter._kinematics._model.lowerPositionLimit, dtype=np.float64).reshape(-1)
    upper = np.asarray(contact_adapter._kinematics._model.upperPositionLimit, dtype=np.float64).reshape(-1)
    solutions = contact_adapter._solve_waypoint_sequence(
        current_q=current_q,
        poses=poses,
        lower=lower,
        upper=upper,
    )
    ik_summary = {stage: solved for stage, (solved, _) in solutions.items()}
    joint_targets = {
        stage: None if q is None else q.astype(float).tolist()
        for stage, (_, q) in solutions.items()
    }

    continuity_ok = contact_adapter._continuity_ok(joint_targets)
    margin_flags: list[bool] = []
    margin_scores: list[float] = []
    for stage in ("pregrasp", "grasp", "lift", "retreat"):
        solved, q = solutions[stage]
        if not solved or q is None:
            continue
        margin_ok_stage, margin_score = _joint_margin_score(
            q=q,
            lower=lower,
            upper=upper,
            margin_rad=config.min_joint_margin_rad,
        )
        margin_flags.append(margin_ok_stage)
        margin_scores.append(margin_score)
    joint_margin_ok = bool(margin_flags) and all(margin_flags)
    min_margin_score = min(margin_scores) if margin_scores else 0.0

    approach = _normalize(grasp_base[:3, 2])
    retreat = -approach
    table_normal = _normalize(np.asarray(config.table_normal_base, dtype=np.float64))
    downward_alignment_threshold = np.cos(config.max_approach_deviation_rad)
    approach_alignment = float(np.clip(-np.dot(approach, table_normal), -1.0, 1.0))
    topdown_ok = (not config.require_approach_downward) or (approach_alignment >= downward_alignment_threshold)
    table_clearance_ok = all(
        float(pose[2, 3]) >= (config.table_height_m + config.min_tool_height_above_table_m)
        for pose in poses.values()
    )
    camera_keepout_ok = contact_adapter._camera_keepout_ok(poses)
    safety_summary = {
        "topdown_ok": bool(topdown_ok),
        "table_clearance_ok": bool(table_clearance_ok),
        "camera_keepout_ok": bool(camera_keepout_ok),
        "joint_margin_ok": bool(joint_margin_ok),
        "continuity_ok": bool(continuity_ok),
    }
    failure_reasons = contact_adapter._failure_reasons(
        ik_summary=ik_summary,
        safety_summary=safety_summary,
    )

    result_payload: dict[str, Any] = {
        "selected_rank": int(args.grasp_rank),
        "active_binding_label": str(args.binding_label),
        "active_camera_correction_label": str(args.camera_correction_label),
        "active_extrinsic_correction_label": str(args.extrinsic_correction_label),
        "raw_score": float(top_grasp["score"]),
        "width_m": float(top_grasp["width_m"]),
        "height_m": float(top_grasp["height_m"]),
        "depth_m": float(top_grasp["depth_m"]),
        "source_model": "anygrasp_best_direct",
        "transform_source": args.transform_source,
        "current_q_rad": current_q.astype(float).tolist(),
        "ee_to_grasp_transform": _matrix_to_list(config.ee_to_grasp_transform()),
        "grasp_pose_cam": _matrix_to_list(grasp_cam),
        "grasp_pose_base": _matrix_to_list(grasp_base),
        "tool_pregrasp_pose_matrix": _matrix_to_list(poses["pregrasp"]),
        "tool_grasp_pose_matrix": _matrix_to_list(poses["grasp"]),
        "tool_lift_pose_matrix": _matrix_to_list(poses["lift"]),
        "tool_retreat_pose_matrix": _matrix_to_list(poses["retreat"]),
        "pose_summary": {
            "grasp_pose_base": to_dict(_matrix_to_pose(grasp_base)),
            "tool_pregrasp_pose": to_dict(_matrix_to_pose(poses["pregrasp"])),
            "tool_grasp_pose": to_dict(_matrix_to_pose(poses["grasp"])),
            "tool_lift_pose": to_dict(_matrix_to_pose(poses["lift"])),
            "tool_retreat_pose": to_dict(_matrix_to_pose(poses["retreat"])),
        },
        "approach_vector_xyz": approach.astype(float).tolist(),
        "retreat_vector_xyz": retreat.astype(float).tolist(),
        "ik_summary": ik_summary,
        "joint_targets_rad": joint_targets,
        "safety_summary": safety_summary,
        "failure_reasons": failure_reasons,
        "metadata": {
            "approach_down_alignment": approach_alignment,
            "min_joint_margin_score": float(min_margin_score),
            "anygrasp_result_json": str(Path(args.result_json).resolve()),
            "active_binding_label": str(args.binding_label),
            "active_camera_correction_label": str(args.camera_correction_label),
            "active_extrinsic_correction_label": str(args.extrinsic_correction_label),
        },
    }

    result_path = output_dir / "anygrasp_best_direct_result.json"
    if failure_reasons:
        result_path.write_text(json.dumps(result_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(json.dumps({"result_path": str(result_path), "ik_summary": ik_summary, "failure_reasons": failure_reasons}, ensure_ascii=True))
        return 1

    segments = contact_adapter._build_approach_segments(
        type(
            "_TmpCandidate",
            (),
            {
                "joint_targets_rad": joint_targets,
                "tool_pregrasp_pose_matrix": _matrix_to_list(poses["pregrasp"]),
                "tool_grasp_pose_matrix": _matrix_to_list(poses["grasp"]),
            },
        )()
    )
    if segments is None:
        result_payload["failure_reasons"] = ["approach_segment_build_failed"]
        result_path.write_text(json.dumps(result_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(json.dumps({"result_path": str(result_path), "failure_reasons": result_payload["failure_reasons"]}, ensure_ascii=True))
        return 1

    open_command = float(
        np.clip(
            (min(float(top_grasp["width_m"]), config.max_gripper_opening_m) + config.pregrasp_opening_margin_m)
            / config.max_gripper_opening_m,
            0.0,
            1.0,
        )
    )
    plan = ExecutablePlan(
        plan_id="anygrasp-best-direct",
        task_id=args.task_id,
        selected_grasp_candidate_id=f"anygrasp-rank-{int(args.grasp_rank)}",
        backend=args.backend,
        frame_id=args.frame_id,
        joint_trajectory_segments=[
            JointTrajectorySegment(
                segment_type="move_to_pregrasp",
                target_joint_rad=joint_targets["pregrasp"] or [],
                timeout_s=float(config.segment_timeouts_s["move_to_pregrasp"]),
            ),
            *segments,
            JointTrajectorySegment(
                segment_type="lift",
                target_joint_rad=joint_targets["lift"] or [],
                timeout_s=float(config.segment_timeouts_s["lift"]),
            ),
            JointTrajectorySegment(
                segment_type="retreat",
                target_joint_rad=joint_targets["retreat"] or [],
                timeout_s=float(config.segment_timeouts_s["retreat"]),
            ),
        ],
        gripper_commands={
            "open_before_grasp": open_command,
            "close_after_approach": float(config.close_gripper_command),
        },
        ik_summary=dict(ik_summary),
        safety_summary=dict(safety_summary),
        candidate_rank=int(args.grasp_rank),
        source_model="anygrasp_best_direct",
    )

    result_payload["plan_summary"] = {
        "selected_grasp_candidate_id": plan.selected_grasp_candidate_id,
        "gripper_commands": dict(plan.gripper_commands),
        "segment_count": int(len(plan.joint_trajectory_segments)),
    }
    result_path.write_text(json.dumps(result_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    plan_path = output_dir / "selected_plan.json"
    write_json(plan_path, plan)
    print(json.dumps({"result_path": str(result_path), "plan_path": str(plan_path), "ik_summary": ik_summary}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
