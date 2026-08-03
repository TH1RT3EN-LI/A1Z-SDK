import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDirectory, "..");
const repositoryRoot = resolve(frontendRoot, "../..");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const electronCommand = resolve(
  frontendRoot,
  `node_modules/.bin/electron${process.platform === "win32" ? ".cmd" : ""}`,
);
const rawArguments = process.argv.slice(2);
const unsupportedArguments = rawArguments.filter(
  (argument) => argument !== "--development-mode",
);
if (unsupportedArguments.length > 0) {
  throw new Error(
    `Unsupported argument(s): ${unsupportedArguments.join(", ")}. ` +
      "Usage: npm run desktop:dev -- [--development-mode]",
  );
}
const developmentMode = rawArguments.includes("--development-mode");
let closing = false;

const vite = spawn(
  npmCommand,
  [
    "run",
    "dev",
    "--",
    ...(developmentMode ? ["--development-mode"] : []),
    "--host",
    "127.0.0.1",
    "--port",
    "5173",
  ],
  {
    cwd: frontendRoot,
    detached: process.platform !== "win32",
    stdio: "inherit",
  },
);

function stopVite() {
  if (vite.exitCode !== null || vite.signalCode !== null) return;
  if (process.platform === "win32") vite.kill("SIGTERM");
  else process.kill(-vite.pid, "SIGTERM");
}

async function waitForVite() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (vite.exitCode !== null) throw new Error(`Vite exited with code ${vite.exitCode}`);
    try {
      const response = await fetch("http://127.0.0.1:5173/", { signal: AbortSignal.timeout(250) });
      if (response.ok) return;
    } catch {
      // The development server is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
  }
  throw new Error("Vite did not become ready within 10 seconds");
}

async function run() {
  await waitForVite();
  // This Ubuntu host disables unprivileged user namespaces and the source-tree
  // Electron binary cannot own a root/setuid sandbox helper. Renderer content
  // remains local, context-isolated and without Node integration.
  const electronArguments = [
    ...(process.platform === "linux" ? ["--no-sandbox"] : []),
    ".",
    ...(developmentMode ? ["--development-mode"] : []),
  ];
  const electron = spawn(electronCommand, electronArguments, {
    cwd: frontendRoot,
    env: {
      ...process.env,
      A1Z_REPO_ROOT: repositoryRoot,
      VITE_DEV_SERVER_URL: "http://127.0.0.1:5173/",
    },
    stdio: "inherit",
  });

  electron.once("exit", (code, signal) => {
    closing = true;
    stopVite();
    if (signal) process.kill(process.pid, signal);
    else process.exitCode = code ?? 0;
  });
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (closing) return;
    closing = true;
    stopVite();
    process.exit(130);
  });
}

run().catch((error) => {
  closing = true;
  stopVite();
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
