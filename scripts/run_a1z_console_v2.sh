#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/console_v2/frontend"
BACKEND_DIR="$REPO_ROOT/console_v2/backend"
RUNTIME_DIR="$REPO_ROOT/runtime/a1z-console-v2"
PYTHON_ENV="$RUNTIME_DIR/python"
BACKEND_LOG="$RUNTIME_DIR/backend.log"
OPEN_BROWSER=1

if [[ "${1:-}" == "--no-open" ]]; then
    OPEN_BROWSER=0
elif [[ -n "${1:-}" ]]; then
    echo "Usage: $0 [--no-open]" >&2
    exit 2
fi

mkdir -p "$RUNTIME_DIR"

if [[ ! -x "$PYTHON_ENV/bin/python" ]]; then
    python3 -m venv "$PYTHON_ENV"
fi

"$PYTHON_ENV/bin/python" -m pip install \
    --disable-pip-version-check \
    --quiet \
    --requirement "$BACKEND_DIR/requirements.txt"

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    npm --prefix "$FRONTEND_DIR" install --no-audit --no-fund
fi

PYTHONPATH="$BACKEND_DIR" "$PYTHON_ENV/bin/python" -m uvicorn \
    a1z_console_v2.main:app \
    --host 127.0.0.1 \
    --port 8765 \
    >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cleanup() {
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 50); do
    if "$PYTHON_ENV/bin/python" -c \
        'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=0.2)' \
        >/dev/null 2>&1; then
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "Console V2 backend failed to start:" >&2
        tail -n 30 "$BACKEND_LOG" >&2 || true
        exit 1
    fi
    sleep 0.1
done

VITE_ARGS=(--host 127.0.0.1 --port 5173)
if [[ "$OPEN_BROWSER" -eq 1 ]]; then
    VITE_ARGS+=(--open)
fi

echo "A1Z Console V2: http://127.0.0.1:5173"
cd "$FRONTEND_DIR"
npm run dev -- "${VITE_ARGS[@]}"
