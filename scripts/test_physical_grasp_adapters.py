#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from a1z_ext.grasping import (  # noqa: E402
    ParallelJawMapping,
    rate_limit_parallel_jaw_setpoint,
    reduce_contact_impulses,
)


LEFT = "/Robot/left_finger"
RIGHT = "/Robot/right_finger"
TARGET = "/World/GraspObjects/object_000__pudding_box"
GROUND = "/World/GroundPlane"
CARRIER = "/Robot/gripper_carrier"


def record(sensor: str, counterpart: str, impulse_xyz: tuple[float, float, float]) -> dict[str, object]:
    return {
        "body0": sensor,
        "body1": counterpart,
        "impulse": impulse_xyz,
    }


class PhysicalGraspAdapterTests(unittest.TestCase):
    def test_a1z_width_mapping_is_symmetric_and_reversible(self) -> None:
        mapping = ParallelJawMapping.from_sequences(
            open_dofs_m=[0.048, -0.048],
            closed_dofs_m=[0.0, 0.0],
        )
        self.assertAlmostEqual(mapping.open_width_m, 0.096)
        self.assertEqual(mapping.width_to_dofs(0.0), (0.0, 0.0))
        self.assertEqual(mapping.width_to_dofs(0.096), (0.048, -0.048))
        midpoint = mapping.width_to_dofs(0.048)
        self.assertEqual(midpoint, (0.024, -0.024))
        self.assertAlmostEqual(mapping.dofs_to_width(midpoint), 0.048)

    def test_width_mapping_clamps_without_writing_joint_state(self) -> None:
        mapping = ParallelJawMapping((0.048, -0.048), (0.0, 0.0))
        self.assertEqual(mapping.width_to_dofs(-1.0), (0.0, 0.0))
        self.assertEqual(mapping.width_to_dofs(1.0), (0.048, -0.048))

    def test_slow_setpoint_accumulates_when_measured_jaws_are_stalled(self) -> None:
        measured = (0.022, -0.018)
        commanded = measured
        for _ in range(4):
            commanded = rate_limit_parallel_jaw_setpoint(
                previous_dofs_m=commanded,
                measured_dofs_m=measured,
                target_dofs_m=(0.0, 0.0),
                max_velocity_m_s=(0.008, 0.008),
                dt_s=0.1,
                max_lead_m=0.003,
            )
        self.assertAlmostEqual(commanded[0], 0.019)
        self.assertAlmostEqual(commanded[1], -0.015)

    def test_slow_setpoint_respects_velocity_and_tracking_lead_limits(self) -> None:
        commanded = rate_limit_parallel_jaw_setpoint(
            previous_dofs_m=(0.020, -0.020),
            measured_dofs_m=(0.021, -0.019),
            target_dofs_m=(0.0, 0.0),
            max_velocity_m_s=(0.008, 0.008),
            dt_s=0.05,
            max_lead_m=0.003,
        )
        self.assertAlmostEqual(commanded[0], 0.0196)
        self.assertAlmostEqual(commanded[1], -0.0196)
        self.assertLessEqual(abs(commanded[0] - 0.021), 0.003)
        self.assertLessEqual(abs(commanded[1] - -0.019), 0.003)

    def test_impulse_is_converted_with_actual_physics_dt(self) -> None:
        snapshot = reduce_contact_impulses(
            left_records=[record(LEFT, TARGET, (0.001, 0.0, 0.0))],
            right_records=[record(RIGHT, TARGET, (-0.0012, 0.0, 0.0))],
            left_finger_body_path=LEFT,
            right_finger_body_path=RIGHT,
            target_body_path=TARGET,
            physics_dt_s=0.002,
        )
        self.assertTrue(snapshot.bilateral_for(TARGET, 0.5))
        self.assertAlmostEqual(snapshot.left_normal_force_n, 0.5)
        self.assertAlmostEqual(snapshot.right_normal_force_n, 0.6)

    def test_multiple_target_contacts_are_aggregated_per_finger(self) -> None:
        child = f"{TARGET}/CollisionMesh"
        snapshot = reduce_contact_impulses(
            left_records=[
                record(LEFT, child, (0.0004, 0.0, 0.0)),
                record(LEFT, child, (0.0006, 0.0, 0.0)),
            ],
            right_records=[record(RIGHT, TARGET, (0.001, 0.0, 0.0))],
            left_finger_body_path=LEFT,
            right_finger_body_path=RIGHT,
            target_body_path=TARGET,
            physics_dt_s=0.002,
        )
        self.assertAlmostEqual(snapshot.left_normal_force_n, 0.5)
        self.assertEqual(snapshot.left_body_paths, (TARGET,))

    def test_targetless_reduction_discovers_strongest_common_body(self) -> None:
        other = "/World/TrashSet/other_object"
        snapshot = reduce_contact_impulses(
            left_records=[
                record(LEFT, TARGET, (0.001, 0.0, 0.0)),
                record(LEFT, other, (0.0002, 0.0, 0.0)),
            ],
            right_records=[
                record(RIGHT, TARGET, (-0.0012, 0.0, 0.0)),
                record(RIGHT, other, (-0.0001, 0.0, 0.0)),
            ],
            left_finger_body_path=LEFT,
            right_finger_body_path=RIGHT,
            physics_dt_s=0.002,
        )
        self.assertEqual(snapshot.strongest_bilateral_body(None), TARGET)
        self.assertEqual(snapshot.strongest_bilateral_body(0.5), TARGET)
        self.assertEqual(snapshot.normal_force_for(TARGET), (0.5, 0.6))

    def test_ground_contact_is_recorded_as_support_without_blocking(self) -> None:
        snapshot = reduce_contact_impulses(
            left_records=[record(LEFT, GROUND, (0.0, 0.0, 0.01))],
            right_records=[record(RIGHT, TARGET, (-0.001, 0.0, 0.0))],
            left_finger_body_path=LEFT,
            right_finger_body_path=RIGHT,
            physics_dt_s=0.002,
            support_body_paths=[GROUND],
        )
        self.assertFalse(snapshot.has_blocking_contact)
        self.assertEqual(snapshot.left_support_body_paths, (GROUND,))
        self.assertEqual(snapshot.right_support_body_paths, ())
        self.assertIsNone(snapshot.strongest_bilateral_body(None))

    def test_support_body_is_never_selected_even_with_bilateral_contact(self) -> None:
        snapshot = reduce_contact_impulses(
            left_records=[record(LEFT, GROUND, (0.0, 0.0, 0.01))],
            right_records=[record(RIGHT, f"{GROUND}/Collision", (0.0, 0.0, 0.02))],
            left_finger_body_path=LEFT,
            right_finger_body_path=RIGHT,
            physics_dt_s=0.002,
            support_body_paths=[GROUND],
        )
        self.assertFalse(snapshot.bilateral_for(GROUND, None))
        self.assertIsNone(snapshot.strongest_bilateral_body(None))
        self.assertEqual(snapshot.left_body_paths, (GROUND,))
        self.assertEqual(snapshot.right_body_paths, (GROUND,))

    def test_support_contact_does_not_hide_a_real_bilateral_target(self) -> None:
        snapshot = reduce_contact_impulses(
            left_records=[
                record(LEFT, GROUND, (0.0, 0.0, 0.01)),
                record(LEFT, TARGET, (0.001, 0.0, 0.0)),
            ],
            right_records=[record(RIGHT, TARGET, (-0.0012, 0.0, 0.0))],
            left_finger_body_path=LEFT,
            right_finger_body_path=RIGHT,
            physics_dt_s=0.002,
            support_body_paths=[GROUND],
        )
        self.assertEqual(snapshot.strongest_bilateral_body(0.5), TARGET)
        self.assertTrue(snapshot.bilateral_for(TARGET, 0.5))
        self.assertEqual(snapshot.left_support_body_paths, (GROUND,))

    def test_explicit_hazard_contact_remains_blocking(self) -> None:
        snapshot = reduce_contact_impulses(
            left_records=[record(LEFT, CARRIER, (0.0, 0.0, 0.01))],
            right_records=[],
            left_finger_body_path=LEFT,
            right_finger_body_path=RIGHT,
            physics_dt_s=0.002,
            blocking_body_paths=[CARRIER],
            support_body_paths=[GROUND],
        )
        self.assertTrue(snapshot.has_blocking_contact)
        self.assertEqual(snapshot.blocking_reason, f"blocking_contact:{CARRIER}")

    def test_invalid_dt_is_rejected_before_force_thresholds(self) -> None:
        with self.assertRaisesRegex(ValueError, "physics_dt_s"):
            reduce_contact_impulses(
                left_records=[],
                right_records=[],
                left_finger_body_path=LEFT,
                right_finger_body_path=RIGHT,
                target_body_path=TARGET,
                physics_dt_s=0.0,
            )


if __name__ == "__main__":
    unittest.main()
