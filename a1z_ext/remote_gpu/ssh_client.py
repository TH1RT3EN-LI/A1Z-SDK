"""SSH transport for one-shot remote GPU jobs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import Mapping
import uuid

from .protocol import (
    JOB_TYPE,
    SCHEMA_VERSION,
    ProtocolError,
    create_archive,
    read_json,
    rebase_json_files,
    replace_directory,
    safe_extract_archive,
    write_json,
)


class RemoteGpuError(RuntimeError):
    """A transport, protocol, or remote execution failure."""


@dataclass(frozen=True)
class RemoteGpuConfig:
    host: str
    user: str
    remote_root: str
    port: int = 22
    identity_file: str = ""
    timeout_s: float = 600.0
    connect_timeout_s: float = 10.0
    strict_host_key_checking: str = "accept-new"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "RemoteGpuConfig":
        required = {
            "A1Z_REMOTE_GPU_HOST": env.get("A1Z_REMOTE_GPU_HOST", "").strip(),
            "A1Z_REMOTE_GPU_USER": env.get("A1Z_REMOTE_GPU_USER", "").strip(),
            "A1Z_REMOTE_GPU_ROOT": env.get("A1Z_REMOTE_GPU_ROOT", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RemoteGpuError(
                "missing remote GPU configuration: " + ", ".join(missing)
            )
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", required["A1Z_REMOTE_GPU_USER"]):
            raise RemoteGpuError("A1Z_REMOTE_GPU_USER is not a valid SSH username")
        if not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]+", required["A1Z_REMOTE_GPU_HOST"]):
            raise RemoteGpuError("A1Z_REMOTE_GPU_HOST is not a valid host or IP")
        if not required["A1Z_REMOTE_GPU_ROOT"].startswith("/"):
            raise RemoteGpuError("A1Z_REMOTE_GPU_ROOT must be an absolute path")
        try:
            port = int(env.get("A1Z_REMOTE_GPU_PORT", "22"))
            timeout_s = float(env.get("A1Z_REMOTE_GPU_TIMEOUT_S", "600"))
            connect_timeout_s = float(
                env.get("A1Z_REMOTE_GPU_CONNECT_TIMEOUT_S", "10")
            )
        except ValueError as exc:
            raise RemoteGpuError("remote GPU port and timeouts must be numeric") from exc
        if not 1 <= port <= 65535:
            raise RemoteGpuError("A1Z_REMOTE_GPU_PORT must be between 1 and 65535")
        if timeout_s <= 0 or connect_timeout_s <= 0:
            raise RemoteGpuError("remote GPU timeouts must be positive")
        strict_host_key_checking = env.get(
            "A1Z_REMOTE_GPU_STRICT_HOST_KEY_CHECKING", "accept-new"
        )
        if strict_host_key_checking not in {"yes", "accept-new"}:
            raise RemoteGpuError(
                "A1Z_REMOTE_GPU_STRICT_HOST_KEY_CHECKING must be yes or accept-new"
            )
        return cls(
            host=required["A1Z_REMOTE_GPU_HOST"],
            user=required["A1Z_REMOTE_GPU_USER"],
            remote_root=required["A1Z_REMOTE_GPU_ROOT"],
            port=port,
            identity_file=env.get("A1Z_REMOTE_GPU_IDENTITY_FILE", "").strip(),
            timeout_s=timeout_s,
            connect_timeout_s=connect_timeout_s,
            strict_host_key_checking=strict_host_key_checking,
        )

    @property
    def destination(self) -> str:
        return f"{self.user}@{self.host}"

    def ssh_command(self, remote_arguments: list[str]) -> list[str]:
        command = [
            "ssh",
            "-T",
            "-p",
            str(self.port),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            f"ConnectTimeout={self.connect_timeout_s:g}",
            "-o",
            f"StrictHostKeyChecking={self.strict_host_key_checking}",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
        ]
        if self.identity_file:
            command.extend(["-i", str(Path(self.identity_file).expanduser())])
        remote_command = " ".join(shlex.quote(argument) for argument in remote_arguments)
        command.extend([self.destination, remote_command])
        return command


def preflight_remote_gpu(config: RemoteGpuConfig) -> dict[str, object]:
    command = config.ssh_command(
        [
            "python3",
            f"{config.remote_root.rstrip('/')}/scripts/a1z_remote_gpu_worker.py",
            "preflight",
        ]
    )
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=min(config.timeout_s, 180.0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RemoteGpuError(f"remote GPU preflight transport failed: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RemoteGpuError(
            f"remote GPU preflight failed (exit {result.returncode}): {detail}"
        )
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RemoteGpuError("remote GPU preflight returned invalid JSON") from exc
    if not isinstance(payload, dict) or not payload.get("ready"):
        raise RemoteGpuError(f"remote GPU is not ready: {payload}")
    return payload


def run_remote_vision_pipeline(
    *,
    config: RemoteGpuConfig,
    instruction: str,
    provider: str,
    capture_dir: Path,
    target_dir: Path,
    anygrasp_dir: Path,
    runtime_dir: Path,
) -> dict[str, object]:
    """Offload target selection and AnyGrasp, then materialize all results locally."""

    request_id = uuid.uuid4().hex
    required_inputs = {
        "inputs/color.png": capture_dir / "color.png",
        "inputs/rgb.npy": capture_dir / "rgb.npy",
        "inputs/depth_m.npy": capture_dir / "depth_m.npy",
        "inputs/intrinsics.json": capture_dir / "intrinsics.json",
    }
    missing = [str(path) for path in required_inputs.values() if not path.is_file()]
    if missing:
        raise RemoteGpuError("capture is missing remote GPU inputs: " + ", ".join(missing))

    runtime_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="a1z-remote-gpu-client-") as temporary:
        temporary_root = Path(temporary)
        request_json = temporary_root / "request.json"
        request_archive = temporary_root / "request.tar.gz"
        response_archive = temporary_root / "response.tar.gz"
        extracted = temporary_root / "response"
        write_json(
            request_json,
            {
                "schema_version": SCHEMA_VERSION,
                "job_type": JOB_TYPE,
                "request_id": request_id,
                "instruction": instruction,
                "provider": provider,
            },
        )
        create_archive(
            request_archive,
            {"request.json": request_json, **required_inputs},
        )
        command = config.ssh_command(
            [
                "python3",
                f"{config.remote_root.rstrip('/')}/scripts/a1z_remote_gpu_worker.py",
                "run",
            ]
        )
        stderr_path = runtime_dir / f"{request_id}.transport.log"
        try:
            with (
                request_archive.open("rb") as request_stream,
                response_archive.open("wb") as response_stream,
            ):
                result = subprocess.run(
                    command,
                    stdin=request_stream,
                    stdout=response_stream,
                    stderr=subprocess.PIPE,
                    timeout=config.timeout_s,
                    check=False,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RemoteGpuError(f"remote GPU transport failed: {exc}") from exc
        stderr_path.write_bytes(result.stderr)
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RemoteGpuError(
                f"remote GPU worker failed (exit {result.returncode}): {detail}"
            )
        if not response_archive.is_file() or response_archive.stat().st_size == 0:
            raise RemoteGpuError("remote GPU worker returned an empty response")

        try:
            safe_extract_archive(response_archive, extracted)
            response = read_json(extracted / "response.json")
        except (OSError, ProtocolError) as exc:
            raise RemoteGpuError(f"invalid remote GPU response: {exc}") from exc
        if response.get("schema_version") != SCHEMA_VERSION:
            raise RemoteGpuError("remote GPU response schema does not match the client")
        if response.get("request_id") != request_id:
            raise RemoteGpuError("remote GPU response request_id does not match")

        returned_logs = extracted / "logs"
        if returned_logs.is_dir():
            for log_path in returned_logs.iterdir():
                if log_path.is_file():
                    shutil.copy2(log_path, runtime_dir / log_path.name)

        artifacts = extracted / "artifacts"
        returned_target = artifacts / "target"
        returned_anygrasp = artifacts / "anygrasp"
        if returned_target.is_dir():
            replace_directory(returned_target, target_dir)
        if returned_anygrasp.is_dir():
            replace_directory(returned_anygrasp, anygrasp_dir)

        paths = response.get("worker_paths")
        if isinstance(paths, dict):
            replacements: dict[str, str] = {}
            remote_capture = paths.get("capture")
            remote_target = paths.get("target")
            remote_anygrasp = paths.get("anygrasp")
            if isinstance(remote_capture, str):
                replacements[remote_capture] = str(capture_dir.resolve())
            if isinstance(remote_target, str):
                replacements[remote_target] = str(target_dir.resolve())
            if isinstance(remote_anygrasp, str):
                replacements[remote_anygrasp] = str(anygrasp_dir.resolve())
            if replacements:
                rebase_json_files(target_dir, replacements)
                rebase_json_files(anygrasp_dir, replacements)

        local_response = dict(response)
        local_response.pop("worker_paths", None)
        local_response["client_artifacts"] = {
            "target": str(target_dir.resolve()),
            "anygrasp": str(anygrasp_dir.resolve()),
            "logs": str(runtime_dir.resolve()),
        }
        write_json(runtime_dir / f"{request_id}.response.json", local_response)
        if response.get("status") != "succeeded":
            raise RemoteGpuError(
                "remote GPU job failed: " + str(response.get("error", "unknown error"))
            )
        expected = anygrasp_dir / "anygrasp" / "anygrasp_result.json"
        if not expected.is_file():
            raise RemoteGpuError(f"remote GPU response is missing {expected}")
        return local_response
