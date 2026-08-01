from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from a1z_ext.remote_gpu.protocol import (
    ProtocolError,
    create_archive,
    rebase_json_files,
    safe_extract_archive,
)
from a1z_ext.remote_gpu.ssh_client import (
    RemoteGpuConfig,
    RemoteGpuError,
    run_remote_vision_pipeline,
)


ROOT = Path(__file__).resolve().parents[1]


def test_archive_round_trip_and_path_rebase(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "selection.json").write_text(
        json.dumps(
            {
                "image": "/workspace/A1Z/runtime/remote-job/inputs/color.png",
                "mask": "/workspace/A1Z/runtime/remote-job/target/mask.npy",
            }
        ),
        encoding="utf-8",
    )
    archive = tmp_path / "response.tar.gz"
    create_archive(archive, {"artifacts/target": source})

    extracted = tmp_path / "extracted"
    safe_extract_archive(archive, extracted)
    target = extracted / "artifacts" / "target"
    rebase_json_files(
        target,
        {
            "/workspace/A1Z/runtime/remote-job/inputs": "/laptop/capture",
            "/workspace/A1Z/runtime/remote-job/target": "/laptop/target",
        },
    )
    payload = json.loads((target / "selection.json").read_text(encoding="utf-8"))
    assert payload["image"] == "/laptop/capture/color.png"
    assert payload["mask"] == "/laptop/target/mask.npy"


@pytest.mark.parametrize("member_name", ["../escape", "/absolute/path"])
def test_archive_rejects_path_traversal(tmp_path: Path, member_name: str) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo(member_name)
        payload = b"unsafe"
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))
    with pytest.raises(ProtocolError, match="unsafe archive"):
        safe_extract_archive(archive, tmp_path / "output")


def test_archive_rejects_links(tmp_path: Path) -> None:
    archive = tmp_path / "link.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        handle.addfile(info)
    with pytest.raises(ProtocolError, match="type is not allowed"):
        safe_extract_archive(archive, tmp_path / "output")


def test_remote_config_requires_explicit_endpoint() -> None:
    with pytest.raises(RemoteGpuError, match="A1Z_REMOTE_GPU_HOST"):
        RemoteGpuConfig.from_env({})
    config = RemoteGpuConfig.from_env(
        {
            "A1Z_REMOTE_GPU_HOST": "10.66.0.11",
            "A1Z_REMOTE_GPU_USER": "robot",
            "A1Z_REMOTE_GPU_ROOT": "/srv/A1Z",
        }
    )
    command = config.ssh_command(["python3", "/srv/A1Z/worker.py", "run"])
    assert command[-2] == "robot@10.66.0.11"
    assert command[-1] == "python3 /srv/A1Z/worker.py run"
    assert "BatchMode=yes" in command
    assert "IdentitiesOnly=yes" in command


def test_worker_returns_failure_archive_and_cleans_temporary_job(
    tmp_path: Path,
) -> None:
    jobs_root = ROOT / "runtime" / "remote_gpu_jobs"
    before = set(jobs_root.glob("job-*")) if jobs_root.is_dir() else set()
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "a1z_remote_gpu_worker.py"), "run"],
        input=b"not a tar archive",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    response_archive = tmp_path / "response.tar.gz"
    response_archive.write_bytes(result.stdout)
    extracted = tmp_path / "response"
    safe_extract_archive(response_archive, extracted)
    response = json.loads((extracted / "response.json").read_text(encoding="utf-8"))
    assert response["status"] == "failed"
    assert (extracted / "logs" / "worker_error.log").is_file()
    after = set(jobs_root.glob("job-*")) if jobs_root.is_dir() else set()
    assert after == before


def test_forced_worker_rejects_an_interactive_command() -> None:
    env = dict(os.environ)
    env["SSH_ORIGINAL_COMMAND"] = "bash"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "a1z_remote_gpu_worker.py"),
            "forced",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    assert result.returncode == 126
    assert b"restricted to the A1Z worker" in result.stderr


def test_ssh_client_materializes_response_only_on_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text(
        """#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tarfile
import tempfile

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    request_archive = root / "request.tar.gz"
    request_archive.write_bytes(sys.stdin.buffer.read())
    with tarfile.open(request_archive, "r:gz") as archive:
        archive.extractall(root / "request")
    request = json.loads((root / "request" / "request.json").read_text())
    target = root / "artifacts" / "target" / "selection"
    result = root / "artifacts" / "anygrasp" / "anygrasp"
    logs = root / "logs"
    target.mkdir(parents=True)
    result.mkdir(parents=True)
    logs.mkdir()
    (target / "selection.json").write_text(json.dumps({
        "selected_mask": {
            "mask_npy_path": "/workspace/A1Z/runtime/job/output/target/selection/mask.npy"
        },
        "image_path": "/workspace/A1Z/runtime/job/incoming/inputs/color.png"
    }))
    (target / "mask.npy").write_bytes(b"mask")
    (result / "anygrasp_result.json").write_text(json.dumps({"ran": True}))
    (logs / "anygrasp.log").write_text("ok")
    response = {
        "schema_version": 1,
        "job_type": "a1z.real.vision_pipeline",
        "request_id": request["request_id"],
        "status": "succeeded",
        "worker_paths": {
            "capture": "/workspace/A1Z/runtime/job/incoming/inputs",
            "target": "/workspace/A1Z/runtime/job/output/target",
            "anygrasp": "/workspace/A1Z/runtime/job/output/anygrasp"
        }
    }
    (root / "response.json").write_text(json.dumps(response))
    response_archive = root / "response.tar.gz"
    with tarfile.open(response_archive, "w:gz") as archive:
        archive.add(root / "response.json", arcname="response.json")
        archive.add(root / "artifacts", arcname="artifacts")
        archive.add(logs, arcname="logs")
    sys.stdout.buffer.write(response_archive.read_bytes())
""",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ["PATH"])

    capture = tmp_path / "capture"
    capture.mkdir()
    for filename in ("color.png", "rgb.npy", "depth_m.npy", "intrinsics.json"):
        (capture / filename).write_bytes(b"input")
    target = tmp_path / "target"
    anygrasp = tmp_path / "anygrasp"
    runtime = tmp_path / "remote_gpu"
    response = run_remote_vision_pipeline(
        config=RemoteGpuConfig(
            host="10.66.0.11",
            user="robot",
            remote_root="/srv/A1Z",
        ),
        instruction="pick the object",
        provider="test",
        capture_dir=capture,
        target_dir=target,
        anygrasp_dir=anygrasp,
        runtime_dir=runtime,
    )
    assert response["status"] == "succeeded"
    selection = json.loads(
        (target / "selection" / "selection.json").read_text(encoding="utf-8")
    )
    assert selection["image_path"] == str(capture / "color.png")
    assert selection["selected_mask"]["mask_npy_path"] == str(
        target / "selection" / "mask.npy"
    )
    assert (anygrasp / "anygrasp" / "anygrasp_result.json").is_file()
    assert (runtime / "anygrasp.log").read_text(encoding="utf-8") == "ok"


def test_simulation_cannot_select_remote_gpu() -> None:
    pipeline = (ROOT / "scripts" / "run_pick_pipeline.py").read_text(encoding="utf-8")
    assert 'args.profile != "real" and args.vision_backend == "remote_ssh"' in pipeline
    assert "simulation remains on its host" in pipeline
