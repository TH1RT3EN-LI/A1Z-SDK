import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { execFile, spawn } from "node:child_process";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { app, BrowserWindow, ipcMain, Menu, net, protocol, shell } from "electron";
import * as pty from "node-pty";

const electronDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(electronDirectory, "..");
const sourceRepositoryRoot = resolve(frontendRoot, "../..");
const terminalSessions = new Map();
const robotTelemetrySessions = new Map();
const robotCommandOwners = new Set();
const execFileAsync = promisify(execFile);
const developmentMode = process.argv.includes("--development-mode");

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

function requireRealHardwareMode() {
  if (developmentMode) {
    throw new Error("开发模式已启用，不会连接或控制真机。");
  }
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

function closeRobotTelemetry(ownerId) {
  const session = robotTelemetrySessions.get(ownerId);
  if (!session) return;
  robotTelemetrySessions.delete(ownerId);
  session.closed = true;
  try {
    session.child.kill();
  } catch {
    // The telemetry bridge may already have exited.
  }
}

function telemetryCommand(deploymentMode) {
  const tcpHost = process.env.A1Z_CONSOLE_TCP_HOST || "127.0.0.1";
  const tcpPort = process.env.A1Z_CONSOLE_TCP_PORT || "37104";
  const sharedEnvironment = {
    A1Z_SOCKET_PATH: "",
    A1Z_TCP_HOST: tcpHost,
    A1Z_TCP_PORT: tcpPort,
    A1Z_REQUEST_TIMEOUT_S: "0.8",
  };

  if (deploymentMode === "docker") {
    const containerName =
      process.env.A1Z_SDK_CONTAINER_NAME ||
      process.env.A1Z_ROS2_CONTAINER_NAME ||
      "a1z-ros2-humble-real";
    return {
      command: "docker",
      args: [
        "exec",
        "-w",
        "/workspace/A1Z",
        "-e",
        "PYTHONPATH=/workspace/A1Z",
        "-e",
        `A1Z_SOCKET_PATH=${sharedEnvironment.A1Z_SOCKET_PATH}`,
        "-e",
        `A1Z_TCP_HOST=${sharedEnvironment.A1Z_TCP_HOST}`,
        "-e",
        `A1Z_TCP_PORT=${sharedEnvironment.A1Z_TCP_PORT}`,
        "-e",
        `A1Z_REQUEST_TIMEOUT_S=${sharedEnvironment.A1Z_REQUEST_TIMEOUT_S}`,
        containerName,
        "/usr/bin/python3",
        "-m",
        "a1z_sdk.telemetry",
        "--interval",
        "0.4",
      ],
      options: { cwd: repositoryRoot(), env: process.env },
    };
  }

  const root = repositoryRoot();
  const pythonPath = [root, process.env.PYTHONPATH].filter(Boolean).join(":");
  return {
    command: process.env.A1Z_PYTHON || "python3",
    args: ["-m", "a1z_sdk.telemetry", "--interval", "0.4"],
    options: {
      cwd: root,
      env: { ...process.env, ...sharedEnvironment, PYTHONPATH: pythonPath },
    },
  };
}

function robotCliCommand(deploymentMode, cliArguments, requestTimeoutSeconds) {
  const tcpHost = process.env.A1Z_CONSOLE_TCP_HOST || "127.0.0.1";
  const tcpPort = process.env.A1Z_CONSOLE_TCP_PORT || "37104";
  const sharedEnvironment = {
    A1Z_SOCKET_PATH: "",
    A1Z_TCP_HOST: tcpHost,
    A1Z_TCP_PORT: tcpPort,
    A1Z_REQUEST_TIMEOUT_S: String(requestTimeoutSeconds),
  };

  if (deploymentMode === "docker") {
    const containerName =
      process.env.A1Z_SDK_CONTAINER_NAME ||
      process.env.A1Z_ROS2_CONTAINER_NAME ||
      "a1z-ros2-humble-real";
    return {
      command: "docker",
      args: [
        "exec",
        "-w",
        "/workspace/A1Z",
        "-e",
        "PYTHONPATH=/workspace/A1Z",
        "-e",
        `A1Z_SOCKET_PATH=${sharedEnvironment.A1Z_SOCKET_PATH}`,
        "-e",
        `A1Z_TCP_HOST=${sharedEnvironment.A1Z_TCP_HOST}`,
        "-e",
        `A1Z_TCP_PORT=${sharedEnvironment.A1Z_TCP_PORT}`,
        "-e",
        `A1Z_REQUEST_TIMEOUT_S=${sharedEnvironment.A1Z_REQUEST_TIMEOUT_S}`,
        containerName,
        "/usr/bin/python3",
        "-m",
        "a1z_sdk",
        "--json",
        ...cliArguments,
      ],
      options: { cwd: repositoryRoot(), env: process.env },
    };
  }

  const root = repositoryRoot();
  const pythonPath = [root, process.env.PYTHONPATH].filter(Boolean).join(":");
  return {
    command: process.env.A1Z_PYTHON || "python3",
    args: ["-m", "a1z_sdk", "--json", ...cliArguments],
    options: {
      cwd: root,
      env: { ...process.env, ...sharedEnvironment, PYTHONPATH: pythonPath },
    },
  };
}

function robotModeCommand(deploymentMode, mode) {
  return robotCliCommand(deploymentMode, ["mode", mode], 2.5);
}

function robotMoveCommand(deploymentMode, jointsDeg, speedRadS) {
  return robotCliCommand(
    deploymentMode,
    [
      "target",
      jointsDeg.map((value) => String(value)).join(","),
      "--speed",
      String(speedRadS),
      "--motion-timeout",
      "120",
    ],
    5,
  );
}

function lastJsonObject(output) {
  const lines = String(output || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      const value = JSON.parse(lines[index]);
      if (value && typeof value === "object") return value;
    } catch {
      // SDK logs can precede the compact JSON response.
    }
  }
  return null;
}

