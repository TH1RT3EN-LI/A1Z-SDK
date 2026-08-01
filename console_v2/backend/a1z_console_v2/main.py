"""Local-only API and PTY bridge for A1Z Console V2."""

from __future__ import annotations

import asyncio
import json
import os
import pty
import signal
import struct
import termios
from contextlib import suppress
from fcntl import ioctl
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_TERMINAL_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}

app = FastAPI(title="A1Z Console V2", docs_url=None, redoc_url=None)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "scope": "framework"}


def _resize_terminal(file_descriptor: int, columns: int, rows: int) -> None:
    safe_columns = max(20, min(columns, 500))
    safe_rows = max(5, min(rows, 300))
    window_size = struct.pack("HHHH", safe_rows, safe_columns, 0, 0)
    ioctl(file_descriptor, termios.TIOCSWINSZ, window_size)


def _spawn_shell() -> tuple[int, int]:
    child_pid, master_fd = pty.fork()
    if child_pid == 0:
        os.chdir(REPOSITORY_ROOT)
        shell = os.environ.get("SHELL", "/bin/bash")
        if not Path(shell).is_file():
            shell = "/bin/bash"
        environment = os.environ.copy()
        environment.update(
            {
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "A1Z_CONSOLE_V2": "1",
            }
        )
        os.execvpe(shell, [shell, "-l"], environment)
    return child_pid, master_fd


async def _send_pty_output(websocket: WebSocket, master_fd: int) -> None:
    while True:
        try:
            output = await asyncio.to_thread(os.read, master_fd, 8192)
        except OSError:
            return
        if not output:
            return
        await websocket.send_bytes(output)


async def _receive_terminal_input(websocket: WebSocket, master_fd: int) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
        text = message.get("text")
        if text is None:
            continue
        try:
            payload: dict[str, Any] = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        message_type = payload.get("type")
        if message_type == "input":
            data = payload.get("data")
            if isinstance(data, str):
                await asyncio.to_thread(os.write, master_fd, data.encode())
        elif message_type == "resize":
            columns = payload.get("cols")
            rows = payload.get("rows")
            if isinstance(columns, int) and isinstance(rows, int):
                _resize_terminal(master_fd, columns, rows)


def _close_shell(child_pid: int, master_fd: int) -> None:
    with suppress(OSError):
        os.close(master_fd)
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(child_pid, signal.SIGHUP)
    with suppress(ChildProcessError):
        os.waitpid(child_pid, os.WNOHANG)


@app.websocket("/api/terminal")
async def terminal(websocket: WebSocket) -> None:
    if websocket.headers.get("origin") not in ALLOWED_TERMINAL_ORIGINS:
        await websocket.close(code=1008, reason="terminal origin is not allowed")
        return
    await websocket.accept()
    child_pid, master_fd = _spawn_shell()
    _resize_terminal(master_fd, 100, 28)
    output_task = asyncio.create_task(_send_pty_output(websocket, master_fd))
    input_task = asyncio.create_task(_receive_terminal_input(websocket, master_fd))
    tasks = {output_task, input_task}
    try:
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        _close_shell(child_pid, master_fd)
