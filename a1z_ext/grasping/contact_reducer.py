from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

from .physical_types import ContactSnapshot


def _matches_path(candidate: str, expected: str) -> bool:
    return candidate == expected or candidate.startswith(expected.rstrip("/") + "/")


def _counterpart(record: Mapping[str, object], sensor_body_path: str) -> str:
    body0 = str(record.get("body0", "") or "")
    body1 = str(record.get("body1", "") or "")
    if _matches_path(body0, sensor_body_path):
        return body1
    if _matches_path(body1, sensor_body_path):
        return body0
    return ""


def _vector_magnitude(value: object) -> float:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 3:
        return 0.0
    vector = [float(value[index]) for index in range(3)]
    if not all(math.isfinite(component) for component in vector):
        return 0.0
    return math.sqrt(sum(component * component for component in vector))


def _reduce_side(
    records: Iterable[Mapping[str, object]],
    *,
    sensor_body_path: str,
    target_body_path: str,
    blocking_body_paths: tuple[str, ...],
    support_body_paths: tuple[str, ...],
    physics_dt_s: float,
) -> tuple[tuple[str, ...], tuple[tuple[str, float], ...], float | None, bool, str | None]:
    bodies: set[str] = set()
    force_by_body: dict[str, float] = {}
    blocked = False
    blocking_reason: str | None = None
    for record in records:
        counterpart = _counterpart(record, sensor_body_path)
        if not counterpart:
            continue
        if target_body_path and _matches_path(counterpart, target_body_path):
            canonical_body = target_body_path
        else:
            canonical_body = next(
                (
                    support
                    for support in support_body_paths
                    if _matches_path(counterpart, support)
                ),
                counterpart,
            )
        bodies.add(canonical_body)
        force_by_body[canonical_body] = (
            force_by_body.get(canonical_body, 0.0)
            + _vector_magnitude(record.get("impulse")) / physics_dt_s
        )
        for blocker in blocking_body_paths:
            if _matches_path(counterpart, blocker):
                blocked = True
                blocking_reason = f"blocking_contact:{blocker}"
                break
    forces = tuple(sorted(force_by_body.items()))
    target_force = force_by_body.get(target_body_path) if target_body_path else None
    return tuple(sorted(bodies)), forces, target_force, blocked, blocking_reason


def reduce_contact_impulses(
    *,
    left_records: Iterable[Mapping[str, object]],
    right_records: Iterable[Mapping[str, object]],
    left_finger_body_path: str,
    right_finger_body_path: str,
    target_body_path: str = "",
    physics_dt_s: float,
    blocking_body_paths: Iterable[str] = (),
    support_body_paths: Iterable[str] = (),
) -> ContactSnapshot:
    """Reduce contact impulses for explicit-target or targetless physical grasping."""

    if target_body_path and not target_body_path.startswith("/"):
        raise ValueError("target_body_path must be an absolute prim path")
    if not left_finger_body_path or not right_finger_body_path:
        raise ValueError("left and right finger body paths are required")
    dt = float(physics_dt_s)
    if not math.isfinite(dt) or dt <= 0.0 or dt > 1.0:
        raise ValueError("physics_dt_s must be finite and within (0, 1]")
    blockers = tuple(str(path) for path in blocking_body_paths if str(path))
    supports = tuple(str(path) for path in support_body_paths if str(path))
    left_bodies, left_forces, left_force, left_blocked, left_reason = _reduce_side(
        left_records,
        sensor_body_path=left_finger_body_path,
        target_body_path=target_body_path,
        blocking_body_paths=blockers,
        support_body_paths=supports,
        physics_dt_s=dt,
    )
    right_bodies, right_forces, right_force, right_blocked, right_reason = _reduce_side(
        right_records,
        sensor_body_path=right_finger_body_path,
        target_body_path=target_body_path,
        blocking_body_paths=blockers,
        support_body_paths=supports,
        physics_dt_s=dt,
    )
    return ContactSnapshot(
        left_body_paths=left_bodies,
        right_body_paths=right_bodies,
        left_normal_force_n=left_force,
        right_normal_force_n=right_force,
        left_force_by_body_n=left_forces,
        right_force_by_body_n=right_forces,
        support_body_paths=tuple(sorted(set(supports))),
        left_blocked=left_blocked,
        right_blocked=right_blocked,
        blocking_reason=left_reason or right_reason,
    )
