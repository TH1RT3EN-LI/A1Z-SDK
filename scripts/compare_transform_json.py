#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare two transform JSON payloads.")
    parser.add_argument("--lhs", required=True)
    parser.add_argument("--rhs", required=True)
    parser.add_argument("--output", default="")
    return parser


def _load_matrix(path: Path) -> tuple[dict[str, object], list[list[float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    matrix = [[float(v) for v in row] for row in payload["transform"]["matrix"]]
    return payload, matrix


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    out = [[0.0] * len(b[0]) for _ in range(len(a))]
    for i in range(len(a)):
        for j in range(len(b[0])):
            out[i][j] = sum(a[i][k] * b[k][j] for k in range(len(b)))
    return out


def _invert_rigid(t: list[list[float]]) -> list[list[float]]:
    rot = [[t[i][j] for j in range(3)] for i in range(3)]
    trans = [t[i][3] for i in range(3)]
    rot_t = [[rot[j][i] for j in range(3)] for i in range(3)]
    inv = [[0.0] * 4 for _ in range(4)]
    for i in range(3):
        for j in range(3):
            inv[i][j] = rot_t[i][j]
        inv[i][3] = -sum(rot_t[i][k] * trans[k] for k in range(3))
    inv[3][3] = 1.0
    return inv


def main() -> int:
    args = _build_parser().parse_args()
    lhs_payload, lhs = _load_matrix(Path(args.lhs))
    rhs_payload, rhs = _load_matrix(Path(args.rhs))

    delta = _matmul(_invert_rigid(lhs), rhs)
    trans = [delta[i][3] for i in range(3)]
    rot = [[delta[i][j] for j in range(3)] for i in range(3)]
    trace = rot[0][0] + rot[1][1] + rot[2][2]
    cos_theta = max(-1.0, min(1.0, (trace - 1.0) * 0.5))
    angle_rad = float(math.acos(cos_theta))

    report = {
        "lhs_source": lhs_payload.get("source", ""),
        "rhs_source": rhs_payload.get("source", ""),
        "lhs_target_frame_id": lhs_payload.get("target_frame_id", ""),
        "rhs_target_frame_id": rhs_payload.get("target_frame_id", ""),
        "translation_delta_m": [float(v) for v in trans],
        "translation_delta_norm_m": math.sqrt(sum(v * v for v in trans)),
        "rotation_delta_rad": angle_rad,
        "rotation_delta_deg": math.degrees(angle_rad),
        "delta_matrix": [[float(v) for v in row] for row in delta],
    }
    payload = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
