"""Stream measured robot state for thin GUI adapters.

The process emits one JSON object per line.  It never owns hardware and uses
the same :class:`a1z_sdk.A1ZClient` API as command-line callers.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from typing import Any

from .client import A1ZClient
from .errors import A1ZError


def read_telemetry(client: A1ZClient, *, sequence: int) -> dict[str, Any]:
    try:
        state = client.status()
        return {
            "ok": True,
            "sequence": sequence,
            "timestampMs": time.time_ns() // 1_000_000,
            "data": dict(state.raw),
        }
    except (A1ZError, OSError, RuntimeError, ValueError) as exc:
        return {
            "ok": False,
            "sequence": sequence,
            "timestampMs": time.time_ns() // 1_000_000,
            "error": str(exc),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=0.4)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    interval = float(args.interval)
    if not 0.1 <= interval <= 10.0:
        raise SystemExit("--interval must be in [0.1, 10.0]")

    client = A1ZClient()
    sequence = 0
    try:
        while True:
            started_at = time.monotonic()
            payload = read_telemetry(client, sequence=sequence)
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
            sequence += 1
            if args.once:
                return 0 if payload["ok"] else 1
            remaining = interval - (time.monotonic() - started_at)
            if remaining > 0:
                time.sleep(remaining)
    except (BrokenPipeError, KeyboardInterrupt):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
