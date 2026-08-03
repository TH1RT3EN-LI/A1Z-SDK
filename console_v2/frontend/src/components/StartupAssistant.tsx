import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronLeft,
  CircleAlert,
  LoaderCircle,
  Power,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import type { DeploymentMode } from "../deployment";
import type { StartupControlMode, StartupParameters } from "../startup";
import type { ThemeMode } from "../theme";
import RobotViewport from "./RobotViewport";

type StartupStep = "power" | "connection" | "parameters";
type CheckState = "idle" | "running" | "passed" | "failed";
type StartupCheckCode =
  | "ready"
  | "deployment_unavailable"
  | "device_missing"
  | "device_inactive"
  | "communication_fault"
  | "check_unavailable";

const steps: Array<{ id: StartupStep; label: string }> = [
  { id: "power", label: "电源" },
  { id: "connection", label: "连接" },
  { id: "parameters", label: "启动" },
];

const checkMessages: Record<Exclude<StartupCheckCode, "ready">, string> = {
  deployment_unavailable: "运行环境不可用，请检查设置。",
  device_missing: "未找到机械臂，请检查电源与 USB。",
  device_inactive: "连接未就绪，请重新连接。",
  communication_fault: "机械臂通信异常，请检查线束和终端电阻。",
  check_unavailable: "无法完成检查，请稍后重试。",
};

function DeploymentSummary({
  mode,
  state,
}: {
  mode: DeploymentMode;
  state?: CheckState;
}) {
  const stateLabel = state === "running" ? "检查中" : undefined;
  const modeLabel = mode === "host" ? "宿主机" : "Docker";
  return (
    <div className="startup-deployment-summary" aria-label={`部署方式：${modeLabel}`}>
      <span>部署</span>
      <strong>{modeLabel}</strong>
      {stateLabel ? <em>{stateLabel}</em> : null}
    </div>
  );
}

function StartupProgress({ currentStep }: { currentStep: number }) {
  return (
    <ol className="startup-progress" aria-label={`启动准备，第 ${currentStep + 1} 步，共 3 步`}>
      {steps.map((step, index) => (
        <li
          className={index < currentStep ? "is-complete" : index === currentStep ? "is-current" : ""}
          key={step.id}
          aria-current={index === currentStep ? "step" : undefined}
        >
          <span aria-hidden="true" />
          <span className="startup-progress-label">{step.label}</span>
        </li>
      ))}
    </ol>
  );
}

function StartupFooter({
  currentStep,
  allowSkip,
  primaryLabel,
  primaryDisabled,
  onBack,
  onPrimary,
  onSkip,
}: {
  currentStep: number;
  allowSkip: boolean;
  primaryLabel: string;
  primaryDisabled?: boolean;
  onBack: () => void;
  onPrimary: () => void;
  onSkip: () => void;
}) {
  return (
    <footer className="startup-footer">
      <div>
        {currentStep > 0 ? (
          <button className="startup-back-button" type="button" onClick={onBack}>
            <ChevronLeft size={15} strokeWidth={2} aria-hidden="true" />
            返回
          </button>
        ) : null}
      </div>
      <div className="startup-footer-actions">
        {allowSkip ? (
          <button className="startup-skip-button" type="button" onClick={onSkip}>
            跳过
          </button>
        ) : null}
        <button
          className="startup-primary-button"
          type="button"
          disabled={primaryDisabled}
          onClick={onPrimary}
        >
          <span className="startup-button-label" key={primaryLabel}>
            {primaryLabel}
          </span>
        </button>
      </div>
    </footer>
  );
}

