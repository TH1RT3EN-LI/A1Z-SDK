#!/usr/bin/env python3
"""Compare A1Z J4 gravity compensation modes in Isaac Sim 6.

The experiment intentionally uses the physical SDK gains and the same
Pinocchio inverse-dynamics feedforward path as the real SocketCAN backend.
It runs a nominal matched-model case, J4 under-compensation cases, and a
position-hold control case from the same initial pose.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from isaacsim import SimulationApp


ROOT_DIR = Path(__file__).resolve().parents[1]


def _float_list(raw: str, *, count: int, option: str) -> list[float]:
    values = [float(value.strip()) for value in raw.split(",")]
    if len(values) != count or not all(math.isfinite(value) for value in values):
        raise argparse.ArgumentTypeError(f"{option} requires {count} finite comma-separated values")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        default=str(ROOT_DIR / "build" / "scenes" / "A1Z_G1Z_world.usd"),
    )
    parser.add_argument(
        "--control-urdf",
        default=str(
            ROOT_DIR
            / "build"
            / "robot_packages"
            / "A1Z_G1Z"
            / "urdf"
            / "A1Z_G1Z_control.urdf"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get(
            "A1Z_J4_TEST_OUTPUT_DIR",
            str(ROOT_DIR / "runtime" / "validation" / "a1z_j4_gravity"),
        ),
    )
    parser.add_argument("--articulation-root", default="/World/A1Z_G1Z/Geometry")
    parser.add_argument("--physics-dt", type=float, default=1.0 / 250.0)
    parser.add_argument("--duration-s", type=float, default=3.0)
    parser.add_argument("--pose-deg", default="0,60,-60,0,0,0")
    parser.add_argument("--j4-undercomp-scales", default="0.9,0.75")
    args, _ = parser.parse_known_args()
    if not math.isfinite(args.physics_dt) or not 0.0 < args.physics_dt <= 0.02:
        parser.error("--physics-dt must be finite and within (0, 0.02]")
    if not math.isfinite(args.duration_s) or args.duration_s < 3.0:
        parser.error("--duration-s must be at least 3.0 seconds")
    args.pose_deg = _float_list(args.pose_deg, count=6, option="--pose-deg")
    scales = [float(value.strip()) for value in args.j4_undercomp_scales.split(",")]
    if not scales or not all(math.isfinite(value) and 0.0 < value < 1.0 for value in scales):
        parser.error("--j4-undercomp-scales must contain values within (0, 1)")
    args.j4_undercomp_scales = scales
    return args


ARGS = parse_args()
SIMULATION_APP = SimulationApp(
    {
        "headless": True,
        "renderer": "RayTracedLighting",
        "width": 640,
        "height": 480,
    }
)

# Isaac and project imports must happen after SimulationApp starts.
import carb.settings  # noqa: E402
import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from isaacsim.core.rendering_manager import RenderingManager  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, UsdGeom, UsdLux, UsdPhysics  # noqa: E402


def _extend_python_path() -> None:
    configured_isaac_root = os.environ.get("ISAAC_SIM_DIR") or os.environ.get("ISAAC_SIM_ROOT")
    if configured_isaac_root:
        isaac_root = Path(configured_isaac_root).resolve()
    else:
        executable = Path(sys.executable).resolve()
        isaac_root = executable.parents[3] if len(executable.parents) > 3 else executable.parent
    pink_prebundle = isaac_root / "exts" / "isaacsim.robot_motion.pink" / "pip_prebundle"
    candidates = [
        ROOT_DIR,
        ROOT_DIR / "vendor" / "GALAXEA-A1Z",
        pink_prebundle,
        pink_prebundle / "cmeel.prefix" / "lib" / "python3.12" / "site-packages",
    ]
    for candidate in candidates:
        value = str(candidate)
        if candidate.exists() and value not in sys.path:
            sys.path.insert(0, value)


_extend_python_path()

from a1z.robots.kinematics import Kinematics  # noqa: E402
from a1z_ext.config import get_control_defaults  # noqa: E402
from a1z_ext.robots.get_robot import create_a1z_robot  # noqa: E402
from a1z_ext.robots.isaac6_backend import Isaac6WorldView  # noqa: E402


REAL_KP = np.array([30.0, 30.0, 30.0, 20.0, 5.0, 5.0], dtype=np.float64)
REAL_KD = np.array([1.0, 1.0, 1.0, 0.5, 0.5, 0.5], dtype=np.float64)
ARM_DOF_NAMES = tuple(f"arm_joint{index}" for index in range(1, 7))


def _open_stage(path: Path) -> None:
    result = stage_utils.open_stage(str(path.resolve()))
    success = bool(result[0]) if isinstance(result, tuple) else bool(result)
    if not success:
        raise RuntimeError(f"failed to open stage: {path}")
    while stage_utils.is_stage_loading():
        SIMULATION_APP.update()
    for _ in range(5):
        SIMULATION_APP.update()


def _ensure_lighting(stage) -> None:
    dome = UsdLux.DomeLight.Define(stage, "/World/J4TestDomeLight")
    dome.CreateIntensityAttr().Set(300.0)
    distant = UsdLux.DistantLight.Define(stage, "/World/J4TestDistantLight")
    distant.CreateIntensityAttr().Set(900.0)
    distant.CreateAngleAttr().Set(1.0)
    UsdGeom.Xformable(distant.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 25.0, 20.0))
    settings = carb.settings.get_settings()
    settings.set("/rtx/rendermode", "RayTracedLighting")
    settings.set("/rtx/post/tonemap/op", 4)
    settings.set("/rtx/post/tonemap/filmIso", 200.0)


def _mass_audit(stage, control_urdf: Path) -> dict:
    urdf_root = ET.parse(control_urdf).getroot()
    urdf_masses: dict[str, float] = {}
    for link in urdf_root.findall("link"):
        inertial = link.find("inertial")
        mass = inertial.find("mass") if inertial is not None else None
        if mass is not None:
            urdf_masses[str(link.attrib["name"])] = float(mass.attrib["value"])

    usd_masses: dict[str, float] = {}
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.MassAPI) and prim.GetName() in urdf_masses:
            value = UsdPhysics.MassAPI(prim).GetMassAttr().Get()
            if value is not None:
                usd_masses[str(prim.GetName())] = float(value)

    differences = {}
    for link_name, urdf_mass in urdf_masses.items():
        usd_mass = usd_masses.get(link_name)
        differences[link_name] = {
            "urdf_kg": urdf_mass,
            "usd_kg": usd_mass,
            "difference_kg": None if usd_mass is None else usd_mass - urdf_mass,
            "matches": usd_mass is not None and abs(usd_mass - urdf_mass) <= 1.0e-6,
        }
    return {
        "matches": all(item["matches"] for item in differences.values()),
        "links": differences,
    }


def _scene_audit(stage, robot, physics_dt: float, control_urdf: Path) -> dict:
    dof_names = tuple(robot.get_robot_info().get("dof_names", ()))
    fixed_base_joints = []
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.FixedJoint):
            body0 = [str(path) for path in prim.GetRelationship("physics:body0").GetTargets()]
            body1 = [str(path) for path in prim.GetRelationship("physics:body1").GetTargets()]
            if any("A1Z_G1Z" in path for path in body0 + body1):
                fixed_base_joints.append(str(prim.GetPath()))
    return {
        "stage_root_layer": str(stage.GetRootLayer().realPath or stage.GetRootLayer().identifier),
        "articulation_root": ARGS.articulation_root,
        "dof_names": list(dof_names),
        "arm_dof_order_matches": dof_names[:6] == ARM_DOF_NAMES,
        "fixed_base_joint_paths": fixed_base_joints,
        "physics_engine": str(SimulationManager.get_active_physics_engine()),
        "physics_dt_s": physics_dt,
        "rendering_dt_s": float(RenderingManager.get_dt()),
        "control_frequency_hz": int(round(1.0 / physics_dt)),
        "real_kp": REAL_KP.tolist(),
        "real_kd": REAL_KD.tolist(),
        "zero_gravity_kp": np.zeros(6, dtype=np.float64).tolist(),
        "zero_gravity_kd": (REAL_KD * 0.5).tolist(),
        "mass_model": _mass_audit(stage, control_urdf),
    }


def _end_effector_z(kinematics: Kinematics, q: np.ndarray) -> float:
    return float(kinematics.fk(q, frame_name="grasp_tcp")[2, 3])


def _configure_real_profile(robot) -> None:
    # The production Isaac profile is intentionally much stiffer than hardware.
    # This test overrides only the test instance so both modes use SDK gains.
    robot._hold_kp = REAL_KP.copy()
    robot._hold_kd = REAL_KD.copy()
    robot._default_kp = REAL_KP.copy()
    robot._default_kd = REAL_KD.copy()
    robot._gravity_mode_kd_scale = 0.5


def _reset_case(robot, q0: np.ndarray, *, gravity_mode: bool, j4_scale: float) -> None:
    robot._gravity_torque_scale = np.ones(6, dtype=np.float64)
    robot._gravity_torque_scale[3] = float(j4_scale)
    robot.set_gravity_mode(False)
    robot._force_arm_positions(q0)
    robot.set_gravity_mode(gravity_mode)


def _run_case(
    robot,
    kinematics: Kinematics,
    q0: np.ndarray,
    *,
    name: str,
    gravity_mode: bool,
    j4_scale: float,
    physics_dt: float,
    duration_s: float,
) -> tuple[dict, list[dict]]:
    _reset_case(robot, q0, gravity_mode=gravity_mode, j4_scale=j4_scale)
    steps = int(round(duration_s / physics_dt))
    rows: list[dict] = []

    robot.process_pending(physics_dt)
    state0 = robot.get_joint_state()
    info0 = robot.get_robot_info()
    initial_q = np.asarray(state0["pos"], dtype=np.float64)
    initial_z = _end_effector_z(kinematics, initial_q)

    for step in range(steps + 1):
        if step:
            SIMULATION_APP.update()
            robot.process_pending(physics_dt)
        state = robot.get_joint_state()
        info = robot.get_robot_info()
        q = np.asarray(state["pos"], dtype=np.float64)
        qd = np.asarray(state["vel"], dtype=np.float64)
        tau_id = np.asarray(info["gravity_debug_tau_id"], dtype=np.float64)
        effort_cmd = np.asarray(info["gravity_debug_effort"], dtype=np.float64)
        effort_measured = np.asarray(state["eff"], dtype=np.float64)
        row = {
            "scenario": name,
            "time_s": step * physics_dt,
            "j4_pos_deg": float(np.rad2deg(q[3])),
            "j4_vel_rad_s": float(qd[3]),
            "j4_tau_id_nm": float(tau_id[3]),
            "j4_effort_command_nm": float(effort_cmd[3]),
            "j4_effort_measured_nm": float(effort_measured[3]),
            "ee_z_m": _end_effector_z(kinematics, q),
        }
        for joint_index in range(6):
            joint_number = joint_index + 1
            row[f"j{joint_number}_pos_deg"] = float(np.rad2deg(q[joint_index]))
            row[f"j{joint_number}_vel_rad_s"] = float(qd[joint_index])
            row[f"j{joint_number}_tau_id_nm"] = float(tau_id[joint_index])
            row[f"j{joint_number}_effort_command_nm"] = float(effort_cmd[joint_index])
        rows.append(row)

    final = rows[-1]
    j4_values = np.asarray([row["j4_pos_deg"] for row in rows], dtype=np.float64)
    velocity_values = np.asarray([row["j4_vel_rad_s"] for row in rows], dtype=np.float64)
    z_values = np.asarray([row["ee_z_m"] for row in rows], dtype=np.float64)
    joint_positions_deg = np.asarray(
        [[row[f"j{joint_number}_pos_deg"] for joint_number in range(1, 7)] for row in rows],
        dtype=np.float64,
    )
    summary = {
        "scenario": name,
        "control_mode": "gravity_comp_effort" if gravity_mode else "position_hold",
        "j4_gravity_scale": float(j4_scale),
        "duration_s": duration_s,
        "initial_j4_deg": float(j4_values[0]),
        "final_j4_deg": float(j4_values[-1]),
        "j4_drift_deg": float(j4_values[-1] - j4_values[0]),
        "max_abs_j4_drift_deg": float(np.max(np.abs(j4_values - j4_values[0]))),
        "joint_drift_deg": (joint_positions_deg[-1] - joint_positions_deg[0]).tolist(),
        "max_abs_joint_drift_deg": np.max(
            np.abs(joint_positions_deg - joint_positions_deg[0]), axis=0
        ).tolist(),
        "peak_abs_j4_velocity_rad_s": float(np.max(np.abs(velocity_values))),
        "initial_ee_z_m": initial_z,
        "final_ee_z_m": float(z_values[-1]),
        "end_effector_drop_mm": float((initial_z - z_values[-1]) * 1000.0),
        "initial_j4_tau_id_nm": float(rows[0]["j4_tau_id_nm"]),
        "initial_j4_effort_command_nm": float(rows[0]["j4_effort_command_nm"]),
        "final_j4_effort_command_nm": float(final["j4_effort_command_nm"]),
        "initial_debug_q_deg": np.rad2deg(np.asarray(info0["gravity_debug_q"])).tolist(),
    }
    return summary, rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_plot(path: Path, rows: list[dict]) -> None:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for scenario in dict.fromkeys(row["scenario"] for row in rows):
        selected = [row for row in rows if row["scenario"] == scenario]
        time_s = [row["time_s"] for row in selected]
        axes[0].plot(time_s, [row["j4_pos_deg"] for row in selected], label=scenario)
        axes[1].plot(
            time_s,
            [(selected[0]["ee_z_m"] - row["ee_z_m"]) * 1000.0 for row in selected],
            label=scenario,
        )
    axes[0].set_ylabel("J4 position (deg)")
    axes[1].set_ylabel("End-effector drop (mm)")
    axes[1].set_xlabel("Simulation time (s)")
    for axis in axes:
        axis.grid(True, alpha=0.3)
        axis.legend()
    figure.suptitle("A1Z physical-SDK gravity-control semantics in Isaac Sim")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _capture_scene(path: Path) -> dict:
    camera = rep.create.camera(position=(1.1, 1.1, 0.9), look_at=(0.0, 0.0, 0.45))
    render_product = rep.create.render_product(camera, (640, 480))
    annotator = rep.AnnotatorRegistry.get_annotator("rgb")
    annotator.attach(render_product)
    for _ in range(40):
        SIMULATION_APP.update()
    rgb = np.asarray(annotator.get_data())
    annotator.detach()
    Image.fromarray(rgb[:, :, :3].astype(np.uint8), mode="RGB").save(path, compress_level=1)
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "mean_rgb": float(np.mean(rgb[:, :, :3], dtype=np.float64)),
        "max_rgb": int(np.max(rgb[:, :, :3])),
        "variance_rgb": float(np.var(rgb[:, :, :3], dtype=np.float64)),
    }


def run() -> dict:
    stage_path = Path(ARGS.stage).resolve()
    control_urdf = Path(ARGS.control_urdf).resolve()
    output_dir = Path(ARGS.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not stage_path.is_file() or not control_urdf.is_file():
        raise FileNotFoundError(f"missing stage or control URDF: {stage_path}, {control_urdf}")

    _open_stage(stage_path)
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Isaac USD context has no active stage")
    _ensure_lighting(stage)
    test_scene_path = output_dir / "a1z_j4_gravity_test_scene.usda"
    if not stage.GetRootLayer().Export(str(test_scene_path)):
        raise RuntimeError(f"failed to export test scene: {test_scene_path}")

    SimulationManager.switch_physics_engine("physx")
    RenderingManager.set_dt(ARGS.physics_dt)
    SimulationManager.setup_simulation(dt=ARGS.physics_dt, device="cpu")
    app_utils.play()
    for _ in range(20):
        SIMULATION_APP.update()

    defaults = get_control_defaults()
    robot = create_a1z_robot(
        backend="isaacsim",
        control_freq_hz=int(round(1.0 / ARGS.physics_dt)),
        with_gripper=True,
        articulation_root_prim=ARGS.articulation_root,
        urdf_path=str(control_urdf),
        default_kp=REAL_KP,
        default_kd=REAL_KD,
        gravity_comp_factor=1.0,
        zero_gravity_mode=False,
    )
    _configure_real_profile(robot)
    world = Isaac6WorldView()
    robot.start(existing_world=world, reset_world=False)

    q0 = np.deg2rad(np.asarray(ARGS.pose_deg, dtype=np.float64))
    kinematics = Kinematics(str(control_urdf), end_effector_frame="grasp_tcp")
    cases = [
        ("gravity_nominal_factor1", True, 1.0),
        *[
            (f"gravity_j4_{int(round(scale * 100))}pct", True, scale)
            for scale in ARGS.j4_undercomp_scales
        ],
        (
            f"position_hold_j4_{int(round(ARGS.j4_undercomp_scales[-1] * 100))}pct",
            False,
            ARGS.j4_undercomp_scales[-1],
        ),
    ]
    summaries = []
    rows: list[dict] = []
    for name, gravity_mode, j4_scale in cases:
        summary, case_rows = _run_case(
            robot,
            kinematics,
            q0,
            name=name,
            gravity_mode=gravity_mode,
            j4_scale=j4_scale,
            physics_dt=ARGS.physics_dt,
            duration_s=ARGS.duration_s,
        )
        summaries.append(summary)
        rows.extend(case_rows)

    audit = _scene_audit(stage, robot, ARGS.physics_dt, control_urdf)
    robot.stop()
    screenshot = _capture_scene(output_dir / "a1z_j4_gravity_scene.png")
    app_utils.stop()
    SIMULATION_APP.update()

    _write_csv(output_dir / "a1z_j4_gravity_timeseries.csv", rows)
    _write_plot(output_dir / "a1z_j4_gravity_plot.png", rows)
    nominal = summaries[0]
    undercomp = summaries[-2]
    hold = summaries[-1]
    checks = {
        "arm_dof_order_matches": audit["arm_dof_order_matches"],
        "usd_masses_match_control_urdf": audit["mass_model"]["matches"],
        "physx_active": "physx" in audit["physics_engine"].lower(),
        "physics_and_control_at_250hz": (
            abs(audit["physics_dt_s"] - 0.004) <= 1.0e-9
            and abs(audit["rendering_dt_s"] - 0.004) <= 1.0e-9
            and audit["control_frequency_hz"] == 250
        ),
        "factor1_nominal_finite": all(math.isfinite(value) for value in (
            nominal["j4_drift_deg"], nominal["end_effector_drop_mm"]
        )),
        "undercomp_changes_j4_more_than_nominal": (
            undercomp["max_abs_j4_drift_deg"]
            > nominal["max_abs_j4_drift_deg"] + 0.25
        ),
        "position_hold_reduces_undercomp_drift": (
            hold["max_abs_j4_drift_deg"] < undercomp["max_abs_j4_drift_deg"]
        ),
        "scene_capture_nonblack": (
            screenshot["size_bytes"] >= 150_000
            and screenshot["mean_rgb"] > 30.0
            and screenshot["variance_rgb"] > 15.0
        ),
    }
    return {
        "schema_version": 1,
        "valid": all(checks.values()),
        "requested_pose_deg": ARGS.pose_deg,
        "control_urdf": str(control_urdf),
        "plant_stage": str(stage_path),
        "saved_test_scene": str(test_scene_path),
        "checks": checks,
        "audit": audit,
        "scenarios": summaries,
        "scene_capture": screenshot,
        "outputs": {
            "timeseries_csv": str((output_dir / "a1z_j4_gravity_timeseries.csv").resolve()),
            "trajectory_plot": str((output_dir / "a1z_j4_gravity_plot.png").resolve()),
        },
    }


def main() -> int:
    try:
        report = run()
        output_path = Path(ARGS.output_dir).resolve() / "a1z_j4_gravity_report.json"
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["valid"] else 1
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        SIMULATION_APP.close()


if __name__ == "__main__":
    raise SystemExit(main())
