#!/usr/bin/env python3
"""Execute one-shot A1Z vision jobs on a trusted GPU host.

The ``run`` mode reads a gzip tar request from stdin and writes exactly one
gzip tar response to stdout. Operational logs go inside the response archive
or to stderr, so SSH can safely transport the binary stream without a daemon.
"""

from __future__ import annotations

import argparse
import atexit
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from a1z_ext.remote_gpu.protocol import (  # noqa: E402
    JOB_TYPE,
    MAX_ARCHIVE_BYTES,
    SCHEMA_VERSION,
    ProtocolError,
    create_archive,
    read_json,
    safe_extract_archive,
    validate_request,
    write_json,
)

WORKSPACE_ROOT = Path("/workspace/A1Z")


def _git_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update(_read_env_file(ROOT / "config" / "common.env"))
    env.update(_read_env_file(ROOT / "config" / "remote_gpu_server.env"))
    return env


def _workspace_path(path: Path) -> str:
    return str(WORKSPACE_ROOT / path.resolve().relative_to(ROOT))


def _run_logged(
    command: list[str],
    log_path: Path,
    *,
    env: dict[str, str],
    timeout_s: float,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        log.write(("+ " + " ".join(command) + "\n").encode("utf-8"))
        log.flush()
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed with exit {result.returncode}; see {log_path.name}"
        )


def _ensure_container(env: dict[str, str], log_path: Path) -> str:
    container = env.get("A1Z_VISION_CONTAINER_NAME", "a1z-vision-gpu")
    _run_logged(
        [str(ROOT / "scripts" / "ensure_a1z_vision_container.sh")],
        log_path,
        env=env,
        timeout_s=180.0,
    )
    return container


def _docker_exec(
    container: str,
    arguments: list[str],
    log_path: Path,
    *,
    env: dict[str, str],
    docker_env: dict[str, str] | None = None,
    timeout_s: float,
) -> None:
    command = ["docker", "exec", "-u", f"{os.getuid()}:{os.getgid()}"]
    for name, value in (docker_env or {}).items():
        command.extend(["-e", f"{name}={value}"])
    command.append(container)
    command.extend(arguments)
    _run_logged(command, log_path, env=env, timeout_s=timeout_s)


def _write_stdin_to_file(destination: Path) -> None:
    total = 0
    with destination.open("wb") as output:
        while True:
            chunk = sys.stdin.buffer.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise ProtocolError(f"request exceeds {MAX_ARCHIVE_BYTES} bytes")
            output.write(chunk)
    if total == 0:
        raise ProtocolError("request archive is empty")


def _cleanup_stale_jobs(jobs_root: Path, max_age_s: float) -> None:
    cutoff = time.time() - max_age_s
    for candidate in jobs_root.glob("job-*"):
        try:
            if candidate.is_dir() and candidate.stat().st_mtime < cutoff:
                shutil.rmtree(candidate)
        except OSError:
            continue


def _exit_on_disconnect(signum: int, _frame: object) -> None:
    raise SystemExit(128 + signum)


