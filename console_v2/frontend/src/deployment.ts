export type DeploymentMode = "host" | "docker";

const DEPLOYMENT_MODE_STORAGE_KEY = "a1z-console-deployment-mode";

export function readDeploymentMode(): DeploymentMode {
  try {
    const storedMode = window.localStorage.getItem(DEPLOYMENT_MODE_STORAGE_KEY);
    if (storedMode === "host" || storedMode === "docker") return storedMode;
  } catch {
    // Storage can be unavailable in hardened browser contexts.
  }
  return "host";
}

export function storeDeploymentMode(mode: DeploymentMode) {
  try {
    window.localStorage.setItem(DEPLOYMENT_MODE_STORAGE_KEY, mode);
  } catch {
    // The in-memory selection still applies for the current session.
  }
}
