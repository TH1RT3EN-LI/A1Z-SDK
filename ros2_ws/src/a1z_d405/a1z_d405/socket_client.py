"""Minimal TCP client for the A1Z camera protocol."""

from __future__ import annotations

import json
import socket
from typing import Any


def _tcp_connect_hosts(tcp_host: str) -> list[str]:
    host = str(tcp_host or "").strip()
    if not host or host == "0.0.0.0":
        return ["127.0.0.1", "localhost"]
    if host == "::":
        return ["::1", "127.0.0.1", "localhost"]
    return [host]


class A1ZCameraClient:
    def __init__(self, *, tcp_host: str, tcp_port: int, timeout_s: float = 30.0) -> None:
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._timeout_s = timeout_s

    def call(self, cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        request = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
        payload = b""
        last_error: Exception | None = None
        for host in _tcp_connect_hosts(self._tcp_host):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._timeout_s)
            try:
                sock.connect((host, self._tcp_port))
                sock.sendall(request.encode("utf-8"))
                while b"\n" not in payload:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    payload += chunk
                if payload:
                    break
            except Exception as exc:
                last_error = exc
                payload = b""
            finally:
                sock.close()

        if not payload:
            if last_error is not None:
                raise RuntimeError(
                    f"No response from A1Z camera server via {self._tcp_host}:{self._tcp_port}: {last_error}"
                ) from last_error
            raise RuntimeError("No response from A1Z camera server.")
        response = json.loads(payload.split(b"\n", 1)[0].decode("utf-8"))
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "unknown error")))
        return dict(response.get("data", {}))
