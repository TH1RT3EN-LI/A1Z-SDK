from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v2_telemetry_bridge_uses_public_sdk_in_both_deployments() -> None:
    main = (ROOT / "console_v2/frontend/electron/main.mjs").read_text()
    telemetry = (ROOT / "a1z_sdk/telemetry.py").read_text()

    assert '"-m", "a1z_sdk.telemetry"' in main
    assert '"/usr/bin/python3",' in main
    assert '"a1z_sdk.telemetry",' in main
    assert "client.status()" in telemetry
    assert "tools/a1zctl" not in main


def test_v2_joint_readback_and_model_labels_share_one_measurement() -> None:
    app = (ROOT / "console_v2/frontend/src/App.tsx").read_text()
    viewport = (
        ROOT / "console_v2/frontend/src/components/RobotViewport.tsx"
    ).read_text()

    assert "telemetry={robotTelemetry}" in app
    assert "jointPositionsDeg={robotTelemetry.jointsDeg}" in app
    assert "showJointLabels={showJointLabels}" in app
    assert "applyMeasuredWorkspacePose" in viewport
    assert "Array.from({ length: 6 }" in viewport
    assert "arm_joint${index + 1}" in viewport
    assert 'className="joint-leader-path"' in viewport
    assert 'side: "left" | "right"' in viewport
    assert 'jointLeaderSvgRef.current?.setAttribute("viewBox"' in viewport


def test_v2_control_mode_is_allowlisted_and_feedback_confirmed() -> None:
    main = (ROOT / "console_v2/frontend/electron/main.mjs").read_text()
    preload = (ROOT / "console_v2/frontend/electron/preload.cjs").read_text()
    telemetry = (ROOT / "console_v2/frontend/src/robot-telemetry.ts").read_text()
    control = (
        ROOT / "console_v2/frontend/src/components/ArmModeControl.tsx"
    ).read_text()

    assert 'mode !== "hold" && mode !== "zero-force"' in main
    assert 'robotCliCommand(deploymentMode, ["mode", mode], 2.5)' in main
    assert 'ipcRenderer.invoke("robot:set-control-mode"' in preload
    assert 'controlMode: ArmControlMode | null' in telemetry
    assert 'telemetry.controlMode === pendingMode' in control
    assert '扶稳机械臂' in control
    assert 'setConfirmationTarget(target)' in control
    assert '切换到位置保持' in control
    assert 'gravityCompFactor <= 0' in control
    assert 'type="range"' not in control


def test_v2_development_preview_requires_parameter_and_never_sends_robot_command() -> None:
    app = (ROOT / "console_v2/frontend/src/App.tsx").read_text()
    telemetry = (ROOT / "console_v2/frontend/src/robot-telemetry.ts").read_text()
    control = (
        ROOT / "console_v2/frontend/src/components/ArmModeControl.tsx"
    ).read_text()
    main = (ROOT / "console_v2/frontend/electron/main.mjs").read_text()
    preload = (ROOT / "console_v2/frontend/electron/preload.cjs").read_text()
    desktop_runner = (
        ROOT / "console_v2/frontend/scripts/run-desktop.mjs"
    ).read_text()
    vite_runner = (ROOT / "console_v2/frontend/scripts/run-vite.mjs").read_text()

    assert 'import.meta.env.VITE_A1Z_DEVELOPMENT_MODE === "1"' in app
    assert "developmentMode={developmentMode}" in app
    assert "allowSkip={developmentMode}" in app
    assert "import.meta.env.DEV" not in app
    assert "return developmentMode" in telemetry
    assert 'process.argv.includes("--development-mode")' in main
    assert "requireRealHardwareMode();" in main
    assert 'process.argv.includes("--a1z-development-mode=1")' in preload
    assert 'argument !== "--development-mode"' in desktop_runner
    assert 'argument !== "--development-mode"' in vite_runner
    assert 'VITE_A1Z_DEVELOPMENT_MODE: developmentMode ? "1" : "0"' in vite_runner
    assert 'className="development-preview-label"' in control
    assert "预览 · 不会控制真机" in control
    preview_branch = control.index("if (developmentPreview) {")
    command_call = control.index("desktopApi.setRobotControlMode")
    assert preview_branch < command_call
    assert "runDevelopmentPreview(target);" in control[preview_branch:command_call]


def test_v2_position_mode_direct_joint_target_is_asynchronously_accepted() -> None:
    main = (ROOT / "console_v2/frontend/electron/main.mjs").read_text()
    preload = (ROOT / "console_v2/frontend/electron/preload.cjs").read_text()
    readback = (
        ROOT / "console_v2/frontend/src/components/JointReadback.tsx"
    ).read_text()
    target = (
        ROOT / "console_v2/frontend/src/components/JointTargetControl.tsx"
    ).read_text()

    assert "<JointTargetControl" in readback
    assert 'controlMode === "position_hold"' in target
    assert "draftAngles.map" in target
    assert "<span>J{index + 1}</span>" not in target
    assert "a1z-console:joint-speed-rad-s" in target
    assert 'className="joint-speed-slider"' in target
    assert 'type="range"' in target
    assert 'step="0.01"' in target
    assert 'aria-label={`转动速度数值' in target
    assert "desktopApi.moveRobotJoints" in target
    preview_branch = target.index("if (developmentPreview) {")
    command_call = target.index("desktopApi.moveRobotJoints")
    assert preview_branch < command_call
    assert '"target"' in main
    assert '"--speed"' in main
    assert 'payload?.completion === "accepted"' in main
    assert 'motion.state === "holding"' in target
    assert 'motion.state === "failed"' in target
    assert "motion.goalId > submittedGoalId" in target
    assert "已切换到新目标" in target
    assert "Number.isInteger(goalId)" in main
    assert 'ipcMain.handle("robot:move-joints"' in main
    assert 'ipcRenderer.invoke("robot:move-joints"' in preload
    assert "robotCommandOwners.has(event.sender.id)" in main