function friendlyModeCommandError(detail) {
  if (/estop|emergency stop/i.test(detail)) {
    return "急停已锁定，请解除急停后重试。";
  }
  if (/fault/i.test(detail)) {
    return "机械臂控制异常，请排除故障后重试。";
  }
  if (/gravity.*factor|compensation factor/i.test(detail)) {
    return "零力模式尚未就绪，请检查启动设置。";
  }
  if (/recording|another operation|busy/i.test(detail)) {
    return "机械臂正在执行其他操作，请结束后重试。";
  }
  if (
    /not running|restart the control service|connection refused|timed out|no such file|cannot connect/i.test(
      detail,
    )
  ) {
    return "控制服务尚未就绪，请检查连接后重试。";
  }
  return "模式调整未完成，请保持机械臂不动并重试。";
}

async function setRobotControlMode(deploymentMode, mode) {
  const launch = robotModeCommand(deploymentMode, mode);
  let stdout = "";
  let stderr = "";
  try {
    const result = await execFileAsync(launch.command, launch.args, {
      ...launch.options,
      encoding: "utf8",
      timeout: 8000,
      maxBuffer: 1024 * 1024,
    });
    stdout = result.stdout;
    stderr = result.stderr;
  } catch (error) {
    stdout = typeof error?.stdout === "string" ? error.stdout : "";
    stderr = [error?.stderr, error?.message]
      .filter((value) => typeof value === "string")
      .join("\n");
  }

  const payload = lastJsonObject(stdout);
  if (payload?.ok === true) {
    return { accepted: true };
  }

  const detail = [payload?.error, stderr, stdout]
    .filter((value) => typeof value === "string" && value.trim())
    .join("\n");
  console.warn(`A1Z mode command failed (${deploymentMode}/${mode}): ${detail}`);
  throw new Error(friendlyModeCommandError(detail));
}

function friendlyMoveCommandError(detail) {
  if (/estop|emergency stop/i.test(detail)) {
    return "急停已锁定，请解除急停后重试。";
  }
  if (/fault/i.test(detail)) {
    return "机械臂控制异常，请排除故障后重试。";
  }
  if (/position-hold|position_hold|wrong mode|requires position/i.test(detail)) {
    return "请先切换到位置保持模式。";
  }
  if (/joint limit|exceeds.*limit|outside.*range/i.test(detail)) {
    return "目标角度超出机械臂范围，请检查标记的关节。";
  }
  if (/recording|another operation|busy/i.test(detail)) {
    return "机械臂正在执行其他操作，请结束后重试。";
  }
  if (/not reached|submitted_unverified|feedback.*verify/i.test(detail)) {
    return "机械臂未能确认到达目标位置，请保持安全距离并检查状态。";
  }
  if (/timed out|timeout|killed/i.test(detail)) {
    return "执行结果无法确认，机械臂可能仍在运动，请保持安全距离并检查状态。";
  }
  if (/not running|restart the control service|connection refused|no such file|cannot connect/i.test(detail)) {
    return "控制服务尚未就绪，请检查连接后重试。";
  }
  return "目标运动未完成，请保持安全距离并检查机械臂状态。";
}

