import { useEffect, useRef, useState } from "react";
import type { DeploymentMode } from "./deployment";

export type RobotTelemetryStatus =
  | "idle"
  | "waiting"
  | "live"
  | "stale"
  | "stopped"
  | "faulted"
  | "estopped"
  | "unavailable";

export type ArmControlMode = "position_hold" | "gravity_comp_effort";

export type ArmMotionSpeedLimits = {
  minimum: number;
  default: number;
  maximum: number;
};

export type ArmMotionRuntime = {
  goalId: number | null;
  state: string;
  maxJointErrorDeg: number | null;
  jointPositionToleranceDeg: number | null;
  positionErrorMm: number | null;
  positionToleranceMm: number | null;
  orientationErrorDeg: number | null;
  error: string;
};

export type RobotTelemetryState = {
  status: RobotTelemetryStatus;
  jointsDeg: readonly number[] | null;
  controlMode: ArmControlMode | null;
  gravityCompFactor: number | null;
  jointLimitsDeg: readonly (readonly [number, number])[] | null;
  motionSpeedLimits: ArmMotionSpeedLimits | null;
  motion: ArmMotionRuntime | null;
  receivedAt: number | null;
  error: string;
};

const INITIAL_STATE: RobotTelemetryState = {
  status: "idle",
  jointsDeg: null,
  controlMode: null,
  gravityCompFactor: null,
  jointLimitsDeg: null,
  motionSpeedLimits: null,
  motion: null,
  receivedAt: null,
  error: "",
};

function measuredJoints(value: unknown): readonly number[] | null {
  if (!Array.isArray(value) || value.length < 6) return null;
  const joints = value.slice(0, 6).map(Number);
  return joints.every(Number.isFinite) ? joints : null;
}

function measuredControlMode(value: unknown): ArmControlMode | null {
  return value === "position_hold" || value === "gravity_comp_effort"
    ? value
    : null;
}

function measuredGravityFactor(value: unknown): number | null {
  const factor = Number(value);
  return Number.isFinite(factor) && factor >= 0 && factor <= 1 ? factor : null;
}

function measuredJointLimits(
  value: unknown,
): readonly (readonly [number, number])[] | null {
  if (!Array.isArray(value) || value.length !== 6) return null;
  const limits = value.map((pair) => {
    if (!Array.isArray(pair) || pair.length !== 2) return null;
    const minimum = Number(pair[0]);
    const maximum = Number(pair[1]);
    return Number.isFinite(minimum) && Number.isFinite(maximum) && minimum < maximum
      ? ([minimum, maximum] as const)
      : null;
  });
  return limits.every((pair) => pair !== null)
    ? (limits as Array<readonly [number, number]>)
    : null;
}

function measuredMotionSpeedLimits(value: unknown): ArmMotionSpeedLimits | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const minimum = Number(raw.minimum);
  const defaultSpeed = Number(raw.default);
  const maximum = Number(raw.maximum);
  return Number.isFinite(minimum) &&
    Number.isFinite(defaultSpeed) &&
    Number.isFinite(maximum) &&
    0 < minimum &&
    minimum <= defaultSpeed &&
    defaultSpeed <= maximum
    ? { minimum, default: defaultSpeed, maximum }
    : null;
}

function measuredMotion(value: unknown): ArmMotionRuntime | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const rawGoalId = Number(raw.goal_id);
  const numberOrNull = (candidate: unknown) => {
    if (candidate === null || candidate === undefined || candidate === "") {
      return null;
    }
    const number = Number(candidate);
    return Number.isFinite(number) ? number : null;
  };
  return {
    goalId: Number.isInteger(rawGoalId) && rawGoalId > 0 ? rawGoalId : null,
    state: typeof raw.state === "string" ? raw.state : "idle",
    maxJointErrorDeg: numberOrNull(raw.max_joint_error_deg),
    jointPositionToleranceDeg: numberOrNull(raw.joint_position_tolerance_deg),
    positionErrorMm: numberOrNull(raw.position_error_mm),
    positionToleranceMm: numberOrNull(raw.endpoint_position_tolerance_mm),
    orientationErrorDeg: numberOrNull(raw.orientation_error_deg),
    error: typeof raw.error === "string" ? raw.error : "",
  };
}

export function isDevelopmentControlPreview(
  developmentMode: boolean,
): boolean {
  return developmentMode;
}

export function useRobotTelemetry(
  deploymentMode: DeploymentMode,
  enabled: boolean,
): RobotTelemetryState {
  const [state, setState] = useState<RobotTelemetryState>(INITIAL_STATE);
  const failedSamplesRef = useRef(0);

  useEffect(() => {
    const desktopApi = window.a1zDesktop;
    if (!desktopApi || !enabled) {
      failedSamplesRef.current = 0;
      setState((current) => ({
        ...current,
        status: enabled ? "unavailable" : "idle",
        error: enabled ? "桌面遥测接口不可用。" : "",
      }));
      return undefined;
    }

    let active = true;
    failedSamplesRef.current = 0;
    setState({ ...INITIAL_STATE, status: "waiting" });
    const unsubscribe = desktopApi.onRobotTelemetry((payload) => {
      if (!active) return;
      const joints = measuredJoints(payload.data?.pos_deg);
      if (!payload.ok || !joints) {
        failedSamplesRef.current += 1;
        if (failedSamplesRef.current >= 3) {
          setState((current) => ({
            ...current,
            status: "unavailable",
            error: payload.error || "没有收到有效的关节状态。",
          }));
        }
        return;
      }

      failedSamplesRef.current = 0;
      const controlMode = measuredControlMode(payload.data?.control_mode);
      const gravityCompFactor = measuredGravityFactor(
        payload.data?.gravity_comp_factor,
      );
      const jointLimitsDeg = measuredJointLimits(payload.data?.joint_limits_deg);
      const motionSpeedLimits = measuredMotionSpeedLimits(
        payload.data?.arm_motion_speed_rad_s,
      );
      const motion = measuredMotion(payload.data?.motion);
      const status: RobotTelemetryStatus = payload.data?.estopped
        ? "estopped"
        : payload.data?.faulted
          ? "faulted"
          : payload.data?.running === false
            ? "stopped"
            : "live";
      setState({
        status,
        jointsDeg: joints,
        controlMode,
        gravityCompFactor,
        jointLimitsDeg,
        motionSpeedLimits,
        motion,
        receivedAt: Date.now(),
        error:
          status === "faulted" && typeof payload.data?.fault_message === "string"
            ? payload.data.fault_message
            : "",
      });
    });

    void desktopApi.startRobotTelemetry(deploymentMode).catch((error: unknown) => {
      if (!active) return;
      setState({
        ...INITIAL_STATE,
        status: "unavailable",
        error: error instanceof Error ? error.message : "无法启动 SDK 遥测。",
      });
    });

    const freshnessTimer = window.setInterval(() => {
      setState((current) => {
        if (
          current.receivedAt === null ||
          current.status === "unavailable" ||
          Date.now() - current.receivedAt <= 1600
        ) {
          return current;
        }
        return { ...current, status: "stale", error: "关节状态更新已中断。" };
      });
    }, 400);

    return () => {
      active = false;
      window.clearInterval(freshnessTimer);
      unsubscribe();
      desktopApi.stopRobotTelemetry();
    };
  }, [deploymentMode, enabled]);

  return state;
}
