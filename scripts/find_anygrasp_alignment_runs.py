#!/usr/bin/env python3

"""List AnyGrasp pipeline directories ordered by alignment-evidence quality."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find AnyGrasp runs suitable for alignment decisions.")
    parser.add_argument(
        "--runtime-dir",
        default="runtime",
        help="Runtime root to scan. Defaults to ./runtime",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of runs to print.",
    )
    parser.add_argument(
        "--require-analysis",
        action="store_true",
        help="Only keep runs that already contain analysis/analysis_summary.json.",
    )
    parser.add_argument(
        "--require-current-joints",
        action="store_true",
        help="Only keep runs whose capture/current_joints_rad.json is present.",
    )
    parser.add_argument(
        "--require-reliable",
        action="store_true",
        help="Only keep runs whose analysis marks best_direct_reference_state_reliable=true.",
    )
    parser.add_argument(
        "--include-fixtures",
        action="store_true",
        help="Include verify/smoke/analysis fixture directories in the scan.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a text table.",
    )
    return parser


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _read_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _candidate_dirs(runtime_dir: Path) -> list[Path]:
    rows: list[Path] = []
    for manifest_path in runtime_dir.rglob("pipeline_manifest.json"):
        if "isaac-sim-portable" in manifest_path.parts:
            continue
        rows.append(manifest_path.parent)
    return sorted(rows)


def _looks_like_fixture_dir(pipeline_dir: Path) -> bool:
    name = pipeline_dir.name
    fixture_tokens = (
        "verify",
        "smoke",
        "analysis_input",
        "analysis_verify",
        "adapter_verify",
        "tcp_scan",
    )
    return any(token in name for token in fixture_tokens)


def _collect_row(pipeline_dir: Path) -> dict[str, Any] | None:
    manifest = _load_json(pipeline_dir / "pipeline_manifest.json")
    status = _load_json(pipeline_dir / "pipeline_status.json")
    if manifest is None or status is None:
        return None

    adapter = manifest.get("adapter")
    summary = manifest.get("summary", {})
    if not isinstance(adapter, dict):
        return None
    adapter_result = str(adapter.get("result_json", ""))
    best_direct_result = str(adapter.get("best_direct_result_json", ""))
    if not adapter_result.endswith("anygrasp_adapter_result.json") and not best_direct_result.endswith(
        "anygrasp_best_direct_result.json"
    ):
        return None

    analysis_path = pipeline_dir / "analysis" / "analysis_summary.json"
    analysis = _load_json(analysis_path) if analysis_path.is_file() else None
    capture = manifest.get("capture", {})
    current_joints_path = None
    current_joints_present = False
    if isinstance(capture, dict):
        raw = capture.get("current_joints_rad_json")
        if raw:
            current_joints_path = Path(str(raw))
            if not current_joints_path.is_absolute():
                current_joints_path = (pipeline_dir / current_joints_path).resolve()
            current_joints_present = current_joints_path.is_file()

    if analysis is not None:
        reliable = bool(analysis.get("best_direct_reference_state_reliable", False))
        fit_for_decision = bool(
            analysis.get("diagnostic_summary", {})
            .get("evidence_quality", {})
            .get("alignment_fit_for_decision", False)
        )
        best_direct_gap_norm_m = analysis.get("best_direct_grasp_gap_norm_m")
        best_direct_gap_deg = analysis.get("best_direct_grasp_orientation_gap_deg")
    else:
        reliable = False
        fit_for_decision = False
        best_direct_gap_norm_m = None
        best_direct_gap_deg = None

    return {
        "pipeline_dir": str(pipeline_dir.resolve()),
        "run_name": pipeline_dir.name,
        "is_fixture_dir": _looks_like_fixture_dir(pipeline_dir),
        "mtime": _read_timestamp(pipeline_dir / "pipeline_manifest.json"),
        "analysis_present": analysis is not None,
        "current_joints_present": current_joints_present,
        "best_direct_reference_state_reliable": reliable,
        "alignment_fit_for_decision": fit_for_decision,
        "selected_rank": status.get("selected_rank"),
        "adapter_executable_count": status.get("adapter_executable_count"),
        "best_direct_result_present": status.get("best_direct_result_present"),
        "active_binding_label": summary.get("active_binding_label"),
        "active_camera_correction_label": summary.get("active_camera_correction_label"),
        "active_extrinsic_correction_label": summary.get("active_extrinsic_correction_label"),
        "best_direct_grasp_gap_norm_m": best_direct_gap_norm_m,
        "best_direct_grasp_orientation_gap_deg": best_direct_gap_deg,
    }


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if row["alignment_fit_for_decision"] else 1,
        0 if row["best_direct_reference_state_reliable"] else 1,
        0 if row["current_joints_present"] else 1,
        0 if row["analysis_present"] else 1,
        row["mtime"],
    )


def _print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No AnyGrasp pipeline runs found.")
        return
    print(
        "alignment_fit  reliable  joints  analysis  mtime                gap_m   gap_deg  pipeline_dir"
    )
    for row in rows:
        gap_m = row["best_direct_grasp_gap_norm_m"]
        gap_deg = row["best_direct_grasp_orientation_gap_deg"]
        print(
            f"{str(row['alignment_fit_for_decision']).lower():<14}"
            f"{str(row['best_direct_reference_state_reliable']).lower():<10}"
            f"{str(row['current_joints_present']).lower():<8}"
            f"{str(row['analysis_present']).lower():<10}"
            f"{row['mtime']:<21}"
            f"{('-' if gap_m is None else f'{float(gap_m):.3f}'):<8}"
            f"{('-' if gap_deg is None else f'{float(gap_deg):.1f}'):<9}"
            f"{row['pipeline_dir']}"
        )


def main() -> int:
    args = build_parser().parse_args()
    runtime_dir = Path(args.runtime_dir).resolve()
    if not runtime_dir.is_dir():
        raise SystemExit(f"runtime_dir not found: {runtime_dir}")

    rows = []
    for pipeline_dir in _candidate_dirs(runtime_dir):
        row = _collect_row(pipeline_dir)
        if row is None:
            continue
        if not args.include_fixtures and row["is_fixture_dir"]:
            continue
        if args.require_analysis and not row["analysis_present"]:
            continue
        if args.require_current_joints and not row["current_joints_present"]:
            continue
        if args.require_reliable and not row["best_direct_reference_state_reliable"]:
            continue
        rows.append(row)
    rows.sort(
        key=lambda row: (
            not row["alignment_fit_for_decision"],
            not row["best_direct_reference_state_reliable"],
            not row["current_joints_present"],
            not row["analysis_present"],
            -datetime.fromisoformat(row["mtime"]).timestamp(),
        )
    )
    rows = rows[: max(1, int(args.limit))]

    if args.json:
        print(json.dumps({"runs": rows}, ensure_ascii=True, indent=2))
    else:
        _print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