async function moveRobotJoints(deploymentMode, jointsDeg, speedRadS) {
  const launch = robotMoveCommand(deploymentMode, jointsDeg, speedRadS);
  let stdout = "";
  let stderr = "";
  try {
    const result = await execFileAsync(launch.command, launch.args, {
      ...launch.options,
      encoding: "utf8",
      timeout: 8000,
      maxBuffer: 1024 * 1024,
    });
    stdout = result.stdout;
    stderr = result.stderr;
  } catch (error) {
    stdout = typeof error?.stdout === "string" ? error.stdout : "";
    stderr = [
      error?.stderr,
      error?.message,
      error?.killed ? "command killed after timeout" : "",
    ]
      .filter((value) => typeof value === "string" && value)
      .join("\n");
  }

  const payload = lastJsonObject(stdout);
  if (payload?.ok === true && payload?.completion === "accepted") {
    const goalId = Number(payload?.data?.goal_id);
    if (!Number.isInteger(goalId) || goalId <= 0) {
      throw new Error("控制服务接受了目标，但没有返回有效的目标编号。");
    }
    return {
      accepted: true,
      goalId,
      completion: "accepted",
    };
  }

  const detail = [
    payload?.error,
    payload?.execution_state,
    stderr,
    stdout,
  ]
    .filter((value) => typeof value === "string" && value.trim())
    .join("\n");
  console.warn(`A1Z joint move failed (${deploymentMode}): ${detail}`);
  throw new Error(friendlyMoveCommandError(detail));
}

function startRobotTelemetry(owner, deploymentMode) {
  closeRobotTelemetry(owner.id);
  const launch = telemetryCommand(deploymentMode);
  const child = spawn(launch.command, launch.args, {
    ...launch.options,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const session = { child, closed: false, stderr: "", buffer: "" };
  robotTelemetrySessions.set(owner.id, session);

  const send = (payload) => {
    if (
      !session.closed &&
      robotTelemetrySessions.get(owner.id) === session &&
      !owner.isDestroyed()
    ) {
      owner.send("robot:telemetry", payload);
    }
  };

  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    session.buffer += chunk;
    if (session.buffer.length > 1024 * 1024) {
      session.buffer = "";
      send({ ok: false, error: "遥测响应过大，已丢弃。" });
      return;
    }
    let newlineIndex = session.buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = session.buffer.slice(0, newlineIndex).trim();
      session.buffer = session.buffer.slice(newlineIndex + 1);
      if (line) {
        try {
          const payload = JSON.parse(line);
          if (payload && typeof payload === "object") send(payload);
        } catch {
          send({ ok: false, error: "无法解析 SDK 遥测。" });
        }
      }
      newlineIndex = session.buffer.indexOf("\n");
    }
  });

  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => {
    session.stderr = `${session.stderr}${chunk}`.slice(-4096);
  });
  child.once("error", (error) => {
    send({ ok: false, error: `无法启动 SDK 遥测：${error.message}` });
  });
  child.once("exit", (code, signal) => {
    if (session.closed || robotTelemetrySessions.get(owner.id) !== session) return;
    const detail = session.stderr.trim();
    send({
      ok: false,
      error: detail || `SDK 遥测已停止（${signal || (code ?? "unknown")}）。`,
    });
    robotTelemetrySessions.delete(owner.id);
  });
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

async function runStartupCheckCommand(command, args) {
  try {
    const { stdout, stderr } = await execFileAsync(command, args, {
      encoding: "utf8",
      timeout: 5000,
      maxBuffer: 1024 * 1024,
    });
    return { ok: true, output: `${stdout}${stderr}` };
  } catch (error) {
    const output = [error?.stdout, error?.stderr, error?.message]
      .filter((value) => typeof value === "string")
      .join("\n");
    return { ok: false, output };
  }
}

function classifyCanReadiness(commandResult, expectedBitrate) {
  const output = commandResult.output;
  if (!commandResult.ok) {
    if (/does not exist|cannot find device|no such device/i.test(output)) {
      return "device_missing";
    }
    return "check_unavailable";
  }

  if (/can state (bus-off|error-passive)/i.test(output)) {
    return "communication_fault";
  }

  const flags = output.match(/<([^>]+)>/)?.[1]?.split(",") ?? [];
  const isUp = flags.includes("UP") || /\bstate UP\b/.test(output);
  const bitrate = output.match(/\bbitrate\s+(\d+)/)?.[1];
  if (!isUp || bitrate !== expectedBitrate) return "device_inactive";
  return "ready";
}

