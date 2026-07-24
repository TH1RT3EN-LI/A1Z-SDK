"""Host-side process and command helpers for the A1Z desktop console.

This module intentionally has no Tk or Isaac imports.  It is usable from the
system Python for unit tests and keeps every GUI action on the existing A1Z
CLI/script boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from a1z_ext.config import get_arm_motion_speed_limits, validate_arm_motion_speed


LogCallback = Callable[[str, str], None]
DoneCallback = Callable[[str, int], None]
ARM_SPEED_LIMITS = get_arm_motion_speed_limits()

_ANYGRASP_AUTOLAB_NOTICE_PARTS = (
    "Failed to import geometry msgs in rigid_transformations.py",
    "Failed to import ros dependencies in rigid_transforms.py",
    "autolab_core not installed as catkin package",
)
_ANYGRASP_OPEN3D_NOTICE_PARTS = (
    "GLFW Error: Failed to detect any supported platform",
    "GLFW initialized for headless rendering",
    "GLFW Error: OSMesa: Library not found",
    "Failed to create window",
)


@dataclass(frozen=True)
class A1ZProbe:
    reachable: bool
    recognized: bool
    detail: str
    data: dict[str, Any]


@dataclass(frozen=True)
class AnyGraspOptions:
    instruction: str
    host_output_dir: Path
    provider: str = "kimi"
    execution_mode: str = "best_direct"
    grasp_mode: str = "physical_v2"
    arm_speed: float = ARM_SPEED_LIMITS.default
    settle_s: float = 0.05
    target_prim_path: str = ""
    require_current_joints: bool = True
    resolve_target_prim: bool = False
    dry_run: bool = False
    execute: bool = True


def allocate_anygrasp_run_dir(
    root_dir: Path,
    configured_path: str | Path = "",
    *,
    now: datetime | None = None,
) -> Path:
    """Allocate a unique directory for one AnyGrasp invocation."""
    root = root_dir.expanduser().resolve()
    raw = str(configured_path).strip()
    path = Path(raw).expanduser() if raw else root / "runtime" / "anygrasp_gui"
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"输出目录必须位于项目内: {root}") from exc

    name_parts = path.name.split("_")
    is_run_dir = (
        len(name_parts) in (2, 3)
        and len(name_parts[0]) == 8
        and len(name_parts[1]) == 6
        and all(part.isdigit() for part in name_parts)
    )
    run_root = path.parent if is_run_dir else path
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    candidate = run_root / timestamp
    suffix = 1
    while candidate.exists():
        candidate = run_root / f"{timestamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def read_env_file(path: Path) -> dict[str, str]:
    """Read the simple KEY=VALUE env format used by this repository."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def _host_path(value: str, root_dir: Path) -> str:
    prefix = "/workspace/A1Z"
    if value == prefix:
        return str(root_dir)
    if value.startswith(prefix + "/"):
        return str(root_dir / value[len(prefix) + 1 :])
    return value