export default function StartupAssistant({
  deploymentMode,
  theme,
  parameters,
  allowSkip,
  onParametersChange,
  onComplete,
}: {
  deploymentMode: DeploymentMode;
  theme: ThemeMode;
  parameters: StartupParameters;
  allowSkip: boolean;
  onParametersChange: (parameters: StartupParameters) => void;
  onComplete: () => void;
}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [checkState, setCheckState] = useState<CheckState>("idle");
  const [checkCode, setCheckCode] = useState<StartupCheckCode>("check_unavailable");
  const titleRef = useRef<HTMLHeadingElement>(null);
  const step = steps[currentStep].id;

  const runAutomaticCheck = useCallback(async () => {
    setCheckState("running");
    const desktop = window.a1zDesktop;
    if (!desktop) {
      setCheckCode("check_unavailable");
      setCheckState("failed");
      return;
    }
    try {
      const result = await desktop.checkStartupReadiness(deploymentMode);
      setCheckCode(result.code);
      setCheckState(result.ok ? "passed" : "failed");
    } catch {
      setCheckCode("check_unavailable");
      setCheckState("failed");
    }
  }, [deploymentMode]);

  useEffect(() => {
    titleRef.current?.focus();
  }, [currentStep]);

  useEffect(() => {
    if (step === "connection" && checkState === "idle") void runAutomaticCheck();
  }, [checkState, runAutomaticCheck, step]);

  const advance = () => {
    if (currentStep === steps.length - 1) onComplete();
    else setCurrentStep((value) => value + 1);
  };

  const skip = () => {
    if (!allowSkip) return;
    advance();
  };

  const goBack = () => setCurrentStep((value) => Math.max(0, value - 1));

  return (
    <section
      className="startup-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="startup-assistant-title"
    >
      <div
        className={`startup-model-visual is-step-${currentStep + 1}`}
        aria-hidden="true"
      >
        <RobotViewport
          theme={theme}
          presentation="ambient"
          previewVariant={currentStep as 0 | 1 | 2}
        />
      </div>

      <div className="startup-assistant">
        <StartupProgress currentStep={currentStep} />

        <div className="startup-stage">
          <div className="startup-stage-page" key={step}>
          {step === "power" ? (
            <>
              <div className="startup-symbol" aria-hidden="true">
                <Power size={34} strokeWidth={1.5} />
              </div>
              <h1 id="startup-assistant-title" ref={titleRef} tabIndex={-1}>
                准备设备
              </h1>
              <div className="startup-step-content">
                <div className="startup-instruction-list">
                  {["设备已固定", "线缆已连接", "自检已完成"].map(
                    (item) => (
                      <div key={item}>
                        <Check size={15} strokeWidth={2} aria-hidden="true" />
                        <span>{item}</span>
                      </div>
                    ),
                  )}
                </div>
                <DeploymentSummary mode={deploymentMode} />
              </div>
            </>
          ) : null}

          {step === "connection" ? (
            <>
              <div className="startup-symbol" aria-hidden="true">
                <ShieldCheck size={34} strokeWidth={1.5} />
              </div>
              <h1 id="startup-assistant-title" ref={titleRef} tabIndex={-1}>
                检查连接
              </h1>
              <div className="startup-step-content">
                <div className={`startup-check-result is-${checkState}`} role="status" aria-live="polite">
                  {checkState === "running" ? (
                    <LoaderCircle className="startup-spinner" size={24} strokeWidth={1.8} aria-hidden="true" />
                  ) : checkState === "passed" ? (
                    <Check size={24} strokeWidth={2} aria-hidden="true" />
                  ) : (
                    <CircleAlert size={24} strokeWidth={1.8} aria-hidden="true" />
                  )}
                  <div>
                    <strong>
                      {checkState === "running"
                        ? "正在检查"
                        : checkState === "passed"
                          ? "连接正常"
                          : "无法连接"}
                    </strong>
                    {checkState === "failed" ? (
                      <span>
                        {checkMessages[checkCode === "ready" ? "check_unavailable" : checkCode]}
                      </span>
                    ) : null}
                  </div>
                </div>
                <DeploymentSummary mode={deploymentMode} state={checkState} />
              </div>
            </>
          ) : null}

          {step === "parameters" ? (
            <>
              <div className="startup-symbol" aria-hidden="true">
                <SlidersHorizontal size={34} strokeWidth={1.5} />
              </div>
              <h1 id="startup-assistant-title" ref={titleRef} tabIndex={-1}>
                启动设置
              </h1>
              <div className="startup-step-content">
                <div className="startup-mode-options" role="radiogroup" aria-label="机械臂启动状态">
                  {(
                    [
                      {
                        value: "position_hold" as StartupControlMode,
                        title: "位置保持",
                        detail: "保持当前姿态",
                      },
                      {
                        value: "zero_force" as StartupControlMode,
                        title: "零力",
                        detail: "允许手动拖动",
                      },
                    ]
                  ).map((option) => {
                    const selected = parameters.controlMode === option.value;
                    return (
                      <button
                        className={`startup-mode-option ${selected ? "is-selected" : ""}`}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        key={option.value}
                        onClick={() =>
                          onParametersChange({ ...parameters, controlMode: option.value })
                        }
                      >
                        <span>
                          <strong>{option.title}</strong>
                          <small>{option.detail}</small>
                        </span>
                        {selected ? <Check size={17} strokeWidth={2} aria-hidden="true" /> : null}
                      </button>
                    );
                  })}
                </div>
                <div className="startup-gravity-control">
                  <div>
                    <label htmlFor="startup-gravity-factor">重力补偿</label>
                    <output htmlFor="startup-gravity-factor">
                      {Math.round(parameters.gravityCompensation * 100)}%
                    </output>
                  </div>
                  <input
                    id="startup-gravity-factor"
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={parameters.gravityCompensation}
                    onChange={(event) =>
                      onParametersChange({
                        ...parameters,
                        gravityCompensation: Number(event.target.value),
                      })
                    }
                  />
                </div>
              </div>
            </>
          ) : null}
          </div>
        </div>

        <StartupFooter
          currentStep={currentStep}
          allowSkip={allowSkip}
          primaryLabel={
            step === "power"
              ? "继续"
              : step === "connection"
                ? checkState === "passed"
                  ? "继续"
                  : checkState === "running"
                    ? "正在检查"
                    : "重新检查"
                : "进入控制"
          }
          primaryDisabled={step === "connection" && checkState === "running"}
          onBack={goBack}
          onSkip={skip}
          onPrimary={() => {
            if (step === "connection" && checkState !== "passed") {
              void runAutomaticCheck();
              return;
            }
            advance();
          }}
        />
      </div>
    </section>
  );
}