async function checkStartupReadiness(deploymentMode) {
  if (deploymentMode !== "host" && deploymentMode !== "docker") {
    return { ok: false, code: "check_unavailable" };
  }

  const canChannel = process.env.A1Z_CAN_CHANNEL || "can0";
  const canBitrate = process.env.A1Z_CAN_BITRATE || "1000000";
  let result;

  if (deploymentMode === "docker") {
    const containerName =
      process.env.A1Z_SDK_CONTAINER_NAME ||
      process.env.A1Z_ROS2_CONTAINER_NAME ||
      "a1z-ros2-humble-real";
    const container = await runStartupCheckCommand("docker", [
      "inspect",
      "-f",
      "{{.State.Running}}",
      containerName,
    ]);
    if (!container.ok || container.output.trim() !== "true") {
      console.warn("A1Z startup check: selected Docker runtime is unavailable.");
      return { ok: false, code: "deployment_unavailable" };
    }
    result = await runStartupCheckCommand("docker", [
      "exec",
      containerName,
      "ip",
      "-details",
      "-statistics",
      "link",
      "show",
      canChannel,
    ]);
  } else {
    result = await runStartupCheckCommand("ip", [
      "-details",
      "-statistics",
      "link",
      "show",
      canChannel,
    ]);
  }

  const code = classifyCanReadiness(result, canBitrate);
  if (code !== "ready") {
    console.warn(`A1Z startup check failed (${deploymentMode}/${code}).`);
  }
  return { ok: code === "ready", code };
}

function registerStartupIpc() {
  ipcMain.handle("startup:check-readiness", (_event, options = {}) =>
    checkStartupReadiness(options.deploymentMode),
  );
}

