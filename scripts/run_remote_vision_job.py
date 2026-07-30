#!/usr/bin/env python3
"""Preflight or submit an A1Z real-hardware vision job to an SSH GPU host."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from a1z_ext.remote_gpu.ssh_client import (  # noqa: E402
    RemoteGpuConfig,
    preflight_remote_gpu,
    run_remote_vision_pipeline,
)


def _read_env(path: Path) -> dict[str, str]:
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
    env: dict[str, str] = {}
    for path in (
        ROOT / "config" / "common.env",
        ROOT / "config" / "real.env",
        ROOT / "config" / "remote_gpu_client.env",
    ):
        env.update(_read_env(path))
    env.update(os.environ)
    return env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="Verify SSH, GPU container and private assets.")
    run = subparsers.add_parser("run", help="Submit one captured RGB-D frame.")
    run.add_argument("instruction")
    run.add_argument("--provider", default="kimi")
    run.add_argument("--capture-dir", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = RemoteGpuConfig.from_env(_environment())
    if args.command == "preflight":
        print(json.dumps(preflight_remote_gpu(config), ensure_ascii=False, indent=2))
        return 0

    output = args.output_dir.expanduser().resolve()
    result = run_remote_vision_pipeline(
        config=config,
        instruction=args.instruction,
        provider=args.provider,
        capture_dir=args.capture_dir.expanduser().resolve(),
        target_dir=output / "target",
        anygrasp_dir=output / "anygrasp",
        runtime_dir=output / "remote_gpu",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
