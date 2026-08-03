import { useEffect, useRef, useState } from "react";
import type { DeploymentMode } from "../deployment";
import {
  isDevelopmentControlPreview,
  type ArmControlMode,
  type RobotTelemetryState,
} from "../robot-telemetry";

type ModeFeedback = {
  message: string;
  tone: "error";
};

const modeOptions: ReadonlyArray<{
  value: ArmControlMode;
  command: "hold" | "zero-force";
  label: string;
}> = [
  { value: "position_hold", command: "hold", label: "位置保持" },
  { value: "gravity_comp_effort", command: "zero-force", label: "零力" },
];

function commandErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error || "");
  if (detail.includes("急停")) return "请先解除急停。";
  if (detail.includes("异常") || detail.includes("fault")) return "控制异常，请检查机械臂。";
  if (detail.includes("零力模式")) return "零力模式不可用。";
  if (detail.includes("其他操作") || detail.includes("正在调整")) return "当前操作尚未完成。";
  if (detail.includes("控制服务") || detail.includes("connect")) return "控制服务不可用。";
  return "切换失败，请扶稳机械臂后重试。";
}

function readinessMessage(
  telemetry: RobotTelemetryState,
  target: ArmControlMode,
  developmentPreview: boolean,
): string | null {
  if (developmentPreview) return null;
  if (!window.a1zDesktop) return "控制接口不可用。";
  if (telemetry.status === "estopped") {
    return "请先解除急停。";
  }
  if (telemetry.status === "faulted") {
    return "控制异常，请检查机械臂。";
  }
  if (telemetry.status !== "live" || telemetry.controlMode === null) {
    return "控制服务不可用。";
  }
  if (
    target === "gravity_comp_effort" &&
    (telemetry.gravityCompFactor === null || telemetry.gravityCompFactor <= 0)
  ) {
    return "零力模式不可用。";
  }
  return null;
}

function ModeConfirmation({
  developmentPreview,
  targetMode,
  onCancel,
  onConfirm,
}: {
  developmentPreview: boolean;
  targetMode: ArmControlMode;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const enteringZeroForce = targetMode === "gravity_comp_effort";

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      className="arm-mode-dialog"
      ref={dialogRef}
      aria-labelledby="arm-mode-dialog-title"
      aria-describedby="arm-mode-dialog-description"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className="arm-mode-dialog-content">
        <h2 id="arm-mode-dialog-title">
          {enteringZeroForce ? "切换到零力" : "切换到位置保持"}
        </h2>
        <p id="arm-mode-dialog-description" className="arm-mode-safety-note">
          {enteringZeroForce
            ? "扶稳机械臂，并确认运动范围安全。"
            : "停止拖动，并扶稳当前姿态。"}
        </p>
        {developmentPreview ? (
          <p className="development-preview-notice">
            预览 · 不会控制真机
          </p>
        ) : null}
        <div className="arm-mode-dialog-actions">
          <button type="button" autoFocus onClick={onCancel}>
            取消
          </button>
          <button className="is-primary" type="button" onClick={onConfirm}>
            继续
          </button>
        </div>
      </div>
    </dialog>
  );
}