def _execute_job(
    job_root: Path,
    request: dict[str, object],
    env: dict[str, str],
) -> dict[str, object]:
    incoming = job_root / "incoming"
    inputs = incoming / "inputs"
    output = job_root / "output"
    target = output / "target"
    anygrasp = output / "anygrasp"
    logs = job_root / "logs"
    target.mkdir(parents=True, exist_ok=True)
    anygrasp.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    for filename in ("color.png", "rgb.npy", "depth_m.npy", "intrinsics.json"):
        if not (inputs / filename).is_file():
            raise ProtocolError(f"request is missing inputs/{filename}")

    container = _ensure_container(env, logs / "container.log")
    python = f"{env.get('A1Z_VISION_VENV_DIR', '/opt/venvs/a1z-vision')}/bin/python"
    target_arguments = [
        python,
        str(WORKSPACE_ROOT / "scripts" / "run_target_mask_pipeline.py"),
        "--instruction",
        str(request["instruction"]),
        "--image",
        _workspace_path(inputs / "color.png"),
        "--output-dir",
        _workspace_path(target),
        "--env-file",
        str(WORKSPACE_ROOT / "config" / "a1z_vlm.env"),
        "--provider",
        str(request["provider"]),
        "--sam-checkpoint",
        env["A1Z_SAM2_DEFAULT_CKPT"],
    ]

    lock_path = Path(env.get("A1Z_REMOTE_GPU_LOCK_FILE", "/tmp/a1z-gpu0.lock"))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        wait_started = time.monotonic()
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        lock_wait_s = time.monotonic() - wait_started
        _docker_exec(
            container,
            target_arguments,
            logs / "target_perception.log",
            env=env,
            timeout_s=float(env.get("A1Z_REMOTE_GPU_TARGET_TIMEOUT_S", "360")),
        )

        wrapper_dir = job_root / "bin"
        wrapper_dir.mkdir(parents=True, exist_ok=True)
        wrapper = wrapper_dir / "ifconfig"
        wrapper.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'cat "${A1Z_ANYGRASP_IFCONFIG_SNAPSHOT:?}"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        container_path = (
            f"{_workspace_path(wrapper_dir)}:"
            "/opt/venvs/a1z-vision/bin:/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin"
        )
        anygrasp_arguments = [
            python,
            str(WORKSPACE_ROOT / "scripts" / "run_anygrasp_from_selected_mask.py"),
            "--rgb",
            _workspace_path(inputs / "rgb.npy"),
            "--depth",
            _workspace_path(inputs / "depth_m.npy"),
            "--intrinsics",
            _workspace_path(inputs / "intrinsics.json"),
            "--selection-json",
            _workspace_path(target / "selection" / "selection.json"),
            "--output-dir",
            _workspace_path(anygrasp),
            "--sdk-dir",
            env["A1Z_ANYGRASP_SDK_DIR"],
            "--checkpoint-path",
            env["A1Z_ANYGRASP_DETECTION_CKPT"],
            "--license-dir",
            env["A1Z_ANYGRASP_LICENSE_DIR"],
        ]
        _docker_exec(
            container,
            anygrasp_arguments,
            logs / "anygrasp.log",
            env=env,
            docker_env={
                "PATH": container_path,
                "A1Z_ANYGRASP_IFCONFIG_SNAPSHOT": env[
                    "A1Z_ANYGRASP_IFCONFIG_SNAPSHOT"
                ],
            },
            timeout_s=float(env.get("A1Z_REMOTE_GPU_ANYGRASP_TIMEOUT_S", "360")),
        )

    return {
        "lock_wait_s": round(lock_wait_s, 3),
        "worker_paths": {
            "capture": _workspace_path(inputs),
            "target": _workspace_path(target),
            "anygrasp": _workspace_path(anygrasp),
        },
    }


def _run_mode() -> int:
    env = _environment()
    jobs_root = ROOT / "runtime" / "remote_gpu_jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    _cleanup_stale_jobs(
        jobs_root,
        float(env.get("A1Z_REMOTE_GPU_STALE_JOB_AGE_S", "86400")),
    )
    job_root = Path(tempfile.mkdtemp(prefix="job-", dir=jobs_root))
    atexit.register(shutil.rmtree, job_root, ignore_errors=True)
    signal.signal(signal.SIGHUP, _exit_on_disconnect)
    signal.signal(signal.SIGTERM, _exit_on_disconnect)
    request_id = "unparsed"
    response: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "job_type": JOB_TYPE,
        "request_id": request_id,
        "status": "failed",
    }
    try:
        request_archive = job_root / "request.tar.gz"
        incoming = job_root / "incoming"
        _write_stdin_to_file(request_archive)
        safe_extract_archive(request_archive, incoming)
        request = read_json(incoming / "request.json")
        candidate_request_id = request.get("request_id")
        if isinstance(candidate_request_id, str):
            request_id = candidate_request_id
            response["request_id"] = request_id
        validate_request(request)
        response.update(_execute_job(job_root, request, env))
        response["status"] = "succeeded"
    except Exception as exc:
        response["request_id"] = request_id
        response["status"] = "failed"
        response["error"] = str(exc)
        logs = job_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "worker_error.log").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

    response_json = job_root / "response.json"
    response["worker_revision"] = _git_revision()
    write_json(response_json, response)
    archive_members: dict[str, Path] = {"response.json": response_json}
    for archive_name, source in (
        ("logs", job_root / "logs"),
        ("artifacts/target", job_root / "output" / "target"),
        ("artifacts/anygrasp", job_root / "output" / "anygrasp"),
    ):
        if source.exists():
            archive_members[archive_name] = source
    response_archive = job_root / "response.tar.gz"
    try:
        create_archive(response_archive, archive_members)
        with response_archive.open("rb") as response_stream:
            shutil.copyfileobj(response_stream, sys.stdout.buffer)
        sys.stdout.buffer.flush()
        return 0
    except Exception as exc:
        print(f"could not return remote GPU response: {exc}", file=sys.stderr)
        return 2
    finally:
        shutil.rmtree(job_root, ignore_errors=True)


