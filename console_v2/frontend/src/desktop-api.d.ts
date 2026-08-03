export {};

type TerminalDataPayload = {
  sessionId: string;
  data: string;
};

type TerminalExitPayload = {
  sessionId: string;
  exitCode: number;
  signal?: number;
};

type DeploymentMode = "host" | "docker";
type RobotControlModeCommand = "hold" | "zero-force";
type StartupCheckCode =
  | "ready"
  | "deployment_unavailable"
  | "device_missing"
  | "device_inactive"
  | "communication_fault"
  | "check_unavailable";

type RobotTelemetryPayload = {
  ok: boolean;
  sequence?: number;
  timestampMs?: number;
  data?: {
    pos_deg?: unknown;
    running?: unknown;
    faulted?: unknown;
    fault_message?: unknown;
    estopped?: unknown;
    control_mode?: unknown;
    gravity_comp_factor?: unknown;
    joint_limits_deg?: unknown;
    arm_motion_speed_rad_s?: unknown;
    motion?: unknown;
  };
  error?: string;
};

declare global {
  interface Window {
    a1zDesktop?: {
      readonly developmentMode: boolean;
      startTerminal(options: {
        sessionId: string;
        columns: number;
        rows: number;
      }): Promise<{ sessionId: string }>;
      writeTerminal(sessionId: string, data: string): void;
      resizeTerminal(sessionId: string, columns: number, rows: number): void;
      closeTerminal(sessionId: string): void;
      onTerminalData(callback: (payload: TerminalDataPayload) => void): () => void;
      onTerminalExit(callback: (payload: TerminalExitPayload) => void): () => void;
      checkStartupReadiness(deploymentMode: DeploymentMode): Promise<{
        ok: boolean;
        code: StartupCheckCode;
      }>;
      startRobotTelemetry(
        deploymentMode: DeploymentMode,
      ): Promise<{ started: boolean }>;
      stopRobotTelemetry(): void;
      onRobotTelemetry(callback: (payload: RobotTelemetryPayload) => void): () => void;
      setRobotControlMode(
        deploymentMode: DeploymentMode,
        mode: RobotControlModeCommand,
      ): Promise<{ accepted: true }>;
      moveRobotJoints(
        deploymentMode: DeploymentMode,
        jointsDeg: readonly number[],
        speedRadS: number,
      ): Promise<{ accepted: true; goalId: number; completion: "accepted" }>;
      getWindowState(): Promise<{ maximized: boolean }>;
      minimizeWindow(): void;
      toggleMaximizeWindow(): void;
      closeWindow(): void;
      onWindowMaximizedChange(callback: (maximized: boolean) => void): () => void;
    };
  }
}
