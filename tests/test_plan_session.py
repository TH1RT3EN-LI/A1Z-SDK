from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest


def _app():
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication([])


def _profile(name: str = "sim"):
    from a1z_console.profiles import RuntimeProfile

    return RuntimeProfile(
        name=name,
        label="仿真" if name == "sim" else "真机",
        expected_backend="isaacsim" if name == "sim" else "socketcan",
        host="127.0.0.1",
        port=37201 if name == "sim" else 37202,
        socket_path="",
        environment={"A1Z_EXEC_ARM_SPEED": "0.4"},
    )


def _write_pipeline(
    output_dir: Path,
    *,
    profile: str = "sim",
    safety_ok: bool = True,
    plan_path: Path | None = None,
) -> Path:
    planning = output_dir / "planning"
    anygrasp = output_dir / "anygrasp" / "anygrasp"
    planning.mkdir(parents=True, exist_ok=True)
    anygrasp.mkdir(parents=True, exist_ok=True)
    selected_plan = plan_path or planning / "selected_plan.json"
    selected_plan.parent.mkdir(parents=True, exist_ok=True)
    selected_plan.write_text(
        json.dumps(
            {
                "plan_id": "plan-1",
                "selected_grasp_candidate_id": "grasp-1",
                "candidate_rank": 0,
                "frame_id": "base_link",
                "joint_trajectory_segments": [
                    {
                        "segment_type": "move_to_pregrasp",
                        "target_joint_rad": [0.0, 0.1, -0.2, 0.3, -0.4, 0.5],
                        "timeout_s": 3.0,
                    },
                    {
                        "segment_type": "approach",
                        "target_joint_rad": [0.0, 0.1, -0.2, 0.3, -0.4, 0.5],
                        "timeout_s": 3.0,
                    },
                    {
                        "segment_type": "lift",
                        "target_joint_rad": [0.0, 0.1, -0.2, 0.3, -0.4, 0.5],
                        "timeout_s": 3.0,
                    },
                    {
                        "segment_type": "retreat",
                        "target_joint_rad": [0.0, 0.1, -0.2, 0.3, -0.4, 0.5],
                        "timeout_s": 3.0,
                    },
                ],
                "safety_summary": {
                    "topdown_ok": safety_ok,
                    "table_clearance_ok": safety_ok,
                    "camera_keepout_ok": safety_ok,
                    "joint_margin_ok": safety_ok,
                    "continuity_ok": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (anygrasp / "anygrasp_result.json").write_text(
        json.dumps(
            {
                "top_grasps": [
                    {
                        "rank": 0,
                        "score": 0.9,
                        "width_m": 0.04,
                        "translation_xyz_m": [0.1, -0.2, 0.3],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    preview_png = planning / "selected_grasp_point_cloud.png"
    preview_png.write_bytes(b"preview")
    preview_metadata = planning / "selected_grasp_preview.json"
    preview_metadata.write_text(
        json.dumps(
            {
                "candidate_id": "grasp-1",
                "candidate_rank": 0,
                "score": 0.9,
                "gripper_pose_6dof": {
                    "position_xyz_m": [0.4, -0.05, 0.2],
                    "rpy_deg": [10.0, 20.0, 30.0],
                    "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                    "transform_matrix": [],
                },
                "gripper": {"opening_m": 0.04},
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "pipeline_manifest.json").write_text(
        json.dumps(
            {
                "profile": profile,
                "instruction": "抓取杯子",
                "artifacts": {
                    "plan": str(selected_plan),
                    "anygrasp": str(anygrasp / "anygrasp_result.json"),
                    "grasp_preview": str(preview_png),
                    "grasp_preview_metadata": str(preview_metadata),
                },
            }
        ),
        encoding="utf-8",
    )
    return selected_plan


def test_controller_facade_does_not_own_plan_session_state() -> None:
    root = Path(__file__).resolve().parents[1]
    controller = (root / "console" / "a1z_console" / "controller.py").read_text()
    session = (root / "console" / "a1z_console" / "plan_session.py").read_text()

    assert "summarize_pipeline" not in controller
    assert "_plan_summary" not in controller
    assert "_pipeline_output_dir" not in controller
    assert "class PlanSessionCoordinator" in session
    assert "ProcessTaskContract" in session


def test_plan_computation_validates_inputs_and_uses_unique_output_dirs(
    tmp_path: Path,
) -> None:
    _app()
    from a1z_console.plan_session import PlanSessionCoordinator, PlanSessionError

    fixed_now = lambda: datetime(2026, 7, 31, 12, 0, 0)
    session = PlanSessionCoordinator(tmp_path, _profile(), now=fixed_now)

    with pytest.raises(PlanSessionError, match="目标物体"):
        session.prepare_computation("  ", "adapter", "auto")
    with pytest.raises(PlanSessionError, match="规划器"):
        session.prepare_computation("杯子", "unknown", "auto")
    with pytest.raises(PlanSessionError, match="视觉计算位置"):
        session.prepare_computation("杯子", "adapter", "silent_fallback")

    first = session.prepare_computation("  杯子  ", "adapter", "auto")
    second = session.prepare_computation("杯子", "best", "remote_ssh")
    assert first.output_dir != second.output_dir
    assert first.task.kind == "anygrasp_compute"
    assert first.task.contract.cancelable is True
    assert first.task.arguments[1] == "杯子"
    assert "--vision-backend" not in first.task.arguments
    assert second.task.arguments[-2:] == ("--vision-backend", "remote_ssh")


def test_plan_completion_owns_profile_state_and_returns_defensive_copies(
    tmp_path: Path,
) -> None:
    _app()
    from a1z_console.plan_session import PlanSessionCoordinator

    session = PlanSessionCoordinator(tmp_path, _profile())
    request = session.prepare_computation("杯子", "adapter", "auto")
    session.activate_computation(request)
    assert session.state == "computing"
    _write_pipeline(request.output_dir)

    result = session.complete_computation(request, 0)
    assert result.accepted is True
    assert result.success is True
    assert session.state == "ready"
    assert session.current is True
    assert session.safety_passed is True
    assert session.plan_id == "plan-1"
    assert "Base [400.0, -50.0, 200.0]" in session.grasp_summary
    assert session.grasp_preview_available is True
    assert session.grasp_preview_source.startswith("file://")
    assert session.grasp_base_position_text == (
        "抓取位置（Base） · X +400.0 mm · Y -50.0 mm · Z +200.0 mm"
    )

    segments = session.segments
    segments[0]["type"] = "mutated"
    assert session.segments[0]["type"] == "move_to_pregrasp"


def test_profile_switch_rejects_a_late_plan_result(tmp_path: Path) -> None:
    _app()
    from a1z_console.plan_session import PlanSessionCoordinator

    session = PlanSessionCoordinator(tmp_path, _profile())
    request = session.prepare_computation("杯子", "adapter", "auto")
    session.activate_computation(request)
    _write_pipeline(request.output_dir)

    session.select_profile(_profile("real"))
    result = session.complete_computation(request, 0)
    assert result.accepted is False
    assert session.state == "empty"
    assert session.current is False


def test_plan_current_is_cached_but_execution_revalidates_the_artifact(
    tmp_path: Path,
) -> None:
    _app()
    from a1z_console.plan_session import PlanSessionCoordinator, PlanSessionError

    session = PlanSessionCoordinator(tmp_path, _profile())
    request = session.prepare_computation("杯子", "adapter", "auto")
    session.activate_computation(request)
    _write_pipeline(request.output_dir)
    session.complete_computation(request, 0)
    plan_path = Path(session.latest_plan_path)

    assert session.current is True
    plan_path.unlink()
    assert session.current is True
    with pytest.raises(PlanSessionError, match="已不存在"):
        session.prepare_execution(dry_run=True, confirmation="")
    assert session.current is False
    assert session.state == "invalid"


def test_plan_execution_rejects_content_changed_after_review(
    tmp_path: Path,
) -> None:
    _app()
    from a1z_console.plan_session import PlanSessionCoordinator, PlanSessionError

    session = PlanSessionCoordinator(tmp_path, _profile())
    request = session.prepare_computation("杯子", "adapter", "auto")
    session.activate_computation(request)
    plan_path = _write_pipeline(request.output_dir)
    session.complete_computation(request, 0)

    changed = json.loads(plan_path.read_text(encoding="utf-8"))
    changed["joint_trajectory_segments"][0]["target_joint_rad"] = [1.0] * 6
    changed["safety_summary"]["joint_margin_ok"] = False
    plan_path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(PlanSessionError, match="内容已改变"):
        session.prepare_execution(
            dry_run=False,
            confirmation="执行 SIM",
        )
    assert session.current is False
    assert session.state == "invalid"


def test_unsafe_plan_can_be_dry_run_but_not_physically_executed(
    tmp_path: Path,
) -> None:
    _app()
    from a1z_console.interaction_policy import ProcessAccess
    from a1z_console.plan_session import PlanSessionCoordinator, PlanSessionError

    session = PlanSessionCoordinator(tmp_path, _profile())
    request = session.prepare_computation("杯子", "adapter", "auto")
    session.activate_computation(request)
    _write_pipeline(request.output_dir, safety_ok=False)
    session.complete_computation(request, 0)

    assert session.state == "unsafe"
    assert session.current is True
    dry_run = session.prepare_execution(dry_run=True, confirmation="")
    assert dry_run.kind == "plan_dry_run"
    assert dry_run.contract.access is ProcessAccess.TASK_SLOT
    assert dry_run.contract.cancelable is True
    assert "--dry-run" in dry_run.arguments

    with pytest.raises(PlanSessionError, match="实际执行被阻止"):
        session.prepare_execution(
            dry_run=False,
            confirmation="执行 SIM",
        )


def test_incomplete_physical_sequence_never_becomes_execution_ready(
    tmp_path: Path,
) -> None:
    _app()
    from a1z_console.plan_session import PlanSessionCoordinator, PlanSessionError

    session = PlanSessionCoordinator(tmp_path, _profile())
    request = session.prepare_computation("杯子", "adapter", "auto")
    session.activate_computation(request)
    plan_path = _write_pipeline(request.output_dir)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["joint_trajectory_segments"] = [
        plan["joint_trajectory_segments"][1]
    ]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = session.complete_computation(request, 0)

    assert result.success is True
    assert session.state == "unsafe"
    assert session.safety_passed is False
    with pytest.raises(PlanSessionError, match="安全检查未全部通过"):
        session.prepare_execution(
            dry_run=False,
            confirmation="执行 SIM",
        )


def test_real_execution_requires_confirmation_and_online_contract(
    tmp_path: Path,
) -> None:
    _app()
    from a1z_console.interaction_policy import (
        OnlineCapability,
        ProcessAccess,
        ResourceEffect,
    )
    from a1z_console.plan_session import PlanSessionCoordinator, PlanSessionError

    session = PlanSessionCoordinator(tmp_path, _profile("real"))
    request = session.prepare_computation("杯子", "best", "local")
    session.activate_computation(request)
    _write_pipeline(request.output_dir, profile="real")
    session.complete_computation(request, 0)

    with pytest.raises(PlanSessionError, match="确认文本"):
        session.prepare_execution(dry_run=False, confirmation="")
    task = session.prepare_execution(
        dry_run=False,
        confirmation="执行 REAL",
    )
    assert task.kind == "plan_execute"
    assert task.contract.access is ProcessAccess.ONLINE_DEVICE
    assert task.contract.online_capability is OnlineCapability.ARM_GRIPPER_MOTION
    assert task.contract.effects == ResourceEffect.ARM | ResourceEffect.GRIPPER
    assert task.contract.uncertain_on_failure is True
    assert task.contract.blocks_telemetry is True
    assert task.contract.cancelable is True
    digest_index = task.arguments.index("--expected-plan-sha256")
    assert len(task.arguments[digest_index + 1]) == 64


def test_plan_artifact_outside_its_session_is_rejected(tmp_path: Path) -> None:
    _app()
    from a1z_console.plan_session import PlanSessionCoordinator

    session = PlanSessionCoordinator(tmp_path, _profile())
    request = session.prepare_computation("杯子", "adapter", "auto")
    session.activate_computation(request)
    external_plan = tmp_path / "unrelated" / "selected_plan.json"
    _write_pipeline(request.output_dir, plan_path=external_plan)

    result = session.complete_computation(request, 0)
    assert result.success is False
    assert "不在本次计算输出目录" in result.error
    assert session.state == "invalid"
    assert session.current is False
