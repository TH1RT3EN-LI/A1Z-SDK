#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from a1z_ext.grasping import (  # noqa: E402
    ContactSnapshot,
    DriveProfile,
    GraspPhase,
    GripperSnapshot,
    PhysicalGraspConfig,
    PhysicalGraspFSM,
    ParallelJawActuator,
    PhysicalContactObserver,
    Pose3D,
)


TARGET = "/World/GraspObjects/object_000__pudding_box"
GROUND = "/World/GroundPlane"


def config(
    *,
    minimum_force: float | None = None,
    preload_delta_m: float = 0.001,
    maximum_preload_delta_m: float = 0.002,
    target_force: float | None = None,
    force_confirm_frames: int = 3,
    force_window_frames: int = 5,
    contact_loss_grace_frames: int = 0,
    force_loss_grace_frames: int = 3,
    unilateral_recovery_timeout_s: float = 1.0,
) -> PhysicalGraspConfig:
    return PhysicalGraspConfig(
        open_width_m=0.096,
        closed_width_m=0.0,
        preload_delta_m=preload_delta_m,
        maximum_preload_delta_m=maximum_preload_delta_m,
        minimum_stable_frames=3,
        minimum_normal_force_n=minimum_force,
        precheck_timeout_s=1.0,
        soft_close_timeout_s=2.0,
        search_timeout_s=4.0,
        hold_confirm_timeout_s=0.2,
        target_normal_force_n=target_force,
        maximum_normal_force_n=3.0 if target_force is not None else None,
        force_hysteresis_n=0.1,
        force_confirm_frames=force_confirm_frames,
        force_window_frames=force_window_frames,
        preload_step_m=0.0001,
        preload_timeout_s=1.0,
        contact_loss_grace_frames=contact_loss_grace_frames,
        force_loss_grace_frames=force_loss_grace_frames,
        unilateral_recovery_timeout_s=unilateral_recovery_timeout_s,
    )


def gripper(
    width: float,
    *,
    stable: bool = False,
    closed: bool = False,
    residual_force: tuple[float, float] | None = None,
    command_lag: tuple[float, float] | None = None,
) -> GripperSnapshot:
    return GripperSnapshot(
        width_m=width,
        motion_stable=stable,
        fully_closed=closed,
        residual_joint_forces_n=residual_force,
        command_lag_m=command_lag,
    )


def bilateral(*, force: float | None = None) -> ContactSnapshot:
    return ContactSnapshot(
        left_body_paths=(TARGET,),
        right_body_paths=(TARGET,),
        left_normal_force_n=force,
        right_normal_force_n=force,
    )


