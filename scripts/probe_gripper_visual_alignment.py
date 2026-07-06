#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from isaacsim import SimulationApp


SIM_APP = SimulationApp({"headless": True})

import omni.usd  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT_DIR / "vendor" / "GALAXEA-A1Z"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from a1z_ext.robots.get_robot import get_a1z_isaacsim_robot  # noqa: E402


PRIM_PATHS = [
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/arm_link6",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/arm_link6_1",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_left_link",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_left_link/gripper_finger_left_link",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_left_link/gripper_finger_left_link_1",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_rIght_link",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_rIght_link/gripper_finger_rIght_link",
    "/World/A1Z_G1Z/Geometry/base_link/arm_link1/arm_link2/arm_link3/arm_link4/arm_link5/arm_link6/gripper_finger_rIght_link/gripper_finger_rIght_link_1",
]


def _update_app(frames: int = 1) -> None:
    for _ in range(max(0, int(frames))):
        SIM_APP.update()


def _capture(robot, label: str) -> dict[str, object]:
    snapshot: dict[str, object] = {"label": label, "prims": {}}
    for prim_path in PRIM_PATHS:
        snapshot["prims"][prim_path] = robot.get_sim_prim_debug(prim_path=prim_path)
    info = robot.get_robot_info()
    snapshot["robot_info"] = {
        "articulation_root_prim": info.get("articulation_root_prim"),
        "dof_names": list(info.get("dof_names") or []),
        "gripper_joint_paths": list(info.get("gripper_joint_paths") or []),
        "gripper_carrier_body_path": info.get("gripper_carrier_body_path"),
        "left_finger_body_path": info.get("left_finger_body_path"),
        "right_finger_body_path": info.get("right_finger_body_path"),
        "gripper_open_value": info.get("gripper_open_value"),
        "gripper_current_dofs": (
            [float(v) for v in info.get("gripper_current_dofs")]
            if info.get("gripper_current_dofs") is not None
            else None
        ),
    }
    return snapshot


def main() -> int:
    stage_path = os.environ.get("A1Z_WORLD_USD", str(ROOT_DIR / "build" / "scenes" / "A1Z_G1Z_world.usd"))
    output_path = Path(
        os.environ.get(
            "A1Z_GRIPPER_VISUAL_PROBE_OUTPUT",
            str(ROOT_DIR / "runtime" / "gripper_visual_probe.json"),
        )
    )
    ctx = omni.usd.get_context()
    if not ctx.open_stage(stage_path):
        raise RuntimeError(f"Failed to open stage: {stage_path}")
    _update_app(20)

    robot = get_a1z_isaacsim_robot(
        control_freq_hz=int(os.environ.get("A1Z_ISAAC_CONTROL_FREQ_HZ", "60")),
        with_gripper=True,
        articulation_root_prim=os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", "/World/A1Z_G1Z/Geometry"),
        zero_gravity_mode=False,
    )
    robot.start()
    try:
        _update_app(5)
        robot.process_pending()
        _update_app(5)

        report: dict[str, object] = {
            "stage_path": stage_path,
            "snapshots": [],
        }
        report["snapshots"].append(_capture(robot, "initial"))

        robot.command_gripper(1.0)
        _update_app(10)
        robot.process_pending()
        _update_app(10)
        report["snapshots"].append(_capture(robot, "open"))

        robot.command_gripper(0.0)
        _update_app(10)
        robot.process_pending()
        _update_app(10)
        report["snapshots"].append(_capture(robot, "closed"))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(report, ensure_ascii=True, indent=2)
        output_path.write_text(payload + "\n", encoding="utf-8")
        print(payload)
    finally:
        robot.stop()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        SIM_APP.close()
