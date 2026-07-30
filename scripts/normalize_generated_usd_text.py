#!/usr/bin/env python3
"""Stabilize machine-generated ASCII USD metadata after Isaac exits."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROBOT_USD = ROOT / "build" / "scenes" / "A1Z_G1Z_robot.usd"
STABLE_DOCUMENTATION = b"Generated from A1Z_G1Z_isaac.urdf by Isaac Sim 6."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-usd", type=Path, default=DEFAULT_ROBOT_USD)
    return parser.parse_args()


def normalize(robot_usd: Path) -> list[Path]:
    robot_path = robot_usd.expanduser().resolve()
    candidates = [robot_path]
    robot_name = robot_path.stem.removesuffix("_robot")
    payload_dirs = (
        robot_path.parent / f"{robot_name}_isaac",
        robot_path.parent / f"{robot_path.stem}_isaac",
    )
    for payload_dir in payload_dirs:
        if payload_dir.is_dir():
            candidates.extend(payload_dir.rglob("*.usd"))
            candidates.extend(payload_dir.rglob("*.usda"))

    changed: list[Path] = []
    for path in candidates:
        raw = path.read_bytes()
        if not raw.startswith(b"#usda"):
            continue
        header_end = raw.find(b"\n)\n")
        if header_end > 0:
            header = raw[:header_end]
            body = raw[header_end:]
            header = re.sub(
                rb'\n    doc = (?:""".*?"""|"[^"\n]*")',
                b'\n    doc = "' + STABLE_DOCUMENTATION + b'"',
                header,
                count=1,
                flags=re.DOTALL,
            )
            raw = header + body
        normalized = raw.rstrip(b"\r\n") + b"\n"
        if normalized != path.read_bytes():
            path.write_bytes(normalized)
            changed.append(path)
    return changed


def main() -> int:
    changed = normalize(parse_args().robot_usd)
    print(f"Normalized {len(changed)} generated ASCII USD layer(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
