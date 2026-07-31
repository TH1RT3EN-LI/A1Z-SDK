"""Extract an operator-friendly view from AnyGrasp planning artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from a1z_ext.grasping.types import (
    REQUIRED_PLAN_SAFETY_CHECKS,
    normalize_plan_segments,
    validate_physical_segment_sequence,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} 顶层必须是 JSON object")
    return payload


def _workspace_to_host(repo_root: Path, raw: str) -> Path:
    workspace_prefix = "/workspace/A1Z/"
    if raw.startswith(workspace_prefix):
        return repo_root / raw[len(workspace_prefix) :]
    return Path(raw)


def summarize_pipeline(output_dir: Path, repo_root: Path) -> dict[str, Any]:
    manifest_path = output_dir / "pipeline_manifest.json"
    manifest = _load_json(manifest_path)
    artifacts = dict(manifest.get("artifacts", {}) or {})
    plan_path = _workspace_to_host(
        repo_root,
        str(artifacts.get("plan", output_dir / "planning" / "selected_plan.json")),
    )
    if not plan_path.is_file():
        plan_path = output_dir / "planning" / "selected_plan.json"
    plan = _load_json(plan_path)

    raw_segments = normalize_plan_segments(plan)
    try:
        validate_physical_segment_sequence(raw_segments)
    except ValueError:
        physical_sequence_passed = False
    else:
        physical_sequence_passed = True
    segments: list[dict[str, Any]] = []
    for index, segment in enumerate(raw_segments):
        target_rad = segment["target_joint_rad"]
        segments.append(
            {
                "index": index + 1,
                "type": str(segment["segment_type"]),
                "jointsDeg": [round(math.degrees(float(value)), 2) for value in target_rad],
                "timeoutS": float(segment["timeout_s"]),
            }
        )

    anygrasp_path = _workspace_to_host(
        repo_root,
        str(
            artifacts.get(
                "anygrasp",
                output_dir / "anygrasp" / "anygrasp" / "anygrasp_result.json",
            )
        ),
    )
    grasp: dict[str, Any] = {}
    if anygrasp_path.is_file():
        result = _load_json(anygrasp_path)
        top_grasps = result.get("top_grasps", [])
        selected_rank = int(plan.get("candidate_rank", 0) or 0)
        if isinstance(top_grasps, list) and top_grasps:
            candidate = next(
                (
                    item
                    for item in top_grasps
                    if isinstance(item, dict)
                    and int(item.get("rank", -1)) == selected_rank
                ),
                top_grasps[0] if isinstance(top_grasps[0], dict) else {},
            )
            grasp = {
                "rank": int(candidate.get("rank", selected_rank)),
                "score": float(candidate.get("score", 0.0)),
                "widthMm": round(float(candidate.get("width_m", 0.0)) * 1000.0, 2),
                "translationMm": [
                    round(float(value) * 1000.0, 2)
                    for value in candidate.get("translation_xyz_m", [])[:3]
                ],
                "rotationMatrix": candidate.get("rotation_matrix", []),
            }

    raw_safety = plan.get("safety_summary", {})
    safety = dict(raw_safety) if isinstance(raw_safety, dict) else {}
    safety_names = [
        *REQUIRED_PLAN_SAFETY_CHECKS,
        *sorted(set(safety).difference(REQUIRED_PLAN_SAFETY_CHECKS)),
    ]
    return {
        "profile": str(manifest.get("profile", "")),
        "instruction": str(manifest.get("instruction", "")),
        "planPath": str(plan_path.resolve()),
        "manifestPath": str(manifest_path.resolve()),
        "planId": str(plan.get("plan_id", "")),
        "candidateId": str(plan.get("selected_grasp_candidate_id", "")),
        "frameId": str(plan.get("frame_id", "")),
        "segments": segments,
        "grasp": grasp,
        "safety": [
            {"name": str(name), "ok": safety.get(name) is True}
            for name in safety_names
        ] + [
            {
                "name": "physical_sequence_ok",
                "ok": physical_sequence_passed,
            }
        ],
        "allSafetyPassed": all(
            safety.get(name) is True
            for name in REQUIRED_PLAN_SAFETY_CHECKS
        ) and all(
            value is True for value in safety.values()
        ) and physical_sequence_passed,
    }