function registerRobotIpc() {
  ipcMain.handle("robot:telemetry-start", (event, options = {}) => {
    requireRealHardwareMode();
    if (options.deploymentMode !== "host" && options.deploymentMode !== "docker") {
      throw new Error("invalid deployment mode");
    }
    startRobotTelemetry(event.sender, options.deploymentMode);
    return { started: true };
  });
  ipcMain.on("robot:telemetry-stop", (event) => {
    closeRobotTelemetry(event.sender.id);
  });
  ipcMain.handle("robot:set-control-mode", async (event, options = {}) => {
    requireRealHardwareMode();
    const deploymentMode = options.deploymentMode;
    const mode = options.mode;
    if (deploymentMode !== "host" && deploymentMode !== "docker") {
      throw new Error("invalid deployment mode");
    }
    if (mode !== "hold" && mode !== "zero-force") {
      throw new Error("invalid arm control mode");
    }
    if (robotCommandOwners.has(event.sender.id)) {
      throw new Error("机械臂正在执行其他操作，请结束后重试。");
    }
    robotCommandOwners.add(event.sender.id);
    try {
      return await setRobotControlMode(deploymentMode, mode);
    } finally {
      robotCommandOwners.delete(event.sender.id);
    }
  });
  ipcMain.handle("robot:move-joints", async (event, options = {}) => {
    requireRealHardwareMode();
    const deploymentMode = options.deploymentMode;
    const jointsDeg = options.jointsDeg;
    const speedRadS = Number(options.speedRadS);
    if (deploymentMode !== "host" && deploymentMode !== "docker") {
      throw new Error("invalid deployment mode");
    }
    if (
      !Array.isArray(jointsDeg) ||
      jointsDeg.length !== 6 ||
      !jointsDeg.every((value) => Number.isFinite(value))
    ) {
      throw new Error("目标角度必须包含六个有效数值。");
    }
    if (!Number.isFinite(speedRadS) || speedRadS < 0.05 || speedRadS > 1.5) {
      throw new Error("转动速度必须位于 0.05–1.5 rad/s。");
    }
    if (robotCommandOwners.has(event.sender.id)) {
      throw new Error("机械臂正在执行其他操作，请结束后重试。");
    }
    robotCommandOwners.add(event.sender.id);
    try {
      return await moveRobotJoints(deploymentMode, jointsDeg, speedRadS);
    } finally {
      robotCommandOwners.delete(event.sender.id);
    }
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
  if (process.env.A1Z_DESKTOP_SCREENSHOT_SKIP_STARTUP === "1") {
    for (let step = 0; step < 3; step += 1) {
      await window.webContents.executeJavaScript(
        `document.querySelector(".startup-skip-button")?.click()`,
      );
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 160));
    }
  }
  if (process.env.A1Z_DESKTOP_SCREENSHOT_THEME === "light") {
    await window.webContents.executeJavaScript(
      `[...document.querySelectorAll(".menu-trigger")]
        .find((element) => element.textContent?.includes("设置"))?.click()`,
    );
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 80));
    await window.webContents.executeJavaScript(
      `[...document.querySelectorAll(".menu-popover button")]
        .find((element) => element.textContent?.includes("浅色模式"))?.click()`,
    );
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 180));
  }
  if (process.env.A1Z_DESKTOP_SCREENSHOT_SHOW_JOINT_LABELS === "1") {
    await window.webContents.executeJavaScript(
      `document.querySelector('.model-label-toggle button[role="switch"]')?.click()`,
    );
  }
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const ready = await window.webContents.executeJavaScript(
      `Boolean(
        document.querySelector(".robot-viewport.is-ready") &&
        document.querySelector('.terminal-panel[data-connection-state="connected"]') &&
        (${process.env.A1Z_DESKTOP_SCREENSHOT_SHOW_JOINT_LABELS === "1"} === false ||
          document.querySelector(".telemetry-state.is-live"))
      )`,
    );
    if (ready) break;
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
  }
  if (process.env.A1Z_DESKTOP_SCREENSHOT_OPEN_ZERO_FORCE === "1") {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const modeControlReady = await window.webContents.executeJavaScript(
        `Boolean(
          document.querySelector(".telemetry-state.is-live") ||
          document.querySelector(".arm-mode-control.is-development-preview")
        )`,
      );
      if (modeControlReady) break;
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
    }
    await window.webContents.executeJavaScript(
      `document.querySelectorAll(".arm-mode-selector button")[1]?.click()`,
    );
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 180));
    if (process.env.A1Z_DESKTOP_SCREENSHOT_CONFIRM_ZERO_FORCE === "1") {
      await window.webContents.executeJavaScript(
        `document.querySelector(".arm-mode-dialog-actions .is-primary")?.click()`,
      );
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 900));
      if (process.env.A1Z_DESKTOP_SCREENSHOT_RETURN_HOLD === "1") {
        await window.webContents.executeJavaScript(
          `document.querySelectorAll(".arm-mode-selector button")[0]?.click()`,
        );
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 180));
        await window.webContents.executeJavaScript(
          `document.querySelector(".arm-mode-dialog-actions .is-primary")?.click()`,
        );
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 900));
      }
    }
  }
  if (process.env.A1Z_DESKTOP_SCREENSHOT_OPEN_JOINT_MOVE === "1") {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      const targetReady = await window.webContents.executeJavaScript(
        `Boolean(document.querySelector(".joint-target-control:not(.is-locked)"))`,
      );
      if (targetReady) break;
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
    }
    await window.webContents.executeJavaScript(
      `document.querySelector(".execute-joint-target")?.click()`,
    );
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 180));
    if (process.env.A1Z_DESKTOP_SCREENSHOT_CONFIRM_JOINT_MOVE === "1") {
      await window.webContents.executeJavaScript(
        `document.querySelector(".joint-move-dialog-actions .is-primary")?.click()`,
      );
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 1450));
    }
  }
  await new Promise((resolveDelay) => setTimeout(resolveDelay, 400));
  if (process.env.A1Z_DESKTOP_SCREENSHOT_SHOW_JOINT_LABELS === "1") {
    const jointLabels = await window.webContents.executeJavaScript(
      `[...document.querySelectorAll(".joint-model-label")].map((element) => {
        const bounds = element.getBoundingClientRect();
        return {
          text: element.textContent,
          opacity: getComputedStyle(element).opacity,
          x: Math.round(bounds.x),
          y: Math.round(bounds.y),
          width: Math.round(bounds.width),
          height: Math.round(bounds.height),
        };
      })`,
    );
    console.log("A1Z screenshot joint labels", jointLabels);
  }
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
      additionalArguments: [
        `--a1z-development-mode=${developmentMode ? "1" : "0"}`,
      ],
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
  window.webContents.once("destroyed", () => {
    closeOwnedTerminalSessions(webContentsId);
    closeRobotTelemetry(webContentsId);
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    await window.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    await window.loadURL("a1z://localhost/index.html");
  }
}

Menu.setApplicationMenu(null);
registerTerminalIpc();
registerWindowIpc();
registerStartupIpc();
registerRobotIpc();

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
  for (const ownerId of robotTelemetrySessions.keys()) closeRobotTelemetry(ownerId);
});
