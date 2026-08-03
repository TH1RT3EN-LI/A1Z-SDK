const { contextBridge, ipcRenderer } = require("electron");
const developmentMode = process.argv.includes("--a1z-development-mode=1");

contextBridge.exposeInMainWorld(
  "a1zDesktop",
  Object.freeze({
    developmentMode,
    startTerminal(options) {
      return ipcRenderer.invoke("terminal:start", options);
    },
    writeTerminal(sessionId, data) {
      ipcRenderer.send("terminal:write", { sessionId, data });
    },
    resizeTerminal(sessionId, columns, rows) {
      ipcRenderer.send("terminal:resize", { sessionId, columns, rows });
    },
    closeTerminal(sessionId) {
      ipcRenderer.send("terminal:close", { sessionId });
    },
    onTerminalData(callback) {
      const listener = (_event, payload) => callback(payload);
      ipcRenderer.on("terminal:data", listener);
      return () => ipcRenderer.removeListener("terminal:data", listener);
    },
    onTerminalExit(callback) {
      const listener = (_event, payload) => callback(payload);
      ipcRenderer.on("terminal:exit", listener);
      return () => ipcRenderer.removeListener("terminal:exit", listener);
    },
    checkStartupReadiness(deploymentMode) {
      return ipcRenderer.invoke("startup:check-readiness", { deploymentMode });
    },
    startRobotTelemetry(deploymentMode) {
      return ipcRenderer.invoke("robot:telemetry-start", { deploymentMode });
    },
    stopRobotTelemetry() {
      ipcRenderer.send("robot:telemetry-stop");
    },
    onRobotTelemetry(callback) {
      const listener = (_event, payload) => callback(payload);
      ipcRenderer.on("robot:telemetry", listener);
      return () => ipcRenderer.removeListener("robot:telemetry", listener);
    },
    setRobotControlMode(deploymentMode, mode) {
      return ipcRenderer.invoke("robot:set-control-mode", { deploymentMode, mode });
    },
    moveRobotJoints(deploymentMode, jointsDeg, speedRadS) {
      return ipcRenderer.invoke("robot:move-joints", {
        deploymentMode,
        jointsDeg,
        speedRadS,
      });
    },
    getWindowState() {
      return ipcRenderer.invoke("window:get-state");
    },
    minimizeWindow() {
      ipcRenderer.send("window:minimize");
    },
    toggleMaximizeWindow() {
      ipcRenderer.send("window:toggle-maximize");
    },
    closeWindow() {
      ipcRenderer.send("window:close");
    },
    onWindowMaximizedChange(callback) {
      const listener = (_event, maximized) => callback(maximized);
      ipcRenderer.on("window:maximized-changed", listener);
      return () => ipcRenderer.removeListener("window:maximized-changed", listener);
    },
  }),
);
