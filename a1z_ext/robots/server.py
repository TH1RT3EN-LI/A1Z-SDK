"""A1Z robot arm control server.

Binds the configured TCP listener and, when enabled, an optional Unix socket,
then dispatches JSON commands to a live ArmRobot instance. Start via
``tools/a1zctl`` and communicate through the same script.

Protocol
--------
Each connection sends one newline-terminated JSON request and receives one
newline-terminated JSON response:

  Request:  {"cmd": "<name>", "args": {...}}
  Response: {"ok": true,  "data": {...}}
         or {"ok": false, "error": "<message>"}

Commands include status, movement, camera capture, and the physical grasp v2
close/status/release contract.
"""

import json
import os
import select
import signal
import socket
import threading
import time
from typing import Optional

import numpy as np

from a1z_ext.config import (
    get_arm_motion_speed_limits,
    get_default_backend,
    get_default_can_channel,
    get_socket_path,
    get_tcp_host,
    validate_arm_motion_speed,
)
from a1z_ext.robots.get_robot import create_a1z_robot


def _deg(*angles: float) -> np.ndarray:
    return np.deg2rad(np.array(angles, dtype=np.float64))


PRESETS: dict[str, np.ndarray] = {
    "home":    _deg(  0,  60,  -60,   0,   0,   0),
    "ready":   _deg(  0,  30,  -30,   0,  45,   0),
    "salute":  _deg( 30,  35,  -80,   0,  80,  90),
    "wave_l":  _deg(-80,  60,  -60,   0,  60,  90),
    "wave_r":  _deg( 80,  60,  -60,   0, -60, -90),
    "nod_a":   _deg(  0,  70,  -60,  50,   0,   0),
    "nod_b":   _deg(  0,  70,  -60,   0,   0,   0),
    "shake_a": _deg(  0,  70,  -60,   0,  40,   0),
    "shake_b": _deg(  0,  70,  -60,   0, -40,   0),
    "reach":   _deg(  0,  20,  -30,   0,  60,   0),
    "bow":     _deg(  0, 110, -130,   0,   0,   0),
}

# Each move: list of (pose_key, speed_multiplier, pause_s)
DANCE_MOVES: dict[str, list] = {
    "salute": [
        ("salute", 1.0, 0.8), ("home", 0.8, 0.0),
    ],
    "wave": [
        ("ready",  1.0, 0.0), ("wave_l", 1.5, 0.1),
        ("wave_r", 1.5, 0.1), ("wave_l", 1.5, 0.1),
        ("wave_r", 1.5, 0.1), ("home",   1.0, 0.0),
    ],
    "nod": [
        ("nod_a", 1.2, 0.0), ("nod_b", 1.2, 0.0), ("home", 1.0, 0.0),
    ],
    "shake": [
        ("shake_a", 1.2, 0.0), ("shake_b", 1.2, 0.0),
        ("shake_a", 1.2, 0.0), ("shake_b", 1.2, 0.0),
        ("home",    1.0, 0.0),
    ],
    "reach": [("reach", 0.9, 0.5), ("home", 0.9, 0.0)],
    "bow":   [("home", 0.7, 0.0), ("bow", 0.5, 0.8), ("home", 0.5, 0.0)],
}

DEFAULT_DANCE_ORDER = ["salute", "wave", "nod", "reach", "bow"]


