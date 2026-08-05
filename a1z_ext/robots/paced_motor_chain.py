"""SocketCAN command pacing for the mixed A1Z motor chain."""

from __future__ import annotations

import math
import time

import numpy as np

from a1z.motor_drivers.motor_b_driver import MixedMotorChain


class PacedMixedMotorChain(MixedMotorChain):
    """Preserve official SDK frames while spacing consecutive motor commands.

    The HHS ``a8fa:8598`` adapter on affected ``gs_usb`` hosts can suppress the
    response from the last motor in a six-frame back-to-back burst.  A short
    gap between frames keeps every MotorA/MotorB response flowing without
    changing gains, targets, torque, CAN IDs, or feedback parsing.
    """

    def __init__(self, *args, inter_command_delay_s: float, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._inter_command_delay_s = float(inter_command_delay_s)
        if (
            not math.isfinite(self._inter_command_delay_s)
            or self._inter_command_delay_s < 0.0
        ):
            raise ValueError("inter_command_delay_s must be finite and non-negative")

    @property
    def inter_command_delay_s(self) -> float:
        return self._inter_command_delay_s

    def _wait_after_command(self, command_index: int, command_count: int) -> None:
        if (
            self._inter_command_delay_s > 0.0
            and command_index + 1 < command_count
        ):
            time.sleep(self._inter_command_delay_s)

    def send_commands(
        self,
        pos: np.ndarray,
        vel: np.ndarray,
        kp: np.ndarray,
        kd: np.ndarray,
        torque: np.ndarray,
        motor_a_mode: int = 0,
    ) -> None:
        command_count = len(self._motor_a_list) + len(self._motor_b_list)
        command_index = 0
        for motor, joint_index in zip(
            self._motor_a_list,
            self._motor_a_joint_indices,
        ):
            motor.send_mit_command(
                pos=float(pos[joint_index]),
                vel=float(vel[joint_index]),
                kp=float(kp[joint_index]),
                kd=float(kd[joint_index]),
                torque=float(torque[joint_index]),
                mode=motor_a_mode,
            )
            self._wait_after_command(command_index, command_count)
            command_index += 1

        for motor, joint_index in zip(
            self._motor_b_list,
            self._motor_b_joint_indices,
        ):
            motor.send_mit_command(
                pos=float(pos[joint_index]),
                vel=float(vel[joint_index]),
                kp=float(kp[joint_index]),
                kd=float(kd[joint_index]),
                torque=float(torque[joint_index]),
            )
            self._wait_after_command(command_index, command_count)
            command_index += 1
