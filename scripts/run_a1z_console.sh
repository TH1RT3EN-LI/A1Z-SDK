#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_PACKAGES="${A1Z_CONSOLE_PYTHON_PACKAGES:-$ROOT_DIR/runtime/a1z-console-python}"
PYTHON_BIN="${A1Z_CONSOLE_PYTHON:-python3}"

if ! PYTHONPATH="$PYTHON_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON_BIN" -c \
  'import PySide6; major, minor, *_ = map(int, PySide6.__version__.split(".")); assert (major, minor) >= (6, 8)' \
  >/dev/null 2>&1; then
  "$PYTHON_BIN" -m pip install --disable-pip-version-check --upgrade \
    --target "$PYTHON_PACKAGES" \
    -r "$ROOT_DIR/console/requirements.txt"
fi

export PYTHONPATH="$PYTHON_PACKAGES:$ROOT_DIR/console${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" -m a1z_console.main "$@"
