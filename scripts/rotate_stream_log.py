#!/usr/bin/env python3
"""Copy stdin to a size-bounded rotating log without stopping the producer."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import BinaryIO


def _rotate(path: Path, backup_count: int) -> None:
    if backup_count <= 0:
        path.unlink(missing_ok=True)
        return
    oldest = path.with_name(f"{path.name}.{backup_count}")
    oldest.unlink(missing_ok=True)
    for index in range(backup_count - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            os.replace(source, path.with_name(f"{path.name}.{index + 1}"))
    if path.exists():
        os.replace(path, path.with_name(f"{path.name}.1"))


def copy_rotating(
    source: BinaryIO,
    path: Path,
    *,
    max_bytes: int,
    backup_count: int,
) -> None:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if backup_count < 0:
        raise ValueError("backup_count must be non-negative")

    path.parent.mkdir(parents=True, exist_ok=True)
    output = path.open("ab", buffering=0)
    size = path.stat().st_size
    read_chunk = getattr(source, "read1", source.read)
    try:
        while chunk := read_chunk(64 * 1024):
            remaining = memoryview(chunk)
            while remaining:
                if size >= max_bytes:
                    output.close()
                    _rotate(path, backup_count)
                    output = path.open("wb", buffering=0)
                    size = 0
                write_size = min(len(remaining), max_bytes - size)
                output.write(remaining[:write_size])
                remaining = remaining[write_size:]
                size += write_size
    finally:
        output.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--backup-count", type=int, default=3)
    args = parser.parse_args()
    copy_rotating(
        sys.stdin.buffer,
        args.path,
        max_bytes=args.max_bytes,
        backup_count=args.backup_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
