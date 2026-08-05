import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import type { DeploymentMode } from "../deployment";
import type {
  ArmControlMode,
  ArmMotionSpeedLimits,
  RobotTelemetryState,
} from "../robot-telemetry";

type MotionFeedback = {
  message: string;
  tone: "info" | "success" | "error";
};

const developmentJointLimits = [
  [-120, 120],
  [0, 180],
  [-180, 0],
  [-85, 85],
  [-85, 85],
  [-115, 115],
] as const;

const fallbackSpeedLimits: ArmMotionSpeedLimits = {
  minimum: 0.05,
  default: 0.5,
  maximum: 1.5,
};

const developmentTarget = [0, 60, -60, 0, 0, 0] as const;

const targetNumberFormat = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

const compactNumberFormat = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2,
});

function editableAngle(value: number): string {
  return Number(value.toFixed(1)).toString();
}

function editableSpeed(value: number): string {
  return Number(value.toFixed(2)).toString();
}

function readStoredSpeed(): string {
  const stored = Number(window.localStorage.getItem("a1z-console:joint-speed-rad-s"));
  return Number.isFinite(stored) &&
    stored >= fallbackSpeedLimits.minimum &&
    stored <= fallbackSpeedLimits.maximum
    ? stored.toString()
    : fallbackSpeedLimits.default.toString();
}

function motionErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error || "");
  if (detail.includes("急停")) return "请先解除急停。";
  if (detail.includes("异常") || detail.includes("fault")) return "控制异常，请检查机械臂。";
  if (detail.includes("位置保持")) return "请切换到位置保持。";
  if (detail.includes("范围") || detail.includes("limit")) return "目标超出关节范围。";
  if (detail.includes("其他操作")) return "当前操作尚未完成。";
  if (/not reached|submitted_unverified|feedback|timed out|timeout/i.test(detail)) {
    return "结果未确认，机械臂可能仍在运动。";
  }
  if (detail.includes("控制服务") || detail.includes("connect")) return "控制服务不可用。";
  return "移动未完成，请检查机械臂。";
}

function JointMoveConfirmation({
  developmentPreview,
  estimatedSeconds,
  jointsDeg,
  speedRadS,
  onCancel,
  onConfirm,
}: {
  developmentPreview: boolean;
  estimatedSeconds: number | null;
  jointsDeg: readonly number[];
  speedRadS: number;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

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
      className="joint-move-dialog"
      ref={dialogRef}
      aria-labelledby="joint-move-dialog-title"
      aria-describedby="joint-move-dialog-description"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className="joint-move-dialog-content">
        <h2 id="joint-move-dialog-title">移动机械臂</h2>
        <p id="joint-move-dialog-description">
          {compactNumberFormat.format(speedRadS)} rad/s
          {estimatedSeconds === null ? "" : ` · 约 ${estimatedSeconds} 秒`}
        </p>
        <div className="joint-move-summary" aria-label="目标关节角度">
          {jointsDeg.map((value, index) => (
            <span key={index}>
              <small>J{index + 1}</small>
              {targetNumberFormat.format(value)}°
            </span>
          ))}
        </div>
        <p className="joint-move-safety-note">确认运动范围内无人、无障碍物。</p>
        {developmentPreview ? (
          <p className="development-preview-notice">
            预览 · 不会控制真机
          </p>
        ) : null}
        <div className="joint-move-dialog-actions">
          <button type="button" autoFocus onClick={onCancel}>
            取消
          </button>
          <button className="is-primary" type="button" onClick={onConfirm}>
            移动
          </button>
        </div>
      </div>
    </dialog>
  );
}

