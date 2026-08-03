import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDirectory, "..");
const viteCommand = resolve(
  frontendRoot,
  `node_modules/.bin/vite${process.platform === "win32" ? ".cmd" : ""}`,
);
const rawArguments = process.argv.slice(2);
const developmentMode = rawArguments.includes("--development-mode");
const viteArguments = rawArguments.filter((argument) => argument !== "--development-mode");

const vite = spawn(viteCommand, viteArguments, {
  cwd: frontendRoot,
  env: {
    ...process.env,
    // This value is owned by the explicit CLI flag. NODE_ENV and Vite's DEV
    // flag must never enable robot-control previews implicitly.
    VITE_A1Z_DEVELOPMENT_MODE: developmentMode ? "1" : "0",
  },
  stdio: "inherit",
});

vite.once("error", (error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});

vite.once("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 0;
});
