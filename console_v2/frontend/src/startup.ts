export type StartupControlMode = "position_hold" | "zero_force";

export type StartupParameters = {
  controlMode: StartupControlMode;
  gravityCompensation: number;
};

const STARTUP_PARAMETERS_STORAGE_KEY = "a1z-console-startup-parameters";

const defaultStartupParameters: StartupParameters = {
  controlMode: "position_hold",
  gravityCompensation: 0.3,
};

export function readStartupParameters(): StartupParameters {
  try {
    const parsed = JSON.parse(
      window.localStorage.getItem(STARTUP_PARAMETERS_STORAGE_KEY) ?? "null",
    ) as Partial<StartupParameters> | null;
    const controlMode =
      parsed?.controlMode === "position_hold" || parsed?.controlMode === "zero_force"
        ? parsed.controlMode
        : defaultStartupParameters.controlMode;
    const gravityCompensation = Number(parsed?.gravityCompensation);
    return {
      controlMode,
      gravityCompensation:
        Number.isFinite(gravityCompensation) &&
        gravityCompensation >= 0 &&
        gravityCompensation <= 1
          ? gravityCompensation
          : defaultStartupParameters.gravityCompensation,
    };
  } catch {
    return defaultStartupParameters;
  }
}

export function storeStartupParameters(parameters: StartupParameters) {
  try {
    window.localStorage.setItem(
      STARTUP_PARAMETERS_STORAGE_KEY,
      JSON.stringify(parameters),
    );
  } catch {
    // The in-memory selection still applies for the current session.
  }
}
