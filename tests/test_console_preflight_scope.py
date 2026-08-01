from __future__ import annotations

from pathlib import Path

from scripts import a1z_console_preflight as preflight


def test_remote_vision_preflight_never_probes_local_container(
    monkeypatch,
) -> None:
    def unexpected_local_probe(_name: str):
        raise AssertionError("remote vision must not inspect local Docker")

    monkeypatch.setattr(preflight, "docker_running", unexpected_local_probe)
    checks = preflight.vision_checks(
        "real",
        {
            "A1Z_REAL_VISION_BACKEND": "remote_ssh",
            "A1Z_VISION_CONTAINER_NAME": "a1z-vision-gpu",
        },
    )

    assert checks == [
        {
            "name": "视觉计算后端",
            "ok": True,
            "detail": "remote_ssh · 远程容器与资产在视觉任务启动时检查",
            "severity": "advisory",
        }
    ]


def test_local_vision_failures_are_advisory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        preflight,
        "docker_running",
        lambda name: (False, f"{name}: missing"),
    )
    checks = preflight.vision_checks(
        "real",
        {
            "A1Z_REAL_VISION_BACKEND": "local",
            "A1Z_VISION_CONTAINER_NAME": "a1z-vision-gpu",
            "A1Z_ANYGRASP_DETECTION_CKPT": str(tmp_path / "detection.tar"),
            "A1Z_ANYGRASP_LICENSE_DIR": str(tmp_path / "license"),
            "A1Z_ANYGRASP_IFCONFIG_SNAPSHOT": str(tmp_path / "ifconfig.snapshot"),
        },
    )

    assert [item["name"] for item in checks] == [
        "本机视觉容器",
        "本机 AnyGrasp 资产/许可",
    ]
    assert all(item["ok"] is False for item in checks)
    assert all(item["severity"] == "advisory" for item in checks)
    assert not [item for item in checks if item["severity"] == "required"]


def test_hand_eye_status_does_not_gate_startup_or_execution() -> None:
    root = Path(__file__).resolve().parents[1]
    preflight_source = (root / "scripts" / "a1z_console_preflight.py").read_text()
    plan_source = (
        root / "console" / "a1z_console" / "plan_session.py"
    ).read_text()
    pipeline_source = (root / "scripts" / "run_pick_pipeline.py").read_text()

    assert '"手眼标定"' not in preflight_source
    assert "A1Z_HAND_EYE_CALIBRATION_STATUS" not in preflight_source
    assert "A1Z_HAND_EYE_CALIBRATION_STATUS" not in plan_source
    assert "A1Z_HAND_EYE_CALIBRATION_STATUS" not in pipeline_source
    assert "allow-unverified-calibration" not in pipeline_source
