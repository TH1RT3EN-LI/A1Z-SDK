import { chmod } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

if (process.platform === "linux") {
  const scriptDirectory = dirname(fileURLToPath(import.meta.url));
  const packageRoot = resolve(scriptDirectory, "../release/linux-unpacked");
  await Promise.all(
    ["a1z-console-v2", "chrome-sandbox", "chrome_crashpad_handler"].map((name) =>
      chmod(resolve(packageRoot, name), 0o700),
    ),
  );
}
