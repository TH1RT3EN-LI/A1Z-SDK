"""Minimal TCP client for the A1Z camera protocol."""

from __future__ import annotations

import json
import socket
from typing import Any


class A1ZCameraClient:
    def __init__(self, *, tcp_host: str, tcp_port: int, timeout_s: float = 30.0) -> None:
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._timeout_s = timeout_s

    def call(self, cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        request = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._timeout_s)
        try:
            sock.connect((self._tcp_host, self._tcp_port))
            sock.sendall(request.encode("utf-8"))
            payload = b""
            while b"\n" not in payload:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                payload += chunk
        finally:
            sock.close()

        if not payload:
            raise RuntimeError("No response from A1Z camera server.")
        response = json.loads(payload.split(b"\n", 1)[0].decode("utf-8"))
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "unknown error")))
        return dict(response.get("data", {}))
