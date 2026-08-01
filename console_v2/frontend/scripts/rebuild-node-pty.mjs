import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDirectory, "..");
const packageJson = JSON.parse(await readFile(resolve(frontendRoot, "package.json"), "utf8"));
const electronVersion = packageJson.devDependencies.electron;
const nodeGypCommand = resolve(
  frontendRoot,
  `node_modules/.bin/node-gyp${process.platform === "win32" ? ".cmd" : ""}`,
);
const nodePtyRoot = resolve(frontendRoot, "node_modules/node-pty");

const child = spawn(
  nodeGypCommand,
  [
    "rebuild",
    `--target=${electronVersion}`,
    `--arch=${process.arch}`,
    "--dist-url=https://electronjs.org/headers",
  ],
  {
    cwd: nodePtyRoot,
    stdio: "inherit",
  },
);

const exitCode = await new Promise((resolveExit) => child.once("exit", resolveExit));
if (exitCode !== 0) process.exit(exitCode ?? 1);
