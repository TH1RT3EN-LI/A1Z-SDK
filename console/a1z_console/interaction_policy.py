"""Capability-based interaction policy for the A1Z operator console.

The policy describes what an operation does and which device state it needs.
It deliberately does not classify operations by SDK, ROS, helper script, or
other implementation source.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntFlag, auto


class OnlineCapability(Enum):
    """Stateful operations sent to the verified control endpoint."""

    ARM_MOTION = "arm_motion"
    GRIPPER_MOTION = "gripper_motion"
    ARM_GRIPPER_MOTION = "arm_gripper_motion"
    ARM_MODE = "arm_mode"
    GRIPPER_MODE = "gripper_mode"
    RECORDING_START = "recording_start"
    RECORDING_STOP = "recording_stop"
    PLAYBACK = "playback"
    ESTOP_RELEASE = "estop_release"


class ProcessAccess(Enum):
    """Prerequisite families for external process tasks."""

    TASK_SLOT = "task_slot"
    ONLINE_DEVICE = "online_device"
    OFFLINE_DEVICE = "offline_device"
    HARDWARE_INSPECTION = "hardware_inspection"
    RECORDING_RECOVERY = "recording_recovery"


class ResourceEffect(IntFlag):
    """Resources whose state a completed process may invalidate."""

    NONE = 0
    ARM = auto()
    GRIPPER = auto()
    CALIBRATION = auto()
    SERVICE = auto()
    TRANSPORT = auto()


def online_capability_effects(capability: OnlineCapability) -> ResourceEffect:
    """Return the device resources invalidated by a successful command."""

    return {
        OnlineCapability.ARM_MOTION: ResourceEffect.ARM,
        OnlineCapability.GRIPPER_MOTION: ResourceEffect.GRIPPER,
        OnlineCapability.ARM_GRIPPER_MOTION: (
            ResourceEffect.ARM | ResourceEffect.GRIPPER
        ),
        OnlineCapability.ARM_MODE: ResourceEffect.ARM,
        OnlineCapability.GRIPPER_MODE: ResourceEffect.GRIPPER,
        OnlineCapability.RECORDING_START: (
            ResourceEffect.ARM | ResourceEffect.GRIPPER
        ),
        OnlineCapability.RECORDING_STOP: (
            ResourceEffect.ARM | ResourceEffect.GRIPPER
        ),
        OnlineCapability.PLAYBACK: (
            ResourceEffect.ARM | ResourceEffect.GRIPPER
        ),
        OnlineCapability.ESTOP_RELEASE: (
            ResourceEffect.ARM | ResourceEffect.GRIPPER
        ),
    }[capability]


@dataclass(frozen=True)
class ProcessTaskContract:
    """Execution and result semantics for one external process."""

    access: ProcessAccess
    effects: ResourceEffect = ResourceEffect.NONE
    uncertain_on_failure: bool = False
    blocks_telemetry: bool = False
    online_capability: OnlineCapability | None = None
    cancelable: bool = False

    @property
    def affects_device(self) -> bool:
        return bool(
            self.effects
            & (ResourceEffect.ARM | ResourceEffect.GRIPPER | ResourceEffect.CALIBRATION)
        )


@dataclass(frozen=True)
class InteractionPolicy:
    """Immutable view of the controller state used for all capability gates."""

    connected: bool
    backend_matched: bool
    connection_issue: str
    telemetry_fresh: bool
    robot_running: bool
    faulted: bool
    fault_message: str
    control_mode: str
    gripper_free_drive: bool
    command_busy: bool
    task_busy: bool
    task_label: str
    emergency_busy: bool
    recording_active: bool
    outcome_uncertain: bool
    estopped: bool
    outcome_recheck_requested: bool = False
    recording_state: str = "idle"
    supports_hardware_inspection: bool = False
    supports_offline_maintenance: bool = False

    @property
    def control_mode_label(self) -> str:
        return {
            "gravity_comp_effort": "零力漂浮",
            "position_hold": "位置保持",
        }.get(self.control_mode, self.control_mode or "—")

    def task_slot_error(self, *, allow_recording: bool = False) -> str:
        if self.command_busy or self.task_busy:
            return "已有设备命令或外部任务正在执行"
        if self.emergency_busy:
            return "软急停正在发送，其余操作已锁定"
        if self.recording_active and not allow_recording:
            if self.recording_state == "orphaned":
                return "示教录制状态待确认；请恢复连接或放弃未保存会话"
            return "示教录制中；请先停止并保存"
        return ""

    def online_error(self, capability: OnlineCapability) -> str:
        slot_error = self.task_slot_error(
            allow_recording=capability is OnlineCapability.RECORDING_STOP
        )
        if slot_error:
            return slot_error
        if capability is OnlineCapability.RECORDING_STOP:
            if not self.recording_active:
                return "当前没有正在进行的示教录制"
            if not self.connected or not self.backend_matched:
                return "控制服务未连接或后端身份不匹配"
            if not self.telemetry_fresh:
                return "遥测已过期"
            # Stopping a recording is a recovery/finalization operation, not
            # motion. It must remain available after a fault, estop, stopped
            # loop, or an earlier ambiguous result so the persistent recording
            # lock always has an exit.
            return ""
        if capability is OnlineCapability.ESTOP_RELEASE:
            if self.outcome_uncertain:
                return "结果不确定锁存在，请先现场确认并重新核验"
            if not self.connected or not self.backend_matched:
                return "控制服务未连接或后端身份不匹配"
            if not self.telemetry_fresh:
                return "遥测已过期"
            if not self.estopped:
                return "机械臂当前没有软急停锁"
            # Releasing the software latch is a recovery operation. The
            # backend intentionally permits it when the control loop is
            # faulted or stopped.
            return ""
        if self.outcome_uncertain:
            return "上条命令结果不确定，设备控制入口保持锁定"
        if not self.connected or not self.backend_matched:
            return "控制服务未连接或后端身份不匹配"
        if not self.telemetry_fresh:
            return "遥测已过期"
        if self.faulted:
            return self.fault_message or "机械臂控制循环已故障"
        if not self.robot_running:
            return "机械臂控制循环未运行"
        if self.estopped:
            return "机械臂处于软急停状态"
        if (
            capability in {
                OnlineCapability.ARM_MOTION,
                OnlineCapability.ARM_GRIPPER_MOTION,
                OnlineCapability.PLAYBACK,
            }
            and self.control_mode != "position_hold"
        ):
            return (
                "位置运动要求位置保持模式；"
                f"当前为 {self.control_mode_label}"
            )
        if (
            capability in {
                OnlineCapability.GRIPPER_MOTION,
                OnlineCapability.ARM_GRIPPER_MOTION,
                OnlineCapability.PLAYBACK,
            }
            and self.gripper_free_drive
        ):
            return "夹爪处于自由拖动模式，请先恢复开度控制"
        return ""

    def profile_switch_error(self) -> str:
        if self.recording_active:
            if self.recording_state == "orphaned":
                return "示教录制状态尚未重新确认，请先恢复或放弃该会话"
            return "示教录制仍在进行，请先停止并保存"
        if self.outcome_uncertain:
            return "当前 profile 仍有结果不确定锁，请先现场确认"
        if self.estopped:
            return "当前 profile 仍处于软急停，请先处理该状态"
        if self.emergency_busy:
            return "软急停请求正在发送"
        if self.connection_issue == "stale":
            return "当前 profile 遥测已过期，最后物理状态尚未重新确认"
        if self.connection_issue == "checking":
            return "当前 profile 的控制状态仍在核验"
        if self.connection_issue == "backend_mismatch":
            return "当前端点存在后端身份冲突"
        if self.gripper_free_drive:
            return "夹爪仍处于自由拖动，请先恢复夹爪控制"
        if self.control_mode not in {"", "position_hold"}:
            return "机械臂仍处于零力漂浮，请先切回位置保持"
        if self.command_busy or self.task_busy:
            return "命令或任务仍在进行"
        return ""

    def service_start_error(self) -> str:
        slot_error = self.task_slot_error()
        if slot_error:
            return slot_error
        if self.outcome_uncertain and not self.outcome_recheck_requested:
            return "结果不确定锁存在，请先现场确认并请求重新核验"
        if self.estopped and self.connection_issue != "offline":
            return "软急停锁存在，禁止启动另一控制服务"
        if self.connection_issue == "backend_mismatch":
            return "端点被错误后端占用，禁止再次启动；请先处理身份冲突"
        if self.connection_issue in {"checking", "stale"}:
            return "控制状态尚未确认，请先刷新而不是重复启动"
        if self.connection_issue != "offline":
            return "控制服务不是可启动的离线状态"
        return ""

    def service_stop_error(self) -> str:
        slot_error = self.task_slot_error()
        if slot_error:
            return slot_error
        if self.outcome_uncertain:
            return "结果不确定锁存在，请先现场确认并重新核验"
        if self.estopped:
            return "软急停锁存在，请先解除后再停止控制服务"
        if not self.connected or not self.backend_matched:
            return "只有身份已确认的在线控制服务可以从界面停止"
        return ""

    def configuration_error(self) -> str:
        slot_error = self.task_slot_error()
        if slot_error:
            return slot_error
        if self.outcome_uncertain:
            return "结果不确定锁存在，禁止更改启动配置"
        if self.estopped:
            return "软急停锁存在，禁止更改启动配置"
        if self.connection_issue not in {"", "offline"}:
            return "当前连接状态尚未确认，禁止更改启动配置"
        if self.connected and (
            self.control_mode != "position_hold" or self.gripper_free_drive
        ):
            return "应用启动配置前，请恢复位置保持和夹爪控制"
        return ""

    def recording_recovery_error(self) -> str:
        slot_error = self.task_slot_error(allow_recording=True)
        if slot_error:
            return slot_error
        if not self.recording_active or self.connected:
            return "只有录制状态残留且控制端点离线时才能放弃该会话"
        return ""

    def kinematics_read_error(self) -> str:
        slot_error = self.task_slot_error()
        if slot_error:
            return slot_error
        if not self.connected or not self.backend_matched:
            return "控制服务未连接或后端身份不匹配"
        if not self.telemetry_fresh:
            return "遥测已过期"
        return ""

    def hardware_inspection_error(self) -> str:
        slot_error = self.task_slot_error()
        if slot_error:
            return slot_error
        if not self.supports_hardware_inspection:
            return "当前运行配置不提供硬件链路检查"
        return ""

    def offline_device_error(self) -> str:
        slot_error = self.task_slot_error()
        if slot_error:
            return slot_error
        if not self.supports_offline_maintenance:
            return "当前运行配置不提供离线设备维护"
        if self.outcome_uncertain:
            return "结果不确定锁存在，禁止启动离线设备维护"
        if self.estopped:
            return "软急停锁存在，禁止绕过控制服务直接维护设备"
        if self.connected:
            return "直接设备维护要求先停止控制服务"
        if self.connection_issue != "offline":
            return "控制服务状态尚未确认为离线，禁止直接维护设备"
        return ""

    def process_access_error(
        self,
        access: ProcessAccess,
        *,
        online_capability: OnlineCapability | None = None,
    ) -> str:
        if access is ProcessAccess.ONLINE_DEVICE:
            if online_capability is None:
                return "在线设备任务未声明具体控制能力"
            return self.online_error(online_capability)
        if access is ProcessAccess.OFFLINE_DEVICE:
            return self.offline_device_error()
        if access is ProcessAccess.HARDWARE_INSPECTION:
            return self.hardware_inspection_error()
        if access is ProcessAccess.RECORDING_RECOVERY:
            return self.recording_recovery_error()
        return self.task_slot_error()

    @property
    def motion_gate_text(self) -> str:
        if self.recording_active:
            if self.recording_state == "orphaned":
                return "示教录制状态待确认；只能恢复连接、放弃会话或软急停"
            return "示教录制中；只能停止保存或使用软急停"
        if self.emergency_busy:
            return "软急停正在发送；其余操作已锁定"
        if self.outcome_uncertain:
            return "上条命令结果不确定，请先核对现场并解除锁定"
        if self.estopped:
            return "软急停已锁定"
        if self.faulted:
            return (
                "控制循环故障："
                + (self.fault_message or "请重启控制服务")
            )
        if self.task_busy:
            return f"{self.task_label or '任务'}进行中"
        if self.command_busy:
            return "单命令事务执行中"
        if not self.connected:
            return "控制服务未连接"
        if not self.backend_matched:
            return "Real / Sim 后端身份不匹配"
        if not self.telemetry_fresh:
            return "遥测已过期"
        if not self.robot_running:
            return "服务端点在线，但机械臂控制循环未运行"
        if self.control_mode != "position_hold":
            return "位置运动已锁定；请先切换到位置保持"
        return "就绪：一次点击只发送一次运动"

    @property
    def motion_recovery_action(self) -> str:
        if (
            self.command_busy
            or self.task_busy
            or self.emergency_busy
            or self.recording_active
        ):
            return ""
        if self.outcome_uncertain:
            if (
                self.outcome_recheck_requested
                and self.connection_issue == "offline"
            ):
                return "start_server"
            return ""
        if self.estopped:
            return "start_server" if self.connection_issue == "offline" else ""
        if self.connection_issue == "offline":
            return "start_server"
        if self.connection_issue == "stale":
            return "refresh"
        if self.connection_issue in {"checking", "backend_mismatch"}:
            return ""
        if self.faulted or not self.robot_running:
            return "restart_server"
        if self.control_mode != "position_hold":
            return "position_hold"
        return ""
