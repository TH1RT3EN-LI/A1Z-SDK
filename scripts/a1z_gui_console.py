#!/usr/bin/env python3
"""A1Z host desktop console for Isaac Sim, robot control, and AnyGrasp."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from a1z_ext.gui_console import (  # noqa: E402
    ARM_SPEED_LIMITS,
    AnyGraspOptions,
    ManagedProcess,
    allocate_anygrasp_run_dir,
    build_a1zctl_command,
    build_anygrasp_command,
    build_host_isaac_env,
    build_isaac_command,
    build_ros_bridge_env,
    build_ros_bridge_start_command,
    build_ros_bridge_stop_command,
    build_rviz_command,
    build_rviz_env,
    classify_log_message,
    load_json,
    normalize_process_log_line,
    probe_a1z_server,
    request_a1z,
    summarize_anygrasp_output,
)


SETTINGS_PATH = ROOT_DIR / "runtime" / "gui-console" / "settings.json"
LOG_DIR = ROOT_DIR / "runtime" / "gui-console" / "logs"
ROS_BRIDGE_STATUS_PATH = ROOT_DIR / "runtime" / "gui-console" / "ros_bridge_start_status.json"


class A1ZConsole:
    BG = "#10141c"
    PANEL = "#19202b"
    PANEL_2 = "#222b38"
    TEXT = "#e8edf4"
    MUTED = "#9aa9ba"
    ACCENT = "#38bdf8"
    GOOD = "#34d399"
    WARN = "#fbbf24"
    BAD = "#fb7185"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("A1Z Host Console")
        self.root.geometry("1280x820")
        self.root.minsize(1040, 680)
        self.root.configure(bg=self.BG)
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.processes: dict[str, ManagedProcess] = {}
        self.isaac_process: ManagedProcess | None = None
        self.ros_bridge_process: ManagedProcess | None = None
        self.rviz_process: ManagedProcess | None = None
        self.ros_bridge_owned = False
        self.ros_bridge_ready = False
        self._probe_running = False
        self._closing = False
        self._stopping_full_project = False
        self._log_file: Path | None = None
        self._collapsed_process_notices: set[tuple[str, str]] = set()
        self._anygrasp_active_dry_run: bool | None = None
        self.settings = self._load_settings()

        self._configure_style()
        self._build_variables()
        self._build_ui()
        self._new_log_file()
        self._write_log("console", "A1Z Host Console 已启动")
        self._write_log("console", "运行模式: 宿主机 Isaac Sim App；WebRTC 未启用")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_events)
        self.root.after(300, self.refresh_status)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=self.BG, foreground=self.TEXT)
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("Card.TFrame", background=self.PANEL_2)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT)
        style.configure("Panel.TLabel", background=self.PANEL, foreground=self.TEXT)
        style.configure("Card.TLabel", background=self.PANEL_2, foreground=self.TEXT)
        style.configure(
            "Title.TLabel",
            background=self.BG,
            foreground=self.TEXT,
            font=("Sans", 20, "bold"),
        )
        style.configure(
            "Sub.TLabel",
            background=self.BG,
            foreground=self.MUTED,
            font=("Sans", 10),
        )
        style.configure(
            "Badge.TLabel",
            background=self.PANEL_2,
            foreground=self.MUTED,
            padding=(10, 5),
            font=("Sans", 9, "bold"),
        )
        style.configure(
            "Accent.TButton",
            background=self.ACCENT,
            foreground="#07111a",
            padding=(13, 7),
            font=("Sans", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#7dd3fc")])
        style.configure("TButton", padding=(11, 6), background=self.PANEL_2, foreground=self.TEXT)
        style.map("TButton", background=[("active", "#303c4d")])
        style.configure("Danger.TButton", background="#7f1d32", foreground="#ffe4e9")
        style.map("Danger.TButton", background=[("active", "#a62b45")])
        style.configure("TEntry", fieldbackground="#0d1118", foreground=self.TEXT)
        style.configure("TCombobox", fieldbackground="#0d1118", foreground=self.TEXT)
        style.configure("TCheckbutton", background=self.PANEL, foreground=self.TEXT)
        style.map("TCheckbutton", background=[("active", self.PANEL)])
        style.configure("Card.TCheckbutton", background=self.PANEL_2, foreground=self.TEXT)
        style.map("Card.TCheckbutton", background=[("active", self.PANEL_2)])
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(15, 8), background=self.PANEL, foreground=self.MUTED)
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.PANEL_2)],
            foreground=[("selected", self.TEXT)],
        )
        style.configure("Horizontal.TProgressbar", background=self.ACCENT, troughcolor=self.PANEL_2)

    def _build_variables(self) -> None:
        default_isaac_root = os.environ.get("ISAAC_SIM_ROOT", str(Path.home() / "isaacsim"))
        default_isaac = self.settings.get("isaac_root", default_isaac_root)
        default_world = self.settings.get(
            "world_usd", str(ROOT_DIR / "build" / "scenes" / "A1Z_G1Z_world.usd")
        )
        self.isaac_root_var = tk.StringVar(value=default_isaac)
        self.world_var = tk.StringVar(value=default_world)
        self.tcp_host_var = tk.StringVar(value=self.settings.get("tcp_host", "127.0.0.1"))
        self.tcp_port_var = tk.StringVar(value=str(self.settings.get("tcp_port", 37103)))
        self.ee_drag_enabled_var = tk.BooleanVar(
            value=bool(self.settings.get("ee_drag_enabled", False))
        )
        self.isaac_badge_var = tk.StringVar(value="ISAAC · 未启动")
        self.server_badge_var = tk.StringVar(value="A1Z · 检查中")
        self.ros_bridge_badge_var = tk.StringVar(value="ROS · 未启动")
        self.anygrasp_badge_var = tk.StringVar(value="ANYGRASP · 空闲")
        self.rviz_badge_var = tk.StringVar(value="RVIZ · 未启动")
        self.status_var = tk.StringVar(value="正在检查本机运行环境…")
        self.rviz_config_var = tk.StringVar(
            value=self.settings.get(
                "rviz_config",
                str(ROOT_DIR / "ros2_ws" / "rviz" / "a1z_d405.rviz"),
            )
        )
        self.rviz_rebuild_var = tk.BooleanVar(value=False)

        self.instruction_var = tk.StringVar(value=self.settings.get("instruction", "抓取桌面上的目标物体"))
        self.provider_var = tk.StringVar(value=self.settings.get("provider", "kimi"))
        self.output_var = tk.StringVar(value="")
        self.exec_mode_var = tk.StringVar(value=self.settings.get("execution_mode", "best_direct"))
        self.grasp_mode_var = tk.StringVar(value=self.settings.get("grasp_mode", "physical_v2"))
        default_speed = f"{ARM_SPEED_LIMITS.default:g}"
        self.arm_speed_var = tk.StringVar(
            value=str(self.settings.get("arm_speed_rad_s", default_speed))
        )
        self.settle_var = tk.StringVar(value="0.05")
        self.require_joints_var = tk.BooleanVar(
            value=bool(self.settings.get("require_current_joints", True))
        )
        self.dry_run_var = tk.BooleanVar(value=bool(self.settings.get("dry_run", False)))
        self.anygrasp_result_var = tk.StringVar(value="尚未运行")

        self.preset_var = tk.StringVar(value="ready")
        self.speed_var = tk.StringVar(
            value=str(self.settings.get("manual_speed_rad_s", default_speed))
        )
        self.joints_var = tk.StringVar(value="0,60,-60,0,0,0")
        self.gripper_var = tk.DoubleVar(value=1.0)
        self.motion_confirm_var = tk.BooleanVar(value=False)
        self.command_cwd_var = tk.StringVar(value=str(ROOT_DIR))
        self.shell_command_var = tk.StringVar(value="python3 tools/a1zctl --json status")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(18, 14))
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 12))
        title_box = ttk.Frame(header)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(title_box, text="A1Z Host Console", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            title_box,
            text="宿主机 Isaac Sim App · 原生 A1Z TCP 控制 · AnyGrasp 工作流",
            style="Sub.TLabel",
        ).pack(anchor=tk.W, pady=(2, 0))
        badges = ttk.Frame(header)
        badges.pack(side=tk.RIGHT)
        ttk.Label(badges, textvariable=self.isaac_badge_var, style="Badge.TLabel").pack(
            side=tk.LEFT, padx=3
        )
        ttk.Label(badges, textvariable=self.server_badge_var, style="Badge.TLabel").pack(
            side=tk.LEFT, padx=3
        )
        ttk.Label(badges, textvariable=self.ros_bridge_badge_var, style="Badge.TLabel").pack(
            side=tk.LEFT, padx=3
        )
        ttk.Label(badges, textvariable=self.anygrasp_badge_var, style="Badge.TLabel").pack(
            side=tk.LEFT, padx=3
        )
        ttk.Label(badges, textvariable=self.rviz_badge_var, style="Badge.TLabel").pack(
            side=tk.LEFT, padx=3
        )

        paned = ttk.Panedwindow(outer, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(paned)
        log_panel = ttk.Frame(paned, style="Panel.TFrame", padding=(10, 8))
        paned.add(top, weight=4)
        paned.add(log_panel, weight=2)

        self.notebook = ttk.Notebook(top)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self._build_start_tab()
        self._build_anygrasp_tab()
        self._build_control_tab()
        self._build_terminal_tab()
        self._build_log_panel(log_panel)

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(9, 0))
        ttk.Label(footer, textvariable=self.status_var, style="Sub.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            footer,
            text="Ctrl+Enter 执行终端命令",
            style="Sub.TLabel",
        ).pack(side=tk.RIGHT)

    def _tab(self, title: str) -> ttk.Frame:
        frame = ttk.Frame(self.notebook, style="Panel.TFrame", padding=18)
        self.notebook.add(frame, text=title)
        return frame

    def _field(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.Variable,
        *,
        browse: Any = None,
    ) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 12), pady=6
        )
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky=tk.EW, pady=6)
        if browse is not None:
            ttk.Button(parent, text="浏览", command=browse).grid(row=row, column=2, padx=(8, 0))
        return entry

    def _build_start_tab(self) -> None:
        tab = self._tab("启动与状态")
        tab.columnconfigure(0, weight=3)
        tab.columnconfigure(1, weight=2)

        config = ttk.Frame(tab, style="Card.TFrame", padding=16)
        config.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 8))
        config.columnconfigure(1, weight=1)
        ttk.Label(config, text="宿主机运行配置", style="Card.TLabel", font=("Sans", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 8)
        )
        self._field(config, 1, "Isaac Sim 根目录", self.isaac_root_var, browse=self._browse_isaac)
        self._field(config, 2, "世界 USD", self.world_var, browse=self._browse_world)
        self._field(config, 3, "A1Z TCP 主机", self.tcp_host_var)
        self._field(config, 4, "A1Z TCP 端口", self.tcp_port_var)
        ttk.Checkbutton(
            config,
            text="启动时启用 EE 视口拖拽控制（默认关闭）",
            variable=self.ee_drag_enabled_var,
        ).grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(7, 2))
        ttk.Label(
            config,
            text="该选项仅在下次启动 Isaac App 时生效；不会启动 WebRTC 服务。",
            style="Card.TLabel",
            foreground=self.MUTED,
        ).grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 2))
        actions = ttk.Frame(config, style="Card.TFrame")
        actions.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(12, 0))
        self.start_button = ttk.Button(
            actions, text="启动完整项目", style="Accent.TButton", command=self.start_full_project
        )
        self.start_button.pack(side=tk.LEFT)
        ttk.Button(actions, text="刷新状态", command=self.refresh_status).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="优雅停止", command=self.stop_full_project).pack(side=tk.LEFT)
        ttk.Button(
            actions,
            text="强制停止自有进程",
            style="Danger.TButton",
            command=self.force_stop_full_project,
        ).pack(side=tk.LEFT, padx=8)

        cards = ttk.Frame(tab, style="Panel.TFrame")
        cards.grid(row=0, column=1, sticky=tk.NSEW, padx=(8, 0))
        for idx, (title, value, detail) in enumerate(
            [
                ("Isaac App", self.isaac_badge_var, "仅跟踪本控制台启动的宿主机进程"),
                ("A1Z 控制服务", self.server_badge_var, "TCP 指纹校验后才允许发送机器人命令"),
                (
                    "ROS 2 数据链路",
                    self.ros_bridge_badge_var,
                    "完整启动会等待 D405，并验证 TF、彩色和深度图像均有真实数据",
                ),
            ]
        ):
            card = ttk.Frame(cards, style="Card.TFrame", padding=15)
            card.pack(fill=tk.X, pady=(0, 9))
            ttk.Label(card, text=title, style="Card.TLabel", font=("Sans", 11, "bold")).pack(anchor=tk.W)
            ttk.Label(card, textvariable=value, style="Card.TLabel", foreground=self.ACCENT).pack(
                anchor=tk.W, pady=(5, 2)
            )
            ttk.Label(card, text=detail, style="Card.TLabel", foreground=self.MUTED, wraplength=360).pack(
                anchor=tk.W
            )

        rviz = ttk.Frame(cards, style="Card.TFrame", padding=15)
        rviz.pack(fill=tk.X, pady=(0, 9))
        ttk.Label(rviz, text="RViz", style="Card.TLabel", font=("Sans", 11, "bold")).pack(
            anchor=tk.W
        )
        ttk.Label(rviz, textvariable=self.rviz_badge_var, style="Card.TLabel", foreground=self.ACCENT).pack(
            anchor=tk.W, pady=(5, 4)
        )
        rviz_path = ttk.Frame(rviz, style="Card.TFrame")
        rviz_path.pack(fill=tk.X)
        ttk.Entry(rviz_path, textvariable=self.rviz_config_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(rviz_path, text="配置", command=self._browse_rviz_config).pack(
            side=tk.LEFT, padx=(7, 0)
        )
        ttk.Checkbutton(
            rviz,
            text="本次启动前重建 RViz 镜像",
            variable=self.rviz_rebuild_var,
            style="Card.TCheckbutton",
        ).pack(anchor=tk.W, pady=(7, 5))
        rviz_actions = ttk.Frame(rviz, style="Card.TFrame")
        rviz_actions.pack(fill=tk.X)
        ttk.Button(rviz_actions, text="启动 RViz", command=self.start_rviz).pack(side=tk.LEFT)
        ttk.Button(rviz_actions, text="停止 RViz", command=self.stop_rviz).pack(
            side=tk.LEFT, padx=7
        )
        ttk.Label(
            rviz,
            text="使用宿主机显示与项目 ROS_DOMAIN_ID；“完整项目”就绪后可直接显示 A1Z 图像/TF。",
            style="Card.TLabel",
            foreground=self.MUTED,
            wraplength=360,
        ).pack(anchor=tk.W, pady=(7, 0))

    def _build_anygrasp_tab(self) -> None:
        tab = self._tab("AnyGrasp")
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, text="自然语言目标", style="Panel.TLabel").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Entry(tab, textvariable=self.instruction_var).grid(
            row=0, column=1, columnspan=3, sticky=tk.EW, pady=6
        )
        ttk.Label(tab, text="Provider", style="Panel.TLabel").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Entry(tab, textvariable=self.provider_var, width=18).grid(row=1, column=1, sticky=tk.W)
        ttk.Label(tab, text="执行计划", style="Panel.TLabel").grid(row=1, column=2, sticky=tk.E, padx=(20, 8))
        ttk.Combobox(
            tab,
            textvariable=self.exec_mode_var,
            values=("best_direct", "adapter_selected"),
            state="readonly",
            width=18,
        ).grid(row=1, column=3, sticky=tk.W)
        ttk.Label(tab, text="抓取模式", style="Panel.TLabel").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Combobox(
            tab,
            textvariable=self.grasp_mode_var,
            values=("physical_v2", "sim_contact_attach", "raw_gripper"),
            state="readonly",
            width=21,
        ).grid(row=2, column=1, sticky=tk.W)
        ttk.Label(
            tab,
            text="physical_v2 由左右指共同接触自动发现刚体，不使用目标路径辅助。",
            style="Panel.TLabel",
            foreground=self.MUTED,
        ).grid(row=2, column=2, columnspan=2, sticky=tk.W, padx=(20, 0))
        ttk.Label(tab, text="输出目录", style="Panel.TLabel").grid(row=3, column=0, sticky=tk.W, pady=6)
        ttk.Entry(tab, textvariable=self.output_var).grid(row=3, column=1, columnspan=2, sticky=tk.EW)
        ttk.Button(tab, text="选择", command=self._browse_output).grid(row=3, column=3, sticky=tk.W, padx=(8, 0))

        tuning = ttk.Frame(tab, style="Panel.TFrame")
        tuning.grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=8)
        ttk.Label(tuning, text="机械臂速度", style="Panel.TLabel").pack(side=tk.LEFT)
        ttk.Spinbox(
            tuning,
            textvariable=self.arm_speed_var,
            from_=ARM_SPEED_LIMITS.minimum,
            to=ARM_SPEED_LIMITS.maximum,
            increment=0.05,
            width=8,
        ).pack(side=tk.LEFT, padx=(8, 6))
        ttk.Label(
            tuning,
            text=(
                f"rad/s ({ARM_SPEED_LIMITS.minimum:g}–"
                f"{ARM_SPEED_LIMITS.maximum:g})"
            ),
            style="Panel.TLabel",
            foreground=self.MUTED,
        ).pack(side=tk.LEFT, padx=(0, 18))
        ttk.Label(tuning, text="稳定等待(s)", style="Panel.TLabel").pack(side=tk.LEFT)
        ttk.Entry(tuning, textvariable=self.settle_var, width=8).pack(side=tk.LEFT, padx=(8, 18))
        ttk.Checkbutton(tuning, text="要求当前关节角", variable=self.require_joints_var).pack(side=tk.LEFT)
        ttk.Checkbutton(
            tuning,
            text="干运行（不驱动机械臂）",
            variable=self.dry_run_var,
        ).pack(side=tk.LEFT, padx=(10, 0))

        warning = ttk.Frame(tab, style="Card.TFrame", padding=12)
        warning.grid(row=5, column=0, columnspan=4, sticky=tk.EW, pady=(8, 10))
        ttk.Label(
            warning,
            text="执行抓取会移动机械臂并闭合夹爪。首次运行建议保持“干运行”，先检查 renders 与 selected_plan.json。",
            style="Card.TLabel",
            foreground=self.WARN,
        ).pack(anchor=tk.W)
        actions = ttk.Frame(tab, style="Panel.TFrame")
        actions.grid(row=6, column=0, columnspan=4, sticky=tk.W)
        ttk.Button(actions, text="仅感知与规划", command=lambda: self.run_anygrasp(False)).pack(side=tk.LEFT)
        ttk.Button(
            actions, text="规划并执行", style="Accent.TButton", command=lambda: self.run_anygrasp(True)
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="停止本轮", command=lambda: self.stop_process("anygrasp")).pack(side=tk.LEFT)
        ttk.Button(actions, text="打开输出目录", command=self.open_anygrasp_output).pack(side=tk.LEFT, padx=8)
        ttk.Label(tab, textvariable=self.anygrasp_result_var, style="Panel.TLabel", foreground=self.MUTED).grid(
            row=7, column=0, columnspan=4, sticky=tk.W, pady=(12, 0)
        )

    def _build_control_tab(self) -> None:
        tab = self._tab("机器人命令")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        confirm = ttk.Checkbutton(
            tab,
            text="我已确认仿真场景与机械臂周边安全，允许本次会话发送运动/夹爪命令",
            variable=self.motion_confirm_var,
        )
        confirm.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

        motion = ttk.Frame(tab, style="Card.TFrame", padding=15)
        motion.grid(row=1, column=0, sticky=tk.NSEW, padx=(0, 8))
        ttk.Label(motion, text="关节与预设", style="Card.TLabel", font=("Sans", 11, "bold")).pack(anchor=tk.W)
        row = ttk.Frame(motion, style="Card.TFrame")
        row.pack(fill=tk.X, pady=9)
        ttk.Label(row, text="预设", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Combobox(
            row,
            textvariable=self.preset_var,
            values=("home", "ready", "reach", "salute", "wave_l", "wave_r", "bow"),
            width=14,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Label(row, text="速度", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Spinbox(
            row,
            textvariable=self.speed_var,
            from_=ARM_SPEED_LIMITS.minimum,
            to=ARM_SPEED_LIMITS.maximum,
            increment=0.05,
            width=8,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="移动", command=self.move_preset).pack(side=tk.LEFT)
        row2 = ttk.Frame(motion, style="Card.TFrame")
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text="J1..J6 (deg)", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.joints_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row2, text="移动", command=self.move_joints).pack(side=tk.LEFT)
        row3 = ttk.Frame(motion, style="Card.TFrame")
        row3.pack(fill=tk.X, pady=8)
        ttk.Label(row3, text="夹爪", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Scale(row3, from_=0.0, to=1.0, variable=self.gripper_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=8
        )
        ttk.Button(row3, text="发送", command=self.send_gripper).pack(side=tk.LEFT)
        quick = ttk.Frame(motion, style="Card.TFrame")
        quick.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(quick, text="状态", command=lambda: self.run_a1zctl(["--json", "status"])).pack(side=tk.LEFT)
        ttk.Button(quick, text="能力信息", command=lambda: self.run_a1zctl(["--json", "info"])).pack(
            side=tk.LEFT, padx=8
        )

        grasp = ttk.Frame(tab, style="Card.TFrame", padding=15)
        grasp.grid(row=1, column=1, sticky=tk.NSEW, padx=(8, 0))
        ttk.Label(grasp, text="物理抓取 v2", style="Card.TLabel", font=("Sans", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(
            grasp,
            text="双指接触后继续慢速加压，弱侧达到目标力才锁定",
            style="Card.TLabel",
        ).pack(anchor=tk.W, pady=(12, 3))
        buttons = ttk.Frame(grasp, style="Card.TFrame")
        buttons.pack(fill=tk.X, pady=12)
        ttk.Button(buttons, text="闭合并保持", style="Accent.TButton", command=self.close_physical).pack(
            side=tk.LEFT
        )
        ttk.Button(
            buttons,
            text="抓取状态",
            command=lambda: self.run_a1zctl(["--json", "grasp-status-physical"]),
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(
            buttons,
            text="释放",
            command=lambda: self.run_a1zctl(
                ["--json", "grasp-release-physical"], requires_confirmation=True
            ),
        ).pack(side=tk.LEFT)
        ttk.Label(
            grasp,
            text=(
                "默认目标为弱侧 2 N，双指虚拟耦合并在掉力时有界补压；"
                "不会创建 FixedJoint，也不会切换目标刚体为 kinematic。"
            ),
            style="Card.TLabel",
            foreground=self.MUTED,
            wraplength=430,
        ).pack(anchor=tk.W, pady=(8, 0))

    def _build_terminal_tab(self) -> None:
        tab = self._tab("项目终端")
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, text="工作目录", style="Panel.TLabel").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Entry(tab, textvariable=self.command_cwd_var).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Button(tab, text="选择", command=self._browse_cwd).grid(row=0, column=2)
        ttk.Label(tab, text="命令", style="Panel.TLabel").grid(row=1, column=0, sticky=tk.W, pady=6)
        command_entry = ttk.Entry(tab, textvariable=self.shell_command_var)
        command_entry.grid(row=1, column=1, sticky=tk.EW, padx=8)
        command_entry.bind("<Control-Return>", lambda _event: self.run_shell_command())
        ttk.Button(tab, text="执行", style="Accent.TButton", command=self.run_shell_command).grid(row=1, column=2)
        tips = ttk.Frame(tab, style="Panel.TFrame")
        tips.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=8)
        for label, command in (
            ("A1Z 状态", "python3 tools/a1zctl --json status"),
            ("运行时状态", "bash scripts/a1z_runtime_status.sh"),
            ("ROS bridge 状态", "bash scripts/run_a1z_ros2_motion_in_container.sh status"),
            ("最新 AnyGrasp", "bash scripts/print_latest_anygrasp_alignment_run.sh"),
        ):
            ttk.Button(tips, text=label, command=lambda value=command: self.shell_command_var.set(value)).pack(
                side=tk.LEFT, padx=(0, 7)
            )
        ttk.Label(
            tab,
            text="该输入会由 /bin/bash -lc 在宿主机执行。停止按钮只终止本控制台启动的命令进程组。",
            style="Panel.TLabel",
            foreground=self.WARN,
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(6, 10))
        ttk.Button(tab, text="停止当前命令", command=lambda: self.stop_process("terminal")).grid(
            row=4, column=0, columnspan=3, sticky=tk.W
        )

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(toolbar, text="统一日志", style="Panel.TLabel", font=("Sans", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="清空显示", command=self._clear_log).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="打开日志目录", command=lambda: self._open_path(LOG_DIR)).pack(
            side=tk.RIGHT, padx=7
        )
        self.log_text = ScrolledText(
            parent,
            height=12,
            bg="#080b10",
            fg="#d8e2ee",
            insertbackground=self.TEXT,
            selectbackground="#164e63",
            relief=tk.FLAT,
            font=("Monospace", 9),
            wrap=tk.NONE,
            state=tk.DISABLED,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("error", foreground=self.BAD)
        self.log_text.tag_configure("warn", foreground=self.WARN)
        self.log_text.tag_configure("good", foreground=self.GOOD)

    def _load_settings(self) -> dict[str, Any]:
        try:
            value = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _save_settings(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "isaac_root": self.isaac_root_var.get(),
            "world_usd": self.world_var.get(),
            "tcp_host": self.tcp_host_var.get(),
            "tcp_port": self._tcp_port(default=37103),
            "ee_drag_enabled": self.ee_drag_enabled_var.get(),
            "instruction": self.instruction_var.get(),
            "provider": self.provider_var.get(),
            "execution_mode": self.exec_mode_var.get(),
            "grasp_mode": self.grasp_mode_var.get(),
            "arm_speed_rad_s": self.arm_speed_var.get(),
            "manual_speed_rad_s": self.speed_var.get(),
            "require_current_joints": self.require_joints_var.get(),
            "dry_run": self.dry_run_var.get(),
            "rviz_config": self.rviz_config_var.get(),
        }
        SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _new_log_file(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._log_file = LOG_DIR / f"console_{datetime.now():%Y%m%d_%H%M%S}.log"

    def _write_log(self, source: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] [{source}] {message}"
        tag = classify_log_message(message)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        if self._log_file is not None:
            try:
                with self._log_file.open("a", encoding="utf-8") as stream:
                    stream.write(line + "\n")
            except OSError:
                pass

    def _queue_log(self, source: str, line: str) -> None:
        normalized = normalize_process_log_line(source, line)
        notice_key = (source, normalized)
        if normalized != line:
            if notice_key in self._collapsed_process_notices:
                return
            self._collapsed_process_notices.add(notice_key)
        self.events.put(("log", (source, normalized)))

    def _queue_done(self, source: str, return_code: int) -> None:
        self.events.put(("done", (source, return_code)))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._write_log(*payload)
                elif kind == "done":
                    self._process_done(*payload)
                elif kind == "probe":
                    self._apply_probe(payload)
                elif kind == "force_needed":
                    self.status_var.set(str(payload))
                    messagebox.showwarning("A1Z Host Console", str(payload))
                elif kind == "error":
                    self.status_var.set(str(payload))
                    self._write_log("console", f"错误: {payload}")
                    messagebox.showerror("A1Z Host Console", str(payload))
                elif kind == "full_stop_done":
                    self._stopping_full_project = False
                    bridge_stopped = bool(payload.get("bridge_stopped", True))
                    if bridge_stopped:
                        self.ros_bridge_owned = False
                        self.ros_bridge_ready = False
                        self.ros_bridge_badge_var.set("ROS · 已停止")
                    self.status_var.set(str(payload.get("message", "完整项目停止流程已完成")))
        except queue.Empty:
            pass
        if not self._closing:
            self.root.after(100, self._drain_events)

    def _run_process(
        self,
        key: str,
        name: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> ManagedProcess:
        current = self.processes.get(key)
        if current is not None and current.running:
            raise RuntimeError(f"{name} 已在运行")
        process = ManagedProcess(
            name,
            command,
            cwd=cwd or ROOT_DIR,
            env=env,
            on_log=self._queue_log,
            on_done=self._queue_done,
        )
        self.processes[key] = process
        process.start()
        return process

    def _process_done(self, source: str, return_code: int) -> None:
        self._write_log(source, f"进程结束，退出码 {return_code}")
        if source == "Isaac App":
            self.isaac_badge_var.set(f"ISAAC · 已退出 ({return_code})")
            self.isaac_process = None
        elif source == "AnyGrasp":
            if return_code == 0 and self._anygrasp_active_dry_run:
                self.anygrasp_badge_var.set("ANYGRASP · 干运行成功（未驱动）")
            else:
                self.anygrasp_badge_var.set("ANYGRASP · 完成" if return_code == 0 else "ANYGRASP · 失败")
            self._anygrasp_active_dry_run = None
            output = self._current_output_dir(create=False)
            if output is not None:
                self.anygrasp_result_var.set(summarize_anygrasp_output(output))
        elif source == "RViz":
            self.rviz_badge_var.set(
                "RVIZ · 已停止" if return_code == 0 else f"RVIZ · 启动/运行失败 ({return_code})"
            )
            self.rviz_process = None
        elif source == "ROS Bridge":
            status = load_json(ROS_BRIDGE_STATUS_PATH)
            ready = bool(status.get("ready")) and return_code == 0
            self.ros_bridge_ready = ready
            self.ros_bridge_owned = ready and status.get("ownership") == "console"
            if ready:
                owner = "自有" if self.ros_bridge_owned else "外部"
                domain = status.get("ros_domain_id", "?")
                self.ros_bridge_badge_var.set(f"ROS · 已就绪 ({owner})")
                self.status_var.set(
                    f"完整项目已就绪：D405、TF、RGB-D · ROS_DOMAIN_ID={domain}"
                )
            else:
                detail = str(status.get("error") or f"启动任务退出码 {return_code}")
                self.ros_bridge_badge_var.set("ROS · 启动失败")
                self.status_var.set(f"ROS 数据链路未就绪：{detail}")
                if not self._closing and not self._stopping_full_project:
                    messagebox.showerror("完整项目启动失败", detail)
            self.ros_bridge_process = None
            self.start_button.configure(state=tk.NORMAL)
        self.refresh_status()

    def _tcp_port(self, *, default: int | None = None) -> int:
        try:
            port = int(self.tcp_port_var.get())
        except ValueError:
            if default is not None:
                return default
            raise ValueError("TCP 端口必须是整数")
        if not 1 <= port <= 65535:
            raise ValueError("TCP 端口必须位于 1..65535")
        return port

    def refresh_status(self) -> None:
        if self._probe_running or self._closing:
            return
        self._probe_running = True
        host = self.tcp_host_var.get().strip() or "127.0.0.1"
        try:
            port = self._tcp_port()
        except ValueError as exc:
            self._probe_running = False
            self.status_var.set(str(exc))
            return

        def worker() -> None:
            probe = probe_a1z_server(host, port)
            self.events.put(("probe", probe))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_probe(self, probe: Any) -> None:
        self._probe_running = False
        if probe.recognized:
            owner = "自有" if self.isaac_process is not None and self.isaac_process.running else "外部"
            self.server_badge_var.set(f"A1Z · 已连接 ({owner})")
            if self.ros_bridge_process is not None and self.ros_bridge_process.running:
                self.status_var.set("完整启动 2/3：正在等待 D405/TF/RGB-D 数据链路…")
            elif self.ros_bridge_ready:
                self.status_var.set("完整项目已就绪：D405、TF、RGB-D")
            else:
                self.status_var.set(probe.detail)
        elif probe.reachable:
            self.server_badge_var.set("A1Z · 端口冲突")
            self.status_var.set(probe.detail)
        else:
            self.server_badge_var.set("A1Z · 离线")
            if self.isaac_process is not None and self.isaac_process.running:
                self.status_var.set("Isaac App 正在启动，等待 A1Z 服务…")
        if not self._closing:
            self.root.after(2000, self.refresh_status)

    def start_full_project(self) -> None:
        if self.ros_bridge_process is not None and self.ros_bridge_process.running:
            messagebox.showinfo("A1Z Host Console", "完整项目启动链正在运行。")
            return
        try:
            port = self._tcp_port()
            if self.isaac_process is not None and self.isaac_process.running:
                self._start_ros_bridge_chain(port)
                return
            root = Path(self.isaac_root_var.get()).expanduser().resolve()
            world = Path(self.world_var.get()).expanduser().resolve()
            if not (root / "isaac-sim.sh").is_file():
                raise ValueError(f"未找到宿主机 Isaac App: {root / 'isaac-sim.sh'}")
            if not world.is_file():
                raise ValueError(f"未找到世界 USD: {world}")
            host = self.tcp_host_var.get().strip() or "127.0.0.1"
            probe = probe_a1z_server(host, port)
            camera_runtime_detected = False
            if not probe.reachable:
                try:
                    camera_runtime_detected = "ready" in request_a1z(
                        host,
                        port,
                        "camera_status",
                        timeout_s=2.0,
                    )
                except Exception:
                    pass
            if probe.reachable:
                if probe.recognized:
                    self._apply_probe(probe)
                    self._write_log(
                        "console",
                        "检测到已运行的 A1Z；保留其所有权并继续补齐 ROS 数据链路",
                    )
                    self._start_ros_bridge_chain(port)
                    return
                raise RuntimeError(probe.detail)
            if camera_runtime_detected:
                self.server_badge_var.set("A1Z · 已连接 (外部)")
                self._write_log(
                    "console",
                    "A1Z info 探测超时，但 camera_status 有效；继续补齐 ROS 数据链路",
                )
                self._start_ros_bridge_chain(port)
                return
            env = build_host_isaac_env(
                ROOT_DIR,
                root,
                world,
                tcp_host=self.tcp_host_var.get().strip() or "127.0.0.1",
                tcp_port=port,
                ee_drag_enabled=self.ee_drag_enabled_var.get(),
            )
            command = build_isaac_command(ROOT_DIR, root, world)
            self.isaac_process = self._run_process("isaac", "Isaac App", command, env=env)
            self.isaac_badge_var.set(f"ISAAC · 启动中 (PID {self.isaac_process.pid})")
            self.status_var.set("完整启动 1/3：正在启动宿主机 Isaac Sim App…")
            self._save_settings()
            self._start_ros_bridge_chain(port)
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("启动失败", str(exc))

    def _start_ros_bridge_chain(self, port: int) -> None:
        if self.ros_bridge_ready:
            owner = "自有" if self.ros_bridge_owned else "外部"
            self.ros_bridge_badge_var.set(f"ROS · 已就绪 ({owner})")
            self.status_var.set("完整项目已经就绪")
            return
        if self.ros_bridge_process is not None and self.ros_bridge_process.running:
            return
        host = self.tcp_host_var.get().strip() or "127.0.0.1"
        env = build_ros_bridge_env(
            ROOT_DIR,
            tcp_host=host,
            tcp_port=port,
        )
        try:
            ROS_BRIDGE_STATUS_PATH.unlink(missing_ok=True)
            command = build_ros_bridge_start_command(
                ROOT_DIR,
                tcp_host=host,
                tcp_port=port,
                status_path=ROS_BRIDGE_STATUS_PATH,
                python_executable=sys.executable,
            )
            self.ros_bridge_process = self._run_process(
                "ros_bridge",
                "ROS Bridge",
                command,
                env=env,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self.ros_bridge_badge_var.set("ROS · 启动失败")
            raise RuntimeError(f"无法启动 ROS 数据链路任务: {exc}") from exc
        self.ros_bridge_badge_var.set("ROS · 等待 D405/TF/RGB-D")
        self.status_var.set(
            f"完整启动 2/3：等待 D405 后启动 ROS bridge · domain {env['ROS_DOMAIN_ID']}…"
        )
        self.start_button.configure(state=tk.DISABLED)

    def _stop_owned_ros_bridge(self) -> tuple[bool, str]:
        env = build_ros_bridge_env(
            ROOT_DIR,
            tcp_host=self.tcp_host_var.get().strip() or "127.0.0.1",
            tcp_port=self._tcp_port(default=37103),
        )
        try:
            result = subprocess.run(
                build_ros_bridge_stop_command(ROOT_DIR),
                cwd=str(ROOT_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=20.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)
        return result.returncode == 0, result.stdout.strip()

    def stop_full_project(self) -> None:
        isaac = self.isaac_process
        bridge_start = self.ros_bridge_process
        has_isaac = isaac is not None and isaac.running
        has_bridge_start = bridge_start is not None and bridge_start.running
        if not (has_isaac or has_bridge_start or self.ros_bridge_owned):
            messagebox.showinfo("A1Z Host Console", "没有由本控制台拥有的完整项目进程。")
            return
        if not messagebox.askyesno(
            "停止完整项目",
            "停止本控制台拥有的 ROS 数据链路，并优雅关闭自有 Isaac App？\n"
            "外部 A1Z/ROS 进程不会被停止。",
        ):
            return
        host = self.tcp_host_var.get().strip() or "127.0.0.1"
        port = self._tcp_port(default=37103)
        self.status_var.set("正在停止完整项目：ROS bridge → Isaac App…")
        self._stopping_full_project = True

        def worker() -> None:
            bridge_stopped = True
            if has_bridge_start and bridge_start is not None:
                bridge_stopped = bridge_start.terminate(grace_s=8.0)
                if not bridge_stopped:
                    bridge_start.kill()
            if self.ros_bridge_owned:
                stopped, output = self._stop_owned_ros_bridge()
                bridge_stopped = bridge_stopped and stopped
                if output:
                    self._queue_log("ROS Bridge", output)
            try:
                probe = probe_a1z_server(host, port)
                if has_isaac and probe.recognized:
                    request_a1z(host, port, "stop", timeout_s=3.0)
                    self._queue_log("console", "已发送 A1Z stop 请求")
            except Exception as exc:
                self._queue_log("console", f"优雅停止请求未完成: {exc}")
            if has_isaac and isaac is not None and not isaac.terminate(grace_s=8.0):
                self.events.put(
                    (
                        "force_needed",
                        "Isaac App 未在等待时间内退出。可点击“强制停止自有进程”；不会影响其他 Isaac 进程。",
                    )
                )
            self.events.put(
                (
                    "full_stop_done",
                    {
                        "bridge_stopped": bridge_stopped,
                        "message": (
                            "完整项目已停止"
                            if bridge_stopped
                            else "Isaac 停止流程已完成，但 ROS bridge 停止失败"
                        ),
                    },
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def force_stop_full_project(self) -> None:
        isaac = self.isaac_process
        bridge_start = self.ros_bridge_process
        has_isaac = isaac is not None and isaac.running
        has_bridge_start = bridge_start is not None and bridge_start.running
        if not (has_isaac or has_bridge_start or self.ros_bridge_owned):
            messagebox.showinfo("A1Z Host Console", "没有可强制停止的自有完整项目进程。")
            return
        if messagebox.askyesno(
            "强制停止",
            "停止自有 ROS bridge，并强制终止本控制台启动的 Isaac/启动任务？"
            "未保存的场景修改会丢失。",
        ):
            self._stopping_full_project = True
            def worker() -> None:
                bridge_stopped = True
                if self.ros_bridge_owned:
                    bridge_stopped, output = self._stop_owned_ros_bridge()
                    if output:
                        self._queue_log("ROS Bridge", output)
                if has_bridge_start and bridge_start is not None:
                    bridge_start.kill()
                if has_isaac and isaac is not None:
                    isaac.kill()
                self.events.put(
                    (
                        "full_stop_done",
                        {
                            "bridge_stopped": bridge_stopped,
                            "message": "已强制停止本控制台拥有的完整项目进程",
                        },
                    )
                )

            threading.Thread(target=worker, daemon=True).start()

    def start_rviz(self) -> None:
        if self.rviz_process is not None and self.rviz_process.running:
            messagebox.showinfo("A1Z Host Console", "本控制台启动的 RViz 已在运行。")
            return
        if not self.ros_bridge_ready:
            messagebox.showwarning(
                "ROS 数据链路未就绪",
                "请先点击“启动完整项目”，等待 ROS 状态变为“已就绪”后再启动 RViz。",
            )
            return
        try:
            config_path = Path(self.rviz_config_var.get()).expanduser().resolve()
            if not config_path.is_file():
                raise ValueError(f"未找到 RViz 配置: {config_path}")
            if not os.environ.get("DISPLAY"):
                raise RuntimeError("当前桌面会话没有 DISPLAY，无法打开 RViz 窗口。")
            env = build_rviz_env(ROOT_DIR)
            command = build_rviz_command(
                ROOT_DIR,
                config_path,
                rebuild=self.rviz_rebuild_var.get(),
            )
            self.rviz_process = self._run_process("rviz", "RViz", command, env=env)
            self.rviz_rebuild_var.set(False)
            self.rviz_badge_var.set(f"RVIZ · 进程运行中 (PID {self.rviz_process.pid})")
            self.status_var.set(
                f"正在启动 RViz · ROS_DOMAIN_ID={env['ROS_DOMAIN_ID']}…"
            )
            self._save_settings()
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("RViz 启动失败", str(exc))

    def _stop_owned_rviz(self, process: ManagedProcess, *, grace_s: float) -> bool:
        env = build_rviz_env(ROOT_DIR)
        container_name = env["A1Z_RVIZ_CONTAINER_NAME"]
        try:
            result = subprocess.run(
                ["docker", "stop", "--timeout", str(max(1, int(grace_s))), container_name],
                cwd=str(ROOT_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=grace_s + 3.0,
                check=False,
            )
            output = result.stdout.strip()
            if output:
                self._queue_log("RViz", output)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._queue_log("RViz", f"容器停止请求未完成: {exc}")
        return process.terminate(grace_s=grace_s)

    def stop_rviz(self) -> None:
        process = self.rviz_process
        if process is None or not process.running:
            self.status_var.set("没有由本控制台拥有的 RViz 进程")
            return
        self.rviz_badge_var.set("RVIZ · 正在停止")
        self.status_var.set("正在停止本控制台启动的 RViz…")

        def worker() -> None:
            if not self._stop_owned_rviz(process, grace_s=5.0):
                self.events.put(("force_needed", "RViz 未退出；请检查统一日志。"))

        threading.Thread(target=worker, daemon=True).start()

    def run_a1zctl(
        self,
        args: list[str],
        *,
        requires_confirmation: bool = False,
    ) -> None:
        if requires_confirmation and not self._motion_allowed():
            return
        try:
            port = self._tcp_port()
        except ValueError as exc:
            messagebox.showerror("TCP 配置错误", str(exc))
            return
        probe = probe_a1z_server(self.tcp_host_var.get(), port)
        if not probe.recognized:
            messagebox.showerror("A1Z 未就绪", probe.detail)
            return
        env = dict(os.environ)
        env.update(
            {
                "A1Z_SOCKET_PATH": "",
                "A1Z_TCP_HOST": self.tcp_host_var.get().strip() or "127.0.0.1",
                "A1Z_TCP_PORT": str(port),
                "A1Z_BACKEND": "isaacsim",
            }
        )
        try:
            self._run_process(
                "control",
                "a1zctl",
                build_a1zctl_command(ROOT_DIR, args, python_executable=sys.executable),
                env=env,
            )
        except RuntimeError as exc:
            messagebox.showwarning("命令忙", str(exc))

    def _motion_allowed(self) -> bool:
        if self.motion_confirm_var.get():
            return True
        messagebox.showwarning("需要确认", "请先勾选本页顶部的运动安全确认。")
        return False

    def _validated_arm_speed(self, raw_value: str) -> str | None:
        try:
            speed = ARM_SPEED_LIMITS.validate(float(raw_value))
        except ValueError as exc:
            messagebox.showerror("机械臂速度错误", str(exc))
            return None
        return f"{speed:g}"

    def move_preset(self) -> None:
        if not self._motion_allowed():
            return
        speed = self._validated_arm_speed(self.speed_var.get())
        if speed is None:
            return
        self.run_a1zctl(
            ["--json", "move", "--preset", self.preset_var.get(), "--speed", speed]
        )

    def move_joints(self) -> None:
        if not self._motion_allowed():
            return
        values = [part.strip() for part in self.joints_var.get().split(",")]
        try:
            if len(values) != 6:
                raise ValueError
            [float(value) for value in values]
        except ValueError:
            messagebox.showerror("关节角错误", "请输入 6 个逗号分隔的数值。")
            return
        speed = self._validated_arm_speed(self.speed_var.get())
        if speed is None:
            return
        self.run_a1zctl(["--json", "move", ",".join(values), "--speed", speed])

    def send_gripper(self) -> None:
        if self._motion_allowed():
            self.run_a1zctl(["--json", "gripper", f"{self.gripper_var.get():.4f}"])

    def close_physical(self) -> None:
        if not self._motion_allowed():
            return
        profile = ROOT_DIR / "config" / "grasping" / "controllers" / "a1z_physical_gripper_v1.json"
        args = [
            "--json",
            "grasp-close-physical",
            "--controller-profile",
            str(profile),
        ]
        self.run_a1zctl(args)

    def _current_output_dir(self, *, create: bool) -> Path | None:
        raw = self.output_var.get().strip()
        if not raw:
            raw = str(ROOT_DIR / "runtime" / "anygrasp_gui" / f"{datetime.now():%Y%m%d_%H%M%S}")
            self.output_var.set(raw)
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT_DIR / path
        path = path.resolve()
        try:
            path.relative_to(ROOT_DIR.resolve())
        except ValueError:
            if create:
                messagebox.showerror("输出目录错误", f"输出目录必须位于项目内:\n{ROOT_DIR}")
            return None
        return path

    def run_anygrasp(self, execute: bool) -> None:
        try:
            port = self._tcp_port()
        except ValueError as exc:
            messagebox.showerror("TCP 配置错误", str(exc))
            return
        probe = probe_a1z_server(
            self.tcp_host_var.get().strip() or "127.0.0.1",
            port,
        )
        if not probe.recognized:
            messagebox.showerror(
                "A1Z 未就绪",
                "AnyGrasp 需要先从 Isaac D405 获取 RGB-D 与关节状态。\n\n" + probe.detail,
            )
            return
        try:
            camera_status = request_a1z(
                self.tcp_host_var.get().strip() or "127.0.0.1",
                port,
                "camera_status",
                timeout_s=2.0,
            )
        except Exception as exc:
            messagebox.showerror("D405 未就绪", f"无法读取 Isaac D405 状态：\n{exc}")
            return
        if not camera_status.get("ready", False):
            detail = camera_status.get("last_error") or "相机仍在 warm-up，稍后重试。"
            messagebox.showwarning("D405 未就绪", str(detail))
            return
        if execute and not self.dry_run_var.get():
            if not messagebox.askyesno(
                "确认执行真实仿真抓取",
                "当前未启用干运行。AnyGrasp 将移动机械臂、闭合夹爪并执行物理抓取，继续吗？",
            ):
                return
        try:
            output = allocate_anygrasp_run_dir(
                ROOT_DIR,
                self.output_var.get().strip(),
            )
            self.output_var.set(str(output))
        except (OSError, ValueError) as exc:
            messagebox.showerror("输出目录错误", str(exc))
            return
        try:
            self._collapsed_process_notices = {
                item for item in self._collapsed_process_notices if item[0] != "AnyGrasp"
            }
            options = AnyGraspOptions(
                instruction=self.instruction_var.get(),
                host_output_dir=output,
                provider=self.provider_var.get(),
                execution_mode=self.exec_mode_var.get(),
                grasp_mode=self.grasp_mode_var.get(),
                arm_speed=float(self.arm_speed_var.get()),
                settle_s=float(self.settle_var.get()),
                target_prim_path="",
                require_current_joints=self.require_joints_var.get(),
                resolve_target_prim=False,
                dry_run=self.dry_run_var.get(),
                execute=execute,
            )
            command = build_anygrasp_command(ROOT_DIR, options)
            self._anygrasp_active_dry_run = bool(execute and options.dry_run)
            env = dict(os.environ)
            env.update(
                {
                    "A1Z_CONTAINER_ENV_FILE": str(ROOT_DIR / "config" / "a1z_container.env"),
                    "A1Z_TCP_HOST": self.tcp_host_var.get().strip() or "127.0.0.1",
                    "A1Z_TCP_PORT": str(port),
                }
            )
            self._run_process("anygrasp", "AnyGrasp", command, env=env)
            self.anygrasp_badge_var.set("ANYGRASP · 运行中")
            self.anygrasp_result_var.set(f"输出: {output}")
            if execute and self.dry_run_var.get():
                self._write_log(
                    "AnyGrasp",
                    "提示：当前为干运行，只生成并验证执行计划，不会驱动机械臂或闭合夹爪。",
                )
            self._save_settings()
        except (OSError, RuntimeError, ValueError) as exc:
            self._anygrasp_active_dry_run = None
            messagebox.showerror("AnyGrasp 启动失败", str(exc))

    def run_shell_command(self) -> None:
        command_text = self.shell_command_var.get().strip()
        if not command_text:
            return
        cwd = Path(self.command_cwd_var.get()).expanduser()
        if not cwd.is_dir():
            messagebox.showerror("工作目录错误", f"目录不存在: {cwd}")
            return
        try:
            port = self._tcp_port()
        except ValueError as exc:
            messagebox.showerror("TCP 配置错误", str(exc))
            return
        env = dict(os.environ)
        env.update(
            {
                "A1Z_TCP_HOST": self.tcp_host_var.get().strip() or "127.0.0.1",
                "A1Z_TCP_PORT": str(port),
                "A1Z_SOCKET_PATH": "",
            }
        )
        try:
            self._run_process(
                "terminal",
                "终端",
                ["/bin/bash", "-lc", command_text],
                cwd=cwd.resolve(),
                env=env,
            )
        except (OSError, RuntimeError) as exc:
            messagebox.showwarning("终端忙", str(exc))

    def stop_process(self, key: str) -> None:
        process = self.processes.get(key)
        if process is None or not process.running:
            self.status_var.set("没有可停止的自有任务")
            return

        def worker() -> None:
            if not process.terminate(grace_s=5.0):
                self.events.put(("force_needed", f"{process.name} 未退出；再次停止前请检查日志。"))

        threading.Thread(target=worker, daemon=True).start()

    def open_anygrasp_output(self) -> None:
        output = self._current_output_dir(create=False)
        if output is not None:
            self._open_path(output)

    def _open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc))

    def _browse_isaac(self) -> None:
        value = filedialog.askdirectory(initialdir=self.isaac_root_var.get())
        if value:
            self.isaac_root_var.set(value)

    def _browse_world(self) -> None:
        value = filedialog.askopenfilename(
            initialdir=str(Path(self.world_var.get()).parent),
            filetypes=(("USD 场景", "*.usd *.usda *.usdc"), ("所有文件", "*")),
        )
        if value:
            self.world_var.set(value)

    def _browse_rviz_config(self) -> None:
        value = filedialog.askopenfilename(
            initialdir=str(Path(self.rviz_config_var.get()).expanduser().parent),
            filetypes=(("RViz 配置", "*.rviz"), ("所有文件", "*")),
        )
        if value:
            self.rviz_config_var.set(value)

    def _browse_output(self) -> None:
        value = filedialog.askdirectory(initialdir=str(ROOT_DIR / "runtime"))
        if value:
            self.output_var.set(value)

    def _browse_cwd(self) -> None:
        value = filedialog.askdirectory(initialdir=self.command_cwd_var.get())
        if value:
            self.command_cwd_var.set(value)

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        active = [process for process in self.processes.values() if process.running]
        if active or self.ros_bridge_owned:
            names_list = [process.name for process in active]
            if self.ros_bridge_owned:
                names_list.append("ROS Bridge（容器内）")
            names = "、".join(dict.fromkeys(names_list))
            choice = messagebox.askyesnocancel(
                "退出控制台",
                f"以下自有进程仍在运行：{names}\n\n"
                "“是”停止所有自有进程后退出；“否”保留它们运行；“取消”返回。",
            )
            if choice is None:
                return
            if choice:
                bridge_start = self.ros_bridge_process
                if bridge_start is not None and bridge_start.running:
                    if not bridge_start.terminate(grace_s=5.0):
                        bridge_start.kill()
                if self.ros_bridge_owned:
                    self._stop_owned_ros_bridge()
                if self.isaac_process is not None and self.isaac_process.running:
                    try:
                        request_a1z(
                            self.tcp_host_var.get(),
                            self._tcp_port(default=37103),
                            "stop",
                            timeout_s=2.0,
                        )
                    except Exception:
                        pass
                for process in active:
                    if process is bridge_start:
                        continue
                    if process is self.rviz_process:
                        stopped = self._stop_owned_rviz(process, grace_s=2.0)
                    else:
                        stopped = process.terminate(grace_s=2.0)
                    if not stopped:
                        process.kill()
        self._closing = True
        self._save_settings()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    A1ZConsole(root)
    root.mainloop()


if __name__ == "__main__":
    main()
