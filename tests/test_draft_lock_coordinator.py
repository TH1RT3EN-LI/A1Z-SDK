from __future__ import annotations

from pathlib import Path

import pytest


def test_draft_locks_match_operation_effects_by_resource() -> None:
    from a1z_console.draft_lock_coordinator import (
        DraftLockCoordinator,
        DraftResource,
    )
    from a1z_console.interaction_policy import ResourceEffect

    locks = DraftLockCoordinator()
    assert locks.update(
        arm_target=True,
        gripper_target=False,
        configuration=False,
    )
    assert locks.summary == "机械臂目标"
    assert locks.conflict_for_effects(ResourceEffect.ARM) == DraftResource.ARM_TARGET
    assert locks.conflict_for_effects(ResourceEffect.GRIPPER) == DraftResource.NONE
    assert (
        locks.conflict_for_effects(
            ResourceEffect.ARM,
            allowed=DraftResource.ARM_TARGET,
        )
        == DraftResource.NONE
    )


def test_service_and_transport_changes_block_every_draft_family() -> None:
    from a1z_console.draft_lock_coordinator import (
        DraftLockCoordinator,
        DraftResource,
    )
    from a1z_console.interaction_policy import ResourceEffect

    locks = DraftLockCoordinator()
    locks.update(
        arm_target=True,
        gripper_target=True,
        configuration=True,
    )
    assert locks.pending == DraftResource.ALL
    assert locks.conflict_for_effects(ResourceEffect.SERVICE) == DraftResource.ALL
    assert locks.conflict_for_effects(ResourceEffect.TRANSPORT) == DraftResource.ALL
    assert "机械臂目标、夹爪开度、重力补偿系数" in locks.error_for_all()
    assert (
        locks.conflict_for_effects(
            ResourceEffect.SERVICE,
            allowed=DraftResource.CONFIGURATION,
        )
        == DraftResource.ARM_TARGET | DraftResource.GRIPPER_TARGET
    )


def test_controller_rejects_draft_bypass_for_profile_and_resource_actions() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication

    from a1z_console.controller import ConsoleController
    from a1z_console.interaction_policy import (
        ProcessAccess,
        ProcessTaskContract,
        ResourceEffect,
    )

    root = Path(__file__).resolve().parents[1]
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    controller = ConsoleController(root)
    operation_called = False
    state_events: list[None] = []
    draft_events: list[None] = []
    controller.stateChanged.connect(lambda: state_events.append(None))
    controller.draftLocksChanged.connect(lambda: draft_events.append(None))

    def operation() -> dict[str, object]:
        nonlocal operation_called
        operation_called = True
        return {"data": {}}

    try:
        controller.setDraftLocks(True, False, False)
        assert state_events == []
        assert draft_events == [None]
        assert controller.pendingDrafts is True
        assert controller.pendingDraftSummary == "机械臂目标"

        controller.setProfile("real")
        assert controller.profile == "sim"
        assert "机械臂目标" in controller.lastError

        controller._submit_operation(
            "不可绕过的机械臂操作",
            operation,
            effects=ResourceEffect.ARM,
        )
        assert operation_called is False
        assert controller.commandBusy is False
        assert "当前操作会使草稿失效" in controller.lastError

        controller.setDraftLocks(False, False, True)
        started = controller._start_process_task(
            "service_change",
            "不可绕过的服务操作",
            "/bin/true",
            [],
            contract=ProcessTaskContract(
                ProcessAccess.TASK_SLOT,
                ResourceEffect.SERVICE,
            ),
        )
        assert started is False
        assert controller.taskBusy is False
        assert "重力补偿系数" in controller.lastError
    finally:
        controller.shutdown()


def test_workspace_synchronizes_persistent_page_drafts_to_controller() -> None:
    root = Path(__file__).resolve().parents[1]
    workspace = (
        root / "console" / "qml" / "A1ZConsole" / "ConsoleWorkspace.qml"
    ).read_text()
    controller = (
        root / "console" / "a1z_console" / "controller.py"
    ).read_text()

    assert "function synchronizeDraftLocks()" in workspace
    assert "root.controller.setDraftLocks(" in workspace
    assert "onArmDraftPendingChanged" in workspace
    assert "onGripperDraftPendingChanged" in workspace
    assert "onConfigurationDraftPendingChanged" in workspace
    assert "def setDraftLocks(" in controller
    assert "error_for_effects" in controller
