"""Cross-page operator draft locks expressed by affected resource."""

from __future__ import annotations

from enum import IntFlag, auto

from .interaction_policy import ResourceEffect


class DraftResource(IntFlag):
    NONE = 0
    ARM_TARGET = auto()
    GRIPPER_TARGET = auto()
    CONFIGURATION = auto()

    ALL = ARM_TARGET | GRIPPER_TARGET | CONFIGURATION


class DraftLockCoordinator:
    """Own the aggregate draft state reported by persistent QML editors."""

    def __init__(self) -> None:
        self._pending = DraftResource.NONE

    @property
    def pending(self) -> DraftResource:
        return self._pending

    @property
    def any_pending(self) -> bool:
        return self._pending != DraftResource.NONE

    @property
    def summary(self) -> str:
        labels = []
        if self._pending & DraftResource.ARM_TARGET:
            labels.append("机械臂目标")
        if self._pending & DraftResource.GRIPPER_TARGET:
            labels.append("夹爪开度")
        if self._pending & DraftResource.CONFIGURATION:
            labels.append("重力补偿系数")
        return "、".join(labels)

    @property
    def fingerprint(self) -> int:
        return int(self._pending)

    def update(
        self,
        *,
        arm_target: bool,
        gripper_target: bool,
        configuration: bool,
    ) -> bool:
        pending = DraftResource.NONE
        if arm_target:
            pending |= DraftResource.ARM_TARGET
        if gripper_target:
            pending |= DraftResource.GRIPPER_TARGET
        if configuration:
            pending |= DraftResource.CONFIGURATION
        if pending == self._pending:
            return False
        self._pending = pending
        return True

    def conflict_for_effects(
        self,
        effects: ResourceEffect,
        *,
        allowed: DraftResource = DraftResource.NONE,
    ) -> DraftResource:
        barrier = DraftResource.NONE
        if effects & ResourceEffect.ARM:
            barrier |= DraftResource.ARM_TARGET
        if effects & ResourceEffect.GRIPPER:
            barrier |= DraftResource.GRIPPER_TARGET
        if effects & (ResourceEffect.SERVICE | ResourceEffect.TRANSPORT):
            barrier |= DraftResource.ALL
        return self._pending & barrier & ~allowed

    def conflict_for_all(
        self,
        *,
        allowed: DraftResource = DraftResource.NONE,
    ) -> DraftResource:
        return self._pending & ~allowed

    def error_for_effects(
        self,
        effects: ResourceEffect,
        *,
        allowed: DraftResource = DraftResource.NONE,
    ) -> str:
        return self._error(self.conflict_for_effects(effects, allowed=allowed))

    def error_for_all(
        self,
        *,
        allowed: DraftResource = DraftResource.NONE,
    ) -> str:
        return self._error(self.conflict_for_all(allowed=allowed))

    @staticmethod
    def _error(conflict: DraftResource) -> str:
        if conflict == DraftResource.NONE:
            return ""
        labels = []
        if conflict & DraftResource.ARM_TARGET:
            labels.append("机械臂目标")
        if conflict & DraftResource.GRIPPER_TARGET:
            labels.append("夹爪开度")
        if conflict & DraftResource.CONFIGURATION:
            labels.append("重力补偿系数")
        return (
            f"存在未发送的{'、'.join(labels)}，当前操作会使草稿失效；"
            "请先发送或放弃"
        )