def build_host_isaac_env(
    root_dir: Path,
    isaac_sim_root: Path,
    world_usd: Path,
    *,
    tcp_host: str = "127.0.0.1",
    tcp_port: int = 37103,
    ee_drag_enabled: bool = False,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a host-safe Isaac environment from the container-oriented config."""
    env = dict(os.environ if base_env is None else base_env)
    merged: dict[str, str] = {}
    merged.update(read_env_file(root_dir / "config" / "a1z_container.env"))
    merged.update(read_env_file(root_dir / "config" / "a1z_isaac6_standalone.env"))
    for key, value in merged.items():
        env.setdefault(key, _host_path(value, root_dir))

    env.update(
        {
            "ISAAC_SIM_ROOT": str(isaac_sim_root),
            "A1Z_REPO_ROOT": str(root_dir),
            "A1Z_WORLD_USD": str(world_usd),
            "A1Z_BACKEND": "isaacsim",
            "A1Z_SOCKET_PATH": "",
            "A1Z_TCP_HOST": tcp_host,
            "A1Z_TCP_PORT": str(int(tcp_port)),
            "A1Z_ISAAC_API_PROFILE": "native_6_0",
            "A1Z_SDK_VENV_DIR": str(
                root_dir / "runtime" / "venvs" / "a1z-sdk"
            ),
            "A1Z_VIEWPORT_ENABLED": "1",
            "A1Z_EE_DRAG_TARGET_ENABLED": "1" if ee_drag_enabled else "0",
            "PYTHONUNBUFFERED": "1",
            "A1Z_D405_STATUS_PATH": str(
                root_dir / "runtime" / "logs" / "d405-link-camera.status"
            ),
            "A1Z_PHYSICAL_GRASP_CONTROLLER_PROFILE": str(
                root_dir
                / "config"
                / "grasping"
                / "controllers"
                / "a1z_physical_gripper_v1.json"
            ),
        }
    )
    return env


def build_isaac_command(
    root_dir: Path,
    isaac_sim_root: Path,
    world_usd: Path,
) -> list[str]:
    return [
        str(root_dir / "scripts" / "open_a1z_isaac_app.sh"),
        "--world-usd",
        str(world_usd),
        "--isaac-sim-root",
        str(isaac_sim_root),
    ]


def host_to_workspace_path(root_dir: Path, path: Path) -> str:
    root = root_dir.resolve()
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"路径必须位于项目目录内: {root}") from exc
    return f"/workspace/A1Z/{relative.as_posix()}"


def build_rviz_env(
    root_dir: Path,
    *,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the host environment used by the project-scoped RViz launcher."""
    env = dict(os.environ if base_env is None else base_env)
    merged: dict[str, str] = {}
    merged.update(read_env_file(root_dir / "config" / "a1z_container.env"))
    merged.update(read_env_file(root_dir / "config" / "a1z_isaac6_standalone.env"))
    for key, value in merged.items():
        env.setdefault(key, value)
    env.setdefault("ROS_DOMAIN_ID", "0")
    env.setdefault("A1Z_RVIZ_CONTAINER_NAME", "a1z-rviz-humble-isaac6")
    return env


def build_rviz_command(
    root_dir: Path,
    config_path: Path,
    *,
    rebuild: bool = False,
) -> list[str]:
    """Build an RViz launcher command with a repository-mounted config path."""
    command = [str(root_dir / "scripts" / "open_a1z_rviz_in_container.sh")]
    if rebuild:
        command.append("--rebuild")
    command.extend(
        [
            "--",
            "--display-config",
            host_to_workspace_path(root_dir, config_path),
        ]
    )
    return command


def build_ros_bridge_env(
    root_dir: Path,
    *,
    tcp_host: str,
    tcp_port: int,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the explicit host/container contract for the ROS bridge chain."""
    env = dict(os.environ if base_env is None else base_env)
    merged: dict[str, str] = {}
    merged.update(read_env_file(root_dir / "config" / "a1z_container.env"))
    merged.update(read_env_file(root_dir / "config" / "a1z_isaac6_standalone.env"))
    for key, value in merged.items():
        env.setdefault(key, value)
    env.update(
        {
            "A1Z_CONTAINER_ENV_FILE": str(root_dir / "config" / "a1z_container.env"),
            "A1Z_TCP_HOST": tcp_host.strip() or "127.0.0.1",
            "A1Z_TCP_PORT": str(int(tcp_port)),
        }
    )
    env.setdefault("ROS_DOMAIN_ID", "0")
    env.setdefault("A1Z_ROS2_CONTAINER_NAME", "a1z-ros2-humble")
    return env


def build_ros_bridge_start_command(
    root_dir: Path,
    *,
    tcp_host: str,
    tcp_port: int,
    status_path: Path,
    python_executable: str,
    timeout_s: float = 180.0,
) -> list[str]:
    """Build the bounded full-project ROS camera/TF readiness command."""
    return [
        python_executable,
        str(root_dir / "scripts" / "start_a1z_ros2_stack.py"),
        "--tcp-host",
        tcp_host.strip() or "127.0.0.1",
        "--tcp-port",
        str(int(tcp_port)),
        "--status-path",
        str(status_path),
        "--timeout-s",
        f"{float(timeout_s):g}",
    ]


def build_ros_bridge_stop_command(root_dir: Path) -> list[str]:
    return [
        str(root_dir / "scripts" / "run_a1z_ros2_motion_in_container.sh"),
        "stop",
    ]


def build_anygrasp_command(root_dir: Path, options: AnyGraspOptions) -> list[str]:
    instruction = options.instruction.strip()
    if not instruction:
        raise ValueError("AnyGrasp 指令不能为空")
    if options.execution_mode not in {"best_direct", "adapter_selected"}:
        raise ValueError(f"不支持的执行模式: {options.execution_mode}")
    if options.grasp_mode not in {"physical_v2", "sim_contact_attach", "raw_gripper"}:
        raise ValueError(f"不支持的抓取模式: {options.grasp_mode}")
    arm_speed = validate_arm_motion_speed(options.arm_speed)

    output_dir = host_to_workspace_path(root_dir, options.host_output_dir)
    if options.execute:
        command = [
            str(root_dir / "scripts" / "run_target_mask_to_anygrasp_pick_attempt.sh"),
        ]
        if options.dry_run:
            command.append("--dry-run")
        command.extend(
            [
                "--arm-speed",
                f"{arm_speed:g}",
                "--settle-s",
                f"{float(options.settle_s):g}",
                "--execution-mode",
                options.execution_mode,
                "--grasp-mode",
                options.grasp_mode,
            ]
        )
        if options.grasp_mode != "physical_v2" and options.target_prim_path.strip():
            command.extend(["--target-prim-path", options.target_prim_path.strip()])
    else:
        command = [
            str(root_dir / "scripts" / "run_target_mask_to_anygrasp_from_ros.sh"),
        ]

    if options.require_current_joints:
        command.append("--require-current-joints")
    if options.resolve_target_prim and options.grasp_mode != "physical_v2":
        command.append("--resolve-target-prim")
    command.extend([instruction, output_dir, options.provider.strip() or "kimi"])
    return command


def normalize_process_log_line(source: str, line: str) -> str:
    """Collapse known optional AnyGrasp dependency noise into actionable notices."""
    if source != "AnyGrasp":
        return line
    if any(part in line for part in _ANYGRASP_AUTOLAB_NOTICE_PARTS):
        return "提示：视觉容器未启用 ROS RigidTransform 扩展；当前 AnyGrasp 推理不使用该扩展。"
    if any(part in line for part in _ANYGRASP_OPEN3D_NOTICE_PARTS):
        return "提示：部分 camera-view 辅助预览缺少 GLFW/OSMesa；EGL 主渲染和抓取计划不受影响。"
    return line


def classify_log_message(message: str) -> str:
    """Return a log tag without treating warning text or empty JSON errors as failures."""
    stripped = message.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            if payload.get("success") is False:
                return "error"
            if payload.get("success") is True:
                return "good"
            if str(payload.get("error", "") or ""):
                return "error"
            anygrasp = payload.get("anygrasp")
            if isinstance(anygrasp, dict):
                if anygrasp.get("ran") is False or str(anygrasp.get("error", "") or ""):
                    return "error"
            if payload.get("capture_ok") is False or str(payload.get("render_error", "") or ""):
                return "warn"
            return ""

    lowered = stripped.lower()
    if "退出码 0" in lowered:
        return "good"
    if "退出码 " in lowered:
        return "error"
    if any(word in lowered for word in ("warning", "warn", "注意", "警告", "提示：")):
        return "warn"
    if any(word in lowered for word in ("error", "failed", "失败", "错误", "traceback")):
        return "error"
    if any(word in lowered for word in ("ready", "完成", "成功", "已连接")):
        return "good"
    return ""


def build_a1zctl_command(
    root_dir: Path,
    args: Sequence[str],
    *,
    python_executable: str,
) -> list[str]:
    return [python_executable, str(root_dir / "tools" / "a1zctl"), *args]


def _read_json_line(sock: socket.socket) -> dict[str, Any]:
    payload = b""
    while b"\n" not in payload:
        chunk = sock.recv(4096)
        if not chunk:
            break
        payload += chunk
        if len(payload) > 2 * 1024 * 1024:
            raise RuntimeError("response exceeds 2 MiB")
    if not payload:
        raise RuntimeError("empty response")
    value = json.loads(payload.split(b"\n", 1)[0].decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("response is not a JSON object")
    return value


def probe_a1z_server(host: str, port: int, timeout_s: float = 0.8) -> A1ZProbe:
    """Probe and fingerprint the listener before the GUI claims ownership."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s) as sock:
            sock.settimeout(timeout_s)
            request = json.dumps({"cmd": "info", "args": {}}) + "\n"
            sock.sendall(request.encode("utf-8"))
            payload = _read_json_line(sock)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return A1ZProbe(False, False, str(exc), {})

    data = payload.get("data", {})
    recognized = bool(
        payload.get("ok")
        and isinstance(data, dict)
        and isinstance(data.get("presets"), list)
        and "backend" in data
    )
    if not recognized:
        return A1ZProbe(True, False, "端口有响应，但不是可识别的 A1Z 服务", {})
    backend = str(data.get("backend", "unknown"))
    articulation = str(data.get("articulation_root_prim", "") or "")
    detail = f"A1Z {backend}"
    if articulation:
        detail += f" · {articulation}"
    return A1ZProbe(True, True, detail, data)


def request_a1z(
    host: str,
    port: int,
    command: str,
    args: Mapping[str, Any] | None = None,
    *,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Send one control request without importing the Isaac/SDK dependency tree."""
    with socket.create_connection((host, int(port)), timeout=timeout_s) as sock:
        sock.settimeout(timeout_s)
        request = json.dumps({"cmd": command, "args": dict(args or {})}) + "\n"
        sock.sendall(request.encode("utf-8"))
        payload = _read_json_line(sock)
    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("error", "A1Z command failed")))
    data = payload.get("data", {})
    return data if isinstance(data, dict) else {}


class ManagedProcess:
    """One owned subprocess group with line streaming and scoped termination."""

    def __init__(
        self,
        name: str,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None,
        on_log: LogCallback,
        on_done: DoneCallback,
    ) -> None:
        self.name = name
        self.command = list(command)
        self.cwd = cwd
        self.env = None if env is None else dict(env)
        self.on_log = on_log
        self.on_done = on_done
        self.process: subprocess.Popen[str] | None = None
        self.started_at: datetime | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        with self._lock:
            return self.process is not None and self.process.poll() is None

    @property
    def pid(self) -> int | None:
        with self._lock:
            return self.process.pid if self.process is not None else None

    def start(self) -> None:
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError(f"{self.name} 已在运行")
            self.started_at = datetime.now()
            self.process = subprocess.Popen(
                self.command,
                cwd=str(self.cwd),
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=True,
            )
            process = self.process
        self.on_log(self.name, f"$ {shlex.join(self.command)}")
        self.on_log(self.name, f"已启动 PID {process.pid}")
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self) -> None:
        with self._lock:
            process = self.process
        if process is None:
            return
        if process.stdout is not None:
            for line in iter(process.stdout.readline, ""):
                self.on_log(self.name, line.rstrip("\n"))
            process.stdout.close()
        return_code = process.wait()
        self.on_done(self.name, return_code)

    def terminate(self, *, grace_s: float = 8.0) -> bool:
        """Terminate only this owned process group. Returns whether it exited."""
        with self._lock:
            process = self.process
        if process is None or process.poll() is not None:
            return True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        try:
            process.wait(timeout=max(0.1, float(grace_s)))
            return True
        except subprocess.TimeoutExpired:
            return False

    def kill(self) -> None:
        with self._lock:
            process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_anygrasp_output(output_dir: Path) -> str:
    status = load_json(output_dir / "pipeline_status.json")
    execution = load_json(output_dir / "execute" / "execution_result.json")
    parts: list[str] = []
    if status:
        count = status.get("anygrasp_grasp_count", "?")
        selected = bool(status.get("selected_plan_present"))
        best = bool(status.get("best_direct_plan_present"))
        parts.append(f"候选 {count} · selected={'是' if selected else '否'} · best={'是' if best else '否'}")
        resolved = str(status.get("resolved_target_prim_path", "") or "")
        if resolved:
            parts.append(f"目标 {resolved}")
    if execution:
        if bool(execution.get("dry_run")):
            parts.append(f"干运行验证 {'成功' if execution.get('success') else '失败'}（未驱动机械臂）")
        else:
            outcome = (
                execution.get("success")
                if "success" in execution
                else execution.get("status") or execution.get("result") or execution.get("ok")
            )
            parts.append(f"执行结果 {outcome}")
    return " · ".join(parts) if parts else "未找到流水线结果文件"


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_s: float,
    interval_s: float = 0.2,
) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return bool(predicate())
