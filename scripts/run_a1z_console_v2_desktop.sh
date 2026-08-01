#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/console_v2/frontend"
RUNTIME_DIR="$REPO_ROOT/runtime/a1z-console-v2"
PTY_MARKER="$RUNTIME_DIR/electron-pty-43.2.0"
DEPENDENCY_MARKER="$RUNTIME_DIR/electron-dependencies"

mkdir -p "$RUNTIME_DIR"

if [[ ! -d "$FRONTEND_DIR/node_modules/electron" || ! -f "$DEPENDENCY_MARKER" || "$FRONTEND_DIR/package-lock.json" -nt "$DEPENDENCY_MARKER" ]]; then
    npm --prefix "$FRONTEND_DIR" install --no-audit --no-fund
    touch "$DEPENDENCY_MARKER"
fi

if [[ ! -x "$FRONTEND_DIR/node_modules/electron/dist/electron" ]]; then
    node "$FRONTEND_DIR/node_modules/electron/install.js"
fi

if [[ ! -f "$PTY_MARKER" || "$FRONTEND_DIR/package.json" -nt "$PTY_MARKER" || "$FRONTEND_DIR/node_modules/node-pty/package.json" -nt "$PTY_MARKER" ]]; then
    npm --prefix "$FRONTEND_DIR" run desktop:rebuild
    touch "$PTY_MARKER"
fi

cd "$FRONTEND_DIR"
exec npm run desktop:dev