def _preflight_mode() -> int:
    env = _environment()
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "job_type": JOB_TYPE,
        "ready": False,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="a1z-gpu-preflight-") as temporary:
            container = _ensure_container(
                env, Path(temporary) / "container.log"
            )
        check = subprocess.run(
            [
                "docker",
                "exec",
                "-u",
                f"{os.getuid()}:{os.getgid()}",
                container,
                f"{env.get('A1Z_VISION_VENV_DIR', '/opt/venvs/a1z-vision')}/bin/python",
                "-c",
                (
                    "import json, pathlib, torch; "
                    "print(json.dumps({'cuda': torch.cuda.is_available(), "
                    "'gpu_count': torch.cuda.device_count()}))"
                ),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60.0,
            check=False,
        )
        gpu = json.loads(check.stdout) if check.returncode == 0 else {}
        required = {
            "sam_checkpoint": env.get("A1Z_SAM2_DEFAULT_CKPT", ""),
            "anygrasp_checkpoint": env.get("A1Z_ANYGRASP_DETECTION_CKPT", ""),
            "anygrasp_sdk": env.get("A1Z_ANYGRASP_SDK_DIR", ""),
            "anygrasp_license": env.get("A1Z_ANYGRASP_LICENSE_DIR", ""),
            "fingerprint_snapshot": env.get(
                "A1Z_ANYGRASP_IFCONFIG_SNAPSHOT", ""
            ),
        }
        checks: dict[str, bool] = {}
        for name, path in required.items():
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-u",
                    f"{os.getuid()}:{os.getgid()}",
                    container,
                    "test",
                    "-e",
                    path,
                ],
                cwd=ROOT,
                env=env,
                timeout=10.0,
                check=False,
            )
            checks[name] = result.returncode == 0
        payload.update(
            {
                "ready": bool(gpu.get("cuda")) and all(checks.values()),
                "cuda": bool(gpu.get("cuda")),
                "gpu_count": int(gpu.get("gpu_count", 0)),
                "container": container,
                "worker_revision": _git_revision(),
                "assets": checks,
            }
        )
    except Exception as exc:
        payload["error"] = str(exc)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ready"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "run", "forced"))
    args = parser.parse_args()
    if args.mode == "forced":
        original = os.environ.get("SSH_ORIGINAL_COMMAND", "")
        try:
            command = shlex.split(original)
        except ValueError:
            command = []
        expected_worker = str(ROOT / "scripts" / "a1z_remote_gpu_worker.py")
        if (
            len(command) != 3
            or command[0] != "python3"
            or command[1] != expected_worker
            or command[2] not in {"preflight", "run"}
        ):
            print("remote GPU key is restricted to the A1Z worker", file=sys.stderr)
            return 126
        if command[2] == "preflight":
            return _preflight_mode()
        return _run_mode()
    if args.mode == "preflight":
        return _preflight_mode()
    return _run_mode()


if __name__ == "__main__":
    raise SystemExit(main())
