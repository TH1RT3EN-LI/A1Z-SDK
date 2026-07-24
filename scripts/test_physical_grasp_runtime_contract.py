#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import json
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "a1z_ext" / "robots" / "isaacsim_robot.py"
PROFILE_PATH = REPO_ROOT / "config" / "grasping" / "controllers" / "a1z_physical_gripper_v1.json"


class PhysicalGraspRuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = BACKEND_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.robot = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "IsaacSimArmRobot"
        )
        cls.methods = {
            node.name: node
            for node in cls.robot.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def _method_source(self, name: str) -> str:
        return ast.get_source_segment(self.source, self.methods[name]) or ""

    def test_runtime_loop_advances_physical_fsm_before_legacy_attach(self) -> None:
        source = self._method_source("process_pending")
        self.assertLess(
            source.index("self._advance_physical_grasp()"),
            source.index("self._advance_pending_grasp_attach()"),
        )

    def test_v2_control_path_has_no_attachment_or_teleport_calls(self) -> None:
        v2_methods = [
            name
            for name in self.methods
            if "physical_grasp" in name or name in {"_physical_contact_snapshot", "_physical_gripper_snapshot"}
        ]
        source = "\n".join(self._method_source(name) for name in sorted(v2_methods))
        for forbidden in (
            "_create_attachment_joint(",
            "_force_gripper_positions(",
            "UsdPhysics.FixedJoint.Define",
            "kinematicEnabled",
            "disableGravity",
        ):
            self.assertNotIn(forbidden, source)

    def test_v2_requires_actual_physics_dt_for_force_reduction(self) -> None:
        source = self._method_source("_physical_contact_snapshot")
        self.assertIn("physics_dt_s=self._physics_dt_s()", source)
        dt_source = self._method_source("_physics_dt_s")
        self.assertIn('getattr(world, "get_physics_dt", None)', dt_source)

    def test_v2_audits_new_constraints_each_runtime_frame(self) -> None:
        source = self._method_source("_advance_physical_grasp")
        self.assertIn("operation.initial_constraint_paths", source)
        self.assertIn("constraint_created_during_physical_grasp", source)

    def test_v2_status_explicitly_denies_attachment_success(self) -> None:
        source = self._method_source("_physical_grasp_status_payload")
        self.assertIn('"contract_version": 2', source)
        self.assertIn('"mode": "physical"', source)
        self.assertIn('"attachment_joint_path": None', source)
        self.assertIn('"attached_object_path": None', source)
        self.assertIn('"constraint_count_delta": len(new_constraints)', source)
        self.assertIn('"target_physics_state_mutated":', source)
        self.assertIn('"target_to_carrier_translation_m": relative_translation', source)
        self.assertIn('"gripper_drive_type":', source)
        self.assertIn('"measured_jaw_dofs_m":', source)

    def test_v2_accepts_injected_controller_profile(self) -> None:
        start_source = self._method_source("_start_physical_grasp_impl")
        self.assertIn("PhysicalGraspConfig.from_controller_profile(profile)", start_source)
        self.assertIn("controller profile jaw widths do not match", start_source)
        command_source = self._method_source("_apply_physical_grasp_command")
        self.assertIn('operation.controller_profile.get("profiles")', command_source)
        self.assertIn('profile_name=f"physical_v2_', command_source)
        self.assertIn("last_applied_command_signature", command_source)
        self.assertIn("freeze_contact_finger", command_source)
        self.assertIn("maximum_center_correction_m", command_source)
        self.assertIn("drive_type=str(", command_source)

    def test_v2_rate_limit_comes_from_controller_profile(self) -> None:
        start_source = self._method_source("_start_physical_grasp_impl")
        self.assertIn('profile["max_close_velocity_m_s"]', start_source)
        self.assertIn('profile.get("max_command_lead_m"', start_source)
        rate_limit_source = self._method_source("_active_gripper_velocity_limits")
        self.assertIn("physical.max_close_velocity_m_s", rate_limit_source)
        self.assertIn("GraspPhase.RELEASING", rate_limit_source)
        limiter_source = self._method_source("_rate_limit_gripper_dofs")
        self.assertIn("rate_limit_parallel_jaw_setpoint(", limiter_source)
        self.assertIn("self._gripper_command_dofs", limiter_source)

    def test_v2_profile_uses_slow_close_with_gravity_authority(self) -> None:
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(profile["drive_type"], "force")
        self.assertLessEqual(float(profile["max_close_velocity_m_s"]), 0.01)
        lead_m = float(profile["max_command_lead_m"])
        self.assertGreaterEqual(lead_m, 0.002)
        self.assertLessEqual(lead_m, 0.004)
        minimum_authority_n = {
            "soft_close": 3.0,
            "search": 6.0,
            "hold": 9.0,
        }
        for phase, required_force in minimum_authority_n.items():
            phase_profile = profile["profiles"][phase]
            self.assertGreaterEqual(
                min(phase_profile["stiffness"]) * lead_m,
                required_force,
            )
            self.assertLessEqual(max(phase_profile["max_effort"]), 40.0)

    def test_v2_profile_closes_the_loop_on_filtered_contact_force(self) -> None:
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        force_control = profile["force_control"]
        self.assertGreater(float(force_control["target_normal_force_n"]), 0.0)
        self.assertGreater(
            float(force_control["maximum_normal_force_n"]),
            float(force_control["target_normal_force_n"]),
        )
        self.assertGreater(int(profile["contact"]["force_window_frames"]), 1)
        self.assertLessEqual(float(force_control["preload_step_m"]), 0.0001)
        self.assertLess(
            float(profile["preload"]["delta_m"]),
            float(profile["preload"]["maximum_delta_m"]),
        )
        self.assertIn("preload", profile["timeouts_s"])

    def test_v2_runtime_reports_contact_force_and_joint_load_resistance(self) -> None:
        snapshot_source = self._method_source("_physical_gripper_snapshot")
        self.assertIn("projected_joint_forces_n=", snapshot_source)
        self.assertIn("command_lag_m=", snapshot_source)
        diagnostic_source = self._method_source(
            "_update_physical_resistance_diagnostics"
        )
        self.assertIn("gripper_effort_baseline_n", diagnostic_source)
        self.assertIn("latest_effort_residual_n", diagnostic_source)
        status_source = self._method_source("_physical_grasp_status_payload")
        self.assertIn('"filtered_weak_normal_force_n"', status_source)
        self.assertIn('"force_target_reached"', status_source)
        self.assertIn('"resistance_confirmed"', status_source)
        self.assertIn('"projected_joint_force_n"', status_source)
        self.assertIn('"effective_grip_force_n"', status_source)
        self.assertIn("guarded fallback", status_source)
        advance_source = self._method_source("_advance_physical_grasp")
        self.assertIn("residual_joint_forces_n=", advance_source)

    def test_runtime_info_exposes_applied_gripper_setpoint(self) -> None:
        source = self._method_source("_get_robot_info_impl")
        self.assertIn('"gripper_command_dofs": gripper_command_dofs', source)

    def test_v2_aborts_if_target_dynamic_flags_are_mutated(self) -> None:
        source = self._method_source("_advance_physical_grasp")
        self.assertIn("operation.initial_target_physics_state", source)
        self.assertIn("target_physics_state_mutated", source)

    def test_v2_discovers_and_audits_target_after_bilateral_contact(self) -> None:
        start_source = self._method_source("_start_physical_grasp_impl")
        self.assertNotIn("target_body_path", start_source.split(") ->", 1)[0])
        advance_source = self._method_source("_advance_physical_grasp")
        self.assertIn("if discovered_path and not operation.target_body_path", advance_source)
        self.assertIn("_validate_physical_grasp_target(discovered_path)", advance_source)
        contact_source = self._method_source("_physical_contact_snapshot")
        self.assertNotIn("requested_target_body_path", contact_source)

    def test_v2_treats_ground_and_tables_as_non_candidate_support_contacts(self) -> None:
        source = self._method_source("_physical_contact_snapshot")
        self.assertIn('"/World/GroundPlane"', source)
        self.assertIn('"/World/Table"', source)
        self.assertIn("support_seeds.append(path)", source)
        self.assertNotIn("blocker_seeds.append(path)", source)
        self.assertIn('"A1Z_PHYSICAL_GRASP_SUPPORT_BODY_PATHS"', source)
        self.assertIn("support_body_paths=support_paths", source)

    def test_v2_keeps_explicit_hazards_separate_and_reports_support_contact(self) -> None:
        contact_source = self._method_source("_physical_contact_snapshot")
        self.assertIn('"A1Z_PHYSICAL_GRASP_BLOCKING_BODY_PATHS"', contact_source)
        self.assertIn("blocking_body_paths=blocking_paths", contact_source)
        status_source = self._method_source("_physical_grasp_status_payload")
        self.assertIn('"support_body_paths": list(contacts.support_body_paths)', status_source)
        self.assertIn('"support_contact_present": bool(', status_source)

    def test_v2_precheck_uses_separate_lead_and_wrist_velocity_limits(self) -> None:
        source = self._method_source("_physical_arm_is_stable")
        self.assertIn("arm_vel[:4]", source)
        self.assertIn("arm_vel[4:6]", source)
        self.assertIn("_GRASP_ATTACH_PRECHECK_MAX_WRIST_VEL_RAD_S", source)


if __name__ == "__main__":
    unittest.main()
