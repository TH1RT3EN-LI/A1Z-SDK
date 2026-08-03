from __future__ import annotations

from a1z_ext.robots.connection_monitor import (
    ArmFeedbackMonitor,
    socketcan_snapshot_from_ip,
)


def _can_payload(state: str, *, flags: list[str] | None = None) -> list[dict]:
    return [
        {
            "ifname": "can0",
            "flags": ["NOARP", "UP", "LOWER_UP"] if flags is None else flags,
            "linkinfo": {
                "info_kind": "can",
                "info_data": {
                    "state": state,
                    "berr_counter": {"tx": 3, "rx": 1},
                },
                "info_xstats": {"bus_off": 2, "restarted": 1},
            },
        }
    ]


def test_socketcan_status_distinguishes_active_degraded_and_disconnected() -> None:
    active = socketcan_snapshot_from_ip(
        _can_payload("ERROR-ACTIVE"), channel="can0", observed_at=10.0
    )
    assert active["status"] == "connected"
    assert active["connected"] is True
    assert active["healthy"] is True
    assert active["bus_state"] == "error_active"
    assert active["tx_error_counter"] == 3
    assert active["bus_off_count"] == 2

    passive = socketcan_snapshot_from_ip(
        _can_payload("ERROR-PASSIVE"), channel="can0", observed_at=11.0
    )
    assert passive["status"] == "degraded"
    assert passive["connected"] is True
    assert passive["healthy"] is False
    assert passive["diagnostic"] == "error_passive"

    bus_off = socketcan_snapshot_from_ip(
        _can_payload("BUS-OFF"), channel="can0", observed_at=12.0
    )
    assert bus_off["status"] == "disconnected"
    assert bus_off["connected"] is False
    assert bus_off["diagnostic"] == "bus_off"

    down = socketcan_snapshot_from_ip(
        _can_payload("STOPPED", flags=["NOARP"]),
        channel="can0",
        observed_at=13.0,
    )
    assert down["status"] == "disconnected"
    assert down["diagnostic"] == "interface_down"


def test_socketcan_status_reports_missing_interface_without_guessing() -> None:
    snapshot = socketcan_snapshot_from_ip([], channel="can0", observed_at=20.0)

    assert snapshot["status"] == "disconnected"
    assert snapshot["interface_present"] is False
    assert snapshot["bus_state"] == "missing"
    assert snapshot["diagnostic"] == "interface_missing"

    wrong_type = socketcan_snapshot_from_ip(
        [{"ifname": "can0", "flags": ["UP"], "link_type": "ether"}],
        channel="can0",
        observed_at=21.0,
    )
    assert wrong_type["connected"] is False
    assert wrong_type["diagnostic"] == "wrong_interface_type"


def test_arm_connection_requires_fresh_feedback_from_all_six_joints() -> None:
    monitor = ArmFeedbackMonitor(range(1, 7), stale_after_s=0.2)
    monitor.reset(now=100.0)

    connecting = monitor.snapshot(now=100.05)
    assert connecting["status"] == "connecting"
    assert connecting["connected"] is False
    assert connecting["missing_joints"] == [1, 2, 3, 4, 5, 6]

    monitor.observe(range(6), now=100.1)
    connected = monitor.snapshot(now=100.15)
    assert connected["status"] == "connected"
    assert connected["connected"] is True
    assert connected["online_joints"] == [1, 2, 3, 4, 5, 6]

    # Only J1 continues replying. Its traffic must not keep J2-J6 online.
    monitor.observe([0], now=100.31)
    partial = monitor.snapshot(now=100.32)
    assert partial["status"] == "partial"
    assert partial["connected"] is False
    assert partial["online_joints"] == [1]
    assert partial["stale_joints"] == [2, 3, 4, 5, 6]
    assert partial["unavailable_joints"] == [2, 3, 4, 5, 6]

    disconnected = monitor.snapshot(now=100.52)
    assert disconnected["status"] == "disconnected"
    assert disconnected["connected"] is False
    assert disconnected["stale_joints"] == [1, 2, 3, 4, 5, 6]


def test_arm_connection_preserves_missing_vs_stale_diagnostics() -> None:
    monitor = ArmFeedbackMonitor([1, 2, 3, 4, 5, 6], stale_after_s=0.2)
    monitor.reset(now=50.0)
    monitor.observe([0, 2, 4], now=50.05)

    snapshot = monitor.snapshot(now=50.24)

    assert snapshot["status"] == "partial"
    assert snapshot["missing_joints"] == [2, 4, 6]
    assert snapshot["stale_joints"] == []
    assert snapshot["online_joints"] == [1, 3, 5]
