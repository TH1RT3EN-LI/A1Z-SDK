#!/usr/bin/env python3
"""Read-only whole-chain checks for the A1Z Qt console."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "console"))

from a1z_console.profiles import load_profiles  # noqa: E402
from a1z_console.camera_protocol import CameraProtocolClient  # noqa: E402
from a1z_console.protocol import A1ZProtocolClient  # noqa: E402


def check(name: str, ok: bool, detail: str, severity: str = "required") -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "detail": str(detail),
        "severity": severity,
    }


def docker_running(name: str) -> tuple[bool, str]:
    if not name:
        return False, "未配置容器名"
    completed = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
    )
    running = completed.returncode == 0 and completed.stdout.strip() == "true"
    detail = "running" if running else (completed.stderr.strip() or "stopped/missing")
    return running, f"{name}: {detail}"


def docker_command(container: str, command: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        ["docker", "exec", container, *command],
        capture_output=True,
        text=True,
        timeout=8.0,
        check=False,
    )
    output = (completed.stdout or completed.stderr).strip()
    return completed.returncode == 0, output[-800:] or f"exit={completed.returncode}"


def workspace_path(raw: str) -> Path:
    prefix = "/workspace/A1Z/"
    if raw.startswith(prefix):
        return ROOT / raw[len(prefix) :]
    return Path(raw)


def find_realsense_usb_devices() -> list[str]:
    """Discover RealSense USB devices by descriptors, never by bus/node number."""

    devices: list[str] = []
    usb_root = Path("/sys/bus/usb/devices")
    if not usb_root.is_dir():
        return devices
    for device in usb_root.iterdir():
        product_path = device / "product"
        if not product_path.is_file():
            continue
        try:
            product = product_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if "realsense" not in product.lower():
            continue
        serial_path = device / "serial"
        speed_path = device / "speed"
        try:
            serial = (
                serial_path.read_text(encoding="utf-8").strip()
                if serial_path.is_file()
                else "unknown"
            )
            speed = (
                speed_path.read_text(encoding="utf-8").strip()
                if speed_path.is_file()
                else "unknown"
            )
        except OSError:
            serial, speed = "unknown", "unknown"
        devices.append(f"{product} · serial={serial} · USB {speed} Mb/s")
    return devices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["sim", "real"], required=True)
    args = parser.parse_args()

    profile = load_profiles(ROOT)[args.profile]
    env = profile.environment
    checks: list[dict[str, Any]] = []
    verified_backend = ""
    checks.append(
        check(
            "配置隔离",
            (args.profile == "sim" and profile.port == 37103)
            or (args.profile == "real" and profile.port == 37104),
            f"{profile.label} → {profile.expected_backend} @ {profile.host}:{profile.port}",
        )
    )

    try:
        endpoint = A1ZProtocolClient(profile).verify_backend(timeout_s=3.0)
        verified_backend = endpoint.backend
        checks.append(
            check(
                "SDK 控制服务",
                True,
                f"{endpoint.backend} / {endpoint.control_mode}",
            )
        )
        status = A1ZProtocolClient(profile).request("status", timeout_s=3.0)
        positions = status.get("pos_deg", [])
        checks.append(
            check(
                "关节状态回读",
                isinstance(positions, list) and len(positions) >= 6,
                f"Joints={positions[:6]} · estop={status.get('estopped', False)}",
            )
        )
    except Exception as exc:
        checks.append(check("SDK 控制服务", False, str(exc)))
        checks.append(check("关节状态回读", False, "控制端点不可用"))

    ros_name = env.get("A1Z_ROS2_CONTAINER_NAME", "")
    ros_ok, ros_detail = docker_running(ros_name)
    checks.append(check("ROS 2 容器", ros_ok, ros_detail))

    try:
        camera_status = CameraProtocolClient(profile).request(
            "camera_status",
            timeout_s=2.0,
        )
        camera_ok = bool(camera_status.get("ready", False))
        camera_detail = (
            f"{profile.camera_host}:{profile.camera_port} · "
            f"{camera_status.get('camera_source', 'unknown')} · "
            f"{camera_status.get('width', '—')}×{camera_status.get('height', '—')} · "
            f"RGB={camera_status.get('color_topic', '—')} · "
            f"Depth={camera_status.get('depth_topic', '—')}"
        )
    except Exception as exc:
        camera_ok = False
        camera_detail = str(exc)
    checks.append(check("GUI RGB-D 相机桥", camera_ok, camera_detail))

    if args.profile == "sim":
        isaac_name = env.get("ISAAC_SIM_CONTAINER_NAME", "")
        isaac_ok, isaac_detail = docker_running(isaac_name)
        isaac_runtime_ok = isaac_ok or verified_backend == "isaacsim"
        if not isaac_ok and isaac_runtime_ok:
            isaac_detail = (
                "原生 Kit/Isaac SDK 端点在线；"
                f"配置的容器仅作备用且当前不存在（{isaac_detail}）"
            )
        checks.append(check("Isaac Sim", isaac_runtime_ok, isaac_detail))
        checks.append(
            check(
                "仿真 D405",
                env.get("A1Z_D405_ENABLED") == "1",
                f"source={env.get('A1Z_CAMERA_SOURCE')} · enabled={env.get('A1Z_D405_ENABLED')}",
            )
        )
    else:
        if ros_ok:
            can_ok, can_detail = docker_command(
                ros_name,
                ["ip", "-details", "link", "show", env.get("A1Z_CAN_CHANNEL", "can0")],
            )
        else:
            can_ok, can_detail = False, "真机容器未运行"
        checks.append(check("SocketCAN", can_ok, can_detail))

        realsense_devices = find_realsense_usb_devices()
        checks.append(
            check(
                "RealSense USB 枚举",
                bool(realsense_devices),
                "；".join(realsense_devices)
                if realsense_devices
                else "未发现带 RealSense 产品描述符的 USB 设备",
            )
        )
        calibration = env.get("A1Z_HAND_EYE_CALIBRATION_STATUS", "missing")
        checks.append(
            check(
                "手眼标定",
                calibration == "verified",
                calibration,
            )
        )

    vision_name = env.get("A1Z_VISION_CONTAINER_NAME", "")
    vision_ok, vision_detail = docker_running(vision_name)
    checks.append(check("视觉容器", vision_ok, vision_detail))

    anygrasp_assets = [
        workspace_path(env.get("A1Z_ANYGRASP_DETECTION_CKPT", "")),
        workspace_path(env.get("A1Z_ANYGRASP_LICENSE_DIR", "")),
        workspace_path(env.get("A1Z_ANYGRASP_IFCONFIG_SNAPSHOT", "")),
    ]
    missing = [str(path) for path in anygrasp_assets if not path.exists()]
    checks.append(
        check(
            "AnyGrasp 资产/许可",
            not missing,
            "已就绪" if not missing else "缺少：" + ", ".join(missing),
        )
    )

    if args.profile == "sim":
        d405_status_path = ROOT / "logs" / "d405-wrist-camera.status"
        checks.append(
            check(
                "仿真 D405 状态文件",
                d405_status_path.is_file(),
                str(d405_status_path),
                severity="advisory",
            )
        )

    required_failures = [
        item for item in checks if item["severity"] == "required" and not item["ok"]
    ]
    payload = {
        "profile": args.profile,
        "ready": not required_failures,
        "checks": checks,
        "required_failure_count": len(required_failures),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.TimeoutExpired, socket.timeout) as exc:
        print(
            json.dumps(
                {
                    "profile": "unknown",
                    "ready": False,
                    "checks": [check("预检运行器", False, f"timeout: {exc}")],
                    "required_failure_count": 1,
                },
                ensure_ascii=False,
            )
        )
        raise SystemExit(0)
