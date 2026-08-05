from __future__ import annotations

import threading
import time

import pytest


np = pytest.importorskip("numpy")

from a1z_ext.robots.motion_controller import LatestTargetMotionController


def linear_tcp_fk(joints):
    transform = np.eye(4, dtype=np.float64)
    transform[0, 3] = float(joints[0]) * 0.1
    return transform


class FeedbackRobot:
    is_running = True
    is_estopped = False
    is_faulted = False
    runtime_fault = ""

    def __init__(self, *, joint_bias_rad: float = 0.0) -> None:
        self.command = np.zeros(6, dtype=np.float64)
        self.position = np.zeros(6, dtype=np.float64)
        self.velocity = np.zeros(6, dtype=np.float64)
        self.joint_bias_rad = float(joint_bias_rad)
        self.writer_threads: set[int] = set()
        self.frames: list[tuple[float, np.ndarray]] = []
        self._lock = threading.Lock()

    def get_robot_info(self):
        with self._lock:
            command = self.command.copy()
        return {
            "control_mode": "position_hold",
            "command_pos": command,
            "joint_limits": np.asarray([[-2.0, 2.0]] * 6, dtype=np.float64),
        }

    def get_joint_state(self):
        with self._lock:
            return {
                "pos": self.position.copy(),
                "vel": self.velocity.copy(),
                "eff": np.zeros(6, dtype=np.float64),
            }

    def command_motion_frame(self, position, velocity, acceleration) -> None:
        del acceleration
        with self._lock:
            self.writer_threads.add(threading.get_ident())
            self.command = np.asarray(position, dtype=np.float64).copy()
            self.position = self.command.copy()
            self.position[0] -= self.joint_bias_rad
            # The fake plant settles within one service frame. This makes the
            # test isolate target arbitration and bias correction rather than
            # model motor dynamics.
            self.velocity = np.zeros(6, dtype=np.float64)
            self.frames.append((time.monotonic(), self.command.copy()))


class NativeFeedbackRobot(FeedbackRobot):
    def __init__(self) -> None:
        super().__init__()
        self.generation = 0
        self.native_calls = []
        self.native_status = {
            "generation": 0,
            "finished": True,
            "equivalent_position_correction_rad": [0.0] * 6,
            "integral_torque_bias_nm": [0.0] * 6,
            "correction_saturated": False,
        }

    def set_joint_trajectory_target(self, position, **limits) -> int:
        with self._lock:
            self.generation += 1
            self.native_calls.append(
                (threading.get_ident(), np.asarray(position).copy(), dict(limits))
            )
            self.command = np.asarray(position, dtype=np.float64).copy()
            self.position = self.command.copy()
            self.velocity.fill(0.0)
            self.native_status = {
                **self.native_status,
                "generation": self.generation,
                "finished": True,
            }
            return self.generation

    def get_joint_trajectory_status(self):
        with self._lock:
            return dict(self.native_status)

    def cancel_joint_trajectory(self) -> None:
        return None

    def command_motion_frame(self, position, velocity, acceleration) -> None:
        del position, velocity, acceleration
        raise AssertionError("native backend must not receive 50 Hz command frames")


def make_controller(robot: FeedbackRobot) -> LatestTargetMotionController:
    return LatestTargetMotionController(
        robot,
        forward_kinematics=linear_tcp_fk,
        endpoint_position_tolerance_mm=0.5,
        endpoint_orientation_tolerance_deg=0.5,
        joint_position_tolerance_deg=0.2,
        joint_stable_samples=3,
        settle_velocity_rad_s=0.02,
        feedback_timeout_s=0.5,
        control_period_s=0.005,
        acceleration_limit_rad_s2=6.0,
        jerk_limit_rad_s3=60.0,
        correction_integral_gain_s_inv=2.0,
        correction_rate_limit_deg_s=2.0,
    )


def test_native_backend_receives_one_final_target_and_owns_the_trajectory() -> None:
    robot = NativeFeedbackRobot()
    controller = make_controller(robot)
    try:
        goal = controller.submit(
            [0.2, -0.1, 0.05, 0.0, 0.0, 0.0],
            speed_rad_s=0.4,
            source="native-owner",
            timeout_s=2.0,
        )
        result = controller.wait(goal, timeout_s=2.0)

        assert result["ok"] is True
        assert len(robot.native_calls) == 1
        _thread_id, target, limits = robot.native_calls[0]
        assert target == pytest.approx(goal.target_rad)
        assert limits["max_velocity_rad_s"] == pytest.approx(0.4)
        assert limits["max_acceleration_rad_s2"] == pytest.approx(6.0)
        assert limits["max_jerk_rad_s3"] == pytest.approx(60.0)
        verification = result["data"]["verification"]
        assert verification["control_owner"] == "socketcan_250hz_control_loop"
        assert verification["trajectory_generator"] == "ruckig"
        assert controller.config_snapshot()["owner"] == "socketcan_250hz_control_loop"
    finally:
        controller.shutdown()


