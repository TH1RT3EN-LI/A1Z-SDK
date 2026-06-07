#!/usr/bin/env python3
"""Host-local A1Z teleop panel using the container control wrapper."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from typing import Any, Callable

try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError as exc:
    raise SystemExit(
        "当前 Python 环境缺少 tkinter。\n"
        "Ubuntu 可先执行: sudo apt install python3-tk"
    ) from exc


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
DEFAULT_RUNNER = os.path.join(REPO_ROOT, "scripts", "a1zctl_in_container.sh")


class A1ZRunnerClient:
    def __init__(self, runner_path: str) -> None:
        self.runner_path = runner_path

    def run(self, *args: str, timeout: float = 5.0) -> dict[str, Any]:
        if not os.path.isfile(self.runner_path):
            raise RuntimeError(f"控制脚本不存在: {self.runner_path}")

        proc = subprocess.run(
            [self.runner_path, "--json", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            stdout = proc.stdout.strip()
            raise RuntimeError(stderr or stdout or f"退出码 {proc.returncode}")

        output = proc.stdout.strip()
        if not output:
            raise RuntimeError("未收到控制响应")

        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"控制输出无法解析: {output}") from exc


class TeleopApp:
    STATUS_POLL_MS = 400
    SEND_INTERVAL_MS = 80
    RECONNECT_MS = 2500

    def __init__(self, root: tk.Tk, runner_path: str) -> None:
        self.root = root
        self.client = A1ZRunnerClient(runner_path)

        self.status_var = tk.StringVar(value="连接中")
        self.backend_var = tk.StringVar(value="-")
        self.step_var = tk.StringVar(value="0.5")
        self.gripper_step_var = tk.StringVar(value="0.05")
        self.home_speed_var = tk.StringVar(value="0.5")
        self.auto_send_var = tk.BooleanVar(value=True)
        self.lock_var = tk.StringVar(value="已锁定")

        self.target_vars = [tk.DoubleVar(value=0.0) for _ in range(6)]
        self.target_text_vars = [tk.StringVar(value="0.0") for _ in range(6)]
        self.actual_vars = [tk.StringVar(value="0.0") for _ in range(6)]
        self.limit_vars = [tk.StringVar(value="[-180.0, 180.0]") for _ in range(6)]
        self.gripper_target_var = tk.StringVar(value="1.00")
        self.gripper_actual_var = tk.StringVar(value="1.00")
        self.gripper_value = 1.0

        self.connected = False
        self.has_gripper = False
        self.joint_limits_deg: list[tuple[float, float]] = [(-180.0, 180.0) for _ in range(6)]

        self._connect_in_flight = False
        self._status_in_flight = False
        self._command_in_flight = False
        self._target_dirty = False
        self._suspend_callbacks = False
        self._callbacks: queue.Queue[tuple[Callable[..., None], tuple[Any, ...]]] = queue.Queue()

        self._build_style()
        self._build_ui()

        self.root.after(120, self._drain_callbacks)
        self.root.after(self.STATUS_POLL_MS, self._poll_status)
        self.root.after(self.SEND_INTERVAL_MS, self._send_loop)
        self.root.after(self.RECONNECT_MS, self._auto_connect_loop)
        self.root.after(180, self.connect)

    def _build_style(self) -> None:
        self.root.title("A1Z 软件主臂")
        self.root.geometry("960x640")
        self.root.minsize(900, 580)
        self.root.configure(bg="#f3f5f7")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Root.TFrame", background="#f3f5f7")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#f3f5f7", font=("Sans", 18, "bold"), foreground="#17202a")
        style.configure("Muted.TLabel", background="#f3f5f7", foreground="#5d6d7e", font=("Sans", 10))
        style.configure("PanelTitle.TLabel", background="#ffffff", foreground="#1f2d3d", font=("Sans", 11, "bold"))
        style.configure("Body.TLabel", background="#ffffff", foreground="#1f2d3d", font=("Sans", 10))
        style.configure("Value.TLabel", background="#ffffff", foreground="#111827", font=("Sans", 10, "bold"))
        style.configure("Small.TButton", padding=(10, 5))
        style.configure("Step.TButton", padding=(10, 3))

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, style="Root.TFrame", padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main, style="Root.TFrame")
        header.pack(fill=tk.X)

        title_box = ttk.Frame(header, style="Root.TFrame")
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text="A1Z 软件主臂", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, textvariable=self.lock_var, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        status_box = ttk.Frame(header, style="Root.TFrame")
        status_box.pack(side=tk.RIGHT)
        ttk.Label(status_box, text="状态", style="Muted.TLabel").grid(row=0, column=0, sticky="e")
        ttk.Label(status_box, textvariable=self.status_var, style="Title.TLabel").grid(row=0, column=1, padx=(8, 18))
        ttk.Label(status_box, text="后端", style="Muted.TLabel").grid(row=0, column=2, sticky="e")
        ttk.Label(status_box, textvariable=self.backend_var, style="Title.TLabel").grid(row=0, column=3, padx=(8, 0))

        toolbar = ttk.Frame(main, style="Panel.TFrame", padding=12)
        toolbar.pack(fill=tk.X, pady=(14, 12))

        left_tools = ttk.Frame(toolbar, style="Panel.TFrame")
        left_tools.pack(side=tk.LEFT)
        ttk.Button(left_tools, text="连接", style="Small.TButton", command=self.connect).pack(side=tk.LEFT)
        ttk.Button(left_tools, text="回读", style="Small.TButton", command=self.sync_from_robot).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(left_tools, text="就位", style="Small.TButton", command=lambda: self.move_preset("ready", "就位")).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(left_tools, text="回零", style="Small.TButton", command=lambda: self.move_preset("home", "回零")).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(left_tools, text="发送", style="Small.TButton", command=self.send_target_once).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        right_tools = ttk.Frame(toolbar, style="Panel.TFrame")
        right_tools.pack(side=tk.RIGHT)
        ttk.Label(right_tools, text="关节步长", style="Body.TLabel").pack(side=tk.LEFT)
        ttk.Combobox(
            right_tools,
            textvariable=self.step_var,
            values=("0.1", "0.2", "0.5", "1.0", "2.0"),
            state="readonly",
            width=6,
        ).pack(side=tk.LEFT, padx=(8, 14))
        ttk.Label(right_tools, text="夹爪步长", style="Body.TLabel").pack(side=tk.LEFT)
        ttk.Combobox(
            right_tools,
            textvariable=self.gripper_step_var,
            values=("0.01", "0.02", "0.05", "0.10"),
            state="readonly",
            width=6,
        ).pack(side=tk.LEFT, padx=(8, 14))
        ttk.Label(right_tools, text="回零速度", style="Body.TLabel").pack(side=tk.LEFT)
        ttk.Combobox(
            right_tools,
            textvariable=self.home_speed_var,
            values=("0.2", "0.3", "0.5", "0.8", "1.0"),
            state="readonly",
            width=6,
        ).pack(side=tk.LEFT, padx=(8, 14))
        ttk.Checkbutton(right_tools, text="自动发送", variable=self.auto_send_var).pack(side=tk.LEFT)

        joints_panel = ttk.Frame(main, style="Panel.TFrame", padding=14)
        joints_panel.pack(fill=tk.BOTH, expand=True)

        head = ttk.Frame(joints_panel, style="Panel.TFrame")
        head.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(head, text="关节控制", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(head, text="目标", style="Body.TLabel").grid(row=0, column=3, padx=(16, 0))
        ttk.Label(head, text="当前", style="Body.TLabel").grid(row=0, column=4, padx=(16, 0))
        ttk.Label(head, text="限位", style="Body.TLabel").grid(row=0, column=5, padx=(16, 0))

        self.scales: list[tk.Scale] = []
        for idx in range(6):
            row = ttk.Frame(joints_panel, style="Panel.TFrame")
            row.pack(fill=tk.X, pady=4)

            ttk.Label(row, text=f"J{idx + 1}", style="PanelTitle.TLabel", width=4).pack(side=tk.LEFT)
            ttk.Button(row, text="-", style="Step.TButton", command=lambda joint_idx=idx: self.nudge_joint(joint_idx, -1)).pack(
                side=tk.LEFT, padx=(8, 6)
            )

            scale = tk.Scale(
                row,
                from_=-180.0,
                to=180.0,
                resolution=0.1,
                orient=tk.HORIZONTAL,
                variable=self.target_vars[idx],
                state=tk.DISABLED,
                showvalue=False,
                highlightthickness=0,
                bd=0,
                sliderlength=18,
                length=380,
                troughcolor="#dce4ea",
                activebackground="#dce4ea",
                bg="#ffffff",
            )
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.scales.append(scale)

            ttk.Button(row, text="+", style="Step.TButton", command=lambda joint_idx=idx: self.nudge_joint(joint_idx, 1)).pack(
                side=tk.LEFT, padx=(6, 12)
            )
            ttk.Label(row, textvariable=self.target_text_vars[idx], style="Value.TLabel", width=8).pack(side=tk.LEFT)
            ttk.Label(row, textvariable=self.actual_vars[idx], style="Body.TLabel", width=8).pack(side=tk.LEFT, padx=(16, 0))
            ttk.Label(row, textvariable=self.limit_vars[idx], style="Body.TLabel", width=18).pack(side=tk.LEFT, padx=(16, 0))

        self.gripper_panel = ttk.Frame(main, style="Panel.TFrame", padding=(14, 0, 14, 14))
        self.gripper_panel.pack(fill=tk.X)

        g_row = ttk.Frame(self.gripper_panel, style="Panel.TFrame")
        g_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(g_row, text="夹爪", style="PanelTitle.TLabel", width=4).pack(side=tk.LEFT)
        ttk.Button(g_row, text="-", style="Step.TButton", command=lambda: self.nudge_gripper(-1)).pack(
            side=tk.LEFT, padx=(8, 6)
        )

        self.gripper_scale = tk.Scale(
            g_row,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=tk.DoubleVar(value=1.0),
            state=tk.DISABLED,
            showvalue=False,
            highlightthickness=0,
            bd=0,
            sliderlength=18,
            length=380,
            troughcolor="#dce4ea",
            activebackground="#dce4ea",
            bg="#ffffff",
        )
        self.gripper_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(g_row, text="+", style="Step.TButton", command=lambda: self.nudge_gripper(1)).pack(
            side=tk.LEFT, padx=(6, 12)
        )
        ttk.Label(g_row, textvariable=self.gripper_target_var, style="Value.TLabel", width=8).pack(side=tk.LEFT)
        ttk.Label(g_row, textvariable=self.gripper_actual_var, style="Body.TLabel", width=8).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Label(g_row, text="[0.00, 1.00]", style="Body.TLabel", width=18).pack(side=tk.LEFT, padx=(16, 0))

    def connect(self) -> None:
        if self._connect_in_flight:
            return
        self._connect_in_flight = True
        self.status_var.set("连接中")
        self._run_async(self._connect_worker, self._on_connect_result)

    def _connect_worker(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.client.run("info", timeout=10.0), self.client.run("status", timeout=10.0)

    def _on_connect_result(self, result: tuple[dict[str, Any], dict[str, Any]] | None, error: Exception | None) -> None:
        self._connect_in_flight = False
        if error is not None:
            self.connected = False
            self.status_var.set("未连接")
            return

        assert result is not None
        info, status = result
        self.connected = True
        self.status_var.set("已连接")
        self.backend_var.set(info.get("backend", "-"))
        self.has_gripper = "gripper_range" in info
        self._apply_joint_limits(info.get("joint_limits_deg", {}))
        self._set_gripper_visible(self.has_gripper)
        self._apply_status(status, sync_targets=True)

    def _auto_connect_loop(self) -> None:
        if not self.connected and not self._connect_in_flight:
            self.connect()
        self.root.after(self.RECONNECT_MS, self._auto_connect_loop)

    def sync_from_robot(self) -> None:
        if not self.connected:
            self.connect()
            return
        self._request_status(sync_targets=True)

    def move_preset(self, preset: str, status_text: str) -> None:
        if not self.connected:
            self.status_var.set("未连接")
            return
        try:
            speed = max(0.1, float(self.home_speed_var.get()))
        except ValueError:
            speed = 0.5
        self.status_var.set(status_text)
        self._run_async(
            lambda: self.client.run("move", "--preset", preset, "--speed", str(speed), timeout=30.0),
            self._on_motion_complete,
        )

    def _on_motion_complete(self, result: dict[str, Any] | None, error: Exception | None) -> None:
        if error is not None:
            self.connected = False
            self.status_var.set("未连接")
            return
        self.connected = True
        self.status_var.set("已连接")
        if result is not None and "pos_deg" in result:
            self._apply_status({"pos_deg": result["pos_deg"]}, sync_targets=True)
        self._request_status(sync_targets=True)

    def send_target_once(self) -> None:
        self._target_dirty = True
        self._maybe_send_target(force=True)

    def nudge_joint(self, joint_idx: int, direction: int) -> None:
        if not self.connected:
            self.status_var.set("未连接")
            return

        try:
            step = float(self.step_var.get())
        except ValueError:
            step = 0.5

        current = self.target_vars[joint_idx].get()
        lo, hi = self.joint_limits_deg[joint_idx]
        target = max(lo, min(hi, current + direction * step))
        self._set_joint_target(joint_idx, target)
        self._after_local_edit()

    def nudge_gripper(self, direction: int) -> None:
        if not self.connected or not self.has_gripper:
            self.status_var.set("未连接")
            return

        try:
            step = float(self.gripper_step_var.get())
        except ValueError:
            step = 0.05

        self.gripper_value = max(0.0, min(1.0, self.gripper_value + direction * step))
        self._set_gripper_target(self.gripper_value)
        self._after_local_edit()

    def _after_local_edit(self) -> None:
        self._target_dirty = True
        if self.auto_send_var.get():
            self._maybe_send_target(force=True)

    def _request_status(self, sync_targets: bool) -> None:
        if self._status_in_flight or not self.connected:
            return
        self._status_in_flight = True
        self._run_async(
            lambda: self.client.run("status", timeout=10.0),
            lambda result, error: self._on_status_result(result, error, sync_targets),
        )

    def _on_status_result(
        self,
        result: dict[str, Any] | None,
        error: Exception | None,
        sync_targets: bool,
    ) -> None:
        self._status_in_flight = False
        if error is not None:
            self.connected = False
            self.status_var.set("未连接")
            return
        self.connected = True
        self.status_var.set("已连接")
        if result is not None:
            self._apply_status(result, sync_targets=sync_targets)

    def _poll_status(self) -> None:
        if self.connected:
            self._request_status(sync_targets=False)
        self.root.after(self.STATUS_POLL_MS, self._poll_status)

    def _send_loop(self) -> None:
        if self.connected and self.auto_send_var.get():
            self._maybe_send_target(force=False)
        self.root.after(self.SEND_INTERVAL_MS, self._send_loop)

    def _maybe_send_target(self, force: bool) -> None:
        if self._command_in_flight or (not self._target_dirty and not force):
            return

        joints = ",".join(f"{var.get():.3f}" for var in self.target_vars)
        cmd = ["command", joints]
        if self.has_gripper:
            cmd.extend(["--gripper", f"{self.gripper_value:.3f}"])

        self._command_in_flight = True
        self._target_dirty = False
        self._run_async(lambda: self.client.run(*cmd, timeout=10.0), self._on_command_result)

    def _on_command_result(self, result: dict[str, Any] | None, error: Exception | None) -> None:
        self._command_in_flight = False
        if error is not None:
            self.connected = False
            self.status_var.set("未连接")
            return
        self.connected = True
        self.status_var.set("已连接")
        if result is not None and "gripper" in result:
            self._set_gripper_target(float(result["gripper"]))

    def _apply_joint_limits(self, joint_limits_deg: dict[str, list[float]]) -> None:
        for idx in range(6):
            lo, hi = joint_limits_deg.get(f"J{idx + 1}", [-180.0, 180.0])
            lo_f = float(lo)
            hi_f = float(hi)
            self.joint_limits_deg[idx] = (lo_f, hi_f)
            self.scales[idx].configure(from_=lo_f, to=hi_f)
            self.limit_vars[idx].set(f"[{lo_f:.1f}, {hi_f:.1f}]")

    def _apply_status(self, status: dict[str, Any], sync_targets: bool) -> None:
        pos_deg = status.get("pos_deg")
        if pos_deg is not None:
            for idx, value in enumerate(pos_deg[:6]):
                self.actual_vars[idx].set(f"{float(value):.1f}")
            if sync_targets:
                self._set_joint_targets_from_status(pos_deg[:6])

        if self.has_gripper and "gripper" in status and status["gripper"] is not None:
            g_value = float(status["gripper"])
            self.gripper_actual_var.set(f"{g_value:.2f}")
            if sync_targets:
                self._set_gripper_target(g_value)

    def _set_joint_targets_from_status(self, joints_deg: list[float]) -> None:
        self._suspend_callbacks = True
        try:
            for idx, value in enumerate(joints_deg[:6]):
                self._set_joint_target(idx, float(value))
        finally:
            self._suspend_callbacks = False
        self._target_dirty = False

    def _set_joint_target(self, idx: int, value: float) -> None:
        self.target_vars[idx].set(value)
        self.target_text_vars[idx].set(f"{value:.1f}")

    def _set_gripper_target(self, value: float) -> None:
        self.gripper_value = max(0.0, min(1.0, value))
        self.gripper_scale.set(self.gripper_value)
        self.gripper_target_var.set(f"{self.gripper_value:.2f}")

    def _set_gripper_visible(self, visible: bool) -> None:
        if visible:
            self.gripper_panel.pack(fill=tk.X)
        else:
            self.gripper_panel.pack_forget()

    def _run_async(
        self,
        worker: Callable[[], Any],
        callback: Callable[[Any | None, Exception | None], None],
    ) -> None:
        def runner() -> None:
            try:
                result = worker()
                self._callbacks.put((callback, (result, None)))
            except Exception as exc:
                self._callbacks.put((callback, (None, exc)))

        threading.Thread(target=runner, daemon=True).start()

    def _drain_callbacks(self) -> None:
        while True:
            try:
                callback, args = self._callbacks.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self.root.after(120, self._drain_callbacks)


def main() -> None:
    root = tk.Tk()
    TeleopApp(root, runner_path=DEFAULT_RUNNER)
    root.mainloop()


if __name__ == "__main__":
    main()
