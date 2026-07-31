from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _executor_module():
    pytest.importorskip("numpy")
    script = ROOT / "scripts" / "execute_a1z_plan.py"
    spec = importlib.util.spec_from_file_location("execute_a1z_plan", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_physical_execution_requires_all_safety_checks() -> None:
    executor = _executor_module()

    executor._validate_execution_safety(
        {
            "safety_summary": {
                "topdown_ok": True,
                "table_clearance_ok": True,
                "camera_keepout_ok": True,
                "joint_margin_ok": True,
                "continuity_ok": True,
            }
        }
    )
    with pytest.raises(ValueError, match="joint_margin_ok"):
        executor._validate_execution_safety(
            {
                "safety_summary": {
                    "topdown_ok": True,
                    "table_clearance_ok": True,
                    "camera_keepout_ok": True,
                    "joint_margin_ok": False,
                    "continuity_ok": True,
                }
            }
        )
    with pytest.raises(ValueError, match="non-empty safety_summary"):
        executor._validate_execution_safety({})

    for missing in (
        "topdown_ok",
        "table_clearance_ok",
        "camera_keepout_ok",
        "joint_margin_ok",
        "continuity_ok",
    ):
        summary = {
            "topdown_ok": True,
            "table_clearance_ok": True,
            "camera_keepout_ok": True,
            "joint_margin_ok": True,
            "continuity_ok": True,
        }
        del summary[missing]
        with pytest.raises(ValueError, match=missing):
            executor._validate_execution_safety(
                {"safety_summary": summary}
            )


def test_executor_rechecks_reviewed_plan_digest(tmp_path: Path) -> None:
    executor = _executor_module()
    plan_path = tmp_path / "selected_plan.json"
    reviewed = {"joint_trajectory_segments": []}
    plan_bytes = json.dumps(reviewed).encode("utf-8")
    plan_path.write_bytes(plan_bytes)
    digest = hashlib.sha256(plan_bytes).hexdigest()

    assert executor._load_reviewed_plan(plan_path, digest) == reviewed
    plan_path.write_text('{"changed": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed SHA-256"):
        executor._load_reviewed_plan(plan_path, digest)


@pytest.mark.parametrize(
    ("segments", "message"),
    (
        (
            [
                {
                    "segment_type": "approach",
                    "target_joint_rad": [float("nan")] * 6,
                    "timeout_s": 1.0,
                }
            ],
            "finite",
        ),
        (
            [
                {
                    "segment_type": "approach",
                    "target_joint_rad": [0.0] * 6,
                    "timeout_s": 0.0,
                }
            ],
            "timeout_s",
        ),
        (
            [
                {
                    "segment_type": "retreat",
                    "target_joint_rad": [0.0] * 6,
                    "timeout_s": 1.0,
                },
                {
                    "segment_type": "approach",
                    "target_joint_rad": [0.0] * 6,
                    "timeout_s": 1.0,
                },
            ],
            "order",
        ),
    ),
)
def test_executor_rejects_invalid_numeric_and_segment_contracts(
    segments: list[dict[str, object]],
    message: str,
) -> None:
    executor = _executor_module()
    with pytest.raises(ValueError, match=message):
        executor._validate_plan({"joint_trajectory_segments": segments})


def test_physical_execution_requires_complete_stage_sequence() -> None:
    executor = _executor_module()
    with pytest.raises(ValueError, match="move_to_pregrasp"):
        executor.validate_physical_segment_sequence(
            [
                {
                    "segment_type": "approach",
                    "target_joint_rad": [0.0] * 6,
                    "timeout_s": 1.0,
                }
            ]
        )


def test_physical_execution_rechecks_backend_joint_limits() -> None:
    executor = _executor_module()
    segments = [
        {
            "segment_type": "approach",
            "target_joint_rad": [0.0] * 6,
            "timeout_s": 1.0,
        }
    ]
    info = {
        "joint_limits_deg": {
            f"J{index}": [-90.0, 90.0]
            for index in range(1, 7)
        }
    }
    executor._validate_backend_joint_limits(segments, info)

    segments[0]["target_joint_rad"][2] = 2.0
    with pytest.raises(ValueError, match="J3 target"):
        executor._validate_backend_joint_limits(segments, info)