class PhysicalGraspFSMTests(unittest.TestCase):
    def test_existing_lightweight_grasping_contract_remains_exported(self) -> None:
        pose = Pose3D(position_xyz=[0.0, 0.0, 0.0], quaternion_xyzw=[0.0, 0.0, 0.0, 1.0])
        self.assertEqual(pose.position_xyz, [0.0, 0.0, 0.0])

    def test_adapter_protocols_require_explicit_physical_boundaries(self) -> None:
        class FakeActuator:
            def snapshot(self) -> GripperSnapshot:
                return gripper(0.096, stable=True)

            def apply(self, command) -> None:
                self.command = command

        class FakeObserver:
            def observe(self, *, target_body_path: str, physics_dt_s: float) -> ContactSnapshot:
                self.request = (target_body_path, physics_dt_s)
                return ContactSnapshot()

        self.assertIsInstance(FakeActuator(), ParallelJawActuator)
        self.assertIsInstance(FakeObserver(), PhysicalContactObserver)

    def test_happy_path_reaches_hold_without_attachment_semantics(self) -> None:
        fsm = PhysicalGraspFSM(config())
        status = fsm.begin(target_body_path=TARGET, now_s=0.0)
        self.assertEqual(status.phase, GraspPhase.PRECHECK)
        status = fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        self.assertEqual(status.phase, GraspPhase.SOFT_CLOSE)
        self.assertEqual(status.command.drive_profile, DriveProfile.SOFT_CLOSE)
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertAlmostEqual(status.contact_width_m, 0.05)
        self.assertAlmostEqual(status.hold_width_m, 0.049)
        self.assertAlmostEqual(status.command.target_width_m, 0.049)
        status = fsm.step(
            now_s=0.5,
            arm_stable=True,
            gripper=gripper(0.049, stable=True),
            contacts=bilateral(),
        )
        self.assertEqual(status.phase, GraspPhase.HOLDING)
        self.assertTrue(status.contact_ready)
        self.assertFalse(hasattr(status, "attached_object_path"))
        self.assertFalse(hasattr(status, "attachment_joint_path"))

    def test_targetless_happy_path_locks_stable_common_contact(self) -> None:
        fsm = PhysicalGraspFSM(config())
        status = fsm.begin(now_s=0.0)
        self.assertIsNone(status.target_body_path)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.5),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertEqual(status.target_body_path, TARGET)
        self.assertEqual(status.candidate_body_path, TARGET)

    def test_loaded_touch_gate_ignores_zero_force_path_contacts_without_ratcheting(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                minimum_force=0.05,
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.008,
                target_force=0.75,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.07, stable=True),
            contacts=ContactSnapshot(),
        )

        # Collision paths alone, and the tiny impulses seen in the failed live
        # AnyGrasp run, must not freeze an oversized contact width.
        for frame, (width, force) in enumerate(
            (
                (0.0526, 0.0),
                (0.0500, 0.0),
                (0.0446, 0.005),
                (0.0400, 0.01),
            )
        ):
            status = fsm.step(
                now_s=0.2 + frame * 0.05,
                arm_stable=True,
                gripper=gripper(width),
                contacts=bilateral(force=force),
            )
            self.assertEqual(status.phase, GraspPhase.SOFT_CLOSE)
            self.assertEqual(status.stable_contact_frames, 0)
            self.assertIsNone(status.contact_width_m)
            self.assertEqual(status.command.reason, "soft_close_search_target")

        # Once both jaws carry a real (but still light) load, the FSM locks the
        # smaller width and performs one continuous force-controlled preload.
        for frame in range(3):
            status = fsm.step(
                now_s=0.5 + frame * 0.05,
                arm_stable=True,
                gripper=gripper(0.0344),
                contacts=bilateral(force=0.06),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertAlmostEqual(status.contact_width_m or 0.0, 0.0344)
        self.assertAlmostEqual(status.hold_width_m or 0.0, 0.0339)

        for frame in range(5):
            status = fsm.step(
                now_s=0.9 + frame * 0.1,
                arm_stable=True,
                gripper=gripper(0.0326, stable=True),
                contacts=bilateral(force=0.8),
            )
        self.assertEqual(status.phase, GraspPhase.HOLDING)
        self.assertGreaterEqual(status.filtered_weak_normal_force_n or 0.0, 0.75)

    def test_high_grip_preload_continues_closing_after_contact(self) -> None:
        fsm = PhysicalGraspFSM(
            config(preload_delta_m=0.004, maximum_preload_delta_m=0.006)
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.5),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertAlmostEqual(status.contact_width_m, 0.05)
        self.assertAlmostEqual(status.hold_width_m, 0.046)
        self.assertAlmostEqual(status.command.target_width_m, 0.046)
        self.assertEqual(status.command.reason, "bilateral_contact_preload")

    def test_force_control_keeps_squeezing_after_contact_until_target_force(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.2),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        initial_hold_width = status.hold_width_m
        status = fsm.step(
            now_s=0.3,
            arm_stable=True,
            gripper=gripper(0.0495),
            contacts=bilateral(force=0.2),
        )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertEqual(status.command.reason, "force_feedback_squeeze")
        self.assertLess(status.hold_width_m, initial_hold_width)
        self.assertTrue(status.contact_ready)
        for frame in range(8):
            status = fsm.step(
                now_s=0.5 + frame * 0.02,
                arm_stable=True,
                gripper=gripper(status.hold_width_m or 0.049, stable=True),
                contacts=bilateral(force=0.85),
            )
        self.assertEqual(status.phase, GraspPhase.HOLDING)
        self.assertTrue(status.force_control_active)
        self.assertGreaterEqual(status.filtered_weak_normal_force_n or 0.0, 0.75)
        self.assertEqual(status.command.reason, "force_target_holding")

    def test_force_control_keeps_squeezing_inside_hysteresis_before_target(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        # 0.70 N is below the 0.75 N target but inside its 0.10 N
        # hysteresis band.  It must not stall before the first target crossing.
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.70),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        initial_hold_width = status.hold_width_m
        status = fsm.step(
            now_s=0.3,
            arm_stable=True,
            gripper=gripper(initial_hold_width or 0.0495),
            contacts=bilateral(force=0.70),
        )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertEqual(status.command.reason, "force_feedback_squeeze")
        self.assertLess(status.hold_width_m, initial_hold_width)
        self.assertEqual(status.force_stable_frames, 0)

    def test_force_control_uses_hysteresis_after_first_target_crossing(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
                force_confirm_frames=3,
                force_window_frames=1,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.70),
            )
        status = fsm.step(
            now_s=0.30,
            arm_stable=True,
            gripper=gripper(status.hold_width_m or 0.0495),
            contacts=bilateral(force=0.80),
        )
        self.assertEqual(status.force_stable_frames, 1)
        target_crossing_hold_width = status.hold_width_m
        status = fsm.step(
            now_s=0.35,
            arm_stable=True,
            gripper=gripper(target_crossing_hold_width or 0.0495),
            contacts=bilateral(force=0.70),
        )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertEqual(status.force_stable_frames, 2)
        self.assertEqual(status.hold_width_m, target_crossing_hold_width)
        status = fsm.step(
            now_s=0.45,
            arm_stable=True,
            gripper=gripper(target_crossing_hold_width or 0.0495),
            contacts=bilateral(force=0.70),
        )
        self.assertEqual(status.phase, GraspPhase.HOLDING)
        self.assertEqual(status.command.reason, "force_target_holding")

    def test_bilateral_joint_resistance_is_guarded_force_fallback(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
                force_confirm_frames=3,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.0),
            )
        for frame in range(4):
            status = fsm.step(
                now_s=0.5 + frame * 0.02,
                arm_stable=True,
                gripper=gripper(
                    0.0495,
                    stable=True,
                    residual_force=(0.9, 0.85),
                    command_lag=(0.001, 0.0012),
                ),
                contacts=bilateral(force=0.0),
            )
        self.assertEqual(status.phase, GraspPhase.HOLDING)
        self.assertEqual(status.grip_force_source, "joint_resistance_surrogate")
        self.assertAlmostEqual(status.effective_grip_force_n or 0.0, 0.85)

    def test_holding_force_drop_triggers_bounded_recovery_squeeze(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
                force_confirm_frames=2,
                force_loss_grace_frames=2,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.9),
            )
        for frame in range(4):
            status = fsm.step(
                now_s=0.5 + frame * 0.02,
                arm_stable=True,
                gripper=gripper(0.0495, stable=True),
                contacts=bilateral(force=0.9),
            )
        self.assertEqual(status.phase, GraspPhase.HOLDING)
        held_width = status.hold_width_m
        for frame in range(6):
            status = fsm.step(
                now_s=0.7 + frame * 0.02,
                arm_stable=True,
                gripper=gripper(held_width or 0.0495),
                contacts=bilateral(force=0.2),
            )
        self.assertEqual(status.phase, GraspPhase.HOLDING)
        self.assertEqual(status.command.reason, "holding_force_recovery")
        self.assertLess(status.hold_width_m, held_width)

    def test_force_control_tolerates_short_contact_sensor_dropout(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
                contact_loss_grace_frames=2,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.4),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        for frame in range(2):
            status = fsm.step(
                now_s=0.3 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.049),
                contacts=ContactSnapshot(),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertEqual(status.contact_loss_frames, 2)
        status = fsm.step(
            now_s=0.33,
            arm_stable=True,
            gripper=gripper(0.049),
            contacts=bilateral(force=0.4),
        )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertEqual(status.contact_loss_frames, 0)

    def test_unilateral_contact_freezes_contacting_finger_while_free_finger_catches_up(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
                unilateral_recovery_timeout_s=0.5,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.4),
            )
        original_width = status.hold_width_m
        status = fsm.step(
            now_s=0.3,
            arm_stable=True,
            gripper=gripper(0.0509),
            contacts=ContactSnapshot(left_body_paths=(TARGET,)),
        )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertTrue(status.unilateral_recovery_active)
        self.assertEqual(status.unilateral_contact_side, "left")
        self.assertEqual(status.command.freeze_contact_finger, "left")
        self.assertEqual(
            status.command.reason,
            "unilateral_left_contact_freeze_right_catchup",
        )
        self.assertLess(status.hold_width_m, original_width)

    def test_unilateral_recovery_times_out_closed_instead_of_claiming_grasp(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
                unilateral_recovery_timeout_s=0.2,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.4),
            )
        fsm.step(
            now_s=0.3,
            arm_stable=True,
            gripper=gripper(0.0509),
            contacts=ContactSnapshot(right_body_paths=(TARGET,)),
        )
        status = fsm.step(
            now_s=0.51,
            arm_stable=True,
            gripper=gripper(0.0505),
            contacts=ContactSnapshot(right_body_paths=(TARGET,)),
        )
        self.assertEqual(status.phase, GraspPhase.FAILED)
        self.assertEqual(
            status.failure_reason,
            "unilateral_contact_recovery_timeout_during_preload",
        )

    def test_force_control_fails_closed_when_target_force_cannot_be_reached(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.0006,
                target_force=0.75,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.2),
            )
        status = fsm.step(
            now_s=1.3,
            arm_stable=True,
            gripper=gripper(0.0494, stable=True),
            contacts=bilateral(force=0.2),
        )
        self.assertEqual(status.phase, GraspPhase.FAILED)
        self.assertEqual(status.failure_reason, "force_target_not_reached")
        self.assertGreaterEqual(status.command.target_width_m, 0.0494)

    def test_force_control_relaxes_then_fails_on_sustained_overforce(self) -> None:
        fsm = PhysicalGraspFSM(
            config(
                preload_delta_m=0.0005,
                maximum_preload_delta_m=0.002,
                target_force=0.75,
                force_confirm_frames=3,
            )
        )
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=4.0),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        for frame in range(3):
            status = fsm.step(
                now_s=0.3 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.0495),
                contacts=bilateral(force=4.0),
            )
        self.assertEqual(status.phase, GraspPhase.FAILED)
        self.assertEqual(
            status.failure_reason,
            "maximum_normal_force_exceeded",
        )

    def test_targetless_candidate_switch_resets_stability(self) -> None:
        other = "/World/TrashSet/other_object"
        fsm = PhysicalGraspFSM(config())
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        first = bilateral(force=0.5)
        second = ContactSnapshot(
            left_body_paths=(other,),
            right_body_paths=(other,),
            left_force_by_body_n=((other, 0.6),),
            right_force_by_body_n=((other, 0.6),),
        )
        status = fsm.step(
            now_s=0.2,
            arm_stable=True,
            gripper=gripper(0.05),
            contacts=first,
        )
        self.assertEqual(status.stable_contact_frames, 1)
        status = fsm.step(
            now_s=0.21,
            arm_stable=True,
            gripper=gripper(0.05),
            contacts=second,
        )
        self.assertEqual(status.stable_contact_frames, 1)
        self.assertEqual(status.candidate_body_path, other)
        self.assertIsNone(status.target_body_path)

    def test_precheck_holds_measured_width_instead_of_opening_fully(self) -> None:
        fsm = PhysicalGraspFSM(config())
        status = fsm.begin(
            target_body_path=TARGET,
            now_s=0.0,
            initial_width_m=0.041,
        )
        self.assertEqual(status.phase, GraspPhase.PRECHECK)
        self.assertAlmostEqual(status.command.target_width_m, 0.041)

    def test_search_timeout_holds_measured_width(self) -> None:
        fsm = PhysicalGraspFSM(config())
        fsm.begin(target_body_path=TARGET, now_s=0.0, initial_width_m=0.04)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.04),
            contacts=ContactSnapshot(),
        )
        fsm.step(
            now_s=2.2,
            arm_stable=True,
            gripper=gripper(0.025),
            contacts=ContactSnapshot(),
        )
        status = fsm.step(
            now_s=6.3,
            arm_stable=True,
            gripper=gripper(0.018),
            contacts=ContactSnapshot(),
        )
        self.assertEqual(status.phase, GraspPhase.FAILED)
        self.assertEqual(status.failure_reason, "search_timeout_without_bilateral_contact")
        self.assertAlmostEqual(status.command.target_width_m, 0.018)

    def test_unilateral_or_wrong_target_never_confirms_contact(self) -> None:
        fsm = PhysicalGraspFSM(config())
        fsm.begin(target_body_path=TARGET, now_s=0.0)
        fsm.step(now_s=0.1, arm_stable=True, gripper=gripper(0.096), contacts=ContactSnapshot())
        unilateral = ContactSnapshot(left_body_paths=(TARGET,), right_body_paths=())
        for frame in range(5):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=unilateral,
            )
        self.assertEqual(status.phase, GraspPhase.SOFT_CLOSE)
        self.assertEqual(status.stable_contact_frames, 0)

    def test_support_contact_does_not_abort_and_target_can_still_lock(self) -> None:
        fsm = PhysicalGraspFSM(config())
        fsm.begin(now_s=0.0)
        fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(),
        )
        support_and_unilateral_target = ContactSnapshot(
            left_body_paths=(GROUND,),
            right_body_paths=(TARGET,),
            right_force_by_body_n=((TARGET, 0.5),),
            support_body_paths=(GROUND,),
        )
        status = fsm.step(
            now_s=0.2,
            arm_stable=True,
            gripper=gripper(0.05),
            contacts=support_and_unilateral_target,
        )
        self.assertEqual(status.phase, GraspPhase.SOFT_CLOSE)
        self.assertEqual(status.stable_contact_frames, 0)
        support_and_bilateral_target = ContactSnapshot(
            left_body_paths=(GROUND, TARGET),
            right_body_paths=(TARGET,),
            left_force_by_body_n=((GROUND, 4.0), (TARGET, 0.5)),
            right_force_by_body_n=((TARGET, 0.6),),
            support_body_paths=(GROUND,),
        )
        for frame in range(3):
            status = fsm.step(
                now_s=0.3 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.048),
                contacts=support_and_bilateral_target,
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)
        self.assertEqual(status.target_body_path, TARGET)

    def test_explicit_hazard_contact_still_fails_closed(self) -> None:
        fsm = PhysicalGraspFSM(config())
        fsm.begin(target_body_path=TARGET, now_s=0.0)
        status = fsm.step(
            now_s=0.1,
            arm_stable=True,
            gripper=gripper(0.096),
            contacts=ContactSnapshot(
                left_blocked=True,
                blocking_reason="blocking_contact:/Robot/gripper_carrier",
            ),
        )
        self.assertEqual(status.phase, GraspPhase.FAILED)
        self.assertEqual(
            status.failure_reason,
            "blocking_contact:/Robot/gripper_carrier",
        )
        self.assertEqual(status.command.drive_profile, DriveProfile.HOLD)

    def test_soft_close_transitions_to_search_then_times_out(self) -> None:
        fsm = PhysicalGraspFSM(config())
        fsm.begin(target_body_path=TARGET, now_s=0.0)
        fsm.step(now_s=0.1, arm_stable=True, gripper=gripper(0.096), contacts=ContactSnapshot())
        status = fsm.step(
            now_s=2.11,
            arm_stable=True,
            gripper=gripper(0.04),
            contacts=ContactSnapshot(),
        )
        self.assertEqual(status.phase, GraspPhase.SEARCH)
        self.assertEqual(status.command.drive_profile, DriveProfile.SEARCH)
        status = fsm.step(
            now_s=6.12,
            arm_stable=True,
            gripper=gripper(0.02),
            contacts=ContactSnapshot(),
        )
        self.assertEqual(status.phase, GraspPhase.FAILED)
        self.assertEqual(status.failure_reason, "search_timeout_without_bilateral_contact")

    def test_force_threshold_is_applied_only_when_configured(self) -> None:
        fsm = PhysicalGraspFSM(config(minimum_force=0.5))
        fsm.begin(target_body_path=TARGET, now_s=0.0)
        fsm.step(now_s=0.1, arm_stable=True, gripper=gripper(0.096), contacts=ContactSnapshot())
        for frame in range(3):
            status = fsm.step(
                now_s=0.2 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.49),
            )
        self.assertEqual(status.phase, GraspPhase.SOFT_CLOSE)
        for frame in range(3):
            status = fsm.step(
                now_s=0.3 + frame * 0.01,
                arm_stable=True,
                gripper=gripper(0.05),
                contacts=bilateral(force=0.5),
            )
        self.assertEqual(status.phase, GraspPhase.PRELOAD)

    def test_release_opens_and_finishes_without_constraint_cleanup(self) -> None:
        fsm = PhysicalGraspFSM(config())
        fsm.begin(target_body_path=TARGET, now_s=0.0)
        fsm.abort(reason="test_setup")
        status = fsm.release(now_s=1.0)
        self.assertEqual(status.phase, GraspPhase.RELEASING)
        self.assertEqual(status.command.drive_profile, DriveProfile.FREE)
        status = fsm.step(
            now_s=1.1,
            arm_stable=True,
            gripper=gripper(0.096, stable=True),
            contacts=ContactSnapshot(),
        )
        self.assertEqual(status.phase, GraspPhase.RELEASED)
        self.assertIsNone(status.command)


if __name__ == "__main__":
    unittest.main()
