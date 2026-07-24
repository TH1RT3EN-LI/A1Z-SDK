#!/usr/bin/env python3

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from a1z_ext.robots.isaac6_backend import (
    Isaac6RigidPrimAdapter,
    _merge_contact_force_data,
    _normalize_contact_filters,
)


class Isaac6ContactAdapterTests(unittest.TestCase):
    def test_nested_contact_filters_remain_shared_by_both_fingers(self) -> None:
        sensors = ["/Robot/left_finger", "/Robot/right_finger"]
        filters = ["/World/Target", "/World/Ground"]
        flat, groups = _normalize_contact_filters(sensors, [filters, filters])
        self.assertEqual(flat, [])
        self.assertEqual(groups, [tuple(filters), tuple(filters)])

    def test_per_finger_contact_data_merges_to_sensor_filter_matrix(self) -> None:
        def dataset(counts: list[int], starts: list[int], force: float):
            return (
                np.asarray([[force], [0.0]], dtype=np.float32),
                np.zeros((2, 3), dtype=np.float32),
                np.asarray([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float32),
                np.zeros((2, 1), dtype=np.float32),
                np.asarray([counts], dtype=np.uint32),
                np.asarray([starts], dtype=np.uint32),
            )

        merged = _merge_contact_force_data(
            [
                dataset([1, 0], [0, 0], 0.4),
                dataset([0, 1], [0, 0], 0.6),
            ]
        )
        self.assertEqual(merged[4].shape, (2, 2))
        np.testing.assert_array_equal(merged[4], [[1, 0], [0, 1]])
        np.testing.assert_array_equal(merged[5], [[0, 0], [2, 2]])
        self.assertEqual(merged[0].shape, (4, 1))

    def test_adapter_builds_one_shared_filter_view_per_finger(self) -> None:
        created: list[dict] = []

        class FakeRigidPrim:
            def __init__(
                self,
                paths,
                *,
                contact_filter_paths=None,
                max_contact_count=0,
            ) -> None:
                created.append(
                    {
                        "paths": list(paths),
                        "filters": contact_filter_paths,
                        "max_contact_count": max_contact_count,
                    }
                )

            def is_physics_tensor_entity_valid(self) -> bool:
                return True

        isaacsim = types.ModuleType("isaacsim")
        core = types.ModuleType("isaacsim.core")
        experimental = types.ModuleType("isaacsim.core.experimental")
        prims = types.ModuleType("isaacsim.core.experimental.prims")
        prims.RigidPrim = FakeRigidPrim
        modules = {
            "isaacsim": isaacsim,
            "isaacsim.core": core,
            "isaacsim.core.experimental": experimental,
            "isaacsim.core.experimental.prims": prims,
        }
        filters = ["/World/Target", "/World/Ground"]
        with patch.dict(sys.modules, modules):
            adapter = Isaac6RigidPrimAdapter(
                ["/Robot/left_finger", "/Robot/right_finger"],
                contact_filter_prim_paths_expr=[filters, filters],
                max_contact_count=128,
            )
        self.assertTrue(adapter.is_physics_handle_valid())
        self.assertEqual(len(created), 3)
        self.assertIsNone(created[0]["filters"])
        self.assertEqual(created[1]["filters"], filters)
        self.assertEqual(created[2]["filters"], filters)


if __name__ == "__main__":
    unittest.main()
