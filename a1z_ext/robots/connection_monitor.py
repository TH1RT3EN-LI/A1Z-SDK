"""Backend-only connectivity monitoring for the real A1Z control service.

The SocketCAN probe never opens or reads a CAN socket, so it cannot steal
feedback frames from the hardware owner.  Arm connectivity is derived only
from successfully parsed feedback for each required joint.
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)

_DISCONNECTED_CAN_STATES = {"bus_off", "stopped", "sleeping"}
_DEGRADED_CAN_STATES = {"error_warning", "error_passive"}


def _normalise_can_state(value: object) -> str:
    return str(value or "unknown").strip().lower().replace("-", "_")


def _integer_or_none(value: object) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def socketcan_snapshot_from_ip(
    payload: object,
    *,
    channel: str,
    observed_at: Optional[float] = None,
) -> dict[str, Any]:
    """Convert ``ip -json -details link`` data into a stable status shape."""

    timestamp = time.monotonic() if observed_at is None else float(observed_at)
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        entries: list[object] = []
    else:
        entries = list(payload)
    raw = next(
        (
            item
            for item in entries
            if isinstance(item, Mapping) and str(item.get("ifname", "")) == channel
        ),
        None,
    )
    if raw is None:
        return {
            "channel": channel,
            "status": "disconnected",
            "connected": False,
            "healthy": False,
            "interface_present": False,
            "interface_up": False,
            "bus_state": "missing",
            "tx_error_counter": None,
            "rx_error_counter": None,
            "bus_off_count": None,
            "restart_count": None,
            "diagnostic": "interface_missing",
            "observed_at_monotonic_s": timestamp,
        }

    flags = {
        str(flag).strip().upper()
        for flag in raw.get("flags", [])
        if isinstance(flag, str)
    }
    linkinfo = raw.get("linkinfo", {})
    if not isinstance(linkinfo, Mapping):
        linkinfo = {}
    info_kind = str(linkinfo.get("info_kind", "") or "").strip().lower()
    link_type = str(raw.get("link_type", "") or "").strip().lower()
    info_data = linkinfo.get("info_data", {})
    if not isinstance(info_data, Mapping):
        info_data = {}
    bus_state = _normalise_can_state(info_data.get("state"))
    interface_up = "UP" in flags

    berr = info_data.get("berr_counter", {})
    if not isinstance(berr, Mapping):
        berr = {}
    xstats = linkinfo.get("info_xstats", {})
    if not isinstance(xstats, Mapping):
        xstats = {}

    diagnostic = "ok"
    status = "connected"
    connected = True
    healthy = True
    if (info_kind and info_kind != "can") or (
        not info_kind and link_type and link_type != "can"
    ):
        status = "disconnected"
        connected = False
        healthy = False
        diagnostic = "wrong_interface_type"
    elif not interface_up:
        status = "disconnected"
        connected = False
        healthy = False
        diagnostic = "interface_down"
    elif bus_state in _DISCONNECTED_CAN_STATES:
        status = "disconnected"
        connected = False
        healthy = False
        diagnostic = bus_state
    elif bus_state in _DEGRADED_CAN_STATES:
        status = "degraded"
        healthy = False
        diagnostic = bus_state
    elif bus_state == "unknown":
        # An UP SocketCAN interface is usable even when an older `ip` build
        # omits the detailed controller state. Keep the uncertainty explicit.
        healthy = False
        diagnostic = "bus_state_unavailable"

    return {
        "channel": channel,
        "status": status,
        "connected": connected,
        "healthy": healthy,
        "interface_present": True,
        "interface_up": interface_up,
        "bus_state": bus_state,
        "tx_error_counter": _integer_or_none(berr.get("tx")),
        "rx_error_counter": _integer_or_none(berr.get("rx")),
        "bus_off_count": _integer_or_none(
            xstats.get("bus_off", xstats.get("bus-off"))
        ),
        "restart_count": _integer_or_none(
            xstats.get("restarted", xstats.get("re-started"))
        ),
        "diagnostic": diagnostic,
        "observed_at_monotonic_s": timestamp,
    }


def _sysfs_socketcan_snapshot(
    channel: str, *, observed_at: Optional[float] = None
) -> dict[str, Any]:
    timestamp = time.monotonic() if observed_at is None else float(observed_at)
    if not channel or Path(channel).name != channel:
        return socketcan_snapshot_from_ip([], channel=channel, observed_at=timestamp)
    interface_path = Path("/sys/class/net") / channel
    if not interface_path.exists():
        return socketcan_snapshot_from_ip([], channel=channel, observed_at=timestamp)
    try:
        flags = int((interface_path / "flags").read_text().strip(), 16)
        interface_up = bool(flags & 0x1)
    except (OSError, ValueError):
        interface_up = False
    return {
        "channel": channel,
        "status": "connected" if interface_up else "disconnected",
        "connected": interface_up,
        "healthy": False,
        "interface_present": True,
        "interface_up": interface_up,
        "bus_state": "unknown",
        "tx_error_counter": None,
        "rx_error_counter": None,
        "bus_off_count": None,
        "restart_count": None,
        "diagnostic": (
            "netlink_details_unavailable" if interface_up else "interface_down"
        ),
        "observed_at_monotonic_s": timestamp,
    }


def probe_socketcan_link(channel: str) -> dict[str, Any]:
    """Inspect one SocketCAN link without touching its receive queue."""

    observed_at = time.monotonic()
    try:
        result = subprocess.run(
            [
                "ip",
                "-details",
                "-statistics",
                "-json",
                "link",
                "show",
                "dev",
                channel,
            ],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return _sysfs_socketcan_snapshot(channel, observed_at=observed_at)
    if result.returncode != 0:
        return _sysfs_socketcan_snapshot(channel, observed_at=observed_at)
    try:
        payload = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        return _sysfs_socketcan_snapshot(channel, observed_at=observed_at)
    return socketcan_snapshot_from_ip(
        payload,
        channel=channel,
        observed_at=observed_at,
    )


class SocketCANLinkMonitor:
    """Periodically cache SocketCAN state without performing recovery."""

    def __init__(
        self,
        channel: str,
        *,
        interval_s: float = 1.0,
        probe: Callable[[str], dict[str, Any]] = probe_socketcan_link,
    ) -> None:
        self._channel = str(channel)
        self._interval_s = max(0.2, float(interval_s))
        self._probe = probe
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._snapshot = {
            **socketcan_snapshot_from_ip([], channel=self._channel),
            "status": "unknown",
            "bus_state": "unknown",
            "diagnostic": "not_checked",
        }
        self._last_log_signature: Optional[tuple[object, ...]] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._refresh()
        self._thread = threading.Thread(
            target=self._run,
            name=f"{self._channel}_link_monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(1.0, self._interval_s + 0.2))
        self._thread = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_s):
            self._refresh()

    def _refresh(self) -> None:
        try:
            snapshot = dict(self._probe(self._channel))
        except Exception as exc:  # Diagnostics must never stop motor control.
            snapshot = {
                **socketcan_snapshot_from_ip([], channel=self._channel),
                "status": "unknown",
                "bus_state": "unknown",
                "diagnostic": f"probe_failed:{type(exc).__name__}",
            }
        with self._lock:
            self._snapshot = snapshot
        self._log_transition(snapshot)

    def _log_transition(self, snapshot: Mapping[str, Any]) -> None:
        signature = (
            snapshot.get("status"),
            snapshot.get("bus_state"),
            snapshot.get("diagnostic"),
        )
        if signature == self._last_log_signature:
            return
        self._last_log_signature = signature
        message = (
            "CAN %s: status=%s bus_state=%s diagnostic=%s"
            % (
                self._channel,
                snapshot.get("status", "unknown"),
                snapshot.get("bus_state", "unknown"),
                snapshot.get("diagnostic", "unknown"),
            )
        )
        if snapshot.get("connected") and snapshot.get("healthy"):
            logger.info(message)
        else:
            logger.warning(message)


class ArmFeedbackStartupGate:
    """Separate slow hardware initialisation from strict runtime freshness.

    Gripper homing and the SDK's initial probe happen before the arm control
    loop is fully running.  Feedback that is missing during that phase must not
    consume the runtime stale-feedback budget.  Once all required joints have
    produced fresh feedback, the gate permanently enters ``monitoring`` and the
    normal per-joint stale check applies.
    """

    def __init__(self, *, timeout_s: float) -> None:
        self._timeout_s = float(timeout_s)
        if not math.isfinite(self._timeout_s) or self._timeout_s <= 0.0:
            raise ValueError("timeout_s must be positive and finite")
        self._lock = threading.Lock()
        self._phase = "stopped"
        self._deadline_monotonic_s: Optional[float] = None

    @property
    def phase(self) -> str:
        with self._lock:
            return self._phase

    @property
    def active(self) -> bool:
        return self.phase in {"initializing", "waiting"}

    def begin_initialization(self) -> None:
        with self._lock:
            self._phase = "initializing"
            self._deadline_monotonic_s = None

    def begin_waiting(self, *, now: Optional[float] = None) -> None:
        timestamp = time.monotonic() if now is None else float(now)
        with self._lock:
            self._phase = "waiting"
            self._deadline_monotonic_s = timestamp + self._timeout_s

    def stop(self) -> None:
        with self._lock:
            self._phase = "stopped"
            self._deadline_monotonic_s = None

    def evaluate(
        self,
        arm_snapshot: Mapping[str, Any],
        *,
        now: Optional[float] = None,
    ) -> str:
        """Return ``probe``, ``ready``, ``timeout``, ``monitor``, or ``stopped``."""

        timestamp = time.monotonic() if now is None else float(now)
        with self._lock:
            if self._phase == "initializing":
                return "probe"
            if self._phase == "waiting":
                if bool(arm_snapshot.get("connected", False)):
                    self._phase = "monitoring"
                    self._deadline_monotonic_s = None
                    return "ready"
                deadline = self._deadline_monotonic_s
                if deadline is not None and timestamp < deadline:
                    return "probe"
                self._phase = "failed"
                self._deadline_monotonic_s = None
                return "timeout"
            if self._phase == "monitoring":
                return "monitor"
            return "stopped"

    def snapshot(self, *, now: Optional[float] = None) -> dict[str, Any]:
        timestamp = time.monotonic() if now is None else float(now)
        with self._lock:
            phase = self._phase
            deadline = self._deadline_monotonic_s
        remaining_ms = None
        if deadline is not None:
            remaining_ms = round(max(0.0, deadline - timestamp) * 1000.0, 1)
        return {
            "phase": phase,
            "timeout_ms": round(self._timeout_s * 1000.0, 1),
            "remaining_ms": remaining_ms,
        }


class ArmFeedbackMonitor:
    """Maintain connection evidence independently for every required joint."""

    def __init__(
        self,
        joint_can_ids: Sequence[int],
        *,
        stale_after_s: float,
    ) -> None:
        self._joint_can_ids = tuple(int(value) for value in joint_can_ids)
        self._stale_after_s = float(stale_after_s)
        if not self._joint_can_ids:
            raise ValueError("joint_can_ids must not be empty")
        if len(set(self._joint_can_ids)) != len(self._joint_can_ids):
            raise ValueError("joint_can_ids must be unique")
        if not math.isfinite(self._stale_after_s) or self._stale_after_s <= 0.0:
            raise ValueError("stale_after_s must be positive and finite")
        self._lock = threading.Lock()
        self._started_at = time.monotonic()
        self._feedback_at: list[Optional[float]] = [None] * len(self._joint_can_ids)

    def reset(self, *, now: Optional[float] = None) -> None:
        timestamp = time.monotonic() if now is None else float(now)
        with self._lock:
            self._started_at = timestamp
            self._feedback_at = [None] * len(self._joint_can_ids)

    def observe(
        self,
        joint_indices: Sequence[int],
        *,
        now: Optional[float] = None,
    ) -> None:
        timestamp = time.monotonic() if now is None else float(now)
        with self._lock:
            for raw_index in joint_indices:
                index = int(raw_index)
                if 0 <= index < len(self._feedback_at):
                    self._feedback_at[index] = timestamp

    def snapshot(self, *, now: Optional[float] = None) -> dict[str, Any]:
        timestamp = time.monotonic() if now is None else float(now)
        with self._lock:
            started_at = self._started_at
            feedback_at = list(self._feedback_at)

        ages = [
            None if value is None else max(0.0, timestamp - value)
            for value in feedback_at
        ]
        online = [
            age is not None and age <= self._stale_after_s
            for age in ages
        ]
        all_online = all(online)
        grace_active = timestamp - started_at <= self._stale_after_s
        if all_online:
            status = "connected"
        elif grace_active and any(value is None for value in feedback_at):
            status = "connecting"
        elif any(online):
            status = "partial"
        else:
            status = "disconnected"

        missing = [
            index + 1
            for index, value in enumerate(feedback_at)
            if value is None
        ]
        stale = [
            index + 1
            for index, age in enumerate(ages)
            if age is not None and age > self._stale_after_s
        ]
        unavailable = [index + 1 for index, value in enumerate(online) if not value]
        oldest = (
            min(feedback_at)
            if all(value is not None for value in feedback_at)
            else None
        )
        maximum_age = max(
            [
                timestamp - started_at if value is None else age
                for value, age in zip(feedback_at, ages)
            ],
            default=0.0,
        )
        return {
            "status": status,
            "connected": all_online,
            "required_joint_count": len(self._joint_can_ids),
            "joint_can_ids": list(self._joint_can_ids),
            "online_joints": [index + 1 for index, value in enumerate(online) if value],
            "unavailable_joints": unavailable,
            "missing_joints": missing,
            "stale_joints": stale,
            "feedback_age_ms": [
                None if age is None else round(age * 1000.0, 1) for age in ages
            ],
            "oldest_feedback_monotonic_s": oldest,
            "maximum_feedback_age_s": maximum_age,
            "stale_after_ms": round(self._stale_after_s * 1000.0, 1),
            "observed_at_monotonic_s": timestamp,
        }
