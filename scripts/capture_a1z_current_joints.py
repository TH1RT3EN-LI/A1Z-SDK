#!/usr/bin/env python3

"""Capture current A1Z arm joints from the local control socket."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.config import get_socket_path, get_tcp_host, get_tcp_port
from a1z_ext.control_client import send_control_request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture current A1Z joints to JSON.")
    parser.add_argument("--socket-path", default=get_socket_path())
    parser.add_argument("--tcp-host", default=get_tcp_host())
    parser.add_argument("--tcp-port", type=int, default=get_tcp_port())
    parser.add_argument("--output-path", required=True, help="Path to write current_joints_rad.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    status = send_control_request(
        "status",
        socket_path=args.socket_path,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
    )
    pos_deg = status.get("pos_deg")
    if not isinstance(pos_deg, list) or len(pos_deg) < 6:
        raise RuntimeError(f"unexpected status payload: {status}")
    joints = [float(value) * 3.141592653589793 / 180.0 for value in pos_deg[:6]]
    output_path = Path(args.output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(joints, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "joint_count": len(joints)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