export default function JointTargetControl({
  telemetry,
  deploymentMode,
  developmentPreview,
  controlMode,
  externalBusy,
  onBusyChange,
}: {
  telemetry: RobotTelemetryState;
  deploymentMode: DeploymentMode;
  developmentPreview: boolean;
  controlMode: ArmControlMode | null;
  externalBusy: boolean;
  onBusyChange: (busy: boolean) => void;
}) {
  const [draftAngles, setDraftAngles] = useState<string[]>(() =>
    developmentTarget.map(editableAngle),
  );
  const [speedDraft, setSpeedDraft] = useState(readStoredSpeed);
  const [edited, setEdited] = useState(false);
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  const [moving, setMoving] = useState(false);
  const [submittedGoalId, setSubmittedGoalId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<MotionFeedback | null>(null);
  const previewTimerRef = useRef<number | null>(null);

  const jointLimits = telemetry.jointLimitsDeg || developmentJointLimits;
  const speedLimits = telemetry.motionSpeedLimits || fallbackSpeedLimits;
  const parsedAngles = draftAngles.map((value) =>
    value.trim() === "" ? Number.NaN : Number(value),
  );
  const invalidJointIndices = parsedAngles.flatMap((value, index) => {
    const [minimum, maximum] = jointLimits[index];
    return Number.isFinite(value) && value >= minimum && value <= maximum
      ? []
      : [index];
  });
  const parsedSpeed = speedDraft.trim() === "" ? Number.NaN : Number(speedDraft);
  const speedValid =
    Number.isFinite(parsedSpeed) &&
    parsedSpeed >= speedLimits.minimum &&
    parsedSpeed <= speedLimits.maximum;
  const sliderSpeed = speedValid
    ? parsedSpeed
    : Math.min(
        speedLimits.maximum,
        Math.max(speedLimits.minimum, speedLimits.default),
      );
  const speedProgress =
    ((sliderSpeed - speedLimits.minimum) /
      (speedLimits.maximum - speedLimits.minimum)) *
    100;
  const positionMode = controlMode === "position_hold";
  const ready = developmentPreview || telemetry.status === "live";
  const editable = positionMode && ready && !moving && !externalBusy;
  const canExecute =
    editable &&
    invalidJointIndices.length === 0 &&
    speedValid &&
    !confirmationOpen;

  const validationMessage = useMemo(() => {
    if (invalidJointIndices.length > 0) {
      const index = invalidJointIndices[0];
      const [minimum, maximum] = jointLimits[index];
      return `J${index + 1}：${compactNumberFormat.format(minimum)}°–${compactNumberFormat.format(maximum)}°`;
    }
    if (!speedValid) {
      return `速度：${compactNumberFormat.format(speedLimits.minimum)}–${compactNumberFormat.format(speedLimits.maximum)} rad/s`;
    }
    return "";
  }, [invalidJointIndices, jointLimits, speedLimits, speedValid]);

  const estimatedSeconds = useMemo(() => {
    if (
      !speedValid ||
      invalidJointIndices.length > 0 ||
      !telemetry.jointsDeg
    ) {
      return null;
    }
    const maxDeltaRad = Math.max(
      ...parsedAngles.map(
        (target, index) =>
          (Math.abs(target - telemetry.jointsDeg![index]) * Math.PI) / 180,
      ),
    );
    return Math.max(1, Math.ceil(Math.max(0.3, maxDeltaRad / parsedSpeed)));
  }, [
    invalidJointIndices.length,
    parsedAngles,
    parsedSpeed,
    speedValid,
    telemetry.jointsDeg,
  ]);

  useEffect(() => {
    if (!edited && telemetry.jointsDeg) {
      setDraftAngles(telemetry.jointsDeg.slice(0, 6).map(editableAngle));
    }
  }, [edited, telemetry.jointsDeg]);

  useEffect(() => {
    setEdited(false);
    setSubmittedGoalId(null);
    setFeedback(null);
  }, [deploymentMode]);

  useEffect(() => {
    const motion = telemetry.motion;
    if (!motion || submittedGoalId === null) {
      return;
    }
    if (
      motion.goalId !== null &&
      motion.goalId > submittedGoalId
    ) {
      setSubmittedGoalId(null);
      setFeedback({
        tone: "info",
        message: "已切换到新目标",
      });
      return;
    }
    if (
      motion.goalId === null &&
      (motion.state === "cancelled" || motion.state === "estopped")
    ) {
      setSubmittedGoalId(null);
      setFeedback({
        tone: motion.state === "estopped" ? "error" : "info",
        message:
          motion.state === "estopped"
            ? "急停已取消目标"
            : "目标已取消",
      });
      return;
    }
    if (motion.goalId !== submittedGoalId) return;
    if (motion.state === "failed") {
      setFeedback({
        tone: "error",
        message: motion.error || "未能到达，请检查机械臂。",
      });
      return;
    }
    if (motion.state === "holding") {
      const error = motion.maxJointErrorDeg;
      setFeedback({
        tone: "success",
        message:
          error === null
            ? "已到达"
            : `已到达 · 最大关节误差 ${compactNumberFormat.format(error)}°`,
      });
      return;
    }
    if (motion.state === "correcting") {
      setFeedback({ tone: "info", message: "正在微调" });
    }
  }, [submittedGoalId, telemetry.motion]);

  useEffect(() => {
    onBusyChange(moving || confirmationOpen);
  }, [confirmationOpen, moving, onBusyChange]);

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
    if (developmentPreview || previewTimerRef.current === null) return;
    window.clearTimeout(previewTimerRef.current);
    previewTimerRef.current = null;
    setMoving(false);
    setFeedback(null);
  }, [developmentPreview]);

  const loadMeasuredAngles = () => {
    if (!telemetry.jointsDeg || !editable) return;
    setDraftAngles(telemetry.jointsDeg.slice(0, 6).map(editableAngle));
    setEdited(true);
    setFeedback({ tone: "info", message: "已载入" });
  };

  const executeMove = async () => {
    setConfirmationOpen(false);
    setMoving(true);
    setFeedback({
      tone: "info",
      message: developmentPreview
        ? "正在预览…"
        : "正在提交…",
    });

    if (developmentPreview) {
      previewTimerRef.current = window.setTimeout(() => {
        previewTimerRef.current = null;
        setMoving(false);
        setFeedback({
          tone: "success",
          message: "预览完成",
        });
      }, 1200);
      return;
    }

    const desktopApi = window.a1zDesktop;
    if (!desktopApi) {
      setMoving(false);
      setFeedback({ tone: "error", message: "控制接口不可用。" });
      return;
    }
    try {
      const result = await desktopApi.moveRobotJoints(
        deploymentMode,
        parsedAngles,
        parsedSpeed,
      );
      setSubmittedGoalId(result.goalId);
      setMoving(false);
      setFeedback({
        tone: "info",
        message: "目标已提交",
      });
    } catch (error) {
      setMoving(false);
      setFeedback({ tone: "error", message: motionErrorMessage(error) });
    }
  };

  const openConfirmation = () => {
    if (!canExecute) return;
    window.localStorage.setItem(
      "a1z-console:joint-speed-rad-s",
      parsedSpeed.toString(),
    );
    setFeedback(null);
    setConfirmationOpen(true);
  };

  const inactiveMessage = externalBusy
      ? "正在切换模式"
    : !ready
      ? "控制服务不可用"
      : !positionMode
        ? "请切换到位置保持"
      : "";
  const visibleFeedback = validationMessage
    ? ({ tone: "error", message: validationMessage } satisfies MotionFeedback)
    : feedback;
  const displayTone = inactiveMessage ? "info" : visibleFeedback?.tone || "info";
  const statusMessage = inactiveMessage || visibleFeedback?.message || "";

  return (
    <section
      className={`joint-target-control ${editable ? "" : "is-locked"}`}
      aria-label="目标关节角度"
    >
      <form
        className="joint-target-form"
        onSubmit={(event) => {
          event.preventDefault();
          openConfirmation();
        }}
      >
        <div className="joint-target-fields">
          {draftAngles.map((value, index) => {
            const [minimum, maximum] = jointLimits[index];
            const invalid = invalidJointIndices.includes(index);
            return (
              <label className="joint-target-field" key={index}>
                <input
                  type="number"
                  inputMode="decimal"
                  min={minimum}
                  max={maximum}
                  step="any"
                  value={value}
                  disabled={!editable}
                  aria-invalid={invalid}
                  aria-label={`关节 ${index + 1} 目标角度，范围 ${minimum} 到 ${maximum} 度`}
                  onChange={(event) => {
                    const next = [...draftAngles];
                    next[index] = event.target.value;
                    setDraftAngles(next);
                    setEdited(true);
                    setFeedback(null);
                  }}
                  onFocus={(event) => event.currentTarget.select()}
                  onWheel={(event) => event.currentTarget.blur()}
                />
                <i aria-hidden="true">°</i>
              </label>
            );
          })}
        </div>

        <div className="joint-target-actions">
          <button
            className="load-measured-button"
            type="button"
            disabled={!editable || !telemetry.jointsDeg}
            onClick={loadMeasuredAngles}
          >
            载入
          </button>
          <div className="joint-speed-control">
            <label className="joint-speed-slider-field">
              <span>速度</span>
              <input
                className="joint-speed-slider"
                type="range"
                min={speedLimits.minimum}
                max={speedLimits.maximum}
                step="0.01"
                value={sliderSpeed}
                disabled={!editable}
                aria-label={`转动速度滑块，范围 ${speedLimits.minimum} 到 ${speedLimits.maximum} 弧度每秒`}
                style={
                  {
                    "--speed-progress": `${speedProgress}%`,
                  } as CSSProperties
                }
                onChange={(event) => {
                  setSpeedDraft(editableSpeed(Number(event.currentTarget.value)));
                  setFeedback(null);
                }}
              />
            </label>
            <label className="joint-speed-field">
              <input
                type="number"
                inputMode="decimal"
                min={speedLimits.minimum}
                max={speedLimits.maximum}
                step="0.01"
                value={speedDraft}
                disabled={!editable}
                aria-invalid={!speedValid}
                aria-label={`转动速度数值，范围 ${speedLimits.minimum} 到 ${speedLimits.maximum} 弧度每秒`}
                onChange={(event) => {
                  setSpeedDraft(event.target.value);
                  setFeedback(null);
                }}
                onFocus={(event) => event.currentTarget.select()}
                onWheel={(event) => event.currentTarget.blur()}
              />
              <i>rad/s</i>
            </label>
          </div>
          <button
            className="execute-joint-target"
            type="submit"
            disabled={!canExecute}
          >
            {moving ? <i aria-hidden="true" /> : null}
            {moving ? "提交中" : "执行"}
          </button>
        </div>
      </form>

      <p
        className={`joint-target-feedback is-${displayTone}`}
        role={displayTone === "error" ? "alert" : "status"}
        aria-live="polite"
        aria-hidden={statusMessage ? undefined : true}
      >
        {statusMessage || "\u00a0"}
      </p>

      {confirmationOpen ? (
        <JointMoveConfirmation
          developmentPreview={developmentPreview}
          estimatedSeconds={estimatedSeconds}
          jointsDeg={parsedAngles}
          speedRadS={parsedSpeed}
          onCancel={() => setConfirmationOpen(false)}
          onConfirm={() => void executeMove()}
        />
      ) : null}
    </section>
  );
}
