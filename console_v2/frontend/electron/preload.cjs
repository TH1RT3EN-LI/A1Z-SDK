const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld(
  "a1zDesktop",
  Object.freeze({
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
  }),
);
