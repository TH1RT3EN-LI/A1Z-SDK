#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.robots.grasp_attach_policy import summarize_attach_contacts


class _AttachPolicyHarness:
    def __init__(self) -> None:
        self._left_finger_body_path = "/World/Robot/left_finger"
        self._right_finger_body_path = "/World/Robot/right_finger"
        self._gripper_carrier_body_path = "/World/Robot/gripper_base"


class GraspAttachPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = _AttachPolicyHarness()

    def _summarize(self, *, left: list[str], right: list[str], target_body_path: str = "") -> tuple[bool, str, dict[str, object]]:
        left_details = [
            {
                "candidate": candidate,
                "rigid_body_candidate": candidate,
                "body0": self.policy._left_finger_body_path,
                "body1": candidate,
                "collider0": self.policy._left_finger_body_path,
                "collider1": candidate,
                "position": (0.0, 0.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
                "impulse": (0.0, 0.0, 0.0),
                "separation": 0.001,
            }
            for candidate in left
        ]
        right_details = [
            {
                "candidate": candidate,
                "rigid_body_candidate": candidate,
                "body0": self.policy._right_finger_body_path,
                "body1": candidate,
                "collider0": self.policy._right_finger_body_path,
                "collider1": candidate,
                "position": (0.0, 0.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
                "impulse": (0.0, 0.0, 0.0),
                "separation": 0.001,
            }
            for candidate in right
        ]
        return summarize_attach_contacts(
            left_raw_candidates=left,
            left_candidates=left,
            left_contact_details=left_details,
            right_raw_candidates=right,
            right_candidates=right,
            right_contact_details=right_details,
            target_body_path=target_body_path,
            require_bilateral_contact=True,
        )

    def test_selects_shared_object_without_explicit_target(self) -> None:
        ok, body_path, summary = self._summarize(
            left=["/World/TrashSet/marker_upright"],
            right=["/World/TrashSet/marker_upright"],
        )
        self.assertTrue(ok)
        self.assertEqual(body_path, "/World/TrashSet/marker_upright")
        self.assertEqual(summary["chosen_body_path"], "/World/TrashSet/marker_upright")
        self.assertEqual(summary["shared_contact_candidates"], ["/World/TrashSet/marker_upright"])
        self.assertFalse(summary["ground_contact_present"])
        self.assertTrue(summary["left_has_selected_body_contact"])
        self.assertTrue(summary["right_has_selected_body_contact"])

    def test_rejects_explicit_target_when_contacts_hit_other_body(self) -> None:
        ok, body_path, summary = self._summarize(
            left=["/World/TrashSet/marker_upright"],
            right=["/World/TrashSet/marker_upright"],
            target_body_path="/World/TrashSet/paper_debris",
        )
        self.assertFalse(ok)
        self.assertEqual(body_path, "")
        self.assertIsNone(summary["chosen_body_path"])
        self.assertFalse(summary["left_has_target_contact"])
        self.assertFalse(summary["right_has_target_contact"])

    def test_ground_plane_is_kept_out_of_candidate_selection(self) -> None:
        ok, body_path, summary = self._summarize(
            left=["/World/GroundPlane", "/World/TrashSet/marker_upright"],
            right=["/World/GroundPlane", "/World/TrashSet/marker_upright"],
        )
        self.assertTrue(ok)
        self.assertEqual(body_path, "/World/TrashSet/marker_upright")
        self.assertTrue(summary["ground_contact_present"])
        self.assertIn("/World/GroundPlane", summary["shared_contact_candidates"])


if __name__ == "__main__":
    unittest.main()
