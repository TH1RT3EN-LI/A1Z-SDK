from __future__ import annotations

import unittest
from types import SimpleNamespace

from a1z_sdk import (
    A1ZClient,
    A1ZCommandRejected,
    A1ZCommandSuperseded,
    A1ZCommandUnverified,
    CommandResult,
    ControlMode,
    Endpoint,
)
from a1z_sdk._transport import JsonLineTransport
from a1z_sdk.cli import build_parser
from a1z_sdk.telemetry import read_telemetry


class FakeTransport:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict, float | None]] = []

    def request(self, command, arguments=None, *, timeout_s=None):
        self.calls.append((command, dict(arguments or {}), timeout_s))
        return dict(self.responses[command])


class PublicSdkTests(unittest.TestCase):
    def test_status_is_measured_and_typed(self) -> None:
        transport = FakeTransport(
            {
                "status": {
                    "pos_deg": [0, 60, -60, 0, 0, 0],
                    "vel_rad_s": [0, 0, 0, 0, 0, 0],
                    "torque_nm": [1, 2, 3, 4, 5, 6],
                    "running": True,
                    "faulted": False,
                    "control_mode": "position_hold",
                    "gravity_comp_factor": 0.3,
                    "gripper_target": 0.5,
                    "gripper_measured": 0.48,
                }
            }
        )
        client = A1ZClient(Endpoint(), transport=transport)

        state = client.status()

        self.assertEqual(state.position_deg, (0, 60, -60, 0, 0, 0))
        self.assertTrue(state.running)
        self.assertEqual(state.control_mode, ControlMode.POSITION_HOLD)
        self.assertEqual(state.gravity_comp_factor, 0.3)
        self.assertEqual(state.gripper_target, 0.5)
        self.assertEqual(state.gripper_measured, 0.48)
        self.assertEqual(transport.calls, [("status", {}, None)])

    def test_verified_move_uses_blocking_service_command(self) -> None:
        transport = FakeTransport(
            {
                "move": {
                    "completion": "feedback_verified",
                    "verification": {"reached": True},
                }
            }
        )
        client = A1ZClient(Endpoint(), transport=transport)

        result = client.move_joints([0, 60, -60, 0, 0, 0], speed_rad_s=0.4)

        self.assertIsInstance(result, CommandResult)
        self.assertTrue(result.feedback_verified)
        self.assertEqual(transport.calls[0][0], "move")
        self.assertEqual(transport.calls[0][1]["speed"], 0.4)
        self.assertEqual(transport.calls[0][1]["timeout_s"], 120.0)
        self.assertEqual(transport.calls[0][2], 122.0)

    def test_target_submission_is_async_and_carries_motion_parameters(self) -> None:
        transport = FakeTransport(
            {
                "command": {
                    "accepted": True,
                    "goal_id": 7,
                    "completion": "accepted",
                }
            }
        )
        client = A1ZClient(Endpoint(), transport=transport)

        result = client.set_joint_target(
            [0, 60, -60, 0, 0, 0],
            speed_rad_s=0.3,
            timeout_s=45.0,
        )

        self.assertFalse(result.feedback_verified)
        self.assertEqual(result.completion, "accepted")
        self.assertEqual(result.data["goal_id"], 7)
        self.assertEqual(transport.calls[0][0], "command")
        self.assertEqual(transport.calls[0][1]["speed"], 0.3)
        self.assertEqual(transport.calls[0][1]["timeout_s"], 45.0)

    def test_control_modes_are_exactly_mutually_exclusive(self) -> None:
        transport = FakeTransport(
            {
                "gravity_mode": {
                    "control_mode": ControlMode.POSITION_HOLD.value,
                }
            }
        )
        client = A1ZClient(Endpoint(), transport=transport)

        client.set_control_mode("hold")
        self.assertEqual(
            transport.calls[-1][1],
            {"enabled": False},
        )
        client.set_control_mode(ControlMode.ZERO_FORCE)
        self.assertEqual(
            transport.calls[-1][1],
            {"enabled": True},
        )

    def test_wire_errors_preserve_safety_relevant_execution_state(self) -> None:
        with self.assertRaises(A1ZCommandRejected):
            JsonLineTransport._decode(
                "move",
                {
                    "ok": False,
                    "execution_state": "rejected",
                    "error": "wrong mode",
                },
            )

        with self.assertRaises(A1ZCommandUnverified) as caught:
            JsonLineTransport._decode(
                "move",
                {
                    "ok": False,
                    "execution_state": "submitted_unverified",
                    "error": "feedback timeout",
                    "data": {"verification": {"reached": False}},
                },
            )
        self.assertEqual(caught.exception.command, "move")
        self.assertIn("verification", caught.exception.data)

        with self.assertRaises(A1ZCommandSuperseded) as superseded:
            JsonLineTransport._decode(
                "move",
                {
                    "ok": False,
                    "execution_state": "superseded",
                    "error": "newer target accepted",
                    "data": {"goal_id": 4, "replacement_goal_id": 5},
                },
            )
        self.assertEqual(superseded.exception.data["replacement_goal_id"], 5)

    def test_new_cli_exposes_real_service_without_backend_selector(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--with-gripper"])

        self.assertEqual(args.command, "serve")
        self.assertFalse(hasattr(args, "backend"))
        self.assertEqual(args.start_mode, "hold")
        self.assertTrue(args.with_gripper)

    def test_gui_telemetry_uses_the_public_measured_state(self) -> None:
        class StubClient:
            def status(self):
                return SimpleNamespace(
                    raw={
                        "pos_deg": [1, 2, 3, 4, 5, 6],
                        "running": True,
                        "faulted": False,
                    }
                )

        payload = read_telemetry(StubClient(), sequence=7)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sequence"], 7)
        self.assertEqual(payload["data"]["pos_deg"], [1, 2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main()