def test_joint_space_closed_loop_corrects_static_tracking_bias() -> None:
    robot = FeedbackRobot(joint_bias_rad=0.01)  # 1 mm TCP bias in linear_tcp_fk.
    controller = make_controller(robot)
    try:
        goal = controller.submit(
            [0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="test",
            timeout_s=4.0,
        )
        result = controller.wait(goal, timeout_s=4.0)

        assert result["ok"] is True
        verification = result["data"]["verification"]
        assert verification["arrival_basis"] == "joint_feedback_settled"
        assert verification["max_joint_error_deg"] <= 0.2
        assert verification["joint_position_tolerance_deg"] == pytest.approx(0.2)
        assert verification["stable_samples"] >= 3
        assert robot.command[0] > goal.target_rad[0]
        assert controller.status_snapshot()["state"] == "holding"
    finally:
        controller.shutdown()


def test_tcp_error_is_diagnostic_only_for_a_joint_target() -> None:
    robot = FeedbackRobot(joint_bias_rad=0.003)

    def amplified_tcp_fk(joints):
        transform = np.eye(4, dtype=np.float64)
        transform[0, 3] = float(joints[0])
        return transform

    controller = LatestTargetMotionController(
        robot,
        forward_kinematics=amplified_tcp_fk,
        endpoint_position_tolerance_mm=0.5,
        joint_position_tolerance_deg=0.2,
        joint_stable_samples=3,
        control_period_s=0.005,
        acceleration_limit_rad_s2=6.0,
        jerk_limit_rad_s3=60.0,
    )
    try:
        goal = controller.submit(
            [0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="joint-arrival",
            timeout_s=4.0,
        )
        result = controller.wait(goal, timeout_s=4.0)

        assert result["ok"] is True
        verification = result["data"]["verification"]
        assert verification["max_joint_error_deg"] <= 0.2
        assert verification["position_error_mm"] > 0.5
        assert verification["arrival_basis"] == "joint_feedback_settled"
    finally:
        controller.shutdown()


def test_unavailable_fk_diagnostics_do_not_break_joint_space_control() -> None:
    robot = FeedbackRobot()

    def unavailable_fk(_joints):
        raise RuntimeError("diagnostic model unavailable")

    controller = LatestTargetMotionController(
        robot,
        forward_kinematics=unavailable_fk,
        joint_stable_samples=3,
        control_period_s=0.005,
        acceleration_limit_rad_s2=6.0,
        jerk_limit_rad_s3=60.0,
    )
    try:
        goal = controller.submit(
            [0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="joint-only",
            timeout_s=4.0,
        )
        result = controller.wait(goal, timeout_s=4.0)

        assert result["ok"] is True
        verification = result["data"]["verification"]
        assert verification["max_joint_error_deg"] <= 0.5
        assert verification["position_error_mm"] is None
        assert verification["orientation_error_deg"] is None
        assert verification["fk_diagnostic_error"] == "diagnostic model unavailable"
    finally:
        controller.shutdown()


def test_joint_correction_is_slew_limited_instead_of_stepwise() -> None:
    robot = FeedbackRobot(joint_bias_rad=0.03)
    controller = make_controller(robot)
    try:
        goal = controller.submit(
            [0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="smooth-correction",
            timeout_s=4.0,
        )
        result = controller.wait(goal, timeout_s=4.0)

        assert result["ok"] is True
        command_frames = [frame[0] for _timestamp, frame in robot.frames]
        correction_steps = [
            current - previous
            for previous, current in zip(command_frames, command_frames[1:])
            if previous > goal.target_rad[0] and current > goal.target_rad[0]
        ]
        assert len(correction_steps) > 5
        # The planner may carry a small residual velocity into correction, but
        # no old-style tenths-of-a-degree correction step is permitted.
        assert float(np.max(correction_steps)) <= np.deg2rad(0.06) + 1e-8
        assert result["data"]["verification"]["joint_correction_deg"][0] > 0.0
    finally:
        controller.shutdown()


def test_newest_valid_target_supersedes_without_a_second_writer_or_queue() -> None:
    robot = FeedbackRobot()
    controller = make_controller(robot)
    try:
        first = controller.submit(
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="cli",
            timeout_s=5.0,
        )
        time.sleep(0.08)
        replacement_time = time.monotonic()
        second = controller.submit(
            [-0.2, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="gui",
            timeout_s=5.0,
        )

        first_result = controller.wait(first, timeout_s=0.2)
        second_result = controller.wait(second, timeout_s=5.0)

        assert first_result["execution_state"] == "superseded"
        assert first_result["data"]["replacement_goal_id"] == second.goal_id
        assert second_result["ok"] is True
        assert robot.position[0] == pytest.approx(-0.2, abs=1e-6)
        assert len(robot.writer_threads) == 1
        # Velocity continuity may carry the arm a few frames in the old
        # direction, but the abandoned +1 rad endpoint is never executed.
        after_replacement = [
            frame[0]
            for timestamp, frame in robot.frames
            if timestamp >= replacement_time
        ]
        assert after_replacement
        assert max(after_replacement) < 0.1
    finally:
        controller.shutdown()


def test_invalid_replacement_does_not_abandon_the_current_goal() -> None:
    robot = FeedbackRobot()
    controller = make_controller(robot)
    try:
        current = controller.submit(
            [0.2, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.4,
            source="current",
            timeout_s=4.0,
        )
        with pytest.raises(ValueError, match="soft limit"):
            controller.submit(
                [3.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                speed_rad_s=0.4,
                source="invalid",
                timeout_s=4.0,
            )

        assert controller.owns_goal(current)
        assert controller.wait(current, timeout_s=4.0)["ok"] is True
    finally:
        controller.shutdown()


def test_equivalent_endpoint_does_not_bypass_joint_space_arrival() -> None:
    robot = FeedbackRobot()

    def constant_fk(_joints):
        return np.eye(4, dtype=np.float64)

    controller = LatestTargetMotionController(
        robot,
        forward_kinematics=constant_fk,
        joint_stable_samples=3,
        control_period_s=0.005,
        acceleration_limit_rad_s2=6.0,
        jerk_limit_rad_s3=60.0,
    )
    try:
        goal = controller.submit(
            [0.3, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="equivalent-pose",
            timeout_s=4.0,
        )

        time.sleep(0.04)
        assert not goal.completion_event.is_set()

        result = controller.wait(goal, timeout_s=4.0)
        assert result["ok"] is True
        verification = result["data"]["verification"]
        assert verification["arrival_basis"] == "joint_feedback_settled"
        assert verification["target_reference_commanded"] is True
        assert verification["max_joint_error_deg"] <= 0.5
        assert robot.command[0] == pytest.approx(0.3, abs=1e-6)
    finally:
        controller.shutdown()


def test_exclusive_control_boundary_rebases_the_next_plan_on_live_position() -> None:
    robot = FeedbackRobot()
    controller = make_controller(robot)
    try:
        first = controller.submit(
            [0.15, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.5,
            source="before-mode-change",
            timeout_s=4.0,
        )
        assert controller.wait(first, timeout_s=4.0)["ok"] is True

        def simulate_manual_reposition() -> None:
            with robot._lock:
                robot.command[0] = -0.4
                robot.position[0] = -0.4
                robot.velocity[:] = 0.0
                robot.frames.clear()

        controller.run_exclusive(
            simulate_manual_reposition,
            reason="test control-mode transition",
        )
        second = controller.submit(
            [-0.3, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.4,
            source="after-mode-change",
            timeout_s=4.0,
        )
        assert controller.wait(second, timeout_s=4.0)["ok"] is True

        assert robot.frames
        first_frame = robot.frames[0][1]
        assert first_frame[0] < -0.39
        assert robot.position[0] == pytest.approx(-0.3, abs=1e-6)
    finally:
        controller.shutdown()


def test_feedback_failure_fails_one_goal_without_killing_the_single_worker() -> None:
    class RecoveringFeedbackRobot(FeedbackRobot):
        def __init__(self) -> None:
            super().__init__()
            self.fail_next_read = True

        def get_joint_state(self):
            if self.fail_next_read:
                self.fail_next_read = False
                raise RuntimeError("temporary feedback read failure")
            return super().get_joint_state()

    robot = RecoveringFeedbackRobot()
    controller = make_controller(robot)
    try:
        failed = controller.submit(
            [0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.4,
            source="failing-read",
            timeout_s=2.0,
        )
        failed_result = controller.wait(failed, timeout_s=1.0)
        assert failed_result["ok"] is False
        assert "temporary feedback read failure" in failed_result["error"]

        recovered = controller.submit(
            [0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
            speed_rad_s=0.4,
            source="recovered-read",
            timeout_s=4.0,
        )
        assert controller.wait(recovered, timeout_s=4.0)["ok"] is True
        assert len(robot.writer_threads) == 1
    finally:
        controller.shutdown()


def test_stale_timestamped_feedback_is_never_used_for_arrival() -> None:
    class StaleFeedbackRobot(FeedbackRobot):
        def get_joint_state(self):
            state = super().get_joint_state()
            state["feedback_monotonic_s"] = time.monotonic() - 1.0
            return state

    robot = StaleFeedbackRobot()
    controller = make_controller(robot)
    try:
        goal = controller.submit(
            [0.0] * 6,
            speed_rad_s=0.4,
            source="stale-feedback",
            timeout_s=2.0,
        )
        result = controller.wait(goal, timeout_s=1.0)
        assert result["ok"] is False
        assert "feedback is stale" in result["error"]
        assert robot.frames == []
    finally:
        controller.shutdown()
