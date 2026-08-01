"""Qt-facing controller with serialized, fail-closed robot operations."""

from __future__ import annotations

import json
import math
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QObject,
    Property,
    QTimer,
    Signal,
    Slot,
)

from .camera_coordinator import CameraCoordinator, CameraManualResult
from .device_command_executor import (
    DeviceCommandExecutor,
    DeviceCommandRequest,
    DeviceCommandResult,
    EmergencyCommandRequest,
    EmergencyCommandResult,
)
from .diagnostics_session import (
    DiagnosticsSessionCoordinator,
    DiagnosticsSessionError,
)
from .draft_lock_coordinator import (
    DraftLockCoordinator,
    DraftResource,
)
from .interaction_policy import (
    InteractionPolicy,
    OnlineCapability,
    ProcessAccess,
    ProcessTaskContract,
    ResourceEffect,
    online_capability_effects,
)
from .kinematics_command_adapter import KinematicsCommandAdapter
from .log_model import ConsoleLogModel
from .plan_session import (
    PlanSessionCoordinator,
    PlanSessionError,
)
from .process_task_runner import (
    ProcessTaskRequest,
    ProcessTaskResult,
    ProcessTaskRunner,
    ProcessTaskSemanticResult,
    ProcessTaskStartFailure,
)
from .profiles import RuntimeProfile, load_profiles
from .protocol import (
    A1ZProtocolClient,
    ProtocolError,
)
from .telemetry_coordinator import TelemetryCoordinator, TelemetryResult
from .teaching_session import (
    TeachingSessionCoordinator,
    TeachingSessionError,
)


