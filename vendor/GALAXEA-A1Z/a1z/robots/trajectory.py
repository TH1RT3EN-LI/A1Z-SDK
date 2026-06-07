"""Shared trajectory and recording helpers for robot backends."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence, Tuple

import numpy as np

Trajectory = List[Tuple[float, np.ndarray]]


def save_trajectory(trajectory: Trajectory, path: str) -> None:
    """Save a trajectory to a JSON file."""
    data = {
        "version": 1,
        "num_joints": len(trajectory[0][1]) if trajectory else 6,
        "frames": [[t, pos.tolist()] for t, pos in trajectory],
    }
    Path(path).write_text(json.dumps(data), encoding="utf-8")


def load_trajectory(path: str) -> Trajectory:
    """Load a trajectory from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(float(t), np.array(pos, dtype=np.float64)) for t, pos in data["frames"]]


def play_trajectory_blocking(
    *,
    trajectory: Trajectory,
    speed_factor: float,
    command_position: Callable[[np.ndarray], None],
) -> None:
    """Play back a trajectory by issuing position commands in recorded time."""
    if not trajectory:
        raise ValueError("Empty trajectory")
    if speed_factor <= 0:
        raise ValueError("speed_factor must be > 0")

    t0_play = time.time()
    for t_rec, pos in trajectory:
        t_target = t0_play + t_rec / speed_factor
        command_position(pos)
        sleep_t = t_target - time.time()
        if sleep_t > 0:
            time.sleep(sleep_t)


@dataclass
class RecordingSession:
    """Thread-safe recording state shared across backends."""

    sample_period_s: float = 1.0 / 50.0
    buffer: Trajectory | None = None
    last_sample_t: float = 0.0
    recording: bool = False

    def __post_init__(self) -> None:
        if self.buffer is None:
            self.buffer = []
        self._lock = threading.Lock()

    def start(self, sample_hz: int) -> None:
        with self._lock:
            self.buffer = []
            self.sample_period_s = 1.0 / max(1, sample_hz)
            self.last_sample_t = 0.0
            self.recording = True

    def stop(self) -> Trajectory:
        with self._lock:
            self.recording = False
            raw = list(self.buffer or [])
        if not raw:
            return []
        t0 = raw[0][0]
        return [(t - t0, pos.copy()) for t, pos in raw]

    def maybe_sample(self, *, now_s: float, pos: Sequence[float]) -> None:
        with self._lock:
            if not self.recording:
                return
            if self.last_sample_t and now_s - self.last_sample_t < self.sample_period_s:
                return
            self.buffer.append((now_s, np.asarray(pos, dtype=np.float64).copy()))
            self.last_sample_t = now_s
