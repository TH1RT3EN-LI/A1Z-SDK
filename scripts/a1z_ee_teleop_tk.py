#!/usr/bin/env python3

"""Tk teleop panel for A1Z Cartesian IK and per-joint trim control."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
HOST_HELPER = ROOT_DIR / "scripts" / "a1z_ee_ik_helper.py"
CONTAINER_HELPER = "/workspace/A1Z/scripts/a1z_ee_ik_helper.py"
CONTAINER_WRAPPER = ROOT_DIR / "scripts" / "a1z_sdk_python_in_container.sh"
CONTAINER_A1ZCTL = ROOT_DIR / "scripts" / "a1zctl_in_container.sh"


class TeleopApp:
    def __init__(self, root: tk.Tk, *, helper_mode: str) -> None:
        self.root = root
        self.root.title("A1Z Teleop")
        self.root.resizable(False, False)

        self.helper_mode = tk.StringVar(value=helper_mode)
        self.frame_mode = tk.StringVar(value="base")
        self.motion_mode = tk.StringVar(value="move")
        self.linear_step_mm = tk.DoubleVar(value=10.0)
        self.angular_step_deg = tk.DoubleVar(value=5.0)
        self.speed = tk.DoubleVar(value=0.5)
        self.ee_frame = tk.StringVar(value="arm_link6")
        self.gripper_value = tk.DoubleVar(value=1.0)

        self.backend_var = tk.StringVar(value="-")
        self.control_mode_var = tk.StringVar(value="-")
        self.socket_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="Idle")
        self.gripper_status_var = tk.StringVar(value="-")
        self.pose_vars = {
            "x": tk.StringVar(value="-"),
            "y": tk.StringVar(value="-"),
            "z": tk.StringVar(value="-"),
            "roll": tk.StringVar(value="-"),
            "pitch": tk.StringVar(value="-"),
            "yaw": tk.StringVar(value="-"),
        }
        self.joint_vars = [tk.StringVar(value="-") for _ in range(6)]
        self.joint_limit_vars = [tk.StringVar(value="-") for _ in range(6)]
        self.joint_target_vars = [tk.StringVar(value="0.0") for _ in range(6)]

        self._busy = False
        self._action_buttons: list[ttk.Button] = []

        self._build_ui()
        self.root.after(150, self.refresh_snapshot)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")

        top = ttk.LabelFrame(main, text="Connection", padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        ttk.Label(top, text="Helper").grid(row=0, column=0, sticky="w")
        helper_combo = ttk.Combobox(
            top,
            state="readonly",
            width=10,
            textvariable=self.helper_mode,
            values=("container", "local"),
        )
        helper_combo.grid(row=0, column=1, sticky="ew", padx=(6, 12))

        ttk.Label(top, text="Frame").grid(row=0, column=2, sticky="w")
        frame_combo = ttk.Combobox(
            top,
            state="readonly",
            width=8,
            textvariable=self.frame_mode,
            values=("base", "tool"),
        )
        frame_combo.grid(row=0, column=3, sticky="ew", padx=(6, 0))

        ttk.Label(top, text="Motion").grid(row=1, column=0, sticky="w", pady=(8, 0))
        motion_combo = ttk.Combobox(
            top,
            state="readonly",
            width=10,
            textvariable=self.motion_mode,
            values=("move", "command"),
        )
        motion_combo.grid(row=1, column=1, sticky="ew", padx=(6, 12), pady=(8, 0))

        ttk.Label(top, text="EE Frame").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(top, width=16, textvariable=self.ee_frame).grid(
            row=1, column=3, sticky="ew", padx=(6, 0), pady=(8, 0)
        )

        ttk.Label(top, text="Backend").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(top, textvariable=self.backend_var).grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Label(top, text="Control").grid(row=2, column=2, sticky="w", pady=(8, 0))
        ttk.Label(top, textvariable=self.control_mode_var).grid(row=2, column=3, sticky="w", pady=(8, 0))

        ttk.Label(top, text="Socket").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(top, textvariable=self.socket_var).grid(
            row=3, column=1, columnspan=3, sticky="w", pady=(8, 0)
        )

        pose_frame = ttk.LabelFrame(main, text="Pose", padding=10)
        pose_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        pose_items = [
            ("X (mm)", "x"),
            ("Y (mm)", "y"),
            ("Z (mm)", "z"),
            ("Roll (deg)", "roll"),
            ("Pitch (deg)", "pitch"),
            ("Yaw (deg)", "yaw"),
        ]
        for idx, (label, key) in enumerate(pose_items):
            row = idx // 3
            col = (idx % 3) * 2
            ttk.Label(pose_frame, text=label).grid(row=row, column=col, sticky="w")
            ttk.Label(pose_frame, textvariable=self.pose_vars[key], width=11).grid(
                row=row, column=col + 1, sticky="w", padx=(6, 18)
            )

        settings = ttk.LabelFrame(main, text="Step Sizes", padding=10)
        settings.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(settings, text="Linear (mm)").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            settings,
            from_=1.0,
            to=100.0,
            increment=1.0,
            width=8,
            textvariable=self.linear_step_mm,
        ).grid(row=0, column=1, sticky="w", padx=(6, 16))
        ttk.Label(settings, text="Angular (deg)").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(
            settings,
            from_=1.0,
            to=45.0,
            increment=1.0,
            width=8,
            textvariable=self.angular_step_deg,
        ).grid(row=0, column=3, sticky="w", padx=(6, 16))
        ttk.Label(settings, text="Speed").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(
            settings,
            from_=0.1,
            to=2.0,
            increment=0.1,
            width=8,
            textvariable=self.speed,
        ).grid(row=0, column=5, sticky="w", padx=(6, 0))

        translate = ttk.LabelFrame(main, text="Translation", padding=10)
        translate.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        translate.columnconfigure(0, weight=1)
        translate.columnconfigure(1, weight=1)
        translate.columnconfigure(2, weight=1)

        self._add_action_button(
            translate,
            row=0,
            column=1,
            text="+X Front",
            command=lambda: self._request_step("translation", "x", +1.0),
        )
        self._add_action_button(
            translate,
            row=1,
            column=0,
            text="+Y Left",
            command=lambda: self._request_step("translation", "y", +1.0),
        )
        self._add_action_button(
            translate,
            row=1,
            column=1,
            text="+Z Up",
            command=lambda: self._request_step("translation", "z", +1.0),
        )
        self._add_action_button(
            translate,
            row=1,
            column=2,
            text="-Y Right",
            command=lambda: self._request_step("translation", "y", -1.0),
        )
        self._add_action_button(
            translate,
            row=2,
            column=1,
            text="-X Back",
            command=lambda: self._request_step("translation", "x", -1.0),
        )
        self._add_action_button(
            translate,
            row=3,
            column=1,
            text="-Z Down",
            command=lambda: self._request_step("translation", "z", -1.0),
        )

        rotate = ttk.LabelFrame(main, text="Rotation", padding=10)
        rotate.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        rotate.columnconfigure(1, weight=1)
        rotate.columnconfigure(2, weight=1)

        rotation_rows = [
            ("Roll", "x", 0),
            ("Pitch", "y", 1),
            ("Yaw", "z", 2),
        ]
        for label, axis, row in rotation_rows:
            ttk.Label(rotate, text=label).grid(row=row, column=0, sticky="w")
            self._add_action_button(
                rotate,
                row=row,
                column=1,
                text=f"{label} -",
                command=lambda axis=axis: self._request_step("rotation", axis, -1.0),
            )
            self._add_action_button(
                rotate,
                row=row,
                column=2,
                text=f"{label} +",
                command=lambda axis=axis: self._request_step("rotation", axis, +1.0),
            )

        joints = ttk.LabelFrame(main, text="Joints", padding=10)
        joints.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(joints, text="Joint").grid(row=0, column=0, sticky="w")
        ttk.Label(joints, text="Angle (deg)").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(joints, text="Soft Limit").grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Label(joints, text="Target").grid(row=0, column=3, sticky="w", padx=(8, 0))
        for idx, (angle_var, limit_var) in enumerate(zip(self.joint_vars, self.joint_limit_vars), start=1):
            ttk.Label(joints, text=f"J{idx}").grid(row=idx, column=0, sticky="w", pady=2)
            ttk.Label(joints, textvariable=angle_var, width=8).grid(
                row=idx, column=1, sticky="w", padx=(8, 0), pady=2
            )
            ttk.Label(joints, textvariable=limit_var, width=18).grid(
                row=idx, column=2, sticky="w", padx=(8, 0), pady=2
            )
            entry = ttk.Entry(joints, width=10, textvariable=self.joint_target_vars[idx - 1])
            entry.grid(row=idx, column=3, sticky="w", padx=(8, 0), pady=2)
            entry.bind("<Return>", lambda _event: self._request_joint_targets())
        self._add_action_button(
            joints,
            row=7,
            column=3,
            text="Send Joints",
            command=self._request_joint_targets,
        )

        gripper = ttk.LabelFrame(main, text="Gripper", padding=10)
        gripper.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        gripper.columnconfigure(1, weight=1)
        ttk.Label(gripper, text="Opening").grid(row=0, column=0, sticky="w")
        ttk.Label(gripper, textvariable=self.gripper_status_var, width=8).grid(
            row=0, column=2, sticky="e", padx=(8, 0)
        )
        scale = ttk.Scale(
            gripper,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.gripper_value,
        )
        scale.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self._add_action_button(
            gripper,
            row=1,
            column=0,
            text="Close",
            command=lambda: self._request_gripper_value(0.0),
        )
        self._add_action_button(
            gripper,
            row=1,
            column=1,
            text="Set Gripper",
            command=self._request_gripper,
        )
        self._add_action_button(
            gripper,
            row=1,
            column=2,
            text="Open",
            command=lambda: self._request_gripper_value(1.0),
        )

        footer = ttk.Frame(main)
        footer.grid(row=7, column=0, sticky="ew", pady=(12, 0))
        self._add_action_button(footer, row=0, column=0, text="Refresh", command=self.refresh_snapshot)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=1, sticky="w", padx=(12, 0))

    def _add_action_button(
        self,
        parent: ttk.Widget,
        *,
        row: int,
        column: int,
        text: str,
        command: Callable[[], None],
    ) -> None:
        button = ttk.Button(parent, text=text, command=command)
        button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
        self._action_buttons.append(button)

    def _set_busy(self, busy: bool, message: str) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for button in self._action_buttons:
            button.configure(state=state)
        self.status_var.set(message)

    def _helper_command(self) -> list[str]:
        if self.helper_mode.get() == "local":
            return [sys.executable, str(HOST_HELPER)]
        return [str(CONTAINER_WRAPPER), CONTAINER_HELPER]

    def _run_helper(
        self,
        args: list[str],
        *,
        success_message: str,
    ) -> None:
        if self._busy:
            return

        self._set_busy(True, "Working...")

        def worker() -> None:
            cmd = self._helper_command() + ["--end-effector-frame", self.ee_frame.get()] + args
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            payload: dict[str, object]
            try:
                payload = json.loads(stdout) if stdout else {}
            except json.JSONDecodeError:
                payload = {"ok": False, "error": stdout or stderr or "Helper returned invalid JSON."}

            if proc.returncode != 0 and payload.get("ok", False):
                payload = {"ok": False, "error": stderr or "Helper command failed."}
            if proc.returncode != 0 and not payload:
                payload = {"ok": False, "error": stderr or "Helper command failed."}

            self.root.after(0, lambda: self._complete_helper(payload, success_message))

        threading.Thread(target=worker, daemon=True).start()

    def _complete_helper(self, payload: dict[str, object], success_message: str) -> None:
        self._set_busy(False, success_message)
        if not payload.get("ok", False):
            error = str(payload.get("error", "Unknown error"))
            self.status_var.set(error)
            messagebox.showerror("A1Z IK Teleop", error)
            return
        self._apply_snapshot(payload)

    def _apply_snapshot(self, payload: dict[str, object]) -> None:
        pose = dict(payload.get("pose", {}))
        xyz_mm = pose.get("xyz_mm", ["-", "-", "-"])
        rpy_deg = pose.get("rpy_deg", ["-", "-", "-"])
        self.pose_vars["x"].set(f"{float(xyz_mm[0]):.1f}")
        self.pose_vars["y"].set(f"{float(xyz_mm[1]):.1f}")
        self.pose_vars["z"].set(f"{float(xyz_mm[2]):.1f}")
        self.pose_vars["roll"].set(f"{float(rpy_deg[0]):.1f}")
        self.pose_vars["pitch"].set(f"{float(rpy_deg[1]):.1f}")
        self.pose_vars["yaw"].set(f"{float(rpy_deg[2]):.1f}")

        joints = list(payload.get("joint_pos_deg", []))
        for idx, var in enumerate(self.joint_vars):
            if idx < len(joints):
                var.set(f"{float(joints[idx]):.1f}")
                self.joint_target_vars[idx].set(f"{float(joints[idx]):.1f}")
            else:
                var.set("-")

        limits = payload.get("joint_limits_deg")
        if isinstance(limits, list):
            for idx, var in enumerate(self.joint_limit_vars):
                if idx < len(limits) and isinstance(limits[idx], list) and len(limits[idx]) == 2:
                    lo_deg = float(limits[idx][0])
                    hi_deg = float(limits[idx][1])
                    var.set(f"[{lo_deg:.0f}, {hi_deg:.0f}]")
                else:
                    var.set("-")
        else:
            for var in self.joint_limit_vars:
                var.set("-")

        self.backend_var.set(str(payload.get("backend", "-")))
        self.control_mode_var.set(str(payload.get("control_mode", "-")))
        self.socket_var.set(str(payload.get("socket_path", "-")))
        gripper = payload.get("gripper")
        if gripper is not None:
            gripper_value = float(gripper)
            self.gripper_value.set(gripper_value)
            self.gripper_status_var.set(f"{gripper_value:.2f}")
        else:
            self.gripper_status_var.set("-")
        self.status_var.set(str(payload.get("status_message", "Ready")))

    def refresh_snapshot(self) -> None:
        self._run_helper(["snapshot"], success_message="Refreshed")

    def _request_step(self, kind: str, axis: str, direction: float) -> None:
        if kind == "translation":
            delta = direction * (self.linear_step_mm.get() / 1000.0)
        else:
            delta = direction * self.angular_step_deg.get()
        args = [
            "step",
            "--kind",
            kind,
            "--axis",
            axis,
            "--delta",
            str(delta),
            "--frame",
            self.frame_mode.get(),
            "--speed",
            str(self.speed.get()),
            "--motion-mode",
            self.motion_mode.get(),
        ]
        self._run_helper(args, success_message="Step complete")

    def _request_joint_targets(self) -> None:
        try:
            joints = [float(var.get()) for var in self.joint_target_vars]
        except ValueError:
            messagebox.showerror("A1Z IK Teleop", "Joint target must be numeric.")
            return

        motion_mode = self.motion_mode.get()
        joints_csv = ",".join(f"{value:.6g}" for value in joints)
        if motion_mode == "move":
            args = [
                "move",
                "--speed",
                str(self.speed.get()),
                "--",
                joints_csv,
            ]
            self._run_a1zctl(args, success_message="Joint move complete")
            return

        args = [
            "command",
            "--",
            joints_csv,
        ]
        self._run_a1zctl(args, success_message="Joint target sent")

    def _request_gripper(self) -> None:
        self._request_gripper_value(float(self.gripper_value.get()))

    def _request_gripper_value(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        self.gripper_value.set(clamped)
        args = ["gripper", str(clamped)]
        self._run_a1zctl(args, success_message="Gripper command sent")

    def _run_a1zctl(self, args: list[str], *, success_message: str) -> None:
        if self._busy:
            return

        self._set_busy(True, "Working...")

        def worker() -> None:
            if self.helper_mode.get() == "local":
                cmd = [sys.executable, str(ROOT_DIR / "tools" / "a1zctl")] + args
            else:
                cmd = [str(CONTAINER_A1ZCTL)] + args
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            if proc.returncode != 0:
                payload = {"ok": False, "error": stderr or stdout or "a1zctl command failed."}
            else:
                payload = {"ok": True}
            self.root.after(0, lambda: self._complete_a1zctl(payload, success_message))

        threading.Thread(target=worker, daemon=True).start()

    def _complete_a1zctl(self, payload: dict[str, object], success_message: str) -> None:
        self._set_busy(False, success_message)
        if not payload.get("ok", False):
            error = str(payload.get("error", "Unknown error"))
            self.status_var.set(error)
            messagebox.showerror("A1Z IK Teleop", error)
            return
        if self.motion_mode.get() == "command":
            self.root.after(400, self.refresh_snapshot)
            return
        self.refresh_snapshot()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tk teleop panel for A1Z Cartesian IK and per-joint trim control."
    )
    parser.add_argument(
        "--helper-mode",
        choices=["container", "local"],
        default="container",
        help="Run IK helper inside the project container or in the local Python environment.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    TeleopApp(root, helper_mode=args.helper_mode)
    root.mainloop()


if __name__ == "__main__":
    main()