class ConsoleController(QObject):
    stateChanged = Signal()
    telemetryTimingChanged = Signal()
    telemetryRefreshChanged = Signal()
    jointTelemetryChanged = Signal()
    gripperTelemetryChanged = Signal()
    gripperStateInvalidated = Signal()
    armPoseChanged = Signal()
    armStateInvalidated = Signal()
    operationFeedbackChanged = Signal()
    cameraStateChanged = Signal()
    cameraPreviewChanged = Signal()
    planChanged = Signal()
    preflightChanged = Signal()
    draftLocksChanged = Signal()
    teachingChanged = Signal()
    startupStateChanged = Signal()
    operationFinished = Signal(str, bool, str)

    def __init__(self, repo_root: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._repo_root = repo_root.resolve()
        self._profiles = load_profiles(self._repo_root)
        self._profile_name = "sim"
        self._connected = False
        self._backend_matched = False
        self._connection_issue = "unprobed"
        self._backend = ""
        self._control_mode = ""
        self._robot_running = False
        self._faulted = False
        self._fault_message = ""
        self._uncertain = False
        self._uncertain_ack_pending = False
        self._estopped = False
        self._status_text = "等待连接"
        self._last_error = ""
        self._health_error = ""
        self._operation_feedback_state = "idle"
        self._operation_feedback_title = ""
        self._operation_feedback_message = ""
        self._joint_rows = self._empty_joint_rows()
        self._gripper: float | None = None
        self._gripper_target: float | None = None
        self._info: dict[str, Any] = {}
        self._teaching = TeachingSessionCoordinator(self._profile_name)
        self._gripper_free_drive = False
        self._gravity_comp_factor = 1.0
        self._ee_pose_text = "未读取"
        self._ee_axis_text = ""
        self._ee_motion_text = ""
        self._log_model = ConsoleLogModel(self)
        self._pending_log_lines: list[str] = []
        self._draft_locks = DraftLockCoordinator()
        self._kinematics = KinematicsCommandAdapter(self._repo_root)
        self._state_lock = threading.Lock()
        self._policy_cache_key: tuple[Any, ...] | None = None
        self._policy_cache: InteractionPolicy | None = None
        self._monitoring_started = False
        self._shutting_down = False

        self._commands = DeviceCommandExecutor(self)
        self._commands.commandFinished.connect(self._on_operation_finished)
        self._commands.emergencyFinished.connect(self._on_emergency_finished)

        self._camera = CameraCoordinator(self._profile, self)
        self._camera.stateChanged.connect(self.cameraStateChanged.emit)
        self._camera.previewChanged.connect(self.cameraPreviewChanged.emit)
        self._camera.logAvailable.connect(self._append_log)
        self._camera.manualStarted.connect(self._on_camera_manual_started)
        self._camera.manualFinished.connect(self._on_camera_manual_finished)

        self._task_runner = ProcessTaskRunner(self)
        self._task_runner.outputAvailable.connect(self._append_log)
        self._task_runner.finished.connect(self._on_process_task_finished)
        self._task_runner.failedToStart.connect(
            self._on_process_task_start_failure
        )
        self._task_runner.stateChanged.connect(
            self.telemetryRefreshChanged.emit
        )

        self._plan = PlanSessionCoordinator(
            self._repo_root,
            self._profile,
            self,
        )
        self._plan.changed.connect(self.planChanged.emit)

        self._diagnostics = DiagnosticsSessionCoordinator(
            self._repo_root,
            self._profile,
        )

        self._telemetry = TelemetryCoordinator(
            self._profile,
            self,
            poll_blocked=lambda: (
                self._task_runner.busy
                and self._task_runner.contract.blocks_telemetry
            ),
        )
        self._telemetry.resultAvailable.connect(self._on_telemetry_result)
        self._telemetry.ageChanged.connect(self._on_telemetry_age_changed)
        self._telemetry.stateChanged.connect(
            self.telemetryRefreshChanged.emit
        )

        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setSingleShot(True)
        self._log_flush_timer.setInterval(80)
        self._log_flush_timer.timeout.connect(self._flush_logs)
        self.stateChanged.connect(self.startupStateChanged.emit)
        self.cameraStateChanged.connect(self.startupStateChanged.emit)
        self.preflightChanged.connect(self.startupStateChanged.emit)

    # ------------------------------------------------------------------
    # Qt properties
    # ------------------------------------------------------------------

    @Property(str, notify=stateChanged)
    def profile(self) -> str:
        return self._profile_name

    @Property(str, notify=stateChanged)
    def profileLabel(self) -> str:
        return self._profile.label

    @Property(str, notify=stateChanged)
    def expectedBackend(self) -> str:
        return self._profile.expected_backend

    @Property(str, notify=stateChanged)
    def endpoint(self) -> str:
        return f"{self._profile.host}:{self._profile.port}"

    @Property(bool, notify=stateChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(bool, notify=stateChanged)
    def backendMatched(self) -> bool:
        return self._backend_matched

    @Property(str, notify=stateChanged)
    def backend(self) -> str:
        return self._backend or "—"

    @Property(str, notify=stateChanged)
    def backendLabel(self) -> str:
        return {
            "isaacsim": "Isaac Sim 仿真",
            "socketcan": "SocketCAN 真机",
            "mock": "Mock 离线",
        }.get(self._backend, self._backend or "—")

    @Property(str, notify=stateChanged)
    def controlMode(self) -> str:
        return self._control_mode or "—"

    @Property(str, notify=stateChanged)
    def controlModeLabel(self) -> str:
        return {
            "gravity_comp_effort": "零力漂浮",
            "position_hold": "位置保持",
        }.get(self._control_mode, self._control_mode or "—")

    @Property(bool, notify=stateChanged)
    def robotRunning(self) -> bool:
        return self._robot_running

    @Property(bool, notify=stateChanged)
    def faulted(self) -> bool:
        return self._faulted

    @Property(str, notify=stateChanged)
    def faultMessage(self) -> str:
        return self._fault_message

    @Property(str, notify=stateChanged)
    def dynamicsSummary(self) -> str:
        frequency = self._info.get("control_freq_hz")
        kp = list(self._info.get("default_kp", []) or [])
        kd = list(self._info.get("default_kd", []) or [])
        parts = []
        if frequency is not None:
            parts.append(f"{int(frequency)} Hz")
        if kp:
            parts.append("Kp [" + ", ".join(f"{float(v):g}" for v in kp[:6]) + "]")
        if kd:
            parts.append("Kd [" + ", ".join(f"{float(v):g}" for v in kd[:6]) + "]")
        torque_limit = self._info.get("gripper_torque_limit_nm")
        if torque_limit is not None:
            parts.append(f"G1Z 上限 {float(torque_limit):g} Nm")
        return " · ".join(parts) if parts else "暂无参数"

    @Property(bool, notify=stateChanged)
    def commandBusy(self) -> bool:
        return self._commands.command_busy

    @Property(bool, notify=draftLocksChanged)
    def pendingDrafts(self) -> bool:
        return self._draft_locks.any_pending

    @Property(str, notify=draftLocksChanged)
    def pendingDraftSummary(self) -> str:
        return self._draft_locks.summary

    @Property(bool, notify=stateChanged)
    def taskBusy(self) -> bool:
        return self._task_runner.busy

    @Property(bool, notify=stateChanged)
    def taskMotion(self) -> bool:
        return self._task_runner.contract.affects_device

    @Property(str, notify=stateChanged)
    def taskLabel(self) -> str:
        return self._task_runner.label

    @Property(str, notify=stateChanged)
    def taskKind(self) -> str:
        return self._task_runner.kind

    @Property(bool, notify=stateChanged)
    def taskCancelable(self) -> bool:
        return self._task_runner.cancelable

    @Property(bool, notify=stateChanged)
    def emergencyBusy(self) -> bool:
        return self._commands.emergency_busy

    @Property(bool, notify=stateChanged)
    def commandOutcomeUncertain(self) -> bool:
        return self._uncertain

    @Property(bool, notify=stateChanged)
    def uncertainRecoveryPending(self) -> bool:
        return self._uncertain_ack_pending

    @Property(bool, notify=stateChanged)
    def estopped(self) -> bool:
        return self._estopped

    @Property(int, notify=telemetryTimingChanged)
    def telemetryAgeMs(self) -> int:
        return self._telemetry.age_ms

    @Property(bool, notify=telemetryTimingChanged)
    def telemetryFresh(self) -> bool:
        return self._telemetry.fresh

    @Property(bool, notify=telemetryRefreshChanged)
    def telemetryRefreshEnabled(self) -> bool:
        return not (
            self._shutting_down
            or self._telemetry.pending
            or (
                self._task_runner.busy
                and self._task_runner.contract.blocks_telemetry
            )
        )

    @Property(bool, notify=telemetryRefreshChanged)
    def telemetryRefreshBusy(self) -> bool:
        return self._telemetry.pending

    @Property(str, notify=stateChanged)
    def armModeState(self) -> str:
        return self._mode_confirmation_state(
            ResourceEffect.ARM,
            "gravity",
        )

    @Property(str, notify=stateChanged)
    def gripperModeState(self) -> str:
        return self._mode_confirmation_state(
            ResourceEffect.GRIPPER,
            "gripper_mode",
        )

    @Property(bool, notify=stateChanged)
    def hardwareInspectionSupported(self) -> bool:
        return self._profile.supports_hardware_inspection

    @Property(bool, notify=stateChanged)
    def offlineMaintenanceSupported(self) -> bool:
        return self._profile.supports_offline_maintenance

    @Property(float, notify=stateChanged)
    def manualMotionDefaultSpeed(self) -> float:
        return self._profile.manual_motion_defaults.speed_rad_s

    @Property(float, notify=stateChanged)
    def manualMotionDefaultJointStepDeg(self) -> float:
        return self._profile.manual_motion_defaults.joint_step_deg

    @Property(int, notify=stateChanged)
    def manualMotionDefaultLinearStepMm(self) -> int:
        return self._profile.manual_motion_defaults.linear_step_mm

    @Property(float, notify=stateChanged)
    def manualMotionDefaultAngularStepDeg(self) -> float:
        return self._profile.manual_motion_defaults.angular_step_deg

    @Property(bool, notify=stateChanged)
    def motionEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.ARM_MOTION)

    @Property(bool, notify=stateChanged)
    def gripperControlEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.GRIPPER_MOTION)

    @Property(bool, notify=stateChanged)
    def modeControlEnabled(self) -> bool:
        return self.armModeControlEnabled

    @Property(bool, notify=stateChanged)
    def armModeControlEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.ARM_MODE)

    @Property(bool, notify=stateChanged)
    def gripperModeControlEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.GRIPPER_MODE)

    @Property(bool, notify=stateChanged)
    def estopReleaseEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.ESTOP_RELEASE)

    @Property(bool, notify=stateChanged)
    def profileSwitchEnabled(self) -> bool:
        return not self._policy.profile_switch_error()

    @Property(bool, notify=stateChanged)
    def planningEnabled(self) -> bool:
        return not self._policy.task_slot_error()

    @Property(bool, notify=stateChanged)
    def planExecutionEnabled(self) -> bool:
        return not self._policy.online_error(
            OnlineCapability.ARM_GRIPPER_MOTION
        )

    @Property(bool, notify=stateChanged)
    def diagnosticsEnabled(self) -> bool:
        return not self._policy.task_slot_error()

    @Property(bool, notify=stateChanged)
    def rosManagementEnabled(self) -> bool:
        return not self._policy.task_slot_error()

    @Property(bool, notify=stateChanged)
    def kinematicsReadEnabled(self) -> bool:
        return not self._policy.kinematics_read_error()

    @Property(bool, notify=stateChanged)
    def hardwareInspectionEnabled(self) -> bool:
        return not self._policy.hardware_inspection_error()

    @Property(bool, notify=stateChanged)
    def offlineMaintenanceEnabled(self) -> bool:
        return not self._policy.offline_device_error()

    @Property(bool, notify=stateChanged)
    def serviceStartEnabled(self) -> bool:
        return not self._policy.service_start_error()

    @Property(bool, notify=stateChanged)
    def serviceStopEnabled(self) -> bool:
        return not self._policy.service_stop_error()

    @Property(bool, notify=stateChanged)
    def configurationEnabled(self) -> bool:
        return not self._policy.configuration_error()

    @Property(bool, notify=stateChanged)
    def recordingStartEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.RECORDING_START)

    @Property(bool, notify=stateChanged)
    def recordingStopEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.RECORDING_STOP)

    @Property(bool, notify=stateChanged)
    def recordingRecoveryEnabled(self) -> bool:
        return not self._policy.recording_recovery_error()

    @Property(bool, notify=stateChanged)
    def playbackEnabled(self) -> bool:
        return not self._policy.online_error(OnlineCapability.PLAYBACK)

    @Property(str, notify=stateChanged)
    def motionGateText(self) -> str:
        if self._uncertain_ack_pending:
            return "已确认现场状态；等待一轮新鲜遥测后解除互锁"
        return self._policy.motion_gate_text

    @Property(str, notify=stateChanged)
    def motionRecoveryAction(self) -> str:
        return self._policy.motion_recovery_action

    @Property(str, notify=stateChanged)
    def motionRecoveryLabel(self) -> str:
        return {
            "start_server": f"启动 {self._profile_name.upper()} 控制服务",
            "refresh": "立即刷新控制状态",
            "restart_server": "重启控制服务",
            "position_hold": "切换到位置保持",
        }.get(self.motionRecoveryAction, "")

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=stateChanged)
    def lastError(self) -> str:
        return self._last_error or self._health_error

    @Property("QVariantList", notify=jointTelemetryChanged)
    def joints(self) -> list[dict[str, Any]]:
        return self._joint_rows

    @Property(float, notify=gripperTelemetryChanged)
    def gripper(self) -> float:
        return -1.0 if self._gripper is None else self._gripper

    @Property(float, notify=gripperTelemetryChanged)
    def gripperMeasured(self) -> float:
        return -1.0 if self._gripper is None else self._gripper

    @Property(float, notify=gripperTelemetryChanged)
    def gripperTarget(self) -> float:
        return -1.0 if self._gripper_target is None else self._gripper_target

    @Property(str, notify=operationFeedbackChanged)
    def operationFeedbackState(self) -> str:
        return self._operation_feedback_state

    @Property(str, notify=operationFeedbackChanged)
    def operationFeedbackTitle(self) -> str:
        return self._operation_feedback_title

    @Property(str, notify=operationFeedbackChanged)
    def operationFeedbackMessage(self) -> str:
        return self._operation_feedback_message

    @Property(bool, notify=operationFeedbackChanged)
    def operationFeedbackDismissible(self) -> bool:
        return self._operation_feedback_state in {"success", "warning", "error"}

    @Property(str, notify=cameraStateChanged)
    def cameraSummary(self) -> str:
        return self._camera.summary

    @Property(str, notify=cameraStateChanged)
    def cameraDetails(self) -> str:
        return self._camera.details

    @Property(str, notify=cameraPreviewChanged)
    def cameraPreviewSource(self) -> str:
        return self._camera.preview_source

    @Property(bool, notify=cameraPreviewChanged)
    def cameraPreviewAvailable(self) -> bool:
        return bool(self._camera.preview_source)

    @Property(bool, notify=cameraStateChanged)
    def cameraBridgeOnline(self) -> bool:
        return self._camera.bridge_online

    @Property(bool, notify=cameraStateChanged)
    def cameraReady(self) -> bool:
        return self._camera.ready

    @Property(bool, notify=cameraStateChanged)
    def cameraBusy(self) -> bool:
        return self._camera.busy

    @Property(str, notify=teachingChanged)
    def recordingSummary(self) -> str:
        return self._teaching.summary

    @Property(bool, notify=teachingChanged)
    def recordingActive(self) -> bool:
        return self._teaching.active

    @Property(str, notify=teachingChanged)
    def recordingState(self) -> str:
        return self._teaching.state

    @Property(bool, notify=stateChanged)
    def gripperFreeDrive(self) -> bool:
        return self._gripper_free_drive

    @Property(float, notify=stateChanged)
    def gravityCompFactor(self) -> float:
        return self._gravity_comp_factor

    @Property(str, notify=stateChanged)
    def eePoseText(self) -> str:
        return self._ee_pose_text

    @Property(str, notify=stateChanged)
    def eeAxisText(self) -> str:
        return self._ee_axis_text

    @Property(str, notify=stateChanged)
    def eeMotionText(self) -> str:
        return self._ee_motion_text

    @Property(QObject, constant=True)
    def logModel(self) -> ConsoleLogModel:
        return self._log_model

    @Property(str, notify=planChanged)
    def planState(self) -> str:
        return self._plan.state

    @Property(str, notify=planChanged)
    def planStatus(self) -> str:
        return self._plan.status

    @Property(str, notify=planChanged)
    def planId(self) -> str:
        return self._plan.plan_id

    @Property(str, notify=planChanged)
    def planFrame(self) -> str:
        return self._plan.frame_id

    @Property(str, notify=planChanged)
    def planProfile(self) -> str:
        return self._plan.profile_name

    @Property(str, notify=planChanged)
    def planInstruction(self) -> str:
        return self._plan.instruction

    @Property(bool, notify=planChanged)
    def planCurrent(self) -> bool:
        return self._plan.current

    @Property(str, notify=planChanged)
    def graspSummary(self) -> str:
        return self._plan.grasp_summary

    @Property(str, notify=planChanged)
    def graspPreviewSource(self) -> str:
        return self._plan.grasp_preview_source

    @Property(bool, notify=planChanged)
    def graspPreviewAvailable(self) -> bool:
        return self._plan.grasp_preview_available

    @Property(str, notify=planChanged)
    def graspBasePositionText(self) -> str:
        return self._plan.grasp_base_position_text

    @Property("QVariantList", notify=planChanged)
    def planSegments(self) -> list[dict[str, Any]]:
        return self._plan.segments

    @Property("QVariantList", notify=planChanged)
    def planSafety(self) -> list[dict[str, Any]]:
        return self._plan.safety

    @Property(bool, notify=planChanged)
    def planSafetyPassed(self) -> bool:
        return self._plan.safety_passed

    @Property("QVariantList", notify=preflightChanged)
    def preflightItems(self) -> list[dict[str, Any]]:
        return self._diagnostics.items

    @Property(str, notify=preflightChanged)
    def preflightState(self) -> str:
        return self._diagnostics.state

    @Property(str, notify=preflightChanged)
    def preflightStatus(self) -> str:
        return self._diagnostics.status

    @Property(bool, notify=startupStateChanged)
    def startupControlReady(self) -> bool:
        return self.motionEnabled

    @Property(bool, notify=startupStateChanged)
    def startupRosReady(self) -> bool:
        return self._camera.bridge_online

    @Property(bool, notify=startupStateChanged)
    def startupCameraReady(self) -> bool:
        return self._camera.ready

    @Property(bool, notify=startupStateChanged)
    def startupPreflightReady(self) -> bool:
        return self._diagnostics.state == "ready"

    @Property(bool, notify=startupStateChanged)
    def startupReady(self) -> bool:
        return (
            self.startupControlReady
            and self.startupRosReady
            and self.startupCameraReady
            and self.startupPreflightReady
        )

    @Property(str, notify=startupStateChanged)
    def startupGateText(self) -> str:
        if not self.startupControlReady:
            return self.motionGateText
        if not self.startupRosReady:
            return "ROS 2 链路未启动或相机桥不可达"
        if not self.startupCameraReady:
            return "RGB-D 还没有新鲜的同步帧"
        if not self.startupPreflightReady:
            return self._diagnostics.status
        return "启动步骤已全部通过"

    @property
    def _profile(self) -> RuntimeProfile:
        return self._profiles[self._profile_name]

    @property
    def _policy(self) -> InteractionPolicy:
        cache_key = (
            self._connected,
            self._backend_matched,
            self._connection_issue,
            self.telemetryFresh,
            self._robot_running,
            self._faulted,
            self._fault_message,
            self._control_mode,
            self._gripper_free_drive,
            self._commands.command_busy,
            self._task_runner.busy,
            self._task_runner.label,
            self._commands.emergency_busy,
            self._teaching.active,
            self._uncertain,
            self._estopped,
            self._uncertain_ack_pending,
            self._teaching.state,
            self._profile.supports_hardware_inspection,
            self._profile.supports_offline_maintenance,
        )
        if (
            self._policy_cache is not None
            and cache_key == self._policy_cache_key
        ):
            return self._policy_cache
        self._policy_cache_key = cache_key
        self._policy_cache = InteractionPolicy(
            connected=self._connected,
            backend_matched=self._backend_matched,
            connection_issue=self._connection_issue,
            telemetry_fresh=self.telemetryFresh,
            robot_running=self._robot_running,
            faulted=self._faulted,
            fault_message=self._fault_message,
            control_mode=self._control_mode,
            gripper_free_drive=self._gripper_free_drive,
            command_busy=self._commands.command_busy,
            task_busy=self._task_runner.busy,
            task_label=self._task_runner.label,
            emergency_busy=self._commands.emergency_busy,
            recording_active=self._teaching.active,
            outcome_uncertain=self._uncertain,
            estopped=self._estopped,
            outcome_recheck_requested=self._uncertain_ack_pending,
            recording_state=self._teaching.state,
            supports_hardware_inspection=(
                self._profile.supports_hardware_inspection
            ),
            supports_offline_maintenance=(
                self._profile.supports_offline_maintenance
            ),
        )
        return self._policy_cache

    def _mode_confirmation_state(
        self,
        effect: ResourceEffect,
        result_handler: str,
    ) -> str:
        if self._uncertain:
            return "uncertain"
        if (
            self._commands.command_busy
            and self._commands.current_effects & effect
            and self._commands.current_result_handler == result_handler
        ):
            return "pending"
        if (
            self._connected
            and self._backend_matched
            and self.telemetryFresh
        ):
            return "confirmed"
        return "unconfirmed"

    def _state_fingerprint(self) -> tuple[Any, ...]:
        return (
            self._profile_name,
            self._connected,
            self._backend_matched,
            self._connection_issue,
            self._backend,
            self._control_mode,
            self._robot_running,
            self._faulted,
            self._fault_message,
            self._commands.command_busy,
            self._task_runner.busy,
            self._task_runner.contract,
            self._task_runner.kind,
            self._task_runner.label,
            self._commands.emergency_busy,
            self._uncertain,
            self._uncertain_ack_pending,
            self._estopped,
            self.telemetryFresh,
            self._status_text,
            self._last_error,
            self._draft_locks.fingerprint,
            self._teaching.fingerprint,
            self._gripper_free_drive,
            self._gravity_comp_factor,
            self._ee_pose_text,
            self._ee_axis_text,
            self._ee_motion_text,
            self.dynamicsSummary,
        )

    # ------------------------------------------------------------------
    # Profile, telemetry, and logging
    # ------------------------------------------------------------------

    @Slot(str)
    def setProfile(self, name: str) -> None:
        if name not in self._profiles or name == self._profile_name:
            return
        draft_error = self._draft_locks.error_for_all()
        if draft_error:
            self._set_error(f"{draft_error}，不能切换 Real / Sim 配置")
            return
        reason = self._policy.profile_switch_error()
        if reason:
            self._set_error(f"{reason}，不能切换 Real / Sim 配置")
            return
        self._profile_name = name
        self._commands.select_profile()
        self._connected = False
        self._backend_matched = False
        self._connection_issue = (
            "checking" if self._monitoring_started else "unprobed"
        )
        self._backend = ""
        self._control_mode = ""
        self._robot_running = False
        self._faulted = False
        self._fault_message = ""
        self._last_error = ""
        self._health_error = ""
        self._set_operation_feedback("idle", "", "")
        self._status_text = f"已选择{self._profile.label}，正在核验后端"
        self._joint_rows = self._empty_joint_rows()
        self._gripper = None
        self._gripper_target = None
        if self._teaching.select_profile(name):
            self.teachingChanged.emit()
        self._gripper_free_drive = False
        self._gravity_comp_factor = 1.0
        self._ee_pose_text = "未读取"
        self._ee_axis_text = ""
        self._ee_motion_text = ""
        self._info = {}
        self._telemetry.select_profile(self._profile, notify=False)
        self._camera.select_profile(self._profile, notify=False)
        self._plan.select_profile(self._profile)
        if self._diagnostics.select_profile(self._profile):
            self.preflightChanged.emit()
        self._append_log(
            f"运行配置切换为 {self._profile.label}："
            f"{self._profile.expected_backend} @ {self.endpoint}"
        )
        self.jointTelemetryChanged.emit()
        self.gripperTelemetryChanged.emit()
        self.telemetryTimingChanged.emit()
        self.cameraStateChanged.emit()
        self.stateChanged.emit()
        if self._monitoring_started:
            self.refreshNow()

    @Slot(bool, bool, bool)
    def setDraftLocks(
        self,
        arm_target: bool,
        gripper_target: bool,
        configuration: bool,
    ) -> None:
        if self._draft_locks.update(
            arm_target=bool(arm_target),
            gripper_target=bool(gripper_target),
            configuration=bool(configuration),
        ):
            self.draftLocksChanged.emit()

    @Slot()
    def startMonitoring(self) -> None:
        if self._monitoring_started or self._shutting_down:
            return
        self._monitoring_started = True
        if self._connection_issue == "unprobed":
            self._connection_issue = "checking"
            self.stateChanged.emit()
        self._telemetry.start_monitoring()
        self._camera.start_monitoring()
        self._append_log("A1Z Console 已启动；运动命令自动重发已禁用。")

    @Slot()
    def refreshNow(self) -> None:
        if self._telemetry.refresh(force_info=True):
            return
        if (
            self._task_runner.busy
            and self._task_runner.contract.blocks_telemetry
        ):
            label = self._task_runner.label or "当前设备任务"
            self._set_operation_feedback(
                "warning",
                "刷新暂不可用",
                f"{label}执行期间遥测读取已暂停",
            )

    @Slot()
    def acknowledgeUncertain(self) -> None:
        if not self._uncertain:
            return
        self._uncertain_ack_pending = True
        self._status_text = "现场确认已记录；等待一轮新鲜遥测后解除互锁"
        self._append_log("操作员已确认现场；结果不确定锁等待新鲜遥测。")
        self.stateChanged.emit()
        self.refreshNow()

    @Slot()
    def clearLogs(self) -> None:
        self._log_flush_timer.stop()
        self._pending_log_lines.clear()
        self._log_model.clear()

    @Slot()
    def neutralizeUi(self) -> None:
        # Motion is edge-triggered and never held, so there is no zero command to
        # publish.  This hook documents and enforces that window deactivation
        # cannot leave a QML timer or key-repeat producer alive.
        self._append_log("窗口失焦：已确认不存在保持式运动输入。")

    @Slot(object)
    def _on_telemetry_result(self, payload: object) -> None:
        if self._shutting_down:
            return
        if not isinstance(payload, TelemetryResult):
            self._set_error("遥测通道返回了无效结果")
            return
        previous_state = self._state_fingerprint()
        if not payload.success:
            message = payload.error
            next_status = (
                "后端身份冲突" if payload.mismatch else "控制服务离线"
            )
            teaching_changed = self._teaching.mark_endpoint_unavailable()
            if teaching_changed:
                self.teachingChanged.emit()
            changed = (
                self._connected
                or self._backend_matched
                or self._status_text != next_status
                or self._health_error != message
                or teaching_changed
            )
            self._connected = False
            self._backend_matched = False
            self._connection_issue = (
                "backend_mismatch" if payload.mismatch else "offline"
            )
            self._status_text = next_status
            self._health_error = message
            if changed:
                self.stateChanged.emit()
            return

        info = payload.info
        has_info_snapshot = info is not None
        if has_info_snapshot:
            self._apply_info(info)
        status = payload.status
        self._apply_status(status)
        self._connected = True
        self._backend_matched = self._backend == self._profile.expected_backend
        self._connection_issue = (
            "" if self._backend_matched else "backend_mismatch"
        )
        if not self._backend_matched and self._teaching.mark_endpoint_unavailable():
            self.teachingChanged.emit()
        if self._faulted:
            self._health_error = self._fault_message or "机械臂控制循环故障"
            self._status_text = "控制服务在线 · 控制循环故障"
        elif not self._robot_running:
            self._health_error = "机械臂控制循环未运行，请重启控制服务"
            self._status_text = "控制服务在线 · 控制循环停止"
        else:
            self._health_error = ""
            self._status_text = "遥测在线 · 控制循环运行中"
        positions = list(status.get("pos_deg", []) or [])
        if (
            self._uncertain
            and self._uncertain_ack_pending
            and self._backend_matched
            and has_info_snapshot
            and len(positions) >= 6
        ):
            self._uncertain = False
            self._uncertain_ack_pending = False
            self._append_log("新鲜遥测已确认，结果不确定互锁解除。")
            if not self._faulted and self._robot_running:
                self._status_text = "现场状态与新鲜遥测已确认 · 控制入口恢复"
            self._set_operation_feedback(
                "success",
                "状态重新确认",
                "已收到同一配置的新鲜关节遥测，结果不确定互锁解除",
            )
        if payload.timing_changed:
            self.telemetryTimingChanged.emit()
        if (
            self._state_fingerprint() != previous_state
            or payload.freshness_changed
        ):
            self.stateChanged.emit()
        if (
            self._uncertain
            and self._uncertain_ack_pending
            and not has_info_snapshot
        ):
            QTimer.singleShot(0, self.refreshNow)

    @Slot(bool)
    def _on_telemetry_age_changed(self, freshness_changed: bool) -> None:
        state_changed = False
        if self.telemetryAgeMs > 3000 and self._connected:
            self._connected = False
            self._connection_issue = "stale"
            self._status_text = "遥测超时，运动已锁定"
            if self._teaching.mark_endpoint_unavailable():
                self.teachingChanged.emit()
            state_changed = True
        self.telemetryTimingChanged.emit()
        if state_changed or freshness_changed:
            self.stateChanged.emit()

    def _apply_info(self, info: dict[str, Any]) -> None:
        self._info = dict(info)
        self._backend = str(info.get("backend", ""))
        self._control_mode = str(info.get("control_mode", ""))
        if "running" in info:
            self._robot_running = bool(info["running"])
        if "faulted" in info:
            self._faulted = bool(info["faulted"])
        if "fault_message" in info:
            self._fault_message = str(info.get("fault_message", "") or "")
        if self._teaching.apply_info(info):
            self.teachingChanged.emit()
        self._gripper_free_drive = bool(info.get("gripper_free_drive", False))
        self._gravity_comp_factor = float(info.get("gravity_comp_factor", 1.0))
        limits = dict(info.get("joint_limits_deg", {}) or {})
        rows = []
        for index, old in enumerate(self._joint_rows):
            pair = limits.get(f"J{index + 1}", [old["minimum"], old["maximum"]])
            rows.append(
                {
                    **old,
                    "minimum": float(pair[0]),
                    "maximum": float(pair[1]),
                }
            )
        if rows != self._joint_rows:
            self._joint_rows = rows
            self.jointTelemetryChanged.emit()

    def _apply_status(self, status: dict[str, Any]) -> None:
        positions = list(status.get("pos_deg", []) or [])
        velocities = list(status.get("vel_rad_s", []) or [])
        torques = list(status.get("torque_nm", []) or [])
        errors = list(status.get("error_codes", []) or [])
        temp_mos = list(status.get("temp_mos_c", []) or [])
        temp_rotor = list(status.get("temp_rotor_c", []) or [])
        rows = []
        for index in range(6):
            previous = self._joint_rows[index]
            error_code = (
                int(errors[index])
                if index < len(errors)
                else int(previous["errorCode"])
            )
            motor_a_raw_status = index < 3
            error_is_fault = (
                not motor_a_raw_status and error_code not in (0, 1)
            )
            if motor_a_raw_status:
                error_status = f"原始 {error_code}"
            elif error_code == 1:
                error_status = "正常"
            elif error_code == 0:
                error_status = "禁用"
            else:
                error_status = f"故障 {error_code:X}"
            rows.append(
                {
                    "name": f"J{index + 1}",
                    "position": float(positions[index]) if index < len(positions) else previous["position"],
                    "velocity": float(velocities[index]) if index < len(velocities) else previous["velocity"],
                    "torque": float(torques[index]) if index < len(torques) else previous["torque"],
                    "minimum": previous["minimum"],
                    "maximum": previous["maximum"],
                    "errorCode": error_code,
                    "errorStatus": error_status,
                    "errorIsFault": error_is_fault,
                    "tempMos": float(temp_mos[index]) if index < len(temp_mos) else previous["tempMos"],
                    "tempRotor": float(temp_rotor[index]) if index < len(temp_rotor) else previous["tempRotor"],
                }
            )
        if rows != self._joint_rows:
            self._joint_rows = rows
            self.jointTelemetryChanged.emit()
        legacy_gripper = status.get("gripper")
        measured = status.get("gripper_measured", legacy_gripper)
        target = status.get("gripper_target", legacy_gripper)
        next_gripper = (
            float(measured) if isinstance(measured, (int, float)) else None
        )
        next_gripper_target = (
            float(target) if isinstance(target, (int, float)) else None
        )
        if (
            next_gripper != self._gripper
            or next_gripper_target != self._gripper_target
        ):
            self._gripper = next_gripper
            self._gripper_target = next_gripper_target
            self.gripperTelemetryChanged.emit()
        if "estopped" in status:
            self._estopped = bool(status["estopped"])
        if "running" in status:
            self._robot_running = bool(status["running"])
        if "faulted" in status:
            self._faulted = bool(status["faulted"])
        if "fault_message" in status:
            self._fault_message = str(status.get("fault_message", "") or "")

    def _append_log(self, message: str) -> None:
        cleaned = str(message).strip()
        if not cleaned:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        for line in cleaned.splitlines():
            self._pending_log_lines.append(f"[{stamp}] {line.rstrip()}")
        if not self._log_flush_timer.isActive():
            self._log_flush_timer.start()

    def _flush_logs(self) -> None:
        if not self._pending_log_lines:
            return
        pending = self._pending_log_lines
        self._pending_log_lines = []
        self._log_model.append_lines(pending)

    def _set_operation_feedback(
        self,
        state: str,
        title: str,
        message: str,
    ) -> None:
        state = str(state)
        title = str(title)
        message = str(message)
        if (
            state == self._operation_feedback_state
            and title == self._operation_feedback_title
            and message == self._operation_feedback_message
        ):
            return
        self._operation_feedback_state = state
        self._operation_feedback_title = title
        self._operation_feedback_message = message
        self.operationFeedbackChanged.emit()

    @Slot()
    def dismissOperationFeedback(self) -> None:
        if not self.operationFeedbackDismissible:
            return
        self._last_error = ""
        self._set_operation_feedback("idle", "", "")
        self.stateChanged.emit()

    def _set_error(self, message: str) -> None:
        self._last_error = str(message)
        self._status_text = "操作失败"
        self._append_log(f"错误：{message}")
        self._set_operation_feedback("error", "操作未执行", self._last_error)
        self.stateChanged.emit()

    def _invalidate_resource_state(self, effects: ResourceEffect) -> None:
        if effects & ResourceEffect.ARM:
            self.armStateInvalidated.emit()
        if effects & ResourceEffect.GRIPPER:
            self._gripper = None
            self._gripper_target = None
            self.gripperTelemetryChanged.emit()
            self.gripperStateInvalidated.emit()

    def _apply_authoritative_command_state(
        self,
        data: dict[str, Any],
    ) -> None:
        """Project state explicitly confirmed by a successful command reply."""

        if "estopped" in data:
            self._estopped = bool(data["estopped"])
        if "gripper_free_drive" in data:
            self._gripper_free_drive = bool(data["gripper_free_drive"])

    @staticmethod
    def _empty_joint_rows() -> list[dict[str, Any]]:
        return [
            {
                "name": f"J{index + 1}",
                "position": 0.0,
                "velocity": 0.0,
                "torque": 0.0,
                "minimum": 0.0,
                "maximum": 0.0,
                "errorCode": 0,
                "errorStatus": "原始 0" if index < 3 else "禁用",
                "errorIsFault": False,
                "tempMos": -1.0,
                "tempRotor": -1.0,
            }
            for index in range(6)
        ]

    # ------------------------------------------------------------------
    # Serialized SDK operations
    # ------------------------------------------------------------------

    def _motion_gate_error(
        self,
        capability: OnlineCapability = OnlineCapability.ARM_MOTION,
    ) -> str:
        return self._policy.online_error(capability)

    def _exclusive_task_gate_error(
        self,
        *,
        allow_recording: bool = False,
    ) -> str:
        return self._policy.task_slot_error(allow_recording=allow_recording)

    @staticmethod
    def _friendly_operation_error(message: object) -> str:
        text = str(message).strip() or "未知错误"
        mappings = (
            (
                "Robot control loop is not running",
                "机械臂控制循环未运行，请重启控制服务",
            ),
            (
                "Robot control loop faulted while executing joint move",
                "关节运动期间控制循环故障",
            ),
            (
                "Robot control loop stopped while executing joint move",
                "关节运动期间控制循环停止",
            ),
            (
                "Robot entered estop while executing joint move",
                "关节运动期间进入软急停",
            ),
            (
                "Position motion requires position-hold mode",
                "位置运动要求位置保持模式，请先切换到位置保持",
            ),
            (
                "Server was started without --with-gripper",
                "控制服务启动时未启用 G1Z 夹爪",
            ),
            (
                "Gripper is in free-drive mode",
                "夹爪处于自由拖动模式，请先恢复夹爪控制",
            ),
            (
                "No live gripper CAN feedback",
                "没有收到 G1Z 的实时 CAN 位置反馈",
            ),
            (
                "Joint target was not reached from SDK feedback",
                "控制服务已接收关节目标，但实际反馈未到位",
            ),
            (
                "Joint feedback did not settle after joint jog",
                "关节点动已发出，但反馈在等待时间内仍未稳定",
            ),
            (
                "Joint feedback did not settle after Cartesian jog",
                "末端点动已发出，但关节反馈在等待时间内仍未稳定",
            ),
            (
                "Gripper target was not reached from SDK feedback",
                "控制服务已接收夹爪目标，但实际开度未到位",
            ),
            (
                "Recording is active",
                "示教录制仍在进行；请先停止并保存",
            ),
            (
                "Trajectory backend mismatch",
                "轨迹来源与当前后端不一致，已禁止回放",
            ),
            (
                "Trajectory has no backend metadata",
                "旧轨迹缺少后端来源信息，已禁止回放",
            ),
        )
        for source, replacement in mappings:
            if source in text:
                detail = text.split(":", 1)[1].strip() if ":" in text else ""
                return replacement + (f"：{detail}" if detail else "")
        return text

    def _set_success_feedback(
        self,
        label: str,
        handler: str,
        data: dict[str, Any],
    ) -> None:
        state = "success"
        message = f"{label}完成"

        if handler == "motion":
            motion_data = dict(data.get("response", data) or {})
            verification = dict(motion_data.get("verification", {}) or {})
            if motion_data.get("motion_performed") is False:
                state = "warning"
                message = f"{label}未产生运动：目标已经在当前位置"
            elif verification.get("settled") is True:
                message = (
                    f"{label}运动已稳定 · 最大单次变化 "
                    f"{float(verification.get('max_sample_delta_deg', 0.0)):.4f}°"
                )
            elif verification:
                message = (
                    f"{label}已到位 · 最大误差 "
                    f"{float(verification.get('max_error_deg', 0.0)):.3f}°"
                )
        elif handler == "gripper":
            verification = dict(data.get("verification", {}) or {})
            if data.get("motion_performed") is False:
                state = "warning"
                message = f"{label}未产生运动：夹爪已经在该开度"
            elif verification:
                message = (
                    f"{label}已到位 · 实际 "
                    f"{float(verification.get('measured', 0.0)):.3f}"
                )
        elif handler == "helper":
            snapshot = dict(data.get("snapshot", {}) or {})
            joint_verification = dict(
                snapshot.get("joint_verification", {}) or {}
            )
            verification = dict(snapshot.get("verification", {}) or {})
            if joint_verification.get("settled") is True:
                message = (
                    f"{label}运动已稳定 · 最大单次变化 "
                    f"{float(joint_verification.get('max_sample_delta_deg', 0.0)):.4f}°"
                )
            elif verification:
                message = f"{label}完成 · 实际 FK 已刷新"
        elif handler == "grasp":
            success = bool(data.get("success", False))
            reason = str(data.get("failure_reason", "") or "")
            phase = str(data.get("phase", "") or "")
            if not success:
                state = "warning"
                message = (
                    f"{label}完成，但未达到预期"
                    + (f" · {reason}" if reason else "")
                )
            elif phase:
                message = f"{label}完成 · {phase}"
        elif handler == "recording" and data.get("safe_state_restored") is False:
            state = "warning"
            message = (
                f"{label}完成，但未能自动恢复位置保持/夹爪控制："
                f"{data.get('restore_warning', '请核对现场状态')}"
            )

        self._set_operation_feedback(state, label, message)

    def _submit_verified(
        self,
        label: str,
        command: str,
        args: dict[str, Any] | None = None,
        *,
        capability: OnlineCapability,
        timeout_s: float = 120.0,
        result_handler: str = "",
        allowed_drafts: DraftResource = DraftResource.NONE,
    ) -> None:
        gate_error = self._policy.online_error(capability)
        if gate_error:
            self._set_error(gate_error)
            return
        profile = self._profile

        def operation() -> dict[str, Any]:
            client = A1ZProtocolClient(profile)
            data, endpoint = client.verified_request(
                command,
                args,
                timeout_s=timeout_s,
                require_running=capability
                not in {
                    OnlineCapability.RECORDING_STOP,
                    OnlineCapability.ESTOP_RELEASE,
                },
                ambiguous_after_send=True,
            )
            return {
                "data": data,
                "backend": endpoint.backend,
                "controlMode": endpoint.control_mode,
            }

        self._submit_operation(
            label,
            operation,
            effects=online_capability_effects(capability),
            result_handler=result_handler,
            allowed_drafts=allowed_drafts,
        )

    def _submit_operation(
        self,
        label: str,
        operation: Callable[[], dict[str, Any]],
        *,
        effects: ResourceEffect,
        result_handler: str = "",
        allowed_drafts: DraftResource = DraftResource.NONE,
    ) -> None:
        if self._shutting_down:
            return
        draft_error = self._draft_locks.error_for_effects(
            effects,
            allowed=allowed_drafts,
        )
        if draft_error:
            self._set_error(draft_error)
            return
        if self._commands.command_busy or self._task_runner.busy:
            self._set_error("已有设备命令或外部任务正在执行")
            return
        if self._commands.emergency_busy:
            self._set_error("软急停正在发送，其余操作已锁定")
            return
        sequence = self._commands.submit_command(
            DeviceCommandRequest(
                label=label,
                operation=operation,
                effects=effects,
                result_handler=result_handler,
            )
        )
        if sequence is None:
            self._set_error("设备命令执行通道正在关闭或已经占用")
            return
        self._last_error = ""
        self._status_text = f"{label}执行中"
        self._append_log(f"开始 #{sequence}：{label}")
        self._set_operation_feedback("running", label, self._status_text)
        self.stateChanged.emit()

    @Slot(object)
    def _on_operation_finished(self, payload: object) -> None:
        if self._shutting_down:
            return
        if not isinstance(payload, DeviceCommandResult):
            self._set_error("设备命令执行通道返回了无效结果")
            return
        result = payload
        label = result.label
        if result.stale_profile:
            message = f"忽略来自旧 profile 的{label}结果"
            self._append_log(message)
            self.operationFinished.emit(label, False, message)
            self.stateChanged.emit()
            return
        if result.superseded_by_emergency:
            message = f"{label}的返回晚于软急停，结果不再用于更新界面状态"
            self._append_log(message)
            self.operationFinished.emit(label, False, message)
            self.stateChanged.emit()
            return
        if not result.success:
            self._last_error = self._friendly_operation_error(
                result.error or "未知错误"
            )
            if result.ambiguous:
                self._uncertain = True
                self._uncertain_ack_pending = False
                self._invalidate_resource_state(result.effects)
                self._status_text = "命令结果不确定，运动已锁定"
                self._set_operation_feedback(
                    "uncertain",
                    label,
                    f"{label}结果不确定：{self._last_error}",
                )
            else:
                self._status_text = f"{label}失败"
                self._set_operation_feedback(
                    "error",
                    label,
                    f"{label}失败：{self._last_error}",
                )
            self._append_log(
                f"失败 #{result.sequence}：{label}：{self._last_error}"
            )
            self.operationFinished.emit(label, False, self._last_error)
            self.stateChanged.emit()
            return

        envelope = result.data
        data = dict(envelope.get("data", {}) or {})
        if envelope.get("backend"):
            self._backend = str(envelope["backend"])
            self._backend_matched = self._backend == self._profile.expected_backend
        if envelope.get("controlMode"):
            self._control_mode = str(envelope["controlMode"])
        handler = result.result_handler
        gripper_snapshot_applied = False
        self._apply_authoritative_command_state(data)
        if handler == "status":
            self._apply_status(data)
        elif handler == "info":
            self._apply_info(data)
        elif handler == "recording":
            if self._teaching.apply_command_result(data):
                self.teachingChanged.emit()
            if "control_mode" in data:
                self._control_mode = str(data["control_mode"])
            if "gripper_free_drive" in data:
                self._gripper_free_drive = bool(data["gripper_free_drive"])
            verification = dict(data.get("verification", {}) or {})
            measured = list(verification.get("measured_deg", []) or [])
            if len(measured) >= 6:
                self._apply_status({"pos_deg": measured[:6]})
        elif handler == "gravity":
            if "gravity_comp_factor" in data:
                self._gravity_comp_factor = float(data["gravity_comp_factor"])
            if "control_mode" in data:
                self._control_mode = str(data["control_mode"])
        elif handler == "gripper":
            target = data.get("gripper_target", data.get("gripper"))
            measured = data.get("gripper_measured")
            changed = False
            if isinstance(target, (int, float)):
                next_target = float(target)
                changed = changed or next_target != self._gripper_target
                self._gripper_target = next_target
                gripper_snapshot_applied = True
            if isinstance(measured, (int, float)):
                next_measured = float(measured)
                changed = changed or next_measured != self._gripper
                self._gripper = next_measured
                gripper_snapshot_applied = True
            if changed or gripper_snapshot_applied:
                self.gripperTelemetryChanged.emit()
        elif handler == "motion":
            motion_data = dict(data.get("response", data) or {})
            verification = dict(motion_data.get("verification", {}) or {})
            measured = list(verification.get("measured_deg", []) or [])
            if len(measured) >= 6:
                self._apply_status({"pos_deg": measured[:6]})
        elif handler == "helper":
            snapshot = dict(data.get("snapshot", {}) or {})
            if snapshot:
                self._apply_helper_snapshot(snapshot)
        effects = result.effects
        if effects & ResourceEffect.ARM:
            self.armPoseChanged.emit()
        if effects & ResourceEffect.GRIPPER and not gripper_snapshot_applied:
            self._invalidate_resource_state(ResourceEffect.GRIPPER)
        self._last_error = ""
        self._status_text = f"{label}完成"
        self._set_success_feedback(label, handler, data)
        self._append_log(
            f"完成 #{result.sequence}：{label}"
            + (f" · {json.dumps(data, ensure_ascii=False)}" if data else "")
        )
        self.operationFinished.emit(label, True, self._status_text)
        self.stateChanged.emit()
        QTimer.singleShot(80, self.refreshNow)

    def _apply_helper_snapshot(self, snapshot: dict[str, Any]) -> None:
        joint_pos = list(snapshot.get("joint_pos_deg", []) or [])
        status: dict[str, Any] = {
            "pos_deg": joint_pos,
            "vel_rad_s": [0.0] * 6,
            "torque_nm": [0.0] * 6,
            "gripper": snapshot.get("gripper"),
            "gripper_target": snapshot.get("gripper_target"),
            "gripper_measured": snapshot.get("gripper_measured"),
        }
        for key in ("estopped", "running", "faulted", "fault_message"):
            if key in snapshot:
                status[key] = snapshot[key]
        self._apply_status(status)
        self._backend = str(snapshot.get("backend", self._backend))
        self._control_mode = str(snapshot.get("control_mode", self._control_mode))
        pose = dict(snapshot.get("pose", {}) or {})
        xyz = list(pose.get("xyz_mm", []) or [])
        rpy = list(pose.get("rpy_deg", []) or [])
        if len(xyz) >= 3 and len(rpy) >= 3:
            self._ee_pose_text = (
                "XYZ ["
                + ", ".join(f"{float(value):.1f}" for value in xyz[:3])
                + "] mm · RPY ["
                + ", ".join(f"{float(value):.1f}" for value in rpy[:3])
                + "]°"
            )
        rotation = list(pose.get("rotation_matrix", []) or [])
        if len(rotation) == 3 and all(isinstance(row, list) and len(row) == 3 for row in rotation):
            axes = []
            for column, axis_name in enumerate(("X", "Y", "Z")):
                values = [float(rotation[row][column]) for row in range(3)]
                axes.append(
                    f"{axis_name}→[{values[0]:+.2f}, {values[1]:+.2f}, {values[2]:+.2f}]"
                )
            self._ee_axis_text = "Tool 轴在 Base 中：" + " · ".join(axes)
        requested = dict(snapshot.get("requested_step", {}) or {})
        verification = dict(snapshot.get("verification", {}) or {})
        if requested:
            delta = float(requested.get("delta", 0.0))
            unit = "m" if requested.get("kind") == "translation" else "°"
            self._ee_motion_text = (
                f"已执行 {str(requested.get('frame', '')).title()} "
                f"{str(requested.get('axis', '')).upper()} {delta:+g}{unit}"
            )
            if verification:
                self._ee_motion_text += (
                    f" · FK 误差 {float(verification.get('translation_error_mm', 0.0)):.2f} mm / "
                    f"{float(verification.get('orientation_error_deg', 0.0)):.2f}°"
                )

    @Slot()
    def refreshKinematics(self) -> None:
        gate_error = self._policy.kinematics_read_error()
        if gate_error:
            self._set_error(gate_error)
            return
        profile = self._profile
        kinematics = self._kinematics

        self._submit_operation(
            "读取末端 FK",
            lambda: kinematics.snapshot(profile),
            effects=ResourceEffect.NONE,
            result_handler="helper",
        )

    @Slot("QVariantList", float)
    def sendJointTarget(self, joints_deg: list[Any], speed: float) -> None:
        try:
            values = [float(value) for value in joints_deg]
        except (TypeError, ValueError) as exc:
            self._set_error(f"关节目标不是有效数字：{exc}")
            return
        if len(values) != 6 or any(not math.isfinite(value) for value in values):
            self._set_error("关节目标必须包含 6 个有限数值")
            return
        for index, value in enumerate(values):
            row = self._joint_rows[index]
            minimum = float(row["minimum"])
            maximum = float(row["maximum"])
            if minimum < maximum and not minimum <= value <= maximum:
                self._set_error(
                    f"J{index + 1} 目标 {value:.3f}° 超出软限位 "
                    f"[{minimum:.3f}, {maximum:.3f}]°"
                )
                return
        if not math.isfinite(float(speed)) or float(speed) <= 0.0:
            self._set_error("关节速度必须是大于 0 的有限数值")
            return
        self._submit_verified(
            "绝对关节运动",
            "move",
            {"joints": values, "speed": float(speed)},
            capability=OnlineCapability.ARM_MOTION,
            result_handler="motion",
            allowed_drafts=DraftResource.ARM_TARGET,
        )

    @Slot(int, float, float)
    def jogJoint(self, joint_index: int, delta_deg: float, speed: float) -> None:
        if not 0 <= joint_index < 6:
            self._set_error("关节编号超出 J1–J6")
            return
        if not math.isfinite(float(delta_deg)) or abs(float(delta_deg)) <= 1e-12:
            self._set_error("关节点动增量必须是非零有限数值")
            return
        if not math.isfinite(float(speed)) or float(speed) <= 0.0:
            self._set_error("关节速度必须是大于 0 的有限数值")
            return
        self._submit_verified(
            f"J{joint_index + 1} 点动 {float(delta_deg):+.2f}°",
            "joint_jog",
            {
                "joint_index": joint_index + 1,
                "delta_deg": float(delta_deg),
                "speed": float(speed),
            },
            capability=OnlineCapability.ARM_MOTION,
            result_handler="motion",
        )

    @Slot(str, str, float, str, float)
    def jogCartesian(
        self,
        kind: str,
        axis: str,
        delta: float,
        frame: str,
        speed: float,
    ) -> None:
        try:
            request = self._kinematics.prepare_step(
                kind,
                axis,
                delta,
                frame,
                speed,
            )
        except (TypeError, ValueError) as exc:
            self._set_error(str(exc))
            return
        gate_error = self._motion_gate_error()
        if gate_error:
            self._set_error(gate_error)
            return
        profile = self._profile
        kinematics = self._kinematics

        unit = "m" if request.kind == "translation" else "°"
        self._submit_operation(
            f"末端 {request.frame}/{request.axis.upper()} "
            f"{request.delta:+g}{unit}",
            lambda: kinematics.step(profile, request),
            effects=ResourceEffect.ARM,
            result_handler="helper",
        )

    @Slot(float)
    def setGripper(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            self._set_error("夹爪目标开度必须是 0.0–1.0 的有限数值")
            return
        self._submit_verified(
            f"夹爪开度 {value:.2f}",
            "gripper",
            {"value": value},
            capability=OnlineCapability.GRIPPER_MOTION,
            timeout_s=30.0,
            result_handler="gripper",
            allowed_drafts=DraftResource.GRIPPER_TARGET,
        )

    @Slot()
    def graspClose(self) -> None:
        self._submit_verified(
            "夹持并检测物体",
            "grasp_close",
            {"timeout_s": 15.0},
            capability=OnlineCapability.GRIPPER_MOTION,
            timeout_s=25.0,
            result_handler="grasp",
        )

    @Slot()
    def graspRelease(self) -> None:
        self._submit_verified(
            "释放夹爪",
            "grasp_release",
            {"timeout_s": 3.0},
            capability=OnlineCapability.GRIPPER_MOTION,
            timeout_s=10.0,
            result_handler="grasp",
        )

    @Slot()
    def emergencyStop(self) -> None:
        # This has a dedicated worker and the server handles it outside the
        # serialized motion lock, so an in-flight blocking move cannot delay it.
        if self._shutting_down:
            return
        if self._commands.emergency_busy:
            self._set_error("软急停请求已经在发送")
            return
        if not self._connected or not self._backend_matched:
            self._set_error("控制服务未连接或后端身份不匹配；请使用现场硬件急停")
            return
        profile = self._profile

        def operation() -> dict[str, Any]:
            client = A1ZProtocolClient(profile)
            data, endpoint = client.verified_request(
                "estop",
                timeout_s=5.0,
                require_running=True,
                ambiguous_after_send=True,
            )
            return {"data": data, "backend": endpoint.backend}

        if not self._commands.submit_emergency(
            EmergencyCommandRequest("软急停", operation)
        ):
            self._set_error("软急停执行通道正在关闭或已经占用")
            return
        self._append_log("发送高优先级软急停（独立通道、禁止重试）。")
        self._set_operation_feedback("running", "软急停", "软急停发送中")
        self.stateChanged.emit()

    @Slot(object)
    def _on_emergency_finished(self, payload: object) -> None:
        if self._shutting_down:
            return
        if not isinstance(payload, EmergencyCommandResult):
            self._set_error("软急停执行通道返回了无效结果")
            return
        result = payload
        if result.stale_profile:
            self._append_log("忽略来自旧 profile 的软急停回调。")
            self.stateChanged.emit()
            return
        if result.success:
            self._estopped = True
            self._status_text = "软急停已锁定"
            self._last_error = ""
            self._append_log("高优先级软急停已确认。")
            self._set_operation_feedback("success", "软急停", self._status_text)
            self.operationFinished.emit("软急停", True, self._status_text)
        else:
            self._last_error = self._friendly_operation_error(
                result.error or "软急停失败"
            )
            if result.ambiguous:
                # Once bytes were sent, fail closed: the robot may already be
                # stopped even if the acknowledgment was lost.
                self._estopped = True
                self._uncertain = True
                self._uncertain_ack_pending = False
                self._status_text = "急停结果不确定；按已急停处理"
                feedback_state = "uncertain"
            else:
                self._status_text = "软急停发送失败，请使用现场硬件急停"
                feedback_state = "error"
            self._set_operation_feedback(
                feedback_state,
                "软急停",
                f"{self._status_text}：{self._last_error}",
            )
            self._append_log(f"软急停异常：{self._last_error}")
            self.operationFinished.emit("软急停", False, self._last_error)
        self.stateChanged.emit()
        QTimer.singleShot(50, self.refreshNow)

    @Slot()
    def releaseEmergencyStop(self) -> None:
        self._submit_verified(
            "解除软急停",
            "estop_release",
            capability=OnlineCapability.ESTOP_RELEASE,
            timeout_s=5.0,
            allowed_drafts=DraftResource.ALL,
        )

    @Slot(bool)
    def setGravityMode(self, enabled: bool) -> None:
        self._submit_verified(
            "切换零力漂浮" if enabled else "切换位置保持",
            "gravity_mode",
            {"enabled": bool(enabled)},
            capability=OnlineCapability.ARM_MODE,
            timeout_s=10.0,
            result_handler="gravity",
        )

    @Slot(float)
    def setGravityFactor(self, factor: float) -> None:
        value = float(factor)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            self._set_error("重力补偿系数必须是 0.0–1.0 的有限数值")
            return
        gate_error = self._policy.configuration_error()
        if gate_error:
            self._set_error(gate_error)
            return
        action = "restart" if self._connected else "start"
        script = str(self._repo_root / "scripts" / "manage_a1z_control_server.sh")
        self._start_process_task(
            "gravity_factor_restart",
            f"重启控制服务并应用重力补偿系数 {value:.2f}",
            script,
            [action, "--gravity-factor", f"{value:.3f}"],
            contract=ProcessTaskContract(
                ProcessAccess.TASK_SLOT,
                ResourceEffect.SERVICE,
            ),
            completion=lambda code, _output: self.refreshNow() if code == 0 else None,
            allowed_drafts=DraftResource.CONFIGURATION,
        )

    @Slot(str, float)
    def movePreset(self, preset: str, speed: float) -> None:
        self._submit_verified(
            f"预置位 {preset}",
            "move",
            {"preset": preset, "speed": float(speed)},
            capability=OnlineCapability.ARM_MOTION,
            result_handler="motion",
        )

    @Slot(str, float)
    def runDance(self, move: str, speed: float) -> None:
        moves = [] if move == "all" else [move]
        args: dict[str, Any] = {"speed": float(speed)}
        if moves:
            args["moves"] = moves
        self._submit_verified(
            f"动作序列 {move}",
            "dance",
            args,
            capability=OnlineCapability.ARM_MOTION,
            timeout_s=180.0,
            result_handler="motion",
        )

    @Slot(int)
    def startRecording(self, sample_hz: int) -> None:
        try:
            normalized_hz = self._teaching.normalize_sample_hz(sample_hz)
        except TeachingSessionError as exc:
            self._set_error(str(exc))
            return
        self._submit_verified(
            "开始示教录制",
            "record_start",
            {"sample_hz": normalized_hz},
            capability=OnlineCapability.RECORDING_START,
            timeout_s=10.0,
            result_handler="recording",
        )

    @Slot(str)
    def stopRecording(self, name: str) -> None:
        safe_name = self._teaching.normalize_recording_name(name)
        self._submit_verified(
            "停止并保存示教录制",
            "record_stop",
            {"name": safe_name},
            capability=OnlineCapability.RECORDING_STOP,
            timeout_s=15.0,
            result_handler="recording",
            allowed_drafts=(
                DraftResource.ARM_TARGET | DraftResource.GRIPPER_TARGET
            ),
        )

    @Slot()
    def discardDisconnectedRecording(self) -> None:
        gate_error = self._policy.recording_recovery_error()
        if gate_error:
            self._set_error(gate_error)
            return
        script = str(self._repo_root / "scripts" / "manage_a1z_control_server.sh")

        def completed(code: int, _output: str) -> None:
            if code != 0:
                return
            if self._teaching.discard_offline():
                self.teachingChanged.emit()
            self._gripper_free_drive = False
            self._control_mode = ""
            self._uncertain = False
            self._uncertain_ack_pending = False
            self._estopped = False
            self._connection_issue = "offline"
            self._invalidate_resource_state(
                ResourceEffect.ARM | ResourceEffect.GRIPPER
            )
            self._append_log(
                "操作员放弃无法连接的未保存示教录制会话；"
                "控制服务已确认停止，本地不确定/急停锁已转换为离线安全状态。"
            )
            self.stateChanged.emit()
            self.refreshNow()

        self._start_process_task(
            "recording_discard",
            "放弃离线录制并确认停止控制服务",
            script,
            ["stop"],
            contract=ProcessTaskContract(
                ProcessAccess.RECORDING_RECOVERY,
                ResourceEffect.SERVICE,
            ),
            completion=completed,
            allowed_drafts=DraftResource.ALL,
        )

    @Slot(str, float)
    def playRecording(self, name: str, speed_factor: float) -> None:
        safe_name = self._teaching.normalize_recording_name(name)
        try:
            normalized_speed = self._teaching.normalize_playback_speed(
                speed_factor
            )
        except TeachingSessionError as exc:
            self._set_error(str(exc))
            return
        self._submit_verified(
            f"回放示教轨迹 {safe_name}",
            "record_play",
            {"name": safe_name, "speed_factor": normalized_speed},
            capability=OnlineCapability.PLAYBACK,
            timeout_s=600.0,
            result_handler="recording",
        )

    @Slot(bool)
    def setGripperFreeDrive(self, enabled: bool) -> None:
        self._submit_verified(
            "夹爪自由拖动" if enabled else "夹爪恢复控制",
            "gripper_free_drive",
            {"enabled": bool(enabled)},
            capability=OnlineCapability.GRIPPER_MODE,
            timeout_s=10.0,
            result_handler="gripper_mode",
        )

    @Slot()
    def runMotionRecovery(self) -> None:
        action = self.motionRecoveryAction
        if action == "start_server":
            self.startServer(False, self._gravity_comp_factor)
        elif action == "refresh":
            self.refreshNow()
        elif action == "restart_server":
            self.restartServer()
        elif action == "position_hold":
            self.setGravityMode(False)

    @Slot()
    def explainStartupGate(self) -> None:
        self._set_error(f"控制入口尚未解锁：{self.startupGateText}")

    @Slot(str)
    def queryCamera(self, command: str) -> None:
        error = self._camera.request_manual(command)
        if error:
            self._set_error(error)

    @Slot(bool)
    def setCameraPreviewEnabled(self, enabled: bool) -> None:
        self._camera.set_preview_enabled(enabled)

    @Slot(str)
    def _on_camera_manual_started(self, label: str) -> None:
        self._last_error = ""
        self._status_text = f"{label}执行中"
        self._append_log(f"开始：{label}")
        self._set_operation_feedback("running", label, self._status_text)
        self.stateChanged.emit()

    @Slot(object)
    def _on_camera_manual_finished(self, payload: object) -> None:
        if not isinstance(payload, CameraManualResult):
            self._set_error("相机请求返回了无效结果")
            return
        if payload.success:
            self._last_error = ""
            self._status_text = f"{payload.label}完成"
            self._set_operation_feedback(
                "success",
                payload.label,
                self._status_text,
            )
            self._append_log(f"完成：{payload.label} · {payload.details}")
            self.operationFinished.emit(
                payload.label,
                True,
                self._status_text,
            )
            self.stateChanged.emit()
            return
        self._last_error = self._friendly_operation_error(payload.error)
        self._status_text = f"{payload.label}失败"
        self._set_operation_feedback(
            "error",
            payload.label,
            f"{payload.label}失败：{self._last_error}",
        )
        self._append_log(
            f"失败：{payload.label}：{self._last_error}"
        )
        self.operationFinished.emit(
            payload.label,
            False,
            self._last_error,
        )
        self.stateChanged.emit()

    # ------------------------------------------------------------------
    # Process-task facade slots and shared lifecycle projection
    # ------------------------------------------------------------------

    @Slot(bool, float)
    def startServer(self, gravity_mode: bool, gravity_factor: float) -> None:
        gate_error = self._policy.service_start_error()
        if gate_error:
            self._set_error(gate_error)
            return
        args = [
            str(self._repo_root / "scripts" / "manage_a1z_control_server.sh"),
            "start",
        ]
        if gravity_mode:
            args.append("--gravity-mode")
        args.extend(["--gravity-factor", f"{float(gravity_factor):.3f}"])
        self._start_process_task(
            "server_start",
            "启动控制服务",
            args[0],
            args[1:],
            contract=ProcessTaskContract(
                ProcessAccess.TASK_SLOT,
                ResourceEffect.SERVICE,
            ),
            completion=lambda code, _output: self.refreshNow() if code == 0 else None,
            allowed_drafts=DraftResource.CONFIGURATION,
        )

    @Slot()
    def restartServer(self) -> None:
        if self._estopped or self._uncertain:
            self._set_error("软急停或结果不确定锁存在时，禁止用重启服务绕过")
            return
        script = str(self._repo_root / "scripts" / "manage_a1z_control_server.sh")
        self._start_process_task(
            "server_restart",
            "重启控制服务",
            script,
            [
                "restart",
                "--gravity-factor",
                f"{float(self._gravity_comp_factor):.3f}",
            ],
            contract=ProcessTaskContract(
                ProcessAccess.TASK_SLOT,
                ResourceEffect.SERVICE,
            ),
            completion=lambda code, _output: self.refreshNow() if code == 0 else None,
        )

    @Slot()
    def stopServer(self) -> None:
        gate_error = self._policy.service_stop_error()
        if gate_error:
            self._set_error(gate_error)
            return
        script = str(self._repo_root / "scripts" / "manage_a1z_control_server.sh")
        self._start_process_task(
            "server_stop",
            "停止控制服务",
            script,
            ["stop"],
            contract=ProcessTaskContract(
                ProcessAccess.TASK_SLOT,
                ResourceEffect.SERVICE,
            ),
            completion=lambda code, _output: self.refreshNow() if code == 0 else None,
        )

    @Slot(str)
    def manageRos(self, action: str) -> None:
        if action not in {"start", "ensure", "stop", "restart", "status", "wait"}:
            self._set_error("ROS 操作不在允许列表中")
            return
        script = str(self._repo_root / "scripts" / "run_a1z_ros2_stack_in_container.sh")
        label = "ROS 2 自动检查并启动" if action == "ensure" else f"ROS 2 {action}"
        self._start_process_task(
            "ros",
            label,
            script,
            [action],
            contract=ProcessTaskContract(
                ProcessAccess.TASK_SLOT,
                ResourceEffect.NONE
                if action in {"status", "wait"}
                else ResourceEffect.TRANSPORT,
            ),
        )

    @Slot()
    def ensureRos(self) -> None:
        self.manageRos("ensure")

    @Slot(str, str, str)
    def computeAnyGrasp(self, instruction: str, planner: str, vision_backend: str) -> None:
        try:
            request = self._plan.prepare_computation(
                instruction,
                planner,
                vision_backend,
            )
        except PlanSessionError as exc:
            self._set_error(str(exc))
            return

        def completed(
            code: int,
            _output: str,
        ) -> ProcessTaskSemanticResult | None:
            result = self._plan.complete_computation(request, code)
            if not result.accepted:
                return None
            if result.error:
                return ProcessTaskSemanticResult(
                    success=False,
                    feedback_state="error",
                    status_text="AnyGrasp 计划产物无效",
                    error=result.error,
                )
            if result.success:
                self._append_log(
                    f"AnyGrasp 只计算完成：{result.plan_path}"
                )
                if self._plan.state == "unsafe":
                    return ProcessTaskSemanticResult(
                        success=True,
                        feedback_state="warning",
                        status_text=self._plan.status,
                    )
            return None

        started = self._start_process_task(
            request.task.kind,
            request.task.label,
            request.task.program,
            list(request.task.arguments),
            contract=request.task.contract,
            completion=completed,
        )
        if started:
            self._plan.activate_computation(request)

    @Slot(bool, str)
    def executePlan(self, dry_run: bool, confirmation: str) -> None:
        try:
            task = self._plan.prepare_execution(
                dry_run=bool(dry_run),
                confirmation=confirmation,
            )
        except PlanSessionError as exc:
            self._set_error(str(exc))
            return
        self._start_process_task(
            task.kind,
            task.label,
            task.program,
            list(task.arguments),
            contract=task.contract,
        )

    @Slot()
    def runPreflight(self) -> None:
        try:
            request = self._diagnostics.prepare_preflight()
        except DiagnosticsSessionError as exc:
            self._set_error(str(exc))
            return

        def completed(
            code: int,
            output: str,
        ) -> ProcessTaskSemanticResult | None:
            result = self._diagnostics.complete_preflight(
                request,
                code,
                output,
            )
            if not result.accepted:
                return None
            self.preflightChanged.emit()
            if result.error:
                return ProcessTaskSemanticResult(
                    success=False,
                    feedback_state="error",
                    status_text=self._diagnostics.status,
                    error=result.error,
                )
            if result.valid:
                self.refreshNow()
                if not result.ready:
                    return ProcessTaskSemanticResult(
                        success=True,
                        feedback_state="warning",
                        status_text=self._diagnostics.status,
                    )
            return None

        task = request.task
        started = self._start_process_task(
            task.kind,
            task.label,
            task.program,
            list(task.arguments),
            contract=task.contract,
            completion=completed,
            log_stdout=task.log_stdout,
        )
        if started:
            self._diagnostics.activate_preflight(request)
            self.preflightChanged.emit()

    @Slot(str, str)
    def runMaintenance(self, action: str, confirmation: str) -> None:
        try:
            task = self._diagnostics.prepare_maintenance(
                action,
                confirmation,
            )
        except DiagnosticsSessionError as exc:
            self._set_error(str(exc))
            return
        self._start_process_task(
            task.kind,
            task.label,
            task.program,
            list(task.arguments),
            contract=task.contract,
            log_stdout=task.log_stdout,
        )

    @Slot()
    def cancelTask(self) -> None:
        label = self._task_runner.label
        if not self._task_runner.cancel():
            return
        self._append_log(
            f"请求中止任务 {label}；不会自动发送任何替代运动命令。"
        )

    def _start_process_task(
        self,
        kind: str,
        label: str,
        program: str,
        arguments: list[str],
        *,
        contract: ProcessTaskContract,
        completion: Callable[
            [int, str],
            ProcessTaskSemanticResult | None,
        ]
        | None = None,
        log_stdout: bool = True,
        allowed_drafts: DraftResource = DraftResource.NONE,
    ) -> bool:
        draft_error = self._draft_locks.error_for_effects(
            contract.effects,
            allowed=allowed_drafts,
        )
        if draft_error:
            self._set_error(draft_error)
            return False
        gate_error = self._policy.process_access_error(
            contract.access,
            online_capability=contract.online_capability,
        )
        if gate_error:
            self._set_error(gate_error)
            return False
        self._last_error = ""
        self._status_text = f"{label}进行中"
        self._append_log(f"启动任务：{label}")
        self._set_operation_feedback("running", label, self._status_text)
        environment = {
            **self._profile.environment,
            "A1Z_PROFILE": self._profile_name,
        }
        request = ProcessTaskRequest.create(
            kind=kind,
            label=label,
            program=program,
            arguments=arguments,
            working_directory=self._repo_root,
            environment=environment,
            contract=contract,
            completion=completion,
            log_stdout=log_stdout,
        )
        if contract.effects & (ResourceEffect.SERVICE | ResourceEffect.TRANSPORT):
            if self._diagnostics.invalidate(
                "控制服务或 ROS 2 链路正在变更；完成后请重新运行全链路预检"
            ):
                self.preflightChanged.emit()
        if not self._task_runner.start(request):
            self._set_error("已有外部任务正在执行，不能启动另一任务")
            return False
        self.stateChanged.emit()
        return True

    @Slot(object)
    def _on_process_task_finished(self, payload: object) -> None:
        result = payload
        if not isinstance(result, ProcessTaskResult):
            self._set_error("外部任务返回了无效结果")
            return
        request = result.request
        exit_code = result.exit_code
        output = result.output
        label = request.label
        contract = request.contract
        semantic: ProcessTaskSemanticResult | None = None
        if result.output_truncated and request.completion is not None:
            semantic = ProcessTaskSemanticResult(
                success=False,
                feedback_state="error",
                status_text=f"{label}输出超过安全上限",
                error="任务输出过大，结果未交给界面解析",
            )
        elif request.completion is not None:
            try:
                semantic = request.completion(exit_code, output)
            except Exception as exc:
                semantic = ProcessTaskSemanticResult(
                    success=False,
                    feedback_state="error",
                    status_text=f"{label}结果处理失败",
                    error=str(exc),
                )
        if exit_code == 0:
            if semantic is None:
                final_success = True
                self._status_text = f"{label}完成"
                self._last_error = ""
                self._append_log(f"任务完成：{label}")
                self._set_operation_feedback(
                    "success",
                    label,
                    self._status_text,
                )
            elif semantic.success:
                final_success = True
                self._status_text = semantic.status_text
                self._last_error = ""
                self._append_log(
                    f"任务完成：{label}：{semantic.status_text}"
                )
                self._set_operation_feedback(
                    semantic.feedback_state,
                    label,
                    semantic.status_text,
                )
            else:
                final_success = False
                self._status_text = semantic.status_text
                self._last_error = self._friendly_operation_error(
                    semantic.error or semantic.status_text
                )
                self._append_log(
                    f"任务结果无效：{label}：{self._last_error}"
                )
                self._set_operation_feedback(
                    semantic.feedback_state,
                    label,
                    f"{semantic.status_text}：{self._last_error}",
                )
        else:
            final_success = False
            tail = output[-1000:] if output else f"exit code {exit_code}"
            self._last_error = self._friendly_operation_error(tail)
            self._status_text = f"{label}失败"
            self._append_log(f"任务失败：{label}：{tail}")
            if contract.uncertain_on_failure:
                self._uncertain = True
                self._uncertain_ack_pending = False
                self._status_text = f"{label}失败，设备结果可能不确定"
                feedback_state = "uncertain"
            else:
                feedback_state = "error"
            self._set_operation_feedback(
                feedback_state,
                label,
                f"{self._status_text}：{self._last_error}",
            )
        self.stateChanged.emit()
        if exit_code == 0 or contract.uncertain_on_failure:
            self._invalidate_resource_state(contract.effects)
        self.operationFinished.emit(label, final_success, self._status_text)
        QTimer.singleShot(100, self.refreshNow)

    @Slot(object)
    def _on_process_task_start_failure(self, payload: object) -> None:
        failure = payload
        if not isinstance(failure, ProcessTaskStartFailure):
            self._set_error("外部任务启动失败")
            return
        self._set_error(failure.message)
        if failure.request.completion is not None:
            try:
                failure.request.completion(-1, failure.message)
            except Exception as exc:
                self._append_log(
                    f"任务启动失败后的结果处理异常：{exc}"
                )

    @Slot()
    def explainCloseBlocked(self) -> None:
        message = self._close_block_message()
        if message:
            self._set_error(message)

    @Property(bool, notify=stateChanged)
    def closeBlocked(self) -> bool:
        return bool(self._close_block_message())

    def _close_block_message(self) -> str:
        if self._teaching.active:
            return "示教录制仍在进行；请先停止并保存，再关闭控制台"
        elif self._commands.emergency_busy:
            return "软急停仍在发送；请等待结果后再关闭控制台"
        elif self._task_runner.busy:
            return (
                f"{self._task_runner.label or '外部任务'}仍在进行；"
                + ("请先使用顶部“中止任务”" if self.taskCancelable else "请等待任务完成")
            )
        elif self._commands.command_busy:
            return "设备命令仍在执行；必要时请先软急停并等待结果"
        elif self._uncertain:
            return (
                "设备命令结果仍不确定；请先核对现场状态并解除不确定锁，"
                "再关闭控制台"
            )
        return ""

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._monitoring_started = False
        self._telemetry.shutdown()
        self._camera.shutdown()
        self._log_flush_timer.stop()
        self._flush_logs()
        self._task_runner.shutdown()
        self._commands.shutdown()
