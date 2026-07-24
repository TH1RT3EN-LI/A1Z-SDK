"""Isaac runtime adapters used by the A1Z runtime migration.

The native Isaac 6 adapter deliberately exposes the small interface that the
bridge needs while implementing it only with public Kit 110 APIs.  Imports of
Isaac modules happen after ``SimulationApp`` has started.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


NATIVE_ISAAC6_PROFILE = "native_6_0"


def is_native_isaac6_profile(profile: str | None) -> bool:
    return str(profile or "").strip().lower() == NATIVE_ISAAC6_PROFILE


def configured_isaac_api_profile() -> str:
    """Return the A1Z-owned profile, accepting the Paw variable for mounting."""
    import os

    return (
        os.environ.get("A1Z_ISAAC_API_PROFILE")
        or os.environ.get("PAW_ISAAC_API_PROFILE")
        or NATIVE_ISAAC6_PROFILE
    ).strip().lower()


def _numpy(values: Any) -> np.ndarray:
    if hasattr(values, "numpy"):
        values = values.numpy()
    return np.asarray(values)


def _single_row(values: Any, *, dtype=np.float32) -> np.ndarray:
    array = _numpy(values).astype(dtype, copy=False)
    if array.ndim > 1 and array.shape[0] == 1:
        array = array[0]
    return array


def _dedupe_paths(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _normalize_contact_filters(
    sensor_paths: list[str],
    expression: Any | None,
) -> tuple[list[str], list[tuple[str, ...]]]:
    """Separate flat filters from legacy per-sensor shared-filter groups."""
    if expression is None:
        return [], []
    if isinstance(expression, str):
        return [expression], []
    pending = list(expression)
    if not pending:
        return [], []
    if all(isinstance(value, str) for value in pending):
        return _dedupe_paths(pending), []
    if len(pending) != len(sensor_paths):
        raise ValueError(
            "nested contact filters must provide one filter group per sensor: "
            f"sensors={len(sensor_paths)} groups={len(pending)}"
        )
    groups = [
        tuple(_dedupe_paths([value] if isinstance(value, str) else value))
        for value in pending
    ]
    if any(group != groups[0] for group in groups[1:]):
        raise ValueError("Isaac 6 contact adapter requires the same filter group for every sensor")
    return [], groups


def _merge_contact_force_data(
    datasets: list[tuple[Any, Any, Any, Any, Any, Any]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Merge one detailed-contact tensor dataset per sensor into one view-shaped result."""
    if not datasets:
        raise ValueError("contact-force datasets cannot be empty")
    forces_parts: list[np.ndarray] = []
    points_parts: list[np.ndarray] = []
    normals_parts: list[np.ndarray] = []
    distances_parts: list[np.ndarray] = []
    count_rows: list[np.ndarray] = []
    start_rows: list[np.ndarray] = []
    data_offset = 0
    filter_count: int | None = None
    for dataset in datasets:
        if len(dataset) != 6:
            raise ValueError("contact-force dataset must contain six arrays")
        forces = _numpy(dataset[0]).reshape(-1, 1)
        points = _numpy(dataset[1]).reshape(-1, 3)
        normals = _numpy(dataset[2]).reshape(-1, 3)
        distances = _numpy(dataset[3]).reshape(-1, 1)
        counts = _numpy(dataset[4]).reshape(1, -1)
        starts = _numpy(dataset[5]).reshape(1, -1).copy()
        if filter_count is None:
            filter_count = int(counts.shape[1])
        elif counts.shape[1] != filter_count:
            raise ValueError(
                "contact-force datasets have inconsistent filter counts: "
                f"expected={filter_count} actual={counts.shape[1]}"
            )
        starts += data_offset
        forces_parts.append(forces)
        points_parts.append(points)
        normals_parts.append(normals)
        distances_parts.append(distances)
        count_rows.append(counts)
        start_rows.append(starts)
        data_offset += int(forces.shape[0])
    return (
        np.concatenate(forces_parts, axis=0),
        np.concatenate(points_parts, axis=0),
        np.concatenate(normals_parts, axis=0),
        np.concatenate(distances_parts, axis=0),
        np.concatenate(count_rows, axis=0),
        np.concatenate(start_rows, axis=0),
    )


@dataclass(slots=True)
class A1ZArticulationCommand:
    joint_positions: Any | None = None
    joint_velocities: Any | None = None
    joint_efforts: Any | None = None
    joint_indices: Any | None = None


