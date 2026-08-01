import { cp, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDirectory, "..");
const repositoryRoot = resolve(frontendRoot, "../..");
const source = resolve(repositoryRoot, "build/robot_packages/A1Z_G1Z");
const destination = resolve(frontendRoot, "public/model/A1Z_G1Z");

await mkdir(dirname(destination), { recursive: true });
await cp(source, destination, { recursive: true, force: true });

process.stdout.write("A1Z_G1Z model assets are ready.\n");
