"""Versioned, archive-based protocol shared by the GPU client and worker."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from typing import Any, Mapping


SCHEMA_VERSION = 1
JOB_TYPE = "a1z.real.vision_pipeline"
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_MEMBER_BYTES = 1024 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_MEMBERS = 20_000


class ProtocolError(RuntimeError):
    """Raised when an untrusted request or response violates the protocol."""


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError(f"expected a JSON object: {path}")
    return payload


def create_archive(
    archive_path: Path,
    members: Mapping[str, Path],
) -> None:
    """Create a gzip tar from an explicit mapping of local paths."""

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz", compresslevel=6) as archive:
        for archive_name, source in sorted(members.items()):
            source = source.resolve()
            if not source.exists():
                raise ProtocolError(f"archive source does not exist: {source}")
            _validate_member_name(archive_name)
            archive.add(source, arcname=archive_name, recursive=True)


def safe_extract_archive(archive_path: Path, destination: Path) -> None:
    """Extract only regular files/directories beneath ``destination``."""

    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ProtocolError(f"archive exceeds {MAX_ARCHIVE_BYTES} bytes")
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            members = archive.getmembers()
            if len(members) > MAX_MEMBERS:
                raise ProtocolError(f"archive has more than {MAX_MEMBERS} members")
            total_size = sum(member.size for member in members)
            if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ProtocolError(
                    "archive uncompressed content exceeds "
                    f"{MAX_TOTAL_UNCOMPRESSED_BYTES} bytes"
                )
            for member in members:
                _validate_member_name(member.name)
                if member.size > MAX_MEMBER_BYTES:
                    raise ProtocolError(f"archive member is too large: {member.name}")
                if not (member.isfile() or member.isdir()):
                    raise ProtocolError(
                        f"archive member type is not allowed: {member.name}"
                    )
                target = (destination / member.name).resolve()
                if target != destination_root and destination_root not in target.parents:
                    raise ProtocolError(
                        f"archive member escapes destination: {member.name}"
                    )
            archive.extractall(destination, members=members)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ProtocolError(f"invalid archive: {archive_path}") from exc


def validate_request(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ProtocolError(
            f"unsupported schema_version: {payload.get('schema_version')!r}"
        )
    if payload.get("job_type") != JOB_TYPE:
        raise ProtocolError(f"unsupported job_type: {payload.get('job_type')!r}")
    request_id = payload.get("request_id")
    if (
        not isinstance(request_id, str)
        or not request_id
        or len(request_id) > 80
        or not all(character.isalnum() or character in "-_" for character in request_id)
    ):
        raise ProtocolError("request_id must contain only letters, digits, '-' and '_'")
    instruction = payload.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ProtocolError("instruction must be a non-empty string")
    if len(instruction) > 8_000:
        raise ProtocolError("instruction is too long")
    provider = payload.get("provider")
    if not isinstance(provider, str) or not provider or len(provider) > 64:
        raise ProtocolError("provider must be a non-empty string up to 64 characters")


def rebase_json_files(root: Path, replacements: Mapping[str, str]) -> None:
    """Rewrite worker-local artifact paths after the response lands on the client."""

    ordered = sorted(
        ((source.rstrip("/"), target.rstrip("/")) for source, target in replacements.items()),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for json_path in root.rglob("*.json"):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rewritten = _rewrite_value(payload, ordered)
        if rewritten != payload:
            json_path.write_text(
                json.dumps(rewritten, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )


def replace_directory(source: Path, destination: Path) -> None:
    """Replace a local result directory without leaving stale artifacts."""

    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise ProtocolError(f"unsafe archive member name: {name!r}")


def _rewrite_value(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        for source, target in replacements:
            if value == source or value.startswith(source + "/"):
                return target + value[len(source) :]
        return value
    if isinstance(value, list):
        return [_rewrite_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {
            key: _rewrite_value(item, replacements)
            for key, item in value.items()
        }
    return value