class Isaac6PhysicsContextAdapter:
    """Read the public PhysX scene contract required by contact validation."""

    @staticmethod
    def _physx_scene():
        from isaacsim.core.simulation_manager import SimulationManager

        scenes = SimulationManager.get_physics_scenes()
        if not scenes:
            raise RuntimeError("Isaac 6 has no registered PhysicsScene")
        for scene in scenes:
            if hasattr(scene, "get_enabled_stabilization"):
                return scene
        raise RuntimeError("Isaac 6 has no public PhysX scene wrapper")

    def is_stablization_enabled(self) -> bool:
        # Preserve the misspelled legacy call surface at the bridge boundary;
        # the value comes from the public Kit 110 PhysxScene wrapper.
        return bool(self._physx_scene().get_enabled_stabilization())


class Isaac6WorldView:
    """Minimal live-world contract for a Kit-owned async application loop."""

    def reset(self) -> None:
        # The caller owns stage/timeline initialization. This adapter only
        # supplies authoritative live timing and PhysicsScene readback.
        return None

    def get_physics_dt(self) -> float:
        from isaacsim.core.simulation_manager import SimulationManager

        scenes = SimulationManager.get_physics_scenes()
        if not scenes:
            raise RuntimeError("Isaac 6 has no registered PhysicsScene")
        dt = float(scenes[0].get_dt())
        if not np.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"Isaac 6 reported invalid physics dt: {dt!r}")
        return dt

    def get_physics_context(self) -> Isaac6PhysicsContextAdapter:
        return Isaac6PhysicsContextAdapter()


