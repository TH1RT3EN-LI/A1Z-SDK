from __future__ import annotations

import argparse
import unittest
from unittest.mock import patch

from scripts import resolve_trash_target_prim as resolver


def _args(*, base_link_prim: str = "") -> argparse.Namespace:
    return argparse.Namespace(
        base_link_prim=base_link_prim,
        socket_path="",
        tcp_host="127.0.0.1",
        tcp_port=37103,
    )


class ResolveTrashTargetPrimTests(unittest.TestCase):
    def test_base_link_comes_from_live_articulation_root(self) -> None:
        root = "/World/A1Z_G1Z/Geometry"
        base = f"{root}/base_link"

        def prim_debug(_args: argparse.Namespace, prim_path: str) -> dict:
            if prim_path == root:
                return {"child_paths": [base]}
            if prim_path == base:
                return {"prim_path": base, "world_matrix": [[1, 0, 0, 0]] * 4}
            raise RuntimeError(f"Invalid prim path: {prim_path}")

        with (
            patch.object(
                resolver,
                "_query_robot_info",
                return_value={"articulation_root_prim": root},
            ),
            patch.object(resolver, "_query_prim_debug", side_effect=prim_debug),
        ):
            resolved_path, debug, attempts = resolver._resolve_base_link_debug(_args())

        self.assertEqual(resolved_path, base)
        self.assertEqual(debug["prim_path"], base)
        self.assertEqual(attempts, [])

    def test_stale_explicit_base_link_falls_back_to_live_root(self) -> None:
        stale = "/DOG/A1Z_PAYLOAD_MOUNT/A1Z_G1Z/Geometry/base_link"
        root = "/World/A1Z_G1Z/Geometry"
        base = f"{root}/base_link"

        def prim_debug(_args: argparse.Namespace, prim_path: str) -> dict:
            if prim_path == root:
                return {"child_paths": [base]}
            if prim_path == stale:
                raise RuntimeError(f"Invalid prim path: {prim_path}")
            if prim_path == base:
                return {"prim_path": base}
            raise AssertionError(prim_path)

        with (
            patch.object(
                resolver,
                "_query_robot_info",
                return_value={"articulation_root_prim": root},
            ),
            patch.object(resolver, "_query_prim_debug", side_effect=prim_debug),
        ):
            resolved_path, _debug, attempts = resolver._resolve_base_link_debug(
                _args(base_link_prim=stale)
            )

        self.assertEqual(resolved_path, base)
        self.assertEqual(attempts[0]["prim_path"], stale)
        self.assertIn("Invalid prim path", attempts[0]["error"])

    def test_marker_hint_accepts_semantic_root_and_legacy_asset_name(self) -> None:
        self.assertEqual(
            resolver._hinted_prim_names("marker_upright"),
            ("marker_upright", "large_marker"),
        )
        self.assertIn("marker_upright", resolver.DEFAULT_CANDIDATE_IDS)


if __name__ == "__main__":
    unittest.main()
