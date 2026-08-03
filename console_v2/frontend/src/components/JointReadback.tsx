import { useState } from "react";
import type { DeploymentMode } from "../deployment";
import {
  isDevelopmentControlPreview,
  type ArmControlMode,
  type RobotTelemetryState,
  type RobotTelemetryStatus,
} from "../robot-telemetry";
import ArmModeControl from "./ArmModeControl";
import JointTargetControl from "./JointTargetControl";

const jointNumberFormat = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

const statusLabels: Record<RobotTelemetryStatus, string> = {
  idle: "未连接",
  waiting: "连接中",
  live: "在线",
  stale: "连接中断",
  stopped: "已停止",
  faulted: "故障",
  estopped: "急停",
  unavailable: "不可用",
};

export default function JointReadback({
  telemetry,
  deploymentMode,
  developmentMode,
  showModelLabels,
  onShowModelLabelsChange,
}: {
  telemetry: RobotTelemetryState;
  deploymentMode: DeploymentMode;
  developmentMode: boolean;
  showModelLabels: boolean;
  onShowModelLabelsChange: (visible: boolean) => void;
}) {
  const statusLabel = statusLabels[telemetry.status];
  const muted = telemetry.status !== "live";
  const [developmentPreviewMode, setDevelopmentPreviewMode] =
    useState<ArmControlMode>("position_hold");
  const [modeBusy, setModeBusy] = useState(false);
  const [motionBusy, setMotionBusy] = useState(false);
  const developmentPreview = isDevelopmentControlPreview(developmentMode);
  const activeControlMode = developmentPreview
    ? developmentPreviewMode
    : telemetry.controlMode;

  return (
    <div className={`joint-readback ${muted ? "is-muted" : ""}`}>
      <div className="joint-readback-toolbar">
        <span
          className={`telemetry-state is-${telemetry.status}`}
          role="status"
          aria-live="polite"
          title={telemetry.error || statusLabel}
        >
          <i aria-hidden="true" />
          {statusLabel}
        </span>
        <div className="joint-readback-controls">
          <ArmModeControl
            telemetry={telemetry}
            deploymentMode={deploymentMode}
            developmentMode={developmentMode}
            developmentPreviewMode={developmentPreviewMode}
            externalBusy={motionBusy}
            onBusyChange={setModeBusy}
            onDevelopmentPreviewModeChange={setDevelopmentPreviewMode}
          />
          <label className="model-label-toggle">
            <span>标注</span>
            <button
              type="button"
              role="switch"
              aria-checked={showModelLabels}
              aria-label="在模型中显示关节角度"
              onClick={() => onShowModelLabelsChange(!showModelLabels)}
            >
              <span aria-hidden="true" />
            </button>
          </label>
        </div>
      </div>

      <div className="joint-readback-body">
        <div
          className="joint-readback-values"
          role="list"
          aria-label="关节角度回读"
        >
          {Array.from({ length: 6 }, (_, index) => {
            const value = telemetry.jointsDeg?.[index];
            const valueText = Number.isFinite(value)
              ? jointNumberFormat.format(value as number)
              : "—";
            return (
              <div className="joint-readback-value" role="listitem" key={index}>
                <span className="joint-axis-label">J{index + 1}</span>
                <output
                  aria-label={`关节 ${index + 1} 角度`}
                  data-unit={Number.isFinite(value) ? "°" : undefined}
                >
                  {valueText}
                </output>
              </div>
            );
          })}
        </div>

        <JointTargetControl
          telemetry={telemetry}
          deploymentMode={deploymentMode}
          developmentPreview={developmentPreview}
          controlMode={activeControlMode}
          externalBusy={modeBusy}
          onBusyChange={setMotionBusy}
        />
      </div>
    </div>
  );
}
