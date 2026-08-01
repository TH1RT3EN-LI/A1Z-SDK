import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { app, BrowserWindow, ipcMain, Menu, net, protocol, shell } from "electron";
import * as pty from "node-pty";

const electronDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(electronDirectory, "..");
const sourceRepositoryRoot = resolve(frontendRoot, "../..");
const terminalSessions = new Map();

protocol.registerSchemesAsPrivileged([
  {
    scheme: "a1z",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

function clampInteger(value, minimum, maximum, fallback) {
  return Number.isInteger(value) ? Math.max(minimum, Math.min(maximum, value)) : fallback;
}

function validSessionId(value) {
  return typeof value === "string" && /^[0-9a-f-]{36}$/i.test(value);
}

function repositoryRoot() {
  const configuredRoot = process.env.A1Z_REPO_ROOT;
  if (configuredRoot && isAbsolute(configuredRoot) && existsSync(configuredRoot)) {
    return configuredRoot;
  }
  return app.isPackaged ? homedir() : sourceRepositoryRoot;
}

function closeTerminalSession(sessionId) {
  const session = terminalSessions.get(sessionId);
  if (!session) return;
  terminalSessions.delete(sessionId);
  try {
    session.terminal.kill();
  } catch {
    // The PTY may already have exited.
  }
}

function closeOwnedTerminalSessions(ownerId) {
  for (const [sessionId, session] of terminalSessions) {
    if (session.ownerId === ownerId) closeTerminalSession(sessionId);
  }
}

function windowFromEvent(event) {
  return BrowserWindow.fromWebContents(event.sender);
}

function registerWindowIpc() {
  ipcMain.handle("window:get-state", (event) => {
    const window = windowFromEvent(event);
    return { maximized: window?.isMaximized() ?? false };
  });

  ipcMain.on("window:minimize", (event) => {
    windowFromEvent(event)?.minimize();
  });

  ipcMain.on("window:toggle-maximize", (event) => {
    const window = windowFromEvent(event);
    if (!window) return;
    if (window.isMaximized()) window.unmaximize();
    else window.maximize();
  });

  ipcMain.on("window:close", (event) => {
    windowFromEvent(event)?.close();
  });
}

function registerTerminalIpc() {
  ipcMain.handle("terminal:start", (event, options = {}) => {
    const sessionId = options.sessionId;
    if (!validSessionId(sessionId)) throw new Error("invalid terminal session id");
    closeTerminalSession(sessionId);

    const shellPath = process.env.SHELL && existsSync(process.env.SHELL) ? process.env.SHELL : "/bin/bash";
    const environment = Object.fromEntries(
      Object.entries(process.env).filter((entry) => typeof entry[1] === "string"),
    );
    environment.TERM = "xterm-256color";
    environment.COLORTERM = "truecolor";
    environment.A1Z_CONSOLE_V2 = "1";
    environment.A1Z_CONSOLE_DESKTOP = "1";

    const terminal = pty.spawn(shellPath, ["-l"], {
      name: "xterm-256color",
      cols: clampInteger(options.columns, 20, 500, 100),
      rows: clampInteger(options.rows, 5, 300, 28),
      cwd: repositoryRoot(),
      env: environment,
    });
    const owner = event.sender;
    terminalSessions.set(sessionId, { terminal, ownerId: owner.id });

    terminal.onData((data) => {
      if (!owner.isDestroyed()) owner.send("terminal:data", { sessionId, data });
    });
    terminal.onExit(({ exitCode, signal }) => {
      terminalSessions.delete(sessionId);
      if (!owner.isDestroyed()) owner.send("terminal:exit", { sessionId, exitCode, signal });
    });
    return { sessionId };
  });

  ipcMain.on("terminal:write", (event, payload = {}) => {
    const session = terminalSessions.get(payload.sessionId);
    if (session?.ownerId !== event.sender.id || typeof payload.data !== "string") return;
    if (payload.data.length > 65536) return;
    session.terminal.write(payload.data);
  });

  ipcMain.on("terminal:resize", (event, payload = {}) => {
    const session = terminalSessions.get(payload.sessionId);
    if (session?.ownerId !== event.sender.id) return;
    session.terminal.resize(
      clampInteger(payload.columns, 20, 500, 100),
      clampInteger(payload.rows, 5, 300, 28),
    );
  });

  ipcMain.on("terminal:close", (event, payload = {}) => {
    const session = terminalSessions.get(payload.sessionId);
    if (session?.ownerId === event.sender.id) closeTerminalSession(payload.sessionId);
  });
}

async function registerDesktopProtocol() {
  const distributionRoot = resolve(frontendRoot, "dist");
  await protocol.handle("a1z", (request) => {
    const requestUrl = new URL(request.url);
    let relativePath = decodeURIComponent(requestUrl.pathname).replace(/^\/+/, "");
    if (!relativePath) relativePath = "index.html";
    const target = resolve(distributionRoot, relativePath);
    if (target !== distributionRoot && !target.startsWith(`${distributionRoot}${sep}`)) {
      return new Response("Forbidden", { status: 403 });
    }
    return net.fetch(pathToFileURL(target).toString());
  });
}

async function captureFrameworkScreenshot(window) {
  const destination = process.env.A1Z_DESKTOP_SCREENSHOT;
  if (!destination) return;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const ready = await window.webContents.executeJavaScript(
      'Boolean(document.querySelector(".model-state.is-ready") && document.querySelector(".connection-state.is-connected"))',
    );
    if (ready) break;
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
  }
  await new Promise((resolveDelay) => setTimeout(resolveDelay, 400));
  const image = await window.webContents.capturePage();
  await mkdir(dirname(destination), { recursive: true });
  await writeFile(destination, image.toPNG());
  app.quit();
}

async function createMainWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1000,
    minHeight: 680,
    frame: false,
    show: false,
    title: "A1Z Console",
    backgroundColor: "#0b0e13",
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(electronDirectory, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://") || url.startsWith("http://")) void shell.openExternal(url);
    return { action: "deny" };
  });
  window.webContents.on("will-navigate", (event, url) => {
    const devUrl = process.env.VITE_DEV_SERVER_URL;
    if ((devUrl && url.startsWith(devUrl)) || url.startsWith("a1z://")) return;
    event.preventDefault();
  });
  window.webContents.once("did-finish-load", () => {
    window.show();
    void captureFrameworkScreenshot(window);
  });
  const sendMaximizedState = () => {
    if (!window.webContents.isDestroyed()) {
      window.webContents.send("window:maximized-changed", window.isMaximized());
    }
  };
  window.on("maximize", sendMaximizedState);
  window.on("unmaximize", sendMaximizedState);
  const webContentsId = window.webContents.id;
  window.webContents.once("destroyed", () => closeOwnedTerminalSessions(webContentsId));

  if (process.env.VITE_DEV_SERVER_URL) {
    await window.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    await window.loadURL("a1z://localhost/index.html");
  }
}

Menu.setApplicationMenu(null);
registerTerminalIpc();
registerWindowIpc();

app.whenReady().then(async () => {
  await registerDesktopProtocol();
  await createMainWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) void createMainWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  for (const sessionId of terminalSessions.keys()) closeTerminalSession(sessionId);
});
