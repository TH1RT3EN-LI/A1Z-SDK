import { useCallback, useEffect, useRef, useState } from "react";
import {
  Box,
  Check,
  ChevronLeft,
  CircleAlert,
  LoaderCircle,
  Monitor,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import type { DeploymentMode } from "../deployment";
import type { StartupControlMode, StartupParameters } from "../startup";
import type { ThemeMode } from "../theme";
import RobotViewport from "./RobotViewport";

type StartupStep = "environment" | "connection" | "service";
type CheckState = "idle" | "running" | "passed" | "failed";
type EnvironmentCheckState = "idle" | "running" | "completed";
type StartupCheckCode =
  | "ready"
  | "configuration_required"
  | "deployment_unavailable"
  | "device_missing"
  | "device_inactive"
  | "communication_fault"
  | "check_unavailable";
type StartupEnvironmentStatus = {
  available: boolean;
  code: "ready" | "setup_required" | "repair_required" | "unavailable";
  detail: string;
};

const steps: Array<{ id: StartupStep; label: string }> = [
  { id: "environment", label: "环境" },
  { id: "connection", label: "CAN" },
  { id: "service", label: "服务" },
];

const checkMessages: Record<Exclude<StartupCheckCode, "ready">, string> = {
  configuration_required: "已检测到 CAN；Docker 启动时会完成接口配置。",
  deployment_unavailable: "运行环境不可用，请返回并重新选择。",
  device_missing: "未找到机械臂 CAN 适配器，请检查 USB 与驱动。",
  device_inactive: "宿主机 CAN 尚未启用，请先完成配置或选择 Docker。",
  communication_fault: "机械臂通信异常，请检查线束和终端电阻。",
  check_unavailable: "无法完成检查，请稍后重试。",
};

const emptyEnvironments: Record<DeploymentMode, StartupEnvironmentStatus | null> = {
  host: null,
  docker: null,
};

function startupErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : "控制服务启动失败。";
  return message.replace(
    /^Error invoking remote method 'startup:start-control-service': Error:\s*/,
    "",
  );
}

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
    <div className="startup-deployment-summary" aria-label={`控制服务运行位置：${modeLabel}`}>
      <span>控制服务</span>
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
  onDeploymentModeChange,
  onParametersChange,
  onComplete,
}: {
  deploymentMode: DeploymentMode;
  theme: ThemeMode;
  parameters: StartupParameters;
  allowSkip: boolean;
  onDeploymentModeChange: (mode: DeploymentMode) => void;
  onParametersChange: (parameters: StartupParameters) => void;
  onComplete: () => void;
}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [environmentCheckState, setEnvironmentCheckState] =
    useState<EnvironmentCheckState>("idle");
  const [environments, setEnvironments] =
    useState<Record<DeploymentMode, StartupEnvironmentStatus | null>>(emptyEnvironments);
  const [checkState, setCheckState] = useState<CheckState>("idle");
  const [checkCode, setCheckCode] = useState<StartupCheckCode>("check_unavailable");
  const [serviceState, setServiceState] = useState<CheckState>("idle");
  const [serviceMessage, setServiceMessage] = useState("");
  const titleRef = useRef<HTMLHeadingElement>(null);
  const step = steps[currentStep].id;

  const inspectEnvironments = useCallback(async () => {
    setEnvironmentCheckState("running");
    const desktop = window.a1zDesktop;
    if (!desktop) {
      setEnvironments({
        host: { available: false, code: "unavailable", detail: "桌面运行接口不可用。" },
        docker: { available: false, code: "unavailable", detail: "桌面运行接口不可用。" },
      });
      setEnvironmentCheckState("completed");
      return;
    }
    try {
      const result = await desktop.inspectStartupEnvironments();
      setEnvironments(result);
      if (!result[deploymentMode].available) {
        const alternative: DeploymentMode = deploymentMode === "host" ? "docker" : "host";
        if (result[alternative].available) onDeploymentModeChange(alternative);
      }
    } catch {
      setEnvironments({
        host: { available: false, code: "unavailable", detail: "宿主机检测失败。" },
        docker: { available: false, code: "unavailable", detail: "Docker 检测失败。" },
      });
    } finally {
      setEnvironmentCheckState("completed");
    }
  }, [deploymentMode, onDeploymentModeChange]);

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

  const runControlService = useCallback(async () => {
    if (allowSkip) {
      onComplete();
      return;
    }
    const desktop = window.a1zDesktop;
    if (!desktop) {
      setServiceMessage("桌面运行接口不可用，无法启动控制服务。");
      setServiceState("failed");
      return;
    }
    setServiceMessage("正在启动控制服务并等待健康检查…");
    setServiceState("running");
    try {
      const result = await desktop.startControlService(deploymentMode, parameters);
      if (!result.started) throw new Error("控制服务未启动。");
      setServiceState("passed");
      setServiceMessage(result.reused ? "已复用并验证现有控制服务。" : "控制服务已启动并通过健康检查。");
      onComplete();
    } catch (error) {
      setServiceMessage(startupErrorMessage(error));
      setServiceState("failed");
    }
  }, [allowSkip, deploymentMode, onComplete, parameters]);

  useEffect(() => {
    titleRef.current?.focus();
  }, [currentStep]);

  useEffect(() => {
    if (step === "environment" && environmentCheckState === "idle") {
      void inspectEnvironments();
    }
  }, [environmentCheckState, inspectEnvironments, step]);

  useEffect(() => {
    if (step === "connection" && checkState === "idle") void runAutomaticCheck();
  }, [checkState, runAutomaticCheck, step]);

  useEffect(() => {
    setCheckState("idle");
    setServiceState("idle");
    setServiceMessage("");
  }, [deploymentMode]);

  const advance = () => {
    if (currentStep === steps.length - 1) onComplete();
    else setCurrentStep((value) => value + 1);
  };

  const skip = () => {
    if (!allowSkip) return;
    advance();
  };

  const goBack = () => {
    if (serviceState === "running") return;
    setCurrentStep((value) => Math.max(0, value - 1));
  };

  const selectedEnvironment = environments[deploymentMode];
  const environmentReady =
    allowSkip ||
    (environmentCheckState === "completed" && selectedEnvironment?.available === true);

  return (
    <section
      className="startup-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="startup-assistant-title"
    >
      <div className={`startup-model-visual is-step-${currentStep + 1}`} aria-hidden="true">
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
            {step === "environment" ? (
              <>
                <div className="startup-symbol" aria-hidden="true">
                  <Monitor size={34} strokeWidth={1.5} />
                </div>
                <h1 id="startup-assistant-title" ref={titleRef} tabIndex={-1}>
                  选择运行环境
                </h1>
                <div className="startup-step-content">
                  <div className="startup-environment-options" role="radiogroup" aria-label="控制服务运行位置">
                    {(
                      [
                        { value: "host" as DeploymentMode, title: "宿主机", Icon: Monitor },
                        { value: "docker" as DeploymentMode, title: "Docker", Icon: Box },
                      ]
                    ).map((option) => {
                      const status = environments[option.value];
                      const selected = deploymentMode === option.value;
                      const unavailable = environmentCheckState === "completed" && !status?.available;
                      return (
                        <button
                          className={`startup-environment-option ${selected ? "is-selected" : ""}`}
                          type="button"
                          role="radio"
                          aria-checked={selected}
                          disabled={unavailable}
                          key={option.value}
                          onClick={() => onDeploymentModeChange(option.value)}
                        >
                          <option.Icon size={20} strokeWidth={1.7} aria-hidden="true" />
                          <span>
                            <strong>{option.title}</strong>
                            <small>
                              {environmentCheckState === "running"
                                ? "检测中…"
                                : status?.detail || "等待检测"}
                            </small>
                          </span>
                          {selected ? <Check size={17} strokeWidth={2} aria-hidden="true" /> : null}
                        </button>
                      );
                    })}
                  </div>
                  <button
                    className="startup-environment-refresh"
                    type="button"
                    disabled={environmentCheckState === "running"}
                    onClick={() => void inspectEnvironments()}
                  >
                    <RefreshCw size={14} strokeWidth={1.8} aria-hidden="true" />
                    重新检测
                  </button>
                </div>
              </>
            ) : null}

            {step === "connection" ? (
              <>
                <div className="startup-symbol" aria-hidden="true">
                  <ShieldCheck size={34} strokeWidth={1.5} />
                </div>
                <h1 id="startup-assistant-title" ref={titleRef} tabIndex={-1}>
                  检查 SocketCAN 通道
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
                            ? "CAN 通道可用"
                            : "CAN 通道不可用"}
                      </strong>
                      {checkCode === "configuration_required" ? (
                        <span>{checkMessages.configuration_required}</span>
                      ) : checkState === "passed" ? (
                        <span>仅表示 CAN 接口已就绪；六轴反馈将在启动服务后验证。</span>
                      ) : checkState === "failed" ? (
                        <span>{checkMessages[checkCode === "ready" ? "check_unavailable" : checkCode]}</span>
                      ) : null}
                    </div>
                  </div>
                  <DeploymentSummary mode={deploymentMode} state={checkState} />
                </div>
              </>
            ) : null}

            {step === "service" ? (
              <>
                <div className="startup-symbol" aria-hidden="true">
                  <SlidersHorizontal size={34} strokeWidth={1.5} />
                </div>
                <h1 id="startup-assistant-title" ref={titleRef} tabIndex={-1}>
                  启动控制服务
                </h1>
                <div className="startup-step-content is-service-step">
                  <div className="startup-mode-options" role="radiogroup" aria-label="机械臂启动状态">
                    {(
                      [
                        {
                          value: "position_hold" as StartupControlMode,
                          title: "位置保持",
                          detail: "启动后保持当前姿态",
                        },
                        {
                          value: "zero_force" as StartupControlMode,
                          title: "零力",
                          detail: "请托住机械臂；启动后允许手动拖动",
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
                          disabled={serviceState === "running"}
                          key={option.value}
                          onClick={() => {
                            setServiceState("idle");
                            setServiceMessage("");
                            onParametersChange({ ...parameters, controlMode: option.value });
                          }}
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
                      disabled={serviceState === "running"}
                      onChange={(event) => {
                        setServiceState("idle");
                        setServiceMessage("");
                        onParametersChange({
                          ...parameters,
                          gravityCompensation: Number(event.target.value),
                        });
                      }}
                    />
                  </div>
                  <div className={`startup-service-result is-${serviceState}`} role="status" aria-live="polite">
                    {serviceState === "running" ? (
                      <LoaderCircle className="startup-spinner" size={17} strokeWidth={1.8} aria-hidden="true" />
                    ) : serviceState === "passed" ? (
                      <Check size={17} strokeWidth={2} aria-hidden="true" />
                    ) : serviceState === "failed" ? (
                      <CircleAlert size={17} strokeWidth={1.8} aria-hidden="true" />
                    ) : (
                      <ShieldCheck size={17} strokeWidth={1.8} aria-hidden="true" />
                    )}
                    <span>
                      {serviceMessage ||
                        `${deploymentMode === "host" ? "宿主机" : "Docker"} · 确认急停可用后启动并验证服务`}
                    </span>
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
            step === "environment"
              ? environmentCheckState === "running"
                ? "正在检测"
                : "继续"
              : step === "connection"
                ? checkState === "passed"
                  ? "继续"
                  : checkState === "running"
                    ? "正在检查"
                    : "重新检查"
                : allowSkip
                  ? "进入预览"
                  : serviceState === "running"
                    ? "正在启动服务"
                    : serviceState === "failed"
                      ? "重新启动"
                      : "启动并进入"
          }
          primaryDisabled={
            (step === "environment" && !environmentReady) ||
            (step === "connection" && checkState === "running") ||
            (step === "service" && serviceState === "running")
          }
          onBack={goBack}
          onSkip={skip}
          onPrimary={() => {
            if (step === "environment") {
              if (environmentReady) advance();
              else void inspectEnvironments();
              return;
            }
            if (step === "connection") {
              if (checkState === "passed") advance();
              else void runAutomaticCheck();
              return;
            }
            void runControlService();
          }}
        />
      </div>
    </section>
  );
}