class Isaac6ArticulationAdapter:
    """Legacy-shaped facade over the public experimental Articulation API."""

    def __init__(self, prim_path: str, name: str | None = None) -> None:
        del name
        from isaacsim.core.experimental.prims import Articulation, RigidPrim

        self.prim_path = str(prim_path)
        self._view = Articulation(self.prim_path)
        link_paths = list(self._view.link_paths[0])
        self._link_view = RigidPrim(link_paths)

    @property
    def dof_names(self) -> tuple[str, ...]:
        return tuple(str(name) for name in self._view.dof_names)

    @property
    def link_names(self) -> tuple[str, ...]:
        return tuple(str(name) for name in self._view.link_names)

    @property
    def body_names(self) -> tuple[str, ...]:
        return self.link_names

    def initialize(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        if not self._view.valid:
            raise RuntimeError(f"invalid Isaac 6 articulation: {self.prim_path}")

    def is_valid(self) -> bool:
        return bool(self._view.valid)

    def author_initial_root_height(self, height: float) -> None:
        """Set a coherent root pose in USD before physics builds the link tree."""
        import isaacsim.core.experimental.utils.backend as backend_utils
        from isaacsim.core.experimental.prims import XformPrim

        path_parts = [part for part in self.prim_path.split("/") if part]
        if not path_parts:
            raise RuntimeError(f"cannot derive robot container from {self.prim_path!r}")
        robot_container = XformPrim(
            "/" + path_parts[0],
            reset_xform_op_properties=True,
        )

        with backend_utils.use_backend(
            "usd",
            raise_on_unsupported=True,
            raise_on_fallback=True,
        ):
            positions, orientations = robot_container.get_world_poses()
            positions = _numpy(positions).astype(np.float32, copy=True)
            orientations = _numpy(orientations).astype(np.float32, copy=True)
            positions[:, 2] = float(height)
            robot_container.set_world_poses(positions=positions, orientations=orientations)

    def is_physics_tensor_entity_valid(self) -> bool:
        return bool(self._view.is_physics_tensor_entity_valid())

    def get_link_state_view(self):
        return self

    def get_link_transforms(self) -> np.ndarray:
        positions, orientations_wxyz = self._link_view.get_world_poses()
        positions = _numpy(positions).astype(np.float32, copy=False)
        orientations_wxyz = _numpy(orientations_wxyz).astype(np.float32, copy=False)
        orientations_xyzw = orientations_wxyz[:, [1, 2, 3, 0]]
        return np.concatenate((positions, orientations_xyzw), axis=1)[None, :, :]

    def get_link_velocities(self) -> np.ndarray:
        linear, angular = self._link_view.get_velocities()
        values = np.concatenate(
            (
                _numpy(linear).astype(np.float32, copy=False),
                _numpy(angular).astype(np.float32, copy=False),
            ),
            axis=1,
        )
        return values[None, :, :]

    def get_joint_positions(self) -> np.ndarray:
        return _single_row(self._view.get_dof_positions())

    def get_joint_velocities(self) -> np.ndarray:
        return _single_row(self._view.get_dof_velocities())

    def get_joint_position_targets(self) -> np.ndarray:
        return _single_row(self._view.get_dof_position_targets())

    def get_measured_joint_efforts(self) -> np.ndarray:
        return _single_row(self._view.get_dof_projected_joint_forces())

    @property
    def dof_properties(self) -> dict[str, np.ndarray]:
        lower_limits, upper_limits = self._view.get_dof_limits()
        stiffnesses, dampings = self.get_gains()
        return {
            "lower": _single_row(lower_limits),
            "upper": _single_row(upper_limits),
            "stiffness": stiffnesses,
            "damping": dampings,
        }

    def set_joint_positions(self, values: Any, joint_indices: Any | None = None) -> None:
        indices = self._dof_indices(joint_indices)
        self._view.set_dof_positions(values, dof_indices=indices)

    def set_joint_velocities(self, values: Any, joint_indices: Any | None = None) -> None:
        indices = self._dof_indices(joint_indices)
        self._view.set_dof_velocities(values, dof_indices=indices)

    def set_joint_efforts(self, values: Any, joint_indices: Any | None = None) -> None:
        indices = self._dof_indices(joint_indices)
        self._view.set_dof_efforts(values, dof_indices=indices)

    def get_world_pose(self) -> tuple[np.ndarray, np.ndarray]:
        positions, orientations = self._link_view.get_world_poses(indices=[0])
        return _single_row(positions), _single_row(orientations)

    def migration_diagnostics(self) -> dict[str, Any]:
        articulation_position, articulation_orientation = self._view.get_world_poses()
        return {
            "requested_prim_path": self.prim_path,
            "resolved_articulation_paths": list(self._view.paths),
            "articulation_position": [float(value) for value in _single_row(articulation_position)],
            "articulation_orientation": [float(value) for value in _single_row(articulation_orientation)],
        }

    def set_world_pose(self, *, position: Any, orientation: Any) -> None:
        position_batch = np.asarray(position, dtype=np.float32).reshape(1, 3)
        orientation_batch = np.asarray(orientation, dtype=np.float32).reshape(1, 4)
        self._view.set_world_poses(
            positions=position_batch,
            orientations=orientation_batch,
        )

    def get_world_velocity(self) -> np.ndarray:
        linear, angular = self._link_view.get_velocities(indices=[0])
        return np.concatenate((_single_row(linear), _single_row(angular)))

    def set_linear_velocity(self, values: Any) -> None:
        velocity_batch = np.asarray(values, dtype=np.float32).reshape(1, 3)
        self._view.set_velocities(linear_velocities=velocity_batch)

    def set_angular_velocity(self, values: Any) -> None:
        velocity_batch = np.asarray(values, dtype=np.float32).reshape(1, 3)
        self._view.set_velocities(angular_velocities=velocity_batch)

    def get_articulation_controller(self):
        return self

    @staticmethod
    def _dof_indices(joint_indices: Any | None) -> list[int] | None:
        if joint_indices is None:
            return None
        return [int(value) for value in _single_row(joint_indices, dtype=np.int64)]

    def set_gains(self, *, kps: Any, kds: Any, joint_indices: Any | None = None) -> None:
        self._view.set_dof_gains(
            stiffnesses=_single_row(kps),
            dampings=_single_row(kds),
            dof_indices=self._dof_indices(joint_indices),
            update_default_gains=False,
        )

    def get_gains(self) -> tuple[np.ndarray, np.ndarray]:
        stiffnesses, dampings = self._view.get_dof_gains()
        return _single_row(stiffnesses), _single_row(dampings)

    def get_max_efforts(self) -> np.ndarray:
        return _single_row(self._view.get_dof_max_efforts())

    def set_max_efforts(self, values: Any, joint_indices: Any | None = None) -> None:
        self._view.set_dof_max_efforts(values, dof_indices=self._dof_indices(joint_indices))

    def get_effort_modes(self) -> list[str]:
        modes = self._view.get_dof_drive_types()
        return list(modes[0]) if modes else []

    def set_effort_modes(self, *, mode: str, joint_indices: Any | None = None) -> None:
        self._view.set_dof_drive_types(str(mode), dof_indices=self._dof_indices(joint_indices))

    def switch_dof_control_mode(self, *, dof_index: int, mode: str) -> None:
        index = [int(dof_index)]
        if mode == "effort":
            self.set_gains(kps=[0.0], kds=[0.0], joint_indices=index)
        elif mode == "velocity":
            _, dampings = self.get_gains()
            self.set_gains(kps=[0.0], kds=[dampings[int(dof_index)]], joint_indices=index)
        elif mode != "position":
            raise ValueError(f"unsupported DOF control mode: {mode}")

    def apply_action(self, action: A1ZArticulationCommand) -> None:
        indices = self._dof_indices(action.joint_indices)
        if action.joint_positions is not None:
            self._view.set_dof_position_targets(action.joint_positions, dof_indices=indices)
        if action.joint_velocities is not None:
            self._view.set_dof_velocity_targets(action.joint_velocities, dof_indices=indices)
        if action.joint_efforts is not None:
            self._view.set_dof_efforts(action.joint_efforts, dof_indices=indices)


class Isaac6RigidPrimAdapter:
    """Legacy-shaped rigid-body/contact facade over public Isaac 6 RigidPrim."""

    def __init__(
        self,
        prim_paths_expr: str | list[str],
        name: str | None = None,
        reset_xform_properties: bool = False,
        contact_filter_prim_paths_expr: Any | None = None,
        prepare_contact_sensors: bool = False,
        disable_stablization: bool = False,
        max_contact_count: int = 0,
    ) -> None:
        del name, reset_xform_properties, prepare_contact_sensors, disable_stablization
        from isaacsim.core.experimental.prims import RigidPrim

        paths = [prim_paths_expr] if isinstance(prim_paths_expr, str) else list(prim_paths_expr)
        flat_filters, per_sensor_filter_groups = _normalize_contact_filters(
            paths,
            contact_filter_prim_paths_expr,
        )
        self._contact_views: list[Any] = []
        if per_sensor_filter_groups:
            # Kit 110 treats a flat filter list whose length matches the sensor
            # count as one filter per sensor. The legacy bridge supplies nested
            # groups to mean "all filters for both fingers", so retain one
            # public RigidPrim contact view per finger and merge their tensors.
            self._view = RigidPrim(paths)
            self._contact_views = [
                RigidPrim(
                    [sensor_path],
                    contact_filter_paths=list(filter_group) or None,
                    max_contact_count=int(max_contact_count),
                )
                for sensor_path, filter_group in zip(paths, per_sensor_filter_groups)
            ]
        else:
            self._view = RigidPrim(
                paths,
                contact_filter_paths=flat_filters or None,
                max_contact_count=int(max_contact_count),
            )

    def is_physics_handle_valid(self) -> bool:
        return bool(
            self._view.is_physics_tensor_entity_valid()
            and all(view.is_physics_tensor_entity_valid() for view in self._contact_views)
        )

    def initialize(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        if not self.is_physics_handle_valid():
            raise RuntimeError("invalid Isaac 6 rigid-body physics tensor view")

    def get_world_poses(self, clone: bool = True):
        del clone
        return self._view.get_world_poses()

    def get_contact_force_data(self, dt: float = 1.0):
        if self._contact_views:
            return _merge_contact_force_data(
                [
                    view.get_contact_force_data(dt=float(dt))
                    for view in self._contact_views
                ]
            )
        return self._view.get_contact_force_data(dt=float(dt))

    def get_contact_force_matrix(self, dt: float = 1.0):
        if self._contact_views:
            return np.concatenate(
                [
                    _numpy(view.get_contact_force_matrix(dt=float(dt)))
                    for view in self._contact_views
                ],
                axis=0,
            )
        return self._view.get_contact_force_matrix(dt=float(dt))

    def get_net_contact_forces(self, dt: float = 1.0):
        if self._contact_views:
            return np.concatenate(
                [
                    _numpy(view.get_net_contact_forces(dt=float(dt)))
                    for view in self._contact_views
                ],
                axis=0,
            )
        return self._view.get_net_contact_forces(dt=float(dt))


async def open_stage_async(usd_path: str) -> tuple[bool, Any]:
    import isaacsim.core.experimental.utils.stage as stage_utils

    return await stage_utils.open_stage_async(usd_path)


def prepare_contact_tracking(paths: list[str], *, threshold: float = 0.0) -> None:
    """Author contact-report schemas before the physics tensor view is built."""
    from isaacsim.core.experimental.prims import RigidPrim

    prims = RigidPrim(list(paths))
    prims.set_enabled_contact_tracking([True], threshold=float(threshold))
