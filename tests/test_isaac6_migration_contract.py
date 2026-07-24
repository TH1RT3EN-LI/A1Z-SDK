from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


class Isaac6MigrationContractTest(unittest.TestCase):
    def test_standalone_and_mounted_configs_are_explicit(self) -> None:
        standalone = _read_env(ROOT / "config" / "a1z_isaac6_standalone.env")
        mounted = _read_env(ROOT / "config" / "a1z_isaac6_paw_mounted.env")

        for config in (standalone, mounted):
            self.assertEqual(config["A1Z_ISAAC_API_PROFILE"], "native_6_0")
            self.assertEqual(config["A1Z_ISAAC_CONTROL_FREQ_HZ"], "60")
            self.assertEqual(config["A1Z_ISAAC_MIRROR_DRIVE_TARGETS_TO_USD"], "0")
            self.assertEqual(config["A1Z_TCP_HOST"], "127.0.0.1")
            self.assertEqual(config["A1Z_TCP_PORT"], "37103")
            self.assertEqual(config["A1Z_SOCKET_PATH"], "")
            self.assertEqual(config["A1Z_D405_FALLBACK_PARENT_PRIM"], "")
            self.assertEqual(config["A1Z_D405_WIDTH"], "320")
            self.assertEqual(config["A1Z_D405_HEIGHT"], "240")
            self.assertEqual(config["A1Z_D405_CAPTURE_HZ"], "10")
            self.assertEqual(config["A1Z_ANYGRASP_GRASP_MODE"], "physical_v2")

        self.assertEqual(
            standalone["A1Z_ISAAC_ARTICULATION_ROOT"],
            "/World/A1Z_G1Z/Geometry",
        )
        self.assertEqual(
            mounted["A1Z_ISAAC_ARTICULATION_ROOT"],
            "/DOG/Geometry/BASE_LINK",
        )
        self.assertEqual(
            mounted["A1Z_ISAAC_ASSET_GEOMETRY_ROOT"],
            "/DOG/A1Z_PAYLOAD_MOUNT/A1Z_G1Z/Geometry",
        )

    def test_native_adapter_has_no_paw_module_dependency(self) -> None:
        source = (ROOT / "a1z_ext" / "robots" / "isaacsim_robot.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("paw_isaac_runtime_backend", imported_modules)
        self.assertIn("a1z_ext.robots.isaac6_backend", imported_modules)
        self.assertIn("configured_isaac_api_profile() == \"native_6_0\"", source)

    def test_physical_profile_matches_parallel_jaw_contract(self) -> None:
        profile = json.loads(
            (
                ROOT
                / "config"
                / "grasping"
                / "controllers"
                / "a1z_physical_gripper_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(profile["schema_version"], 1)
        self.assertEqual(
            profile["joint_names"],
            ["gripper_finger_left_joint", "gripper_finger_rIght_joint"],
        )
        self.assertEqual(profile["open_dofs_m"], [0.048, -0.048])
        self.assertEqual(profile["closed_dofs_m"], [0.0, 0.0])
        self.assertEqual(profile["drive_type"], "force")
        self.assertEqual(profile["max_close_velocity_m_s"], 0.006)
        self.assertEqual(profile["max_command_lead_m"], 0.003)
        self.assertEqual(profile["profiles"]["soft_close"]["stiffness"], [1000.0, 1000.0])
        self.assertEqual(profile["profiles"]["search"]["stiffness"], [2000.0, 2000.0])
        self.assertEqual(profile["profiles"]["hold"]["stiffness"], [3000.0, 3000.0])
        self.assertEqual(profile["profiles"]["hold"]["damping"], [80.0, 80.0])
        self.assertEqual(profile["profiles"]["hold"]["max_effort"], [30.0, 30.0])
        self.assertEqual(profile["preload"]["delta_m"], 0.0005)
        self.assertEqual(profile["preload"]["maximum_delta_m"], 0.008)
        self.assertEqual(profile["force_control"]["target_normal_force_n"], 2.0)
        self.assertEqual(profile["force_control"]["maximum_normal_force_n"], 12.0)
        self.assertEqual(profile["force_control"]["preload_step_m"], 0.00008)
        self.assertEqual(profile["force_control"]["unilateral_recovery_timeout_s"], 1.2)
        self.assertTrue(profile["contact"]["require_bilateral"])
        self.assertEqual(profile["contact"]["minimum_normal_force_n"], 0.05)
        self.assertEqual(profile["timeouts_s"]["precheck"], 3.0)
        self.assertEqual(profile["timeouts_s"]["preload"], 3.0)

    def test_native_contact_adapter_preserves_shared_filter_groups(self) -> None:
        source = (
            ROOT / "a1z_ext" / "robots" / "isaac6_backend.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _normalize_contact_filters(", source)
        self.assertIn("self._contact_views = [", source)
        self.assertIn("def _merge_contact_force_data(", source)
        self.assertIn("starts += data_offset", source)

    def test_generated_isaac6_asset_matches_gripper_profile(self) -> None:
        physics = (
            ROOT
            / "build"
            / "scenes"
            / "A1Z_G1Z_isaac"
            / "payloads"
            / "Physics"
            / "physics.usda"
        ).read_text(encoding="utf-8")
        self.assertIn('def PhysicsPrismaticJoint "gripper_finger_left_joint"', physics)
        self.assertIn('def PhysicsPrismaticJoint "gripper_finger_rIght_joint"', physics)
        self.assertIn("float physics:upperLimit = 0.048", physics)
        self.assertIn("float physics:lowerLimit = -0.048", physics)
        self.assertEqual(physics.count("float physics:mass = 0.02"), 2)
        self.assertEqual(physics.count("float drive:linear:physics:maxForce = 120"), 2)
        self.assertIn('def Material "A1ZGripperPad"', physics)
        self.assertIn("float physics:staticFriction = 2", physics)
        self.assertIn("float physics:dynamicFriction = 1.5", physics)
        self.assertIn('token physxMaterial:frictionCombineMode = "max"', physics)
        self.assertEqual(
            physics.count(
                "rel material:binding:physics = "
                "</A1Z_G1Z/PhysicsMaterials/A1ZGripperPad>"
            ),
            2,
        )
        self.assertNotIn("/TrashSet/", physics)

    def test_runtime_reapplies_gripper_pad_material_before_physical_grasp(self) -> None:
        source = (
            ROOT / "a1z_ext" / "robots" / "isaacsim_robot.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _ensure_gripper_pad_physics_material(", source)
        self.assertIn('CreateFrictionCombineModeAttr().Set("max")', source)
        self.assertIn("_GRIPPER_PAD_STATIC_FRICTION = 2.0", source)
        self.assertIn("_GRIPPER_PAD_DYNAMIC_FRICTION = 1.5", source)
        self.assertIn(
            "Physical grasp requires high-friction material bindings on both finger",
            source,
        )

    def test_arm_position_loop_uses_torque_limited_force_drives(self) -> None:
        defaults = json.loads(
            (ROOT / "a1z_ext" / "config" / "control_defaults.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(defaults["isaacsim"]["arm_drive_type"], "force")

        physics = (
            ROOT
            / "build"
            / "scenes"
            / "A1Z_G1Z_isaac"
            / "payloads"
            / "Physics"
            / "physics.usda"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            physics.count('drive:angular:physics:type = "force"'),
            6,
        )

        startup = (
            ROOT / "scripts" / "open_a1z_world_with_a1z_sdk.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _configure_arm_joint_physics", startup)
        self.assertIn('isaac_cfg.get("arm_drive_type", "force")', startup)
        self.assertIn("math.radians(float(stiffness))", startup)

        importer = (
            ROOT / "scripts" / "import_a1z_g1z_to_usd.py"
        ).read_text(encoding="utf-8")
        self.assertIn('if drive_type == "angular":', importer)
        self.assertIn("stiffness = math.radians(float(stiffness))", importer)

    def test_physical_execution_does_not_default_to_attachment(self) -> None:
        source = (ROOT / "scripts" / "execute_a1z_plan.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('grasp_mode == "physical_v2"', source)
        self.assertIn('"grasp_close_v2"', source)
        self.assertIn('"grasp_status_v2"', source)
        self.assertIn('"grasp_release_v2"', source)

    def test_d405_native_path_uses_one_camera_sensor_for_rgbd(self) -> None:
        source = (
            ROOT / "a1z_ext" / "runtime" / "d405" / "session.py"
        ).read_text(encoding="utf-8")
        self.assertIn("CameraSensor", source)
        self.assertIn('annotators=["rgb", "distance_to_image_plane"]', source)
        self.assertIn("token_after != token_before", source)
        self.assertIn("configured_isaac_api_profile() == \"native_6_0\"", source)


if __name__ == "__main__":
    unittest.main()
