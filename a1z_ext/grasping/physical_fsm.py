from __future__ import annotations

from collections import deque
from statistics import median

from .physical_types import (
    ContactSnapshot,
    DriveProfile,
    GraspCommand,
    GraspPhase,
    GripperSnapshot,
    PhysicalGraspConfig,
    PhysicalGraspStatus,
)


class PhysicalGraspFSM:
    """Pure physical-grasp state machine with no USD or strategy dependencies."""

    def __init__(self, config: PhysicalGraspConfig) -> None:
        self._config = config
        self._phase = GraspPhase.IDLE
        self._phase_started_s = 0.0
        self._target_body_path: str | None = None
        self._stable_contact_frames = 0
        self._contact_width_m: float | None = None
        self._hold_width_m: float | None = None
        self._failure_reason: str | None = None
        self._command: GraspCommand | None = None
        self._last_bilateral_contact = False
        self._candidate_body_path: str | None = None
        self._force_body_path: str | None = None
        self._left_force_window: deque[float] = deque(
            maxlen=self._config.force_window_frames
        )
        self._right_force_window: deque[float] = deque(
            maxlen=self._config.force_window_frames
        )
        self._force_stable_frames = 0
        self._contact_loss_frames = 0
        self._force_loss_frames = 0
        self._overforce_frames = 0
        self._unilateral_recovery_started_s: float | None = None
        self._unilateral_contact_side: str | None = None
        self._effective_grip_force_n: float | None = None
        self._grip_force_source: str | None = None

    @property
    def phase(self) -> GraspPhase:
        return self._phase

    def begin(
        self,
        *,
        target_body_path: str = "",
        now_s: float,
        initial_width_m: float | None = None,
    ) -> PhysicalGraspStatus:
        if target_body_path and not target_body_path.startswith("/"):
            raise ValueError("target_body_path must be an absolute prim path")
        if self._phase not in {
            GraspPhase.IDLE,
            GraspPhase.RELEASED,
            GraspPhase.FAILED,
            GraspPhase.ABORTED,
        }:
            raise RuntimeError(f"cannot begin physical grasp while phase is {self._phase.value}")
        self._phase = GraspPhase.PRECHECK
        self._phase_started_s = float(now_s)
        self._target_body_path = target_body_path or None
        self._stable_contact_frames = 0
        self._contact_width_m = None
        self._hold_width_m = None
        self._failure_reason = None
        self._last_bilateral_contact = False
        self._candidate_body_path = None
        self._reset_force_tracking()
        precheck_width = (
            self._config.open_width_m
            if initial_width_m is None
            else min(
                max(float(initial_width_m), self._config.closed_width_m),
                self._config.open_width_m,
            )
        )
        self._command = GraspCommand(
            drive_profile=DriveProfile.HOLD,
            target_width_m=precheck_width,
            reason="precheck_hold",
        )
        return self.status()

    def abort(self, *, reason: str = "aborted") -> PhysicalGraspStatus:
        self._phase = GraspPhase.ABORTED
        self._failure_reason = str(reason)
        self._command = GraspCommand(
            drive_profile=DriveProfile.HOLD,
            target_width_m=self._current_target_width(),
            reason="abort_hold",
        )
        return self.status()

    def release(self, *, now_s: float) -> PhysicalGraspStatus:
        if self._phase not in {GraspPhase.PRELOAD, GraspPhase.HOLDING, GraspPhase.FAILED, GraspPhase.ABORTED}:
            raise RuntimeError(f"cannot release physical grasp while phase is {self._phase.value}")
        self._phase = GraspPhase.RELEASING
        self._phase_started_s = float(now_s)
        self._command = GraspCommand(
            drive_profile=DriveProfile.FREE,
            target_width_m=self._config.open_width_m,
            reason="release_open",
        )
        return self.status()

    def step(
        self,
        *,
        now_s: float,
        arm_stable: bool,
        gripper: GripperSnapshot,
        contacts: ContactSnapshot,
    ) -> PhysicalGraspStatus:
        now = float(now_s)
        if self._phase == GraspPhase.IDLE:
            return self.status()
        if self._phase in {GraspPhase.FAILED, GraspPhase.ABORTED, GraspPhase.RELEASED}:
            return self.status()
        if self._phase == GraspPhase.RELEASING:
            if (
                gripper.motion_stable
                and abs(gripper.width_m - self._config.open_width_m)
                <= self._config.release_width_tolerance_m
            ):
                self._phase = GraspPhase.RELEASED
                self._command = None
            return self.status()

        if contacts.has_blocking_contact:
            reason = contacts.blocking_reason or "blocking_contact"
            return self._fail(reason, hold_width_m=gripper.width_m)

        if self._phase == GraspPhase.PRECHECK:
            if now - self._phase_started_s >= self._config.precheck_timeout_s:
                return self._fail("precheck_timeout", hold_width_m=gripper.width_m)
            if not arm_stable:
                return self.status()
            self._stable_contact_frames = 0
            self._candidate_body_path = None
            self._transition(GraspPhase.SOFT_CLOSE, now)
            self._command = GraspCommand(
                drive_profile=DriveProfile.SOFT_CLOSE,
                target_width_m=self._config.closed_width_m,
                reason="soft_close_search_target",
            )
            return self.status()

        target = self._target_body_path
        candidate = (
            target
            if target and contacts.bilateral_for(target, self._config.minimum_normal_force_n)
            else (
                None
                if target
                else contacts.strongest_bilateral_body(
                    self._config.minimum_normal_force_n
                )
            )
        )
        bilateral = candidate is not None
        self._last_bilateral_contact = bilateral
        if bilateral:
            self._unilateral_recovery_started_s = None
            self._unilateral_contact_side = None
            if candidate == self._candidate_body_path:
                self._stable_contact_frames += 1
            else:
                self._candidate_body_path = candidate
                self._stable_contact_frames = 1
        else:
            self._candidate_body_path = None
            self._stable_contact_frames = 0
        if candidate is not None:
            self._record_contact_force(candidate, contacts)

        if self._phase in {GraspPhase.SOFT_CLOSE, GraspPhase.SEARCH}:
            if bilateral and self._stable_contact_frames >= self._config.minimum_stable_frames:
                if self._target_body_path is None:
                    self._target_body_path = self._candidate_body_path
                self._contact_width_m = float(gripper.width_m)
                self._hold_width_m = max(
                    self._config.closed_width_m,
                    self._contact_width_m - self._config.preload_delta_m,
                )
                self._transition(GraspPhase.PRELOAD, now)
                self._contact_loss_frames = 0
                self._force_loss_frames = 0
                self._overforce_frames = 0
                self._command = GraspCommand(
                    drive_profile=DriveProfile.HOLD,
                    target_width_m=self._hold_width_m,
                    reason="bilateral_contact_preload",
                )
                return self.status()
            if gripper.fully_closed and not bilateral:
                return self._fail(
                    "fully_closed_without_bilateral_contact",
                    hold_width_m=gripper.width_m,
                )
            elapsed = now - self._phase_started_s
            if self._phase == GraspPhase.SOFT_CLOSE and elapsed >= self._config.soft_close_timeout_s:
                self._transition(GraspPhase.SEARCH, now)
                self._command = GraspCommand(
                    drive_profile=DriveProfile.SEARCH,
                    target_width_m=self._config.closed_width_m,
                    reason="soft_close_timeout_search",
                )
            elif self._phase == GraspPhase.SEARCH and elapsed >= self._config.search_timeout_s:
                return self._fail(
                    "search_timeout_without_bilateral_contact",
                    hold_width_m=gripper.width_m,
                )
            return self.status()

        if self._phase == GraspPhase.PRELOAD:
            if not bilateral:
                unilateral_status = self._recover_unilateral_contact(
                    now=now,
                    contacts=contacts,
                    phase_name="preload",
                )
                if unilateral_status is not None:
                    return unilateral_status
                self._contact_loss_frames += 1
                if self._contact_loss_frames > self._config.contact_loss_grace_frames:
                    return self._fail(
                        "contact_lost_during_preload",
                        hold_width_m=gripper.width_m,
                    )
                self._command = GraspCommand(
                    drive_profile=DriveProfile.HOLD,
                    target_width_m=self._required_hold_width(),
                    reason="temporary_contact_loss_hold",
                )
                return self.status()
            self._contact_loss_frames = 0
            if self._force_control_active():
                return self._step_force_preload(now=now, gripper=gripper)
            if gripper.motion_stable and now - self._phase_started_s >= self._config.hold_confirm_timeout_s:
                self._transition(GraspPhase.HOLDING, now)
                self._command = GraspCommand(
                    drive_profile=DriveProfile.HOLD,
                    target_width_m=self._required_hold_width(),
                    reason="physical_contact_holding",
                )
            return self.status()

        if self._phase == GraspPhase.HOLDING:
            if not bilateral:
                unilateral_status = self._recover_unilateral_contact(
                    now=now,
                    contacts=contacts,
                    phase_name="holding",
                )
                if unilateral_status is not None:
                    return unilateral_status
                self._contact_loss_frames += 1
                if self._contact_loss_frames > self._config.contact_loss_grace_frames:
                    return self._fail(
                        "contact_lost_while_holding",
                        hold_width_m=gripper.width_m,
                    )
                return self.status()
            self._contact_loss_frames = 0
            if self._force_control_active():
                return self._step_force_holding(gripper=gripper)
            return self.status()

        return self._fail(
            f"unsupported_phase_{self._phase.value}",
            hold_width_m=gripper.width_m,
        )

    def status(self) -> PhysicalGraspStatus:
        return PhysicalGraspStatus(
            phase=self._phase,
            target_body_path=self._target_body_path,
            bilateral_contact=self._last_bilateral_contact,
            stable_contact_frames=self._stable_contact_frames,
            contact_width_m=self._contact_width_m,
            hold_width_m=self._hold_width_m,
            failure_reason=self._failure_reason,
            command=self._command,
            candidate_body_path=self._candidate_body_path,
            filtered_left_normal_force_n=self._filtered_left_force(),
            filtered_right_normal_force_n=self._filtered_right_force(),
            filtered_weak_normal_force_n=self._filtered_weak_force(),
            target_normal_force_n=self._config.target_normal_force_n,
            maximum_normal_force_n=self._config.maximum_normal_force_n,
            force_stable_frames=self._force_stable_frames,
            contact_loss_frames=self._contact_loss_frames,
            force_loss_frames=self._force_loss_frames,
            force_control_active=self._force_control_active(),
            unilateral_recovery_active=self._unilateral_recovery_started_s is not None,
            unilateral_contact_side=self._unilateral_contact_side,
            effective_grip_force_n=self._effective_grip_force_n,
            grip_force_source=self._grip_force_source,
        )

    def _transition(self, phase: GraspPhase, now_s: float) -> None:
        self._phase = phase
        self._phase_started_s = float(now_s)

    def _required_hold_width(self) -> float:
        if self._hold_width_m is None:
            raise RuntimeError("hold width is unavailable")
        return self._hold_width_m

    def _force_control_active(self) -> bool:
        return self._config.target_normal_force_n is not None

    def _reset_force_tracking(self) -> None:
        self._force_body_path = None
        self._left_force_window.clear()
        self._right_force_window.clear()
        self._force_stable_frames = 0
        self._contact_loss_frames = 0
        self._force_loss_frames = 0
        self._overforce_frames = 0
        self._unilateral_recovery_started_s = None
        self._unilateral_contact_side = None
        self._effective_grip_force_n = None
        self._grip_force_source = None

    def _recover_unilateral_contact(
        self,
        *,
        now: float,
        contacts: ContactSnapshot,
        phase_name: str,
    ) -> PhysicalGraspStatus | None:
        """Hold the contacting finger while the free finger slowly catches up."""
        target = self._target_body_path
        if target is None:
            return None
        left_contact = target in contacts.left_body_paths
        right_contact = target in contacts.right_body_paths
        if left_contact == right_contact:
            self._unilateral_recovery_started_s = None
            self._unilateral_contact_side = None
            return None

        contact_side = "left" if left_contact else "right"
        if (
            self._unilateral_recovery_started_s is None
            or self._unilateral_contact_side != contact_side
        ):
            self._unilateral_recovery_started_s = now
            self._unilateral_contact_side = contact_side
            self._left_force_window.clear()
            self._right_force_window.clear()
            self._force_stable_frames = 0
            self._force_loss_frames = 0
        self._contact_loss_frames += 1
        if (
            now - self._unilateral_recovery_started_s
            >= self._config.unilateral_recovery_timeout_s
        ):
            return self._fail(
                f"unilateral_contact_recovery_timeout_during_{phase_name}",
                hold_width_m=self._required_hold_width(),
            )

        current = self._required_hold_width()
        target_width = max(
            self._maximum_squeeze_width(),
            current - self._config.preload_step_m,
        )
        self._hold_width_m = target_width
        free_side = "right" if contact_side == "left" else "left"
        self._command = GraspCommand(
            drive_profile=DriveProfile.HOLD,
            target_width_m=target_width,
            reason=(
                f"unilateral_{contact_side}_contact_freeze_"
                f"{free_side}_catchup"
            ),
            freeze_contact_finger=contact_side,
        )
        return self.status()

    def _record_contact_force(
        self,
        body_path: str,
        contacts: ContactSnapshot,
    ) -> None:
        if body_path != self._force_body_path:
            self._force_body_path = body_path
            self._left_force_window.clear()
            self._right_force_window.clear()
            self._force_stable_frames = 0
            self._force_loss_frames = 0
            self._overforce_frames = 0
        left_force, right_force = contacts.normal_force_for(body_path)
        if left_force is None or right_force is None:
            return
        self._left_force_window.append(max(0.0, float(left_force)))
        self._right_force_window.append(max(0.0, float(right_force)))

    def _filtered_left_force(self) -> float | None:
        if not self._left_force_window:
            return None
        return float(median(self._left_force_window))

    def _filtered_right_force(self) -> float | None:
        if not self._right_force_window:
            return None
        return float(median(self._right_force_window))

    def _filtered_weak_force(self) -> float | None:
        left = self._filtered_left_force()
        right = self._filtered_right_force()
        if left is None or right is None:
            return None
        return min(left, right)

    def _filtered_peak_force(self) -> float | None:
        left = self._filtered_left_force()
        right = self._filtered_right_force()
        if left is None or right is None:
            return None
        return max(left, right)

    def _effective_force_pair(
        self,
        gripper: GripperSnapshot,
    ) -> tuple[float, float, str] | None:
        contact_left = self._filtered_left_force()
        contact_right = self._filtered_right_force()
        contact_pair = (
            None
            if contact_left is None or contact_right is None
            else (contact_left, contact_right, "contact_normal_force")
        )
        residual = gripper.residual_joint_forces_n
        lag = gripper.command_lag_m
        resistance_pair = None
        if residual is not None and lag is not None:
            residual_values = tuple(max(0.0, float(value)) for value in residual)
            lag_values = tuple(max(0.0, float(value)) for value in lag)
            if (
                min(residual_values) >= self._config.minimum_effort_residual_n
                and min(lag_values) >= self._config.minimum_position_lag_m
            ):
                resistance_pair = (
                    residual_values[0],
                    residual_values[1],
                    "joint_resistance_surrogate",
                )
        if contact_pair is None:
            return resistance_pair
        if resistance_pair is None:
            return contact_pair
        if min(resistance_pair[:2]) > min(contact_pair[:2]):
            return resistance_pair
        return contact_pair

    def _maximum_squeeze_width(self) -> float:
        if self._contact_width_m is None:
            raise RuntimeError("contact width is unavailable")
        return max(
            self._config.closed_width_m,
            self._contact_width_m - self._config.maximum_preload_delta_m,
        )

    def _increase_preload(self, *, reason: str) -> bool:
        current = self._required_hold_width()
        target = max(
            self._maximum_squeeze_width(),
            current - self._config.preload_step_m,
        )
        if target >= current - 1e-12:
            return False
        self._hold_width_m = target
        self._command = GraspCommand(
            drive_profile=DriveProfile.HOLD,
            target_width_m=target,
            reason=reason,
        )
        return True

    def _relieve_preload(self, *, reason: str) -> float:
        if self._contact_width_m is None:
            raise RuntimeError("contact width is unavailable")
        target = min(
            self._contact_width_m,
            self._required_hold_width() + self._config.preload_step_m,
        )
        self._hold_width_m = target
        self._command = GraspCommand(
            drive_profile=DriveProfile.HOLD,
            target_width_m=target,
            reason=reason,
        )
        return target

    def _step_force_preload(
        self,
        *,
        now: float,
        gripper: GripperSnapshot,
    ) -> PhysicalGraspStatus:
        target_force = self._config.target_normal_force_n
        if target_force is None:
            raise RuntimeError("force preload requires a configured target force")
        effective_pair = self._effective_force_pair(gripper)
        self._effective_grip_force_n = (
            None if effective_pair is None else min(effective_pair[:2])
        )
        self._grip_force_source = None if effective_pair is None else effective_pair[2]
        peak_force = (
            self._filtered_peak_force()
            if effective_pair is None
            else max(effective_pair[:2])
        )
        maximum_force = self._config.maximum_normal_force_n
        if maximum_force is not None and peak_force is not None and peak_force > maximum_force:
            self._overforce_frames += 1
            relieved_width = self._relieve_preload(reason="force_limit_relief")
            if self._overforce_frames >= self._config.force_confirm_frames:
                return self._fail(
                    "maximum_normal_force_exceeded",
                    hold_width_m=relieved_width,
                )
            return self.status()
        self._overforce_frames = 0

        weak_force = self._effective_grip_force_n
        lower_target = max(0.0, target_force - self._config.force_hysteresis_n)
        if weak_force is not None and weak_force >= target_force:
            self._force_stable_frames += 1
            self._force_loss_frames = 0
        elif (
            weak_force is not None
            and self._force_stable_frames > 0
            and weak_force >= lower_target
        ):
            # Hysteresis only absorbs feedback noise after the target has been
            # reached once.  Before that point every sub-target sample must
            # continue the bounded preload ramp instead of entering a deadband.
            self._force_stable_frames += 1
            self._force_loss_frames = 0
        else:
            self._force_stable_frames = 0
            self._force_loss_frames += 1
            self._increase_preload(reason="force_feedback_squeeze")

        elapsed = now - self._phase_started_s
        if (
            self._force_stable_frames >= self._config.force_confirm_frames
            and elapsed >= self._config.hold_confirm_timeout_s
        ):
            self._transition(GraspPhase.HOLDING, now)
            self._command = GraspCommand(
                drive_profile=DriveProfile.HOLD,
                target_width_m=self._required_hold_width(),
                reason="force_target_holding",
            )
            return self.status()
        if elapsed >= self._config.preload_timeout_s:
            return self._fail(
                "force_target_not_reached",
                hold_width_m=self._required_hold_width(),
            )
        return self.status()

    def _step_force_holding(
        self,
        *,
        gripper: GripperSnapshot,
    ) -> PhysicalGraspStatus:
        target_force = self._config.target_normal_force_n
        if target_force is None:
            raise RuntimeError("force holding requires a configured target force")
        effective_pair = self._effective_force_pair(gripper)
        self._effective_grip_force_n = (
            None if effective_pair is None else min(effective_pair[:2])
        )
        self._grip_force_source = None if effective_pair is None else effective_pair[2]
        peak_force = (
            self._filtered_peak_force()
            if effective_pair is None
            else max(effective_pair[:2])
        )
        maximum_force = self._config.maximum_normal_force_n
        if maximum_force is not None and peak_force is not None and peak_force > maximum_force:
            self._overforce_frames += 1
            relieved_width = self._relieve_preload(reason="holding_force_limit_relief")
            if self._overforce_frames >= self._config.force_confirm_frames:
                return self._fail(
                    "maximum_normal_force_exceeded_while_holding",
                    hold_width_m=relieved_width,
                )
            return self.status()
        self._overforce_frames = 0

        weak_force = self._effective_grip_force_n
        lower_target = max(0.0, target_force - self._config.force_hysteresis_n)
        if weak_force is not None and weak_force >= lower_target:
            self._force_stable_frames += 1
            self._force_loss_frames = 0
            return self.status()

        self._force_stable_frames = 0
        self._force_loss_frames += 1
        grace = self._config.force_loss_grace_frames
        if self._force_loss_frames % grace == 0:
            if self._increase_preload(reason="holding_force_recovery"):
                return self.status()
        at_maximum_preload = (
            self._required_hold_width() <= self._maximum_squeeze_width() + 1e-12
        )
        if (
            at_maximum_preload
            and self._force_loss_frames >= grace * self._config.force_confirm_frames
        ):
            return self._fail(
                "holding_force_below_target",
                hold_width_m=gripper.width_m,
            )
        return self.status()

    def _current_target_width(self) -> float:
        if self._command is not None:
            return self._command.target_width_m
        if self._hold_width_m is not None:
            return self._hold_width_m
        return self._config.open_width_m

    def _fail(
        self,
        reason: str,
        *,
        hold_width_m: float | None = None,
    ) -> PhysicalGraspStatus:
        self._phase = GraspPhase.FAILED
        self._failure_reason = str(reason)
        hold_width = (
            self._current_target_width()
            if hold_width_m is None
            else min(
                max(float(hold_width_m), self._config.closed_width_m),
                self._config.open_width_m,
            )
        )
        self._command = GraspCommand(
            drive_profile=DriveProfile.HOLD,
            target_width_m=hold_width,
            reason="failure_hold",
        )
        return self.status()