export default function ArmModeControl({
  telemetry,
  deploymentMode,
  developmentMode,
  developmentPreviewMode,
  externalBusy,
  onBusyChange,
  onDevelopmentPreviewModeChange,
}: {
  telemetry: RobotTelemetryState;
  deploymentMode: DeploymentMode;
  developmentMode: boolean;
  developmentPreviewMode: ArmControlMode;
  externalBusy: boolean;
  onBusyChange: (busy: boolean) => void;
  onDevelopmentPreviewModeChange: (mode: ArmControlMode) => void;
}) {
  const [pendingMode, setPendingMode] = useState<ArmControlMode | null>(null);
  const [awaitingFeedback, setAwaitingFeedback] = useState(false);
  const [confirmationTarget, setConfirmationTarget] =
    useState<ArmControlMode | null>(null);
  const [feedback, setFeedback] = useState<ModeFeedback | null>(null);
  const previewTimerRef = useRef<number | null>(null);
  const wasDevelopmentPreviewRef = useRef(false);
  const developmentPreview = isDevelopmentControlPreview(developmentMode);
  const selectedMode = developmentPreview
    ? developmentPreviewMode
    : telemetry.controlMode;

  useEffect(() => {
    onBusyChange(pendingMode !== null || confirmationTarget !== null);
  }, [confirmationTarget, onBusyChange, pendingMode]);

  useEffect(() => () => onBusyChange(false), [onBusyChange]);

  useEffect(
    () => () => {
      if (previewTimerRef.current !== null) {
        window.clearTimeout(previewTimerRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    const wasDevelopmentPreview = wasDevelopmentPreviewRef.current;
    wasDevelopmentPreviewRef.current = developmentPreview;
    if (!wasDevelopmentPreview && developmentPreview) {
      onDevelopmentPreviewModeChange("position_hold");
      setFeedback(null);
      return;
    }
    if (wasDevelopmentPreview && !developmentPreview) {
      if (previewTimerRef.current !== null) {
        window.clearTimeout(previewTimerRef.current);
        previewTimerRef.current = null;
      }
      setPendingMode(null);
      setAwaitingFeedback(false);
      setConfirmationTarget(null);
      setFeedback(null);
    }
  }, [developmentPreview, onDevelopmentPreviewModeChange]);

  useEffect(() => {
    if (!pendingMode || !awaitingFeedback) return undefined;
    if (telemetry.status === "live" && telemetry.controlMode === pendingMode) {
      setPendingMode(null);
      setAwaitingFeedback(false);
      setFeedback(null);
      return undefined;
    }
    if (telemetry.status !== "live") {
      setPendingMode(null);
      setAwaitingFeedback(false);
      setFeedback({
        tone: "error",
        message:
          readinessMessage(telemetry, pendingMode, false) ||
          "状态未确认，请扶稳机械臂。",
      });
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setPendingMode(null);
      setAwaitingFeedback(false);
      setFeedback({
        tone: "error",
        message: "状态未确认，请扶稳机械臂。",
      });
    }, 4800);
    return () => window.clearTimeout(timer);
  }, [awaitingFeedback, pendingMode, telemetry.controlMode, telemetry.status]);

  const runDevelopmentPreview = (target: ArmControlMode) => {
    setPendingMode(target);
    setAwaitingFeedback(false);
    setFeedback(null);
    previewTimerRef.current = window.setTimeout(() => {
      previewTimerRef.current = null;
      onDevelopmentPreviewModeChange(target);
      setPendingMode(null);
      setFeedback(null);
    }, 900);
  };

  const requestMode = async (target: ArmControlMode) => {
    const error = readinessMessage(telemetry, target, developmentPreview);
    if (error) {
      setFeedback({ tone: "error", message: error });
      return;
    }
    const option = modeOptions.find((candidate) => candidate.value === target);
    if (!option || pendingMode) return;
    if (developmentPreview) {
      runDevelopmentPreview(target);
      return;
    }
    const desktopApi = window.a1zDesktop;
    if (!desktopApi) return;

    setFeedback(null);
    setPendingMode(target);
    setAwaitingFeedback(false);
    try {
      await desktopApi.setRobotControlMode(deploymentMode, option.command);
      setAwaitingFeedback(true);
      setFeedback(null);
    } catch (commandError) {
      setPendingMode(null);
      setAwaitingFeedback(false);
      setFeedback({
        tone: "error",
        message: commandErrorMessage(commandError),
      });
    }
  };

  const selectMode = (target: ArmControlMode) => {
    if (pendingMode || externalBusy || selectedMode === target) return;
    const error = readinessMessage(telemetry, target, developmentPreview);
    if (error) {
      setFeedback({ tone: "error", message: error });
      return;
    }
    setFeedback(null);
    setConfirmationTarget(target);
  };

  return (
    <div
      className={`arm-mode-control ${developmentPreview ? "is-development-preview" : ""}`}
    >
      {developmentPreview ? (
        <span className="development-preview-label" aria-label="开发预览" title="开发预览">
          预览
        </span>
      ) : null}
      <div
        className="arm-mode-selector"
        role="radiogroup"
        aria-label="机械臂控制模式"
        aria-busy={pendingMode !== null}
      >
        {modeOptions.map((option) => {
          const selected = selectedMode === option.value;
          const pending = pendingMode === option.value;
          return (
            <button
              className={`${selected ? "is-selected" : ""} ${pending ? "is-pending" : ""}`}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={pendingMode !== null || externalBusy}
              key={option.value}
              onClick={() => selectMode(option.value)}
            >
              {option.label}
              {pending ? <i aria-hidden="true" /> : null}
            </button>
          );
        })}
      </div>
      {feedback ? (
        <p
          className={`arm-mode-feedback is-${feedback.tone}`}
          role={feedback.tone === "error" ? "alert" : "status"}
          aria-live="polite"
        >
          {feedback.message}
        </p>
      ) : null}
      {confirmationTarget ? (
        <ModeConfirmation
          developmentPreview={developmentPreview}
          targetMode={confirmationTarget}
          onCancel={() => setConfirmationTarget(null)}
          onConfirm={() => {
            const target = confirmationTarget;
            setConfirmationTarget(null);
            void requestMode(target);
          }}
        />
      ) : null}
    </div>
  );
}
