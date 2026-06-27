"""A1Z socket protocol client with TCP support for cross-container ROS use."""

from __future__ import annotations

import json
import socket
from typing import Any


class A1ZSocketClient:
    def __init__(
        self,
        *,
        tcp_host: str,
        tcp_port: int,
        timeout_s: float = 120.0,
    ) -> None:
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
                chunk = sock.recv(4096)
                if not chunk:
                    break
                payload += chunk
        finally:
            sock.close()

        if not payload:
            raise RuntimeError("No response from A1Z TCP server.")
        response = json.loads(payload.split(b"\n", 1)[0].decode("utf-8"))
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "unknown error")))
        return dict(response.get("data", {}))
