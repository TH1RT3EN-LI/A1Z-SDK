#!/usr/bin/env python3
"""Start and verify the project-scoped A1Z ROS 2 camera/TF stack."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from a1z_ext.gui_console import read_env_file, request_a1z  # noqa: E402


def _write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _run(
    command: Sequence[str],
    *,
    env: dict[str, str],
    check: bool = True,
    capture: bool = False,
    timeout_s: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(ROOT_DIR),
        env=env,
        check=check,
        text=True,
        timeout=timeout_s,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def _bridge_running(env: dict[str, str]) -> bool:
    result = _run(
        [str(ROOT_DIR / "scripts" / "run_a1z_ros2_motion_in_container.sh"), "status"],
        env=env,
        check=False,
        capture=True,
        timeout_s=10.0,
    )
    return result.returncode == 0


def _wait_for_camera(
    host: str,
    port: int,
    *,
    timeout_s: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last_detail = ""
    next_report = 0.0
    while time.monotonic() < deadline:
        try:
            status = request_a1z(host, port, "camera_status", timeout_s=2.0)
            if status.get("ready") and status.get("warmup_complete"):
                print(
                    "[full-start] D405 ready "
                    f"generation={status.get('capture_generation')} "
                    f"frequency_hz={status.get('frequency_hz')}",
                    flush=True,
                )
                return status
            last_detail = str(status.get("last_error") or "D405 正在 warm-up")
        except Exception as exc:
            last_detail = f"A1Z camera_status 尚不可用: {exc}"
        now = time.monotonic()
        if now >= next_report:
            print(f"[full-start] 等待 D405: {last_detail}", flush=True)
            next_report = now + 5.0
        time.sleep(0.5)
    raise TimeoutError(f"等待 D405 ready 超时（{timeout_s:g}s）: {last_detail}")


def _wait_for_image_topic(
    env: dict[str, str],
    topic: str,
    *,
    timeout_s: float,
) -> None:
    container = env["A1Z_ROS2_CONTAINER_NAME"]
    domain = env["ROS_DOMAIN_ID"]
    command = [
        "docker",
        "exec",
        "-e",
        f"ROS_DOMAIN_ID={domain}",
        container,
        "bash",
        "-lc",
        """
set -eo pipefail
set +u
source /opt/ros/humble/setup.bash
if [[ -f /workspace/A1Z/ros2_ws/install/setup.bash ]]; then
  source /workspace/A1Z/ros2_ws/install/setup.bash
fi
set -u
timeout "$2" ros2 topic echo \
  --no-daemon \
  --qos-profile sensor_data \
  --once \
  --field header \
  "$1" sensor_msgs/msg/Image >/dev/null
""",
        "bash",
        topic,
        f"{max(1.0, timeout_s):g}s",
    ]
    _run(command, env=env, timeout_s=timeout_s + 5.0)
    print(f"[full-start] 收到图像帧: {topic}", flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tcp-host", default="127.0.0.1")
    parser.add_argument("--tcp-port", type=int, default=37103)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--status-path", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    env = dict(os.environ)
    for path in (
        ROOT_DIR / "config" / "a1z_container.env",
        ROOT_DIR / "config" / "a1z_isaac6_standalone.env",
    ):
        for key, value in read_env_file(path).items():
            env.setdefault(key, value)
    env.update(
        {
            "A1Z_TCP_HOST": args.tcp_host,
            "A1Z_TCP_PORT": str(args.tcp_port),
            "A1Z_CONTAINER_ENV_FILE": str(ROOT_DIR / "config" / "a1z_container.env"),
        }
    )
    env.setdefault("ROS_DOMAIN_ID", "0")
    env.setdefault("A1Z_ROS2_CONTAINER_NAME", "a1z-ros2-humble")

    result: dict[str, Any] = {
        "ready": False,
        "ownership": "none",
        "ros_domain_id": env["ROS_DOMAIN_ID"],
        "container_name": env["A1Z_ROS2_CONTAINER_NAME"],
        "color_topic": "/a1z/d405/color/image_raw",
        "depth_topic": "/a1z/d405/depth/image_rect",
    }
    started_here = False
    completed = False

    def cancel(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt("ROS bridge 启动被取消")

    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)

    try:
        print(
            "[full-start] 等待 Isaac D405 就绪 "
            f"tcp://{args.tcp_host}:{args.tcp_port}",
            flush=True,
        )
        camera = _wait_for_camera(
            args.tcp_host,
            args.tcp_port,
            timeout_s=max(1.0, args.timeout_s),
        )
        result["camera_generation"] = camera.get("capture_generation")

        if _bridge_running(env):
            result["ownership"] = "external"
            print("[full-start] 检测到已有项目 ROS bridge；保留其所有权", flush=True)
        else:
            result["ownership"] = "console"
            started_here = True
            print("[full-start] 创建/启动项目 ROS 容器与 D405/TF bridge", flush=True)
            _run(
                [
                    str(ROOT_DIR / "scripts" / "run_a1z_ros2_motion_in_container.sh"),
                    "start",
                ],
                env=env,
                timeout_s=max(60.0, args.timeout_s),
            )

        print("[full-start] 等待 D405 TF", flush=True)
        _run(
            [
                str(ROOT_DIR / "scripts" / "run_a1z_ros2_motion_in_container.sh"),
                "wait",
            ],
            env=env,
            timeout_s=40.0,
        )
        per_topic_timeout = min(45.0, max(10.0, args.timeout_s / 3.0))
        _wait_for_image_topic(
            env,
            result["color_topic"],
            timeout_s=per_topic_timeout,
        )
        _wait_for_image_topic(
            env,
            result["depth_topic"],
            timeout_s=per_topic_timeout,
        )
        result["ready"] = True
        completed = True
        print(
            "[full-start] ROS bridge、TF、RGB-D 均已就绪 "
            f"ROS_DOMAIN_ID={env['ROS_DOMAIN_ID']}",
            flush=True,
        )
        return 0
    except KeyboardInterrupt as exc:
        result["error"] = str(exc)
        print(f"[full-start] 已取消: {exc}", file=sys.stderr, flush=True)
        return 130
    except Exception as exc:
        result["error"] = str(exc)
        print(f"[full-start] 失败: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if started_here and not completed:
            print("[full-start] 回滚本次启动的 ROS bridge", flush=True)
            _run(
                [
                    str(ROOT_DIR / "scripts" / "run_a1z_ros2_motion_in_container.sh"),
                    "stop",
                ],
                env=env,
                check=False,
                timeout_s=15.0,
            )
            result["ownership"] = "none"
        _write_status(args.status_path, result)


if __name__ == "__main__":
    raise SystemExit(main())
