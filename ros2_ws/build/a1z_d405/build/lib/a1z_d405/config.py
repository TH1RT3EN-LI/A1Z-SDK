"""Shared configuration for the ROS 2 D405 bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class D405BridgeConfig:
    tcp_host: str
    tcp_port: int
    namespace: str
    color_frame_id: str
    depth_frame_id: str
    poll_hz: float


def load_config() -> D405BridgeConfig:
    return D405BridgeConfig(
        tcp_host=os.environ.get("A1Z_TCP_HOST", "127.0.0.1"),
        tcp_port=int(os.environ.get("A1Z_TCP_PORT", "18080")),
        namespace=os.environ.get("A1Z_D405_ROS2_NAMESPACE", "/a1z/d405").rstrip("/"),
        color_frame_id=os.environ.get("A1Z_D405_COLOR_FRAME_ID", "d405_color_optical_frame"),
        depth_frame_id=os.environ.get("A1Z_D405_DEPTH_FRAME_ID", "d405_depth_optical_frame"),
        poll_hz=float(os.environ.get("A1Z_D405_ROS_POLL_HZ", "5.0")),
    )
