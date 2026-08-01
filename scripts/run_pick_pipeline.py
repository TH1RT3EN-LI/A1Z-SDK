#!/usr/bin/env python3
"""Run acquisition -> target perception -> AnyGrasp -> planning -> optional execution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path("/workspace/A1Z")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from a1z_ext.remote_gpu.ssh_client import (  # noqa: E402
    RemoteGpuConfig,
    preflight_remote_gpu,
    run_remote_vision_pipeline,
)
from a1z_ext.control_client import send_control_request  # noqa: E402


def _q(value: object) -> str:
    return shlex.quote(str(value))


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _load_profile(profile: str) -> dict[str, str]:
    env: dict[str, str] = {}
    env.update(_read_env(ROOT / "config" / "common.env"))
    env.update(_read_env(ROOT / "config" / f"{profile}.env"))
    remote_config = ROOT / "config" / "remote_gpu_client.env"
    if profile == "real" and remote_config.is_file():
        env.update(_read_env(remote_config))
    env.update(os.environ)
    env["A1Z_PROFILE"] = profile
    return env


def _workspace_path(host_path: Path) -> str:
    resolved = host_path.resolve()
    relative = resolved.relative_to(ROOT)
    return str(WORKSPACE_ROOT / relative)


def _run(
    command: Sequence[str],
    *,
    env: dict[str, str],
    timeout_s: float | None = None,
) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(
        list(command),
        cwd=ROOT,
        env=env,
        check=True,
        timeout=timeout_s,
    )


def _docker_exec(
    container: str,
    shell: str,
    *,
    env: dict[str, str],
    forwarded: Sequence[str] = (),
    timeout_s: float | None = None,
) -> None:
    host_uid = os.getuid()
    host_gid = os.getgid()
    command = [
        "docker",
        "exec",
        "-u",
        f"{host_uid}:{host_gid}",
        "-e",
        f"HOME=/tmp/a1z-home-{host_uid}",
    ]
    for name in forwarded:
        if name in env:
            command.extend(["-e", f"{name}={env[name]}"])
    command.extend([container, "bash", "-lc", shell])
    _run(command, env=env, timeout_s=timeout_s)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instruction")
    parser.add_argument("--profile", choices=["sim", "real"], default="sim")
    parser.add_argument("--provider", default="kimi")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "runtime" / "pick_pipeline",
    )
    parser.add_argument("--planner", choices=["adapter", "best"], default="adapter")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--arm-speed", type=float, default=None)
    parser.add_argument(
        "--vision-backend",
        choices=["local", "remote_ssh"],
        default=None,
        help=(
            "Vision execution backend. The real profile defaults to remote_ssh and "
            "can be overridden with A1Z_REAL_VISION_BACKEND; simulation is always local."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    env = _load_profile(args.profile)
    if args.profile == "real":
        configured_vision_backend = args.vision_backend or env.get(
            "A1Z_REAL_VISION_BACKEND", "remote_ssh"
        )
    else:
        configured_vision_backend = "local"
    if args.profile != "real" and args.vision_backend == "remote_ssh":
        raise SystemExit(
            "remote GPU offload is intentionally limited to --profile real; "
            "simulation remains on its host"
        )
    if configured_vision_backend not in {"local", "remote_ssh"}:
        raise SystemExit(
            "A1Z_REAL_VISION_BACKEND must be either 'local' or 'remote_ssh'"
        )
    output = args.output_dir.expanduser().resolve()
    try:
        output.relative_to(ROOT)
    except ValueError as exc:
        raise SystemExit(f"--output-dir must be inside {ROOT}") from exc
    output.mkdir(parents=True, exist_ok=True)

    capture = output / "capture"
    target = output / "target"
    anygrasp = output / "anygrasp"
    planning = output / "planning"
    execution = output / "execution"
    for path in (capture, target, anygrasp, planning, execution):
        path.mkdir(parents=True, exist_ok=True)

    capture_ws = _workspace_path(capture)
    target_ws = _workspace_path(target)
    anygrasp_ws = _workspace_path(anygrasp)
    planning_ws = _workspace_path(planning)
    execution_ws = _workspace_path(execution)
    ros_container = env["A1Z_ROS2_CONTAINER_NAME"]
    vision_container = env["A1Z_VISION_CONTAINER_NAME"]
    stages: list[dict[str, object]] = []

    def stage(name: str, command: Sequence[str], timeout_s: float | None = None) -> None:
        _run(command, env=env, timeout_s=timeout_s)
        stages.append({"name": name, "status": "passed"})

    try:
        expected_backend = "socketcan" if args.profile == "real" else "isaacsim"
        info = send_control_request(
            "info",
            socket_path=env.get("A1Z_SOCKET_PATH", ""),
            tcp_host=env.get("A1Z_TCP_HOST", "127.0.0.1"),
            tcp_port=int(env.get("A1Z_TCP_PORT", "0")),
            timeout_s=10.0,
        )
        actual_backend = str(info.get("backend", ""))
        if actual_backend != expected_backend:
            raise RuntimeError(
                "control backend identity mismatch: "
                f"profile={args.profile} expects {expected_backend}, "
                f"endpoint reports {actual_backend or 'unknown'}"
            )
        stages.append(
            {
                "name": "control_backend_identity",
                "status": "passed",
                "backend": actual_backend,
                "tcp_port": int(env.get("A1Z_TCP_PORT", "0")),
            }
        )
        stage(
            "control_server",
            [str(ROOT / "scripts" / "a1zctl_in_container.sh"), "--json", "status"],
            20.0,
        )
        stage(
            "ros_stack_start",
            [str(ROOT / "scripts" / "run_a1z_ros2_stack_in_container.sh"), "start"],
            180.0,
        )
        stage(
            "ros_tf",
            [str(ROOT / "scripts" / "run_a1z_ros2_stack_in_container.sh"), "wait"],
            45.0,
        )
        remote_config = None
        if configured_vision_backend == "remote_ssh":
            remote_config = RemoteGpuConfig.from_env(env)
            remote_preflight = preflight_remote_gpu(remote_config)
            stages.append(
                {
                    "name": "remote_gpu_preflight",
                    "status": "passed",
                    "backend": "remote_ssh",
                    "host": remote_config.host,
                    "gpu_count": remote_preflight.get("gpu_count", 0),
                }
            )
        else:
            stage(
                "vision_container",
                [str(ROOT / "scripts" / "ensure_a1z_vision_container.sh")],
                120.0,
            )

        _docker_exec(
            ros_container,
            (
                "set -eo pipefail; "
                "set +u; "
                "source /opt/ros/humble/setup.bash; "
                "source /workspace/A1Z/ros2_ws/install/setup.bash; "
                "set -u; "
                "python3 /workspace/A1Z/scripts/capture_rgbd.py "
                f"--color-topic {_q(env['A1Z_RGBD_COLOR_TOPIC'])} "
                f"--depth-topic {_q(env['A1Z_RGBD_DEPTH_TOPIC'])} "
                f"--color-camera-info-topic {_q(env['A1Z_RGBD_COLOR_INFO_TOPIC'])} "
                f"--depth-camera-info-topic {_q(env['A1Z_RGBD_DEPTH_INFO_TOPIC'])} "
                f"--target-frame-id {_q(env['A1Z_RGBD_TARGET_FRAME'])} "
                "--timeout-s 30 --tf-lookup-timeout-s 5 "
                f"--fail-if-tf-unavailable --output-dir {_q(capture_ws)}"
            ),
            env=env,
            forwarded=(
                "A1Z_CAMERA_SOURCE",
                "A1Z_TCP_HOST",
                "A1Z_TCP_PORT",
                "A1Z_SOCKET_PATH",
                "ROS_DOMAIN_ID",
            ),
            timeout_s=60.0,
        )
        if not (capture / "current_joints_rad.json").is_file():
            raise RuntimeError("capture did not include current robot joint state")
        stages.append({"name": "rgbd_capture", "status": "passed"})

        if configured_vision_backend == "remote_ssh":
            assert remote_config is not None
            remote_result = run_remote_vision_pipeline(
                config=remote_config,
                instruction=args.instruction,
                provider=args.provider,
                capture_dir=capture,
                target_dir=target,
                anygrasp_dir=anygrasp,
                runtime_dir=output / "remote_gpu",
            )
            stages.extend(
                [
                    {
                        "name": "target_perception",
                        "status": "passed",
                        "backend": "remote_ssh",
                    },
                    {
                        "name": "anygrasp",
                        "status": "passed",
                        "backend": "remote_ssh",
                        "request_id": remote_result.get("request_id"),
                    },
                ]
            )
        else:
            env["A1Z_TARGET_INSTRUCTION"] = args.instruction
            _docker_exec(
                vision_container,
                (
                    "set -euo pipefail; source /opt/venvs/a1z-vision/bin/activate; "
                    "python3 /workspace/A1Z/scripts/run_target_mask_pipeline.py "
                    '--instruction "$A1Z_TARGET_INSTRUCTION" '
                    f"--image {_q(capture_ws + '/color.png')} "
                    f"--output-dir {_q(target_ws)} "
                    "--env-file /workspace/A1Z/config/a1z_vlm.env "
                    f"--provider {_q(args.provider)} "
                    f"--sam-checkpoint {_q(env['A1Z_SAM2_DEFAULT_CKPT'])}"
                ),
                env=env,
                forwarded=("A1Z_TARGET_INSTRUCTION",),
                timeout_s=300.0,
            )
            stages.append(
                {"name": "target_perception", "status": "passed", "backend": "local"}
            )

            _docker_exec(
                vision_container,
                (
                    "set -euo pipefail; source /opt/venvs/a1z-vision/bin/activate; "
                    f"snapshot={_q(env['A1Z_ANYGRASP_IFCONFIG_SNAPSHOT'])}; "
                    "if [[ -f \"$snapshot\" ]]; then "
                    "mkdir -p /tmp/a1z-anygrasp-bin; "
                    "printf '#!/usr/bin/env bash\\ncat \"%s\"\\n' \"$snapshot\" "
                    "> /tmp/a1z-anygrasp-bin/ifconfig; "
                    "chmod +x /tmp/a1z-anygrasp-bin/ifconfig; "
                    "export PATH=/tmp/a1z-anygrasp-bin:$PATH; fi; "
                    "python3 /workspace/A1Z/scripts/run_anygrasp_from_selected_mask.py "
                    f"--rgb {_q(capture_ws + '/rgb.npy')} "
                    f"--depth {_q(capture_ws + '/depth_m.npy')} "
                    f"--intrinsics {_q(capture_ws + '/intrinsics.json')} "
                    f"--selection-json {_q(target_ws + '/selection/selection.json')} "
                    f"--output-dir {_q(anygrasp_ws)} "
                    f"--sdk-dir {_q(env['A1Z_ANYGRASP_SDK_DIR'])} "
                    f"--checkpoint-path {_q(env['A1Z_ANYGRASP_DETECTION_CKPT'])} "
                    f"--license-dir {_q(env['A1Z_ANYGRASP_LICENSE_DIR'])}"
                ),
                env=env,
                timeout_s=300.0,
            )
            stages.append({"name": "anygrasp", "status": "passed", "backend": "local"})

        planner_script = (
            "run_anygrasp_adapter_in_container.sh"
            if args.planner == "adapter"
            else "run_anygrasp_best_plan_in_container.sh"
        )
        planner_command = [
            str(ROOT / "scripts" / planner_script),
            "--result-json",
            f"{anygrasp_ws}/anygrasp/anygrasp_result.json",
            "--extrinsic-camera-to-base",
            f"{capture_ws}/extrinsic_camera_to_base.npy",
            "--current-joints-rad",
            f"{capture_ws}/current_joints_rad.json",
            "--output-dir",
            planning_ws,
            "--frame-id",
            env["A1Z_RGBD_TARGET_FRAME"],
            "--binding-label",
            env["A1Z_ANYGRASP_BINDING_LABEL"],
            "--camera-correction-label",
            env["A1Z_ANYGRASP_CAMERA_CORRECTION_LABEL"],
            "--extrinsic-correction-label",
            env["A1Z_ANYGRASP_EXTRINSIC_CORRECTION_LABEL"],
            "--ee-grasp-origin-xyz-m",
            env["A1Z_ANYGRASP_EE_GRASP_ORIGIN"],
            "--ee-opening-axis-xyz",
            env["A1Z_ANYGRASP_EE_OPENING_AXIS"],
            "--ee-approach-axis-xyz",
            env["A1Z_ANYGRASP_EE_APPROACH_AXIS"],
            "--table-height-m",
            env["A1Z_TABLE_HEIGHT_M"],
            "--backend",
            args.profile,
        ]
        stage("planning", planner_command, 180.0)

        plan = planning / "selected_plan.json"
        if not plan.is_file():
            raise RuntimeError(f"planner did not produce {plan}")
        planner_result = planning / (
            "anygrasp_adapter_result.json"
            if args.planner == "adapter"
            else "anygrasp_best_direct_result.json"
        )
        preview_png = planning / "selected_grasp_point_cloud.png"
        preview_json = planning / "selected_grasp_preview.json"
        preview_command = [
            sys.executable,
            str(ROOT / "scripts" / "render_selected_grasp_preview.py"),
            "--points",
            str(anygrasp / "masked_point_cloud" / "points.npy"),
            "--colors",
            str(anygrasp / "masked_point_cloud" / "colors.npy"),
            "--extrinsic-camera-to-base",
            str(capture / "extrinsic_camera_to_base.npy"),
            "--planner-result",
            str(planner_result),
            "--selected-plan",
            str(plan),
            "--output-png",
            str(preview_png),
            "--output-json",
            str(preview_json),
        ]
        stage("grasp_preview", preview_command, 60.0)
        if args.execute:
            execution_command = [
                str(ROOT / "scripts" / "execute_a1z_plan_in_container.sh"),
                "--plan",
                f"{planning_ws}/selected_plan.json",
                "--output",
                f"{execution_ws}/execution_result.json",
                "--pre-open",
                "--arm-speed",
                str(args.arm_speed or env["A1Z_EXEC_ARM_SPEED"]),
                "--expected-backend",
                expected_backend,
            ]
            if args.dry_run:
                execution_command.append("--dry-run")
            stage("execution", execution_command, 600.0)

        manifest = {
            "profile": args.profile,
            "instruction": args.instruction,
            "camera_source": env["A1Z_CAMERA_SOURCE"],
            "robot_backend": env["A1Z_BACKEND"],
            "vision_backend": configured_vision_backend,
            "planner": args.planner,
            "execution_requested": bool(args.execute),
            "dry_run": bool(args.dry_run),
            "stages": stages,
            "artifacts": {
                "capture": str(capture),
                "selection": str(target / "selection" / "selection.json"),
                "anygrasp": str(anygrasp / "anygrasp" / "anygrasp_result.json"),
                "plan": str(plan),
                "planner_result": str(planner_result),
                "grasp_preview": str(preview_png),
                "grasp_preview_metadata": str(preview_json),
                "execution": str(execution / "execution_result.json"),
            },
        }
        (output / "pipeline_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(manifest, ensure_ascii=False))
        return 0
    except Exception as exc:
        stages.append({"name": "pipeline", "status": "failed", "error": str(exc)})
        (output / "pipeline_manifest.json").write_text(
            json.dumps(
                {
                    "profile": args.profile,
                    "instruction": args.instruction,
                    "vision_backend": configured_vision_backend,
                    "stages": stages,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"pick pipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
