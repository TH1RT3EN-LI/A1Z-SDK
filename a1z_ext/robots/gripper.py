"""Project-local gripper overrides layered on top of the upstream SDK."""

from __future__ import annotations

import logging
import time

from a1z.robots.gripper import (
    GRIPPER_CAN_ID,
    GRIPPER_HOME_VEL,
    GRIPPER_MOTOR_RANGES,
    MOTOR_PEAK_TORQUE_NM,
    Gripper as UpstreamGripper,
)

logger = logging.getLogger(__name__)

GRIPPER_HOME_TORQUE_NM: float = 0.5


class Gripper(UpstreamGripper):
    """Project-local startup behavior without modifying the upstream mirror."""

    def enable(self) -> None:
        self._motor.clear_error()
        super().enable()

    def home(self, timeout: float = 1.5) -> bool:
        bus = self._motor.bus
        t0 = time.time()
        i_home = GRIPPER_HOME_TORQUE_NM / MOTOR_PEAK_TORQUE_NM
        logger.info("Gripper init: driving to open (%+.3f rad) ...", self._open_rad)
        reached = False
        while time.time() - t0 < timeout:
            self._motor.send_hybrid_command(
                pos=self._open_rad,
                vel=GRIPPER_HOME_VEL,
                i_des=i_home,
            )
            msg = bus.recv(timeout=0.01)
            if msg is not None and int(msg.arbitration_id) == self._motor.motor_id:
                fb = self._motor.parse_feedback(msg)
                if fb is not None:
                    self._motor.last_feedback = fb
            fb = self._motor.last_feedback
            if fb is not None and abs(fb.position - self._open_rad) < 0.1:
                logger.info(
                    "Gripper init: open at %+.3f rad (%.1fs).",
                    fb.position,
                    time.time() - t0,
                )
                reached = True
                break
        if not reached:
            logger.warning(
                "Gripper home timed out after %.1fs, pos=%s rad.",
                timeout,
                f"{self._motor.last_feedback.position:+.3f}" if self._motor.last_feedback else "?",
            )
        with self._lock:
            self._cmd_norm = 1.0
        return reached
