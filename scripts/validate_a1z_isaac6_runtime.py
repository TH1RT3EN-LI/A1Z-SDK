#!/usr/bin/env python3
"""Validate the A1Z asset and native runtime inside Isaac Sim 6 / Kit 110."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from isaacsim import SimulationApp


def parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        default=str(root_dir / "build" / "scenes" / "A1Z_G1Z_world.usd"),
    )
    parser.add_argument(
        "--articulation-root",
        default="/World/A1Z_G1Z/Geometry",
    )
    parser.add_argument("--physics-dt", type=float, default=1.0 / 60.0)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--output", default="")
    args, _ = parser.parse_known_args()
    if not math.isfinite(args.physics_dt) or args.physics_dt <= 0.0:
        parser.error("--physics-dt must be finite and positive")
    if args.steps < 2:
        parser.error("--steps must be at least 2")
    return args


ARGS = parse_args()
SIMULATION_APP = SimulationApp(
    {
        "headless": True,
        "renderer": "RayTracedLighting",
        "width": 320,
        "height": 240,
    }
)

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from isaacsim.core.simulation_manager import SimulationEvent, SimulationManager  # noqa: E402
from pxr import PhysxSchema, UsdPhysics  # noqa: E402

from a1z_ext.robots.isaac6_backend import (  # noqa: E402
    A1ZArticulationCommand,
    Isaac6ArticulationAdapter,
    Isaac6RigidPrimAdapter,
    prepare_contact_tracking,
)
from a1z_ext.runtime.d405 import attach_d405_wrist_camera  # noqa: E402
from a1z_ext.runtime.d405.session import D405CaptureSettings, D405FrameSession  # noqa: E402


EXPECTED_DOF_NAMES = (
    "arm_joint1",
    "arm_joint2",
    "arm_joint3",
    "arm_joint4",
    "arm_joint5",
    "arm_joint6",
    "gripper_finger_left_joint",
    "gripper_finger_rIght_joint",
)
FINGER_BODY_PATHS = (
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/"
    "arm_link4/arm_link5/arm_link6/gripper_finger_left_link",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/"
    "arm_link4/arm_link5/arm_link6/gripper_finger_rIght_link",
)
CONTACT_FILTER_PATHS = (
    "/World/TrashSet/marker_upright",
    "/World/TrashSet/can_crushed",
)


def _numpy(values) -> np.ndarray:
    if hasattr(values, "numpy"):
        values = values.numpy()
    return np.asarray(values)


def _attr_bool(prim, name: str, default: bool) -> bool:
    attr = prim.GetAttribute(name)
    if not attr.IsValid() or attr.Get() is None:
        return default
    return bool(attr.Get())


def _stage_audit(stage) -> dict:
    joint_paths: list[str] = []
    fixed_joint_paths: list[str] = []
    suspicious_constraint_paths: list[str] = []
    trash_rigid_bodies: list[dict] = []

    for prim in stage.Traverse():
        prim_path = str(prim.GetPath())
        if prim.IsA(UsdPhysics.Joint):
            joint_paths.append(prim_path)
            if prim.IsA(UsdPhysics.FixedJoint):
                fixed_joint_paths.append(prim_path)
            body_targets = []
            for rel_name in ("physics:body0", "physics:body1"):
                rel = prim.GetRelationship(rel_name)
                if rel.IsValid():
                    body_targets.extend(str(value) for value in rel.GetTargets())
            if any("/TrashSet/" in value for value in body_targets):
                suspicious_constraint_paths.append(prim_path)

        if "/TrashSet/" not in prim_path or not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        collision_count = sum(
            1
            for candidate in stage.TraverseAll()
            if candidate.GetPath().HasPrefix(prim.GetPath())
            and candidate.HasAPI(UsdPhysics.CollisionAPI)
        )
        physx_body = PhysxSchema.PhysxRigidBodyAPI(prim)
        disable_gravity = False
        if physx_body:
            value = physx_body.GetDisableGravityAttr().Get()
            disable_gravity = bool(value) if value is not None else False
        trash_rigid_bodies.append(
            {
                "path": prim_path,
                "rigid_body_enabled": _attr_bool(
                    prim,
                    "physics:rigidBodyEnabled",
                    True,
                ),
                "kinematic_enabled": _attr_bool(
                    prim,
                    "physics:kinematicEnabled",
                    False,
                ),
                "gravity_enabled": not disable_gravity,
                "collision_count": collision_count,
            }
        )

    return {
        "joint_paths": joint_paths,
        "fixed_joint_paths": fixed_joint_paths,
        "suspicious_target_constraint_paths": suspicious_constraint_paths,
        "trash_rigid_bodies": trash_rigid_bodies,
    }


def _open_stage(stage_path: str) -> None:
    result = stage_utils.open_stage(str(Path(stage_path).resolve()))
    success = bool(result[0]) if isinstance(result, tuple) else bool(result)
    if not success:
        raise RuntimeError(f"failed to open stage: {stage_path}")
    while stage_utils.is_stage_loading():
        SIMULATION_APP.update()
    for _ in range(3):
        SIMULATION_APP.update()


def validate() -> dict:
    _open_stage(ARGS.stage)
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Isaac USD context has no stage")

    audit = _stage_audit(stage)
    d405_attachment = attach_d405_wrist_camera(stage)
    if d405_attachment is None:
        raise RuntimeError("D405 attachment could not be authored")
    color_camera_path = str(d405_attachment.camera_paths.get("color") or "")
    depth_camera_path = str(d405_attachment.camera_paths.get("depth") or "")
    if not color_camera_path or not depth_camera_path:
        raise RuntimeError("D405 attachment did not expose both camera paths")

    prepare_contact_tracking(list(FINGER_BODY_PATHS), threshold=0.0)
    SimulationManager.setup_simulation(dt=ARGS.physics_dt, device="cpu")
    articulation = Isaac6ArticulationAdapter(ARGS.articulation_root)
    d405_session = None

    callback_samples: list[float] = []

    def on_pre_step(step_dt: float, context) -> None:
        del context
        callback_samples.append(float(step_dt))

    callback_id = SimulationManager.register_callback(
        on_pre_step,
        event=SimulationEvent.PHYSICS_PRE_STEP,
    )
    try:
        app_utils.play()
        for _ in range(ARGS.steps):
            SIMULATION_APP.update()

        articulation.initialize()
        contact_view = Isaac6RigidPrimAdapter(
            list(FINGER_BODY_PATHS),
            contact_filter_prim_paths_expr=[
                list(CONTACT_FILTER_PATHS),
                list(CONTACT_FILTER_PATHS),
            ],
            max_contact_count=128,
        )
        contact_view.initialize()
        contact_data = contact_view.get_contact_force_data(dt=1.0)
        pair_contact_counts = _numpy(contact_data[4])
        pair_contact_starts = _numpy(contact_data[5])
        dof_names = articulation.dof_names
        positions_before = articulation.get_joint_positions()
        velocities_before = articulation.get_joint_velocities()
        properties = articulation.dof_properties
        d405_session = D405FrameSession(
            attachment=d405_attachment,
            color_camera_path=color_camera_path,
            depth_camera_path=depth_camera_path,
            settings=D405CaptureSettings(
                width=320,
                height=240,
                frequency_hz=10,
                annotator_device="cuda",
                zlib_level=1,
                encode_workers=2,
            ),
            stage_path=str(Path(ARGS.stage).resolve()),
        )
        if not d405_session.warmup(articulation.get_joint_positions, app=SIMULATION_APP):
            raise RuntimeError("D405 failed to produce its first completed RGB-D frame")
        first_d405_capture = d405_session.latest_capture()
        if first_d405_capture is None:
            raise RuntimeError("D405 warmup completed without a readable frame")
        first_d405_timestamp_ns = int(first_d405_capture.observation.timestamp_ns)

        second_d405_capture = None
        for _ in range(240):
            SIMULATION_APP.update()
            d405_session.update(articulation.get_joint_positions())
            candidate = d405_session.latest_capture()
            if (
                candidate is not None
                and int(candidate.observation.timestamp_ns) > first_d405_timestamp_ns
            ):
                second_d405_capture = candidate
                break
        if second_d405_capture is None:
            raise RuntimeError("D405 timestamp did not advance to a second RGB-D frame")
        d405_payload = d405_session.latest_payload(fresh=False)
        d405_health = d405_session.health()

        articulation.apply_action(
            A1ZArticulationCommand(joint_positions=positions_before.copy())
        )
        for _ in range(ARGS.steps):
            SIMULATION_APP.update()
        positions_after = articulation.get_joint_positions()
        velocities_after = articulation.get_joint_velocities()
    finally:
        if d405_session is not None:
            d405_session.close()
        app_utils.stop()
        SIMULATION_APP.update()
        SimulationManager.deregister_callback(callback_id)

    scene_dt = float(SimulationManager.get_physics_scenes()[0].get_dt())
    left_index = dof_names.index("gripper_finger_left_joint")
    right_index = dof_names.index("gripper_finger_rIght_joint")
    lower = np.asarray(properties["lower"], dtype=np.float64)
    upper = np.asarray(properties["upper"], dtype=np.float64)
    finite_state = bool(
        np.all(np.isfinite(positions_before))
        and np.all(np.isfinite(positions_after))
        and np.all(np.isfinite(velocities_before))
        and np.all(np.isfinite(velocities_after))
    )
    callback_dt_valid = bool(
        callback_samples
        and all(
            math.isfinite(value) and abs(value - scene_dt) <= 1.0e-6
            for value in callback_samples
        )
    )
    profile_limits_match = bool(
        abs(float(lower[left_index]) - 0.0) <= 1.0e-6
        and abs(float(upper[left_index]) - 0.048) <= 1.0e-6
        and abs(float(lower[right_index]) + 0.048) <= 1.0e-6
        and abs(float(upper[right_index]) - 0.0) <= 1.0e-6
    )
    target_bodies_valid = bool(
        audit["trash_rigid_bodies"]
        and all(
            item["rigid_body_enabled"]
            and not item["kinematic_enabled"]
            and item["gravity_enabled"]
            and item["collision_count"] > 0
            for item in audit["trash_rigid_bodies"]
        )
    )
    second_rgb = np.asarray(second_d405_capture.rgb)
    second_depth = np.asarray(second_d405_capture.depth_m)
    rgb_mean = float(np.mean(second_rgb, dtype=np.float64))
    rgb_nonzero_ratio = float(np.count_nonzero(second_rgb) / second_rgb.size)
    valid_depth = np.isfinite(second_depth) & (second_depth > 0.0)
    valid_depth_ratio = float(np.count_nonzero(valid_depth) / second_depth.size)
    d405_valid = bool(
        d405_health["ready"]
        and first_d405_timestamp_ns
        < int(second_d405_capture.observation.timestamp_ns)
        == int(d405_payload["timestamp_ns"])
        and second_rgb.shape[:2] == (240, 320)
        and second_depth.shape[:2] == (240, 320)
        and int(d405_payload["rgb"]["compression_level"]) == 1
        and int(d405_payload["depth"]["compression_level"]) == 1
    )
    d405_content_valid = bool(
        rgb_mean >= 1.0
        and rgb_nonzero_ratio >= 0.01
        and valid_depth_ratio >= 0.01
    )
    checks = {
        "dof_order_matches": tuple(dof_names) == EXPECTED_DOF_NAMES,
        "finite_readback": finite_state,
        "physics_callback_advanced": len(callback_samples) >= ARGS.steps,
        "physics_callback_dt_valid": callback_dt_valid,
        "gripper_profile_limits_match": profile_limits_match,
        "no_target_constraints": not audit["suspicious_target_constraint_paths"],
        "trash_targets_dynamic": target_bodies_valid,
        "contact_tensor_shape_matches_two_fingers_by_two_filters": (
            pair_contact_counts.shape == (2, 2)
            and pair_contact_starts.shape == (2, 2)
        ),
        "d405_first_frame_and_monotonic_rgbd": d405_valid,
        "d405_nonblack_rgb_and_valid_depth": d405_content_valid,
    }
    return {
        "schema_version": 1,
        "valid": all(checks.values()),
        "stage": str(Path(ARGS.stage).resolve()),
        "articulation_root": ARGS.articulation_root,
        "checks": checks,
        "runtime": {
            "physics_dt_s": scene_dt,
            "physics_callback_count": len(callback_samples),
            "dof_names": list(dof_names),
            "positions_before": np.asarray(positions_before).tolist(),
            "positions_after": np.asarray(positions_after).tolist(),
            "contact_pair_counts_shape": list(pair_contact_counts.shape),
            "contact_pair_starts_shape": list(pair_contact_starts.shape),
        },
        "d405": {
            "ready": bool(d405_health["ready"]),
            "capture_mode": d405_health["capture_mode"],
            "capture_generation": int(d405_health["capture_generation"]),
            "first_timestamp_ns": first_d405_timestamp_ns,
            "second_timestamp_ns": int(second_d405_capture.observation.timestamp_ns),
            "rgb_shape": list(second_rgb.shape),
            "depth_shape": list(second_depth.shape),
            "rgb_mean": rgb_mean,
            "rgb_nonzero_ratio": rgb_nonzero_ratio,
            "valid_depth_ratio": valid_depth_ratio,
            "payload_encode_ms": d405_health["last_payload_encode_ms"],
            "payload_b64_bytes": int(d405_health["last_payload_b64_bytes"]),
            "color_camera_path": color_camera_path,
            "depth_camera_path": depth_camera_path,
        },
        "asset_audit": audit,
    }


def main() -> int:
    try:
        report = validate()
        encoded = json.dumps(report, indent=2, sort_keys=True)
        print(encoded)
        if ARGS.output:
            output_path = Path(ARGS.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(encoded + "\n", encoding="utf-8")
        return 0 if report["valid"] else 1
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    finally:
        SIMULATION_APP.close()


if __name__ == "__main__":
    raise SystemExit(main())