class RobotServer:
    def __init__(self, robot, with_gripper: bool, camera_session=None) -> None:
        self._robot = robot
        self._with_gripper = with_gripper
        self._camera_session = camera_session
        self._lock = threading.Lock()
        self._camera_lock = threading.Lock()
        self._shutdown = threading.Event()
        self._listener_ready = threading.Event()
        self._listener_startup_error: Optional[BaseException] = None

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_status(self, _args: dict) -> dict:
        state = self._robot.get_joint_state()
        pos_deg = np.rad2deg(state["pos"]).tolist()
        data: dict = {
            "pos_deg":    [round(v, 2) for v in pos_deg],
            "vel_rad_s":  [round(v, 3) for v in state["vel"].tolist()],
            "torque_nm":  [round(v, 3) for v in state["eff"].tolist()],
        }
        if self._with_gripper:
            gpos = self._robot.get_gripper_pos()
            data["gripper"] = round(gpos, 3) if gpos is not None else None
        return {"ok": True, "data": data}

    def _cmd_move(self, args: dict) -> dict:
        speed_limits = get_arm_motion_speed_limits()
        speed = validate_arm_motion_speed(args.get("speed", speed_limits.default))
        if "preset" in args:
            name = args["preset"]
            if name not in PRESETS:
                avail = ", ".join(sorted(PRESETS))
                return {"ok": False, "error": f"Unknown preset '{name}'. Available: {avail}"}
            target = PRESETS[name]
        elif "joints" in args:
            joints = args["joints"]
            if len(joints) != 6:
                return {"ok": False, "error": "joints must be a list of 6 values (degrees)"}
            target = np.deg2rad(np.array(joints, dtype=np.float64))
        else:
            return {"ok": False, "error": "move requires 'preset' or 'joints'"}

        self._robot.move_joints(target, speed=speed)
        pos_deg = np.rad2deg(self._robot.get_joint_pos()[:6]).tolist()
        return {"ok": True, "data": {"pos_deg": [round(v, 2) for v in pos_deg]}}

    def _cmd_command(self, args: dict) -> dict:
        joints = args.get("joints")
        if joints is None:
            return {"ok": False, "error": "command requires 'joints' (6 joint values in degrees)"}
        if len(joints) != 6:
            return {"ok": False, "error": "joints must be a list of 6 values (degrees)"}

        target = np.deg2rad(np.array(joints, dtype=np.float64))
        data: dict = {
            "target_deg": [round(float(v), 2) for v in joints],
        }

        if self._with_gripper and "gripper" in args:
            value = float(args["gripper"])
            if not 0.0 <= value <= 1.0:
                return {"ok": False, "error": "gripper must be in [0.0, 1.0]"}
            target = np.append(target, value)
            data["gripper"] = round(value, 3)

        self._robot.command_joint_pos(target)
        return {"ok": True, "data": data}

    def _cmd_gripper(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        value = float(args.get("value", 1.0))
        if not 0.0 <= value <= 1.0:
            return {"ok": False, "error": "value must be in [0.0, 1.0]"}
        self._robot.command_gripper(value)
        return {"ok": True, "data": {"gripper": value}}

    def _cmd_grasp_attach(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "grasp_close_and_attach"):
            return {"ok": False, "error": "Active backend does not support grasp_attach"}
        data = self._robot.grasp_close_and_attach(
            str(args.get("target_prim_path", "") or ""),
            timeout_s=float(args.get("timeout_s", 2.0)),
            contact_window_s=float(args.get("contact_window_s", 0.15)),
            require_bilateral_contact=bool(args.get("require_bilateral_contact", True)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_link(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "grasp_link_current_contact"):
            return {"ok": False, "error": "Active backend does not support grasp_link"}
        data = self._robot.grasp_link_current_contact(
            str(args.get("target_prim_path", "") or ""),
            require_bilateral_contact=bool(args.get("require_bilateral_contact", True)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_release(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "release_attached_object"):
            return {"ok": False, "error": "Active backend does not support grasp_release"}
        data = self._robot.release_attached_object(
            open_gripper=bool(args.get("open_gripper", True)),
            timeout_s=float(args.get("timeout_s", 2.0)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_status(self, _args: dict) -> dict:
        if not hasattr(self._robot, "get_sim_grasp_status"):
            return {"ok": True, "data": {"has_attached_object": False, "grasp_state": "unsupported"}}
        data = self._robot.get_sim_grasp_status()
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_contacts(self, args: dict) -> dict:
        if not hasattr(self._robot, "get_sim_grasp_contacts"):
            return {"ok": True, "data": {"unsupported": True}}
        data = self._robot.get_sim_grasp_contacts(
            target_prim_path=str(args.get("target_prim_path", "") or ""),
            require_bilateral_contact=bool(args.get("require_bilateral_contact", True)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_close_v2(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "grasp_close_physical"):
            return {"ok": False, "error": "Active backend does not support physical grasp contract v2"}
        minimum_force = args.get("minimum_normal_force_n")
        preload_delta = args.get("preload_delta_m")
        controller_profile = args.get("controller_profile")
        if controller_profile is not None and not isinstance(controller_profile, dict):
            return {"ok": False, "error": "controller_profile must be a JSON object"}
        data = self._robot.grasp_close_physical(
            timeout_s=float(args.get("timeout_s", 15.0)),
            minimum_normal_force_n=(None if minimum_force is None else float(minimum_force)),
            preload_delta_m=(None if preload_delta is None else float(preload_delta)),
            controller_profile=controller_profile,
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_release_v2(self, args: dict) -> dict:
        if not self._with_gripper:
            return {"ok": False, "error": "Server was started without --with-gripper"}
        if not hasattr(self._robot, "release_physical_grasp"):
            return {"ok": False, "error": "Active backend does not support physical grasp contract v2"}
        data = self._robot.release_physical_grasp(
            timeout_s=float(args.get("timeout_s", 3.0)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_grasp_status_v2(self, _args: dict) -> dict:
        if not hasattr(self._robot, "get_physical_grasp_status"):
            return {
                "ok": True,
                "data": {
                    "contract_version": 2,
                    "mode": "physical",
                    "success": False,
                    "phase": "unsupported",
                },
            }
        return {"ok": True, "data": dict(self._robot.get_physical_grasp_status())}

    def _cmd_contact_report(self, args: dict) -> dict:
        if not hasattr(self._robot, "get_sim_contact_report"):
            return {"ok": True, "data": {"unsupported": True}}
        data = self._robot.get_sim_contact_report(
            prim_path=str(args.get("prim_path", "") or ""),
            limit=int(args.get("limit", 200)),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_prim_debug(self, args: dict) -> dict:
        if not hasattr(self._robot, "get_sim_prim_debug"):
            return {"ok": True, "data": {"unsupported": True}}
        data = self._robot.get_sim_prim_debug(
            prim_path=str(args.get("prim_path", "") or ""),
        )
        return {"ok": True, "data": dict(data)}

    def _cmd_dance(self, args: dict) -> dict:
        moves_list = args.get("moves", DEFAULT_DANCE_ORDER)
        speed = float(args.get("speed", 0.6))
        unknown = [m for m in moves_list if m not in DANCE_MOVES]
        if unknown:
            avail = ", ".join(DANCE_MOVES)
            return {"ok": False, "error": f"Unknown moves: {unknown}. Available: {avail}"}

        self._robot.move_joints(PRESETS["home"], speed=speed * 0.7)
        time.sleep(0.4)
        for move_name in moves_list:
            print(f"[a1z] dance: {move_name}")
            for pose_key, spd_mul, pause in DANCE_MOVES[move_name]:
                self._robot.move_joints(PRESETS[pose_key], speed=speed * spd_mul)
                if pause > 0:
                    time.sleep(pause)
            time.sleep(0.2)
        self._robot.move_joints(PRESETS["home"], speed=speed * 0.6)
        return {"ok": True, "data": {"moves": moves_list}}

    def _cmd_stop(self, _args: dict) -> dict:
        self._shutdown.set()
        return {"ok": True, "data": {"message": "Stopping server"}}

    def _cmd_info(self, _args: dict) -> dict:
        info = self._robot.get_robot_info()
        raw_joint_limits = info.get("joint_limits")
        joint_limits = []
        if raw_joint_limits is not None:
            joint_limits = np.asarray(raw_joint_limits, dtype=np.float64).reshape(-1, 2)
        arm_joint_limits = joint_limits[:6]
        joint_limits_deg = {
            f"J{i + 1}": [round(np.rad2deg(lo), 1), round(np.rad2deg(hi), 1)]
            for i, (lo, hi) in enumerate(arm_joint_limits)
        }
        data = {
            "backend": info.get("backend", "socketcan"),
            "presets": sorted(PRESETS),
            "dance_moves": list(DANCE_MOVES),
            "joint_limits_deg": joint_limits_deg,
            "control_mode": info.get("control_mode"),
        }
        if info.get("hard_joint_limits") is not None:
            hard_joint_limits = np.asarray(info["hard_joint_limits"], dtype=np.float64).reshape(-1, 2)[:6]
            data["hard_joint_limits_deg"] = {
                f"J{i + 1}": [round(np.rad2deg(lo), 1), round(np.rad2deg(hi), 1)]
                for i, (lo, hi) in enumerate(hard_joint_limits)
            }
        if info.get("arm_max_velocity") is not None:
            arm_max_velocity = np.asarray(info["arm_max_velocity"], dtype=np.float64).reshape(-1)[:6]
            data["arm_max_velocity_rad_s"] = [round(float(v), 3) for v in arm_max_velocity]
        speed_limits = get_arm_motion_speed_limits()
        data["arm_motion_speed_rad_s"] = {
            "minimum": speed_limits.minimum,
            "default": speed_limits.default,
            "maximum": speed_limits.maximum,
        }
        if info.get("with_gripper"):
            data["gripper_range"] = [0.0, 1.0]
        if info.get("articulation_root_prim"):
            data["articulation_root_prim"] = info["articulation_root_prim"]
        if info.get("dof_names"):
            data["dof_names"] = list(info["dof_names"])
        arm_joint_indices = None
        if info.get("arm_joint_indices") is not None:
            arm_joint_indices = np.asarray(info["arm_joint_indices"], dtype=np.int64).reshape(-1)
            data["arm_joint_indices"] = arm_joint_indices.tolist()
        gripper_joint_indices = None
        if info.get("gripper_joint_indices") is not None:
            gripper_joint_indices = np.asarray(
                info["gripper_joint_indices"], dtype=np.int64
            ).reshape(-1)
            data["gripper_joint_indices"] = gripper_joint_indices.tolist()
        if info.get("gripper_target_value") is not None:
            data["gripper_target_value"] = round(float(info["gripper_target_value"]), 4)
        if info.get("gripper_target_dofs") is not None:
            gripper_target_dofs = np.asarray(info["gripper_target_dofs"], dtype=np.float64).reshape(-1)
            data["gripper_target_dofs"] = [round(float(v), 6) for v in gripper_target_dofs]
        if info.get("gripper_command_dofs") is not None:
            gripper_command_dofs = np.asarray(
                info["gripper_command_dofs"], dtype=np.float64
            ).reshape(-1)
            data["gripper_command_dofs"] = [
                round(float(v), 6) for v in gripper_command_dofs
            ]
        if info.get("gripper_current_dofs") is not None:
            gripper_current_dofs = np.asarray(info["gripper_current_dofs"], dtype=np.float64).reshape(-1)
            data["gripper_current_dofs"] = [round(float(v), 6) for v in gripper_current_dofs]
        if info.get("actual_kp") is not None:
            actual_kp_all = np.asarray(info["actual_kp"], dtype=np.float64).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_kp"] = [
                    round(float(v), 3) for v in actual_kp_all[gripper_joint_indices]
                ]
            actual_kp = actual_kp_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_kp = actual_kp[arm_joint_indices]
            data["actual_kp"] = [round(float(v), 3) for v in actual_kp[:6]]
        if info.get("actual_kd") is not None:
            actual_kd_all = np.asarray(info["actual_kd"], dtype=np.float64).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_kd"] = [
                    round(float(v), 3) for v in actual_kd_all[gripper_joint_indices]
                ]
            actual_kd = actual_kd_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_kd = actual_kd[arm_joint_indices]
            data["actual_kd"] = [round(float(v), 3) for v in actual_kd[:6]]
        if info.get("actual_max_effort") is not None:
            actual_max_effort_all = np.asarray(
                info["actual_max_effort"], dtype=np.float64
            ).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_max_effort"] = [
                    round(float(v), 3)
                    for v in actual_max_effort_all[gripper_joint_indices]
                ]
            actual_max_effort = actual_max_effort_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_max_effort = actual_max_effort[arm_joint_indices]
            data["actual_max_effort_nm"] = [
                round(float(v), 3) for v in actual_max_effort[:6]
            ]
        if info.get("actual_position_targets") is not None:
            actual_position_targets_all = np.asarray(
                info["actual_position_targets"], dtype=np.float64
            ).reshape(-1)
            if gripper_joint_indices is not None and gripper_joint_indices.size:
                data["gripper_actual_position_targets_m"] = [
                    round(float(v), 6)
                    for v in actual_position_targets_all[gripper_joint_indices]
                ]
            actual_position_targets = actual_position_targets_all
            if arm_joint_indices is not None and arm_joint_indices.size:
                actual_position_targets = actual_position_targets[arm_joint_indices]
            data["actual_position_targets_deg"] = [
                round(float(v), 2)
                for v in np.rad2deg(actual_position_targets[:6])
            ]
        if info.get("active_physics_engine"):
            data["active_physics_engine"] = str(info["active_physics_engine"])
        if info.get("configured_arm_drive_type"):
            data["configured_arm_drive_type"] = str(info["configured_arm_drive_type"])
        if info.get("gravity_model_available") is not None:
            data["gravity_model_available"] = bool(info["gravity_model_available"])
        if info.get("position_hold_gravity_compensation_enabled") is not None:
            data["position_hold_gravity_compensation_enabled"] = bool(
                info["position_hold_gravity_compensation_enabled"]
            )
        if info.get("position_hold_gravity_compensation_active") is not None:
            data["position_hold_gravity_compensation_active"] = bool(
                info["position_hold_gravity_compensation_active"]
            )
        if info.get("position_hold_feedforward_limit_nm") is not None:
            position_hold_feedforward_limit = np.asarray(
                info["position_hold_feedforward_limit_nm"], dtype=np.float64
            ).reshape(-1)
            data["position_hold_feedforward_limit_nm"] = [
                round(float(v), 3) for v in position_hold_feedforward_limit[:6]
            ]
        if info.get("controller_kp") is not None:
            controller_kp = np.asarray(info["controller_kp"], dtype=np.float64).reshape(-1)
            data["controller_kp"] = [round(float(v), 3) for v in controller_kp[:6]]
        if info.get("controller_kd") is not None:
            controller_kd = np.asarray(info["controller_kd"], dtype=np.float64).reshape(-1)
            data["controller_kd"] = [round(float(v), 3) for v in controller_kd[:6]]
        if info.get("gravity_debug_q") is not None:
            gravity_q = np.asarray(info["gravity_debug_q"], dtype=np.float64).reshape(-1)
            data["gravity_debug_q_deg"] = [round(float(v), 3) for v in np.rad2deg(gravity_q[:6])]
        if info.get("gravity_debug_qd") is not None:
            gravity_qd = np.asarray(info["gravity_debug_qd"], dtype=np.float64).reshape(-1)
            data["gravity_debug_qd"] = [round(float(v), 3) for v in gravity_qd[:6]]
        if info.get("gravity_debug_pos_err") is not None:
            gravity_pos_err = np.asarray(info["gravity_debug_pos_err"], dtype=np.float64).reshape(-1)
            data["gravity_debug_pos_err_deg"] = [round(float(v), 3) for v in np.rad2deg(gravity_pos_err[:6])]
        if info.get("gravity_debug_vel_err") is not None:
            gravity_vel_err = np.asarray(info["gravity_debug_vel_err"], dtype=np.float64).reshape(-1)
            data["gravity_debug_vel_err"] = [round(float(v), 3) for v in gravity_vel_err[:6]]
        if info.get("gravity_debug_tau_id") is not None:
            gravity_tau_id = np.asarray(info["gravity_debug_tau_id"], dtype=np.float64).reshape(-1)
            data["gravity_debug_tau_id"] = [round(float(v), 3) for v in gravity_tau_id[:6]]
        if info.get("gravity_debug_effort") is not None:
            gravity_effort = np.asarray(info["gravity_debug_effort"], dtype=np.float64).reshape(-1)
            data["gravity_debug_effort"] = [round(float(v), 3) for v in gravity_effort[:6]]
        if info.get("effort_modes") is not None:
            data["effort_modes"] = list(info["effort_modes"])
        if info.get("command_pos") is not None:
            cmd = np.asarray(info["command_pos"], dtype=np.float64).reshape(-1)
            data["command_pos_deg"] = [round(float(v), 2) for v in np.rad2deg(cmd[:6])]
        return {
            "ok": True,
            "data": data,
        }

    def _cmd_camera_status(self, _args: dict) -> dict:
        if self._camera_session is None:
            return {"ok": False, "error": "D405 camera session is not available."}
        return {"ok": True, "data": self._camera_session.health()}

    def _cmd_camera_capture(self, args: dict) -> dict:
        if self._camera_session is None:
            return {"ok": False, "error": "D405 camera session is not available."}
        fresh = bool(args.get("fresh", True))
        return {"ok": True, "data": self._camera_session.latest_payload(fresh=fresh)}

    def _cmd_camera_extrinsic(self, _args: dict) -> dict:
        if self._camera_session is None:
            return {"ok": False, "error": "D405 camera session is not available."}
        return {"ok": True, "data": self._camera_session.latest_extrinsic_payload()}

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    _HANDLERS = {
        "status":  _cmd_status,
        "move":    _cmd_move,
        "command": _cmd_command,
        "gripper": _cmd_gripper,
        "grasp_attach": _cmd_grasp_attach,
        "grasp_link": _cmd_grasp_link,
        "grasp_release": _cmd_grasp_release,
        "grasp_status": _cmd_grasp_status,
        "grasp_contacts": _cmd_grasp_contacts,
        "grasp_close_v2": _cmd_grasp_close_v2,
        "grasp_release_v2": _cmd_grasp_release_v2,
        "grasp_status_v2": _cmd_grasp_status_v2,
        "contact_report": _cmd_contact_report,
        "prim_debug": _cmd_prim_debug,
        "dance":   _cmd_dance,
        "stop":    _cmd_stop,
        "info":    _cmd_info,
        "camera_status": _cmd_camera_status,
        "camera_capture": _cmd_camera_capture,
        "camera_extrinsic": _cmd_camera_extrinsic,
    }
    _CAMERA_READ_COMMANDS = frozenset(
        {"camera_status", "camera_capture", "camera_extrinsic"}
    )

    def _dispatch_request(self, cmd: str, args: dict) -> dict:
        handler = self._HANDLERS.get(cmd)
        if handler is None:
            return {"ok": False, "error": f"Unknown command '{cmd}'"}
        if cmd in self._CAMERA_READ_COMMANDS:
            # A fresh frame can wait for Kit and then spend tens of milliseconds
            # encoding. Keep camera requests serialized without holding the arm
            # command lock for that entire interval.
            with self._camera_lock:
                return handler(self, args)
        with self._lock:
            return handler(self, args)

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk
            req = json.loads(data.split(b"\n", 1)[0].decode())
            cmd = req.get("cmd", "")
            args = req.get("args", {})
            result = self._dispatch_request(cmd, args)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        try:
            conn.sendall((json.dumps(result) + "\n").encode())
        except Exception:
            pass
        finally:
            conn.close()

    def wait_until_ready(self, timeout_s: float = 5.0) -> None:
        if not self._listener_ready.wait(timeout=max(0.0, float(timeout_s))):
            raise TimeoutError("Timed out waiting for A1Z robot server listeners.")
        if self._listener_startup_error is not None:
            raise RuntimeError("A1Z robot server listeners failed to start") from self._listener_startup_error

    def run(
        self,
        socket_path: Optional[str] = None,
        tcp_host: Optional[str] = None,
        tcp_port: Optional[int] = None,
    ) -> None:
        try:
            self._run_listeners(
                socket_path=socket_path,
                tcp_host=tcp_host,
                tcp_port=tcp_port,
            )
        except BaseException as exc:
            if not self._listener_ready.is_set():
                self._listener_startup_error = exc
                self._listener_ready.set()
            raise

    def _run_listeners(
        self,
        socket_path: Optional[str] = None,
        tcp_host: Optional[str] = None,
        tcp_port: Optional[int] = None,
    ) -> None:
        listeners: list[socket.socket] = []
        unix_socket_path = get_socket_path() if socket_path is None else str(socket_path).strip()
        if unix_socket_path:
            if os.path.exists(unix_socket_path):
                os.unlink(unix_socket_path)

            unix_srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            unix_srv.bind(unix_socket_path)
            unix_srv.listen(8)
            unix_srv.setblocking(False)
            listeners.append(unix_srv)
            print(f"[a1z] Listening on unix://{unix_socket_path}")

        if tcp_port is not None and int(tcp_port) > 0:
            resolved_host = tcp_host or get_tcp_host()
            resolved_port = int(tcp_port)
            tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_srv.bind((resolved_host, resolved_port))
            tcp_srv.listen(8)
            tcp_srv.setblocking(False)
            listeners.append(tcp_srv)
            print(f"[a1z] Listening on tcp://{resolved_host}:{resolved_port}")

        if not listeners:
            raise RuntimeError("No A1Z control listener is configured.")
        self._listener_ready.set()
        try:
            while not self._shutdown.is_set():
                try:
                    ready_listeners, _, _ = select.select(listeners, [], [], 0.25)
                except (OSError, ValueError):
                    if self._shutdown.is_set():
                        break
                    raise
                for srv in ready_listeners:
                    try:
                        conn, _ = srv.accept()
                    except BlockingIOError:
                        continue
                    conn.setblocking(True)
                    conn.settimeout(120.0)
                    t = threading.Thread(
                        target=self._handle_connection, args=(conn,), daemon=True
                    )
                    t.start()
        finally:
            for srv in listeners:
                try:
                    srv.close()
                except OSError:
                    pass
            if unix_socket_path and os.path.exists(unix_socket_path):
                os.unlink(unix_socket_path)


# ------------------------------------------------------------------
# Entry point (called from tools/a1zctl)
# ------------------------------------------------------------------

def serve(
    can_channel: str = get_default_can_channel(),
    with_gripper: bool = False,
    gravity_mode: bool = False,
    backend: Optional[str] = None,
    socket_path: Optional[str] = None,
    tcp_host: Optional[str] = None,
    tcp_port: Optional[int] = None,
    control_freq_hz: int = 60,
    articulation_root_prim: Optional[str] = None,
) -> None:
    """Start the robot server in the foreground."""
    backend_name = backend or get_default_backend()
    print(
        f"[a1z] Initialising arm  backend={backend_name}  can={can_channel}  "
        f"gripper={'yes' if with_gripper else 'no'}"
    )
    robot = create_a1z_robot(
        backend=backend_name,
        can_channel=can_channel,
        zero_gravity_mode=gravity_mode,
        with_gripper=with_gripper,
        gravity_comp_factor=1.0,
        control_freq_hz=control_freq_hz,
        articulation_root_prim=articulation_root_prim,
    )

    server = RobotServer(robot, with_gripper=with_gripper)

    def _sigint(sig, frame):
        print("\n[a1z] Interrupted — stopping...")
        server._shutdown.set()

    signal.signal(signal.SIGINT, _sigint)

    robot.start()
    print("[a1z] Arm ready.  Press Ctrl+C to stop.")

    try:
        server.run(
            socket_path=socket_path,
            tcp_host=tcp_host,
            tcp_port=tcp_port,
        )
    finally:
        robot.stop()
        print("[a1z] Arm stopped.")
