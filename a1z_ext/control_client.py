"""Helpers for talking to the A1Z control server over Unix socket or TCP."""

from __future__ import annotations

import json
import socket
from typing import Any

from a1z_ext.config import get_socket_path, get_tcp_host, get_tcp_port


def _read_json_line(sock: socket.socket) -> dict[str, Any]:
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    if not data:
        raise RuntimeError("no response from A1Z server")
    payload = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected response payload: {payload!r}")
    return payload


def _send_unix_socket_request(socket_path: str, cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    request = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    try:
        sock.connect(socket_path)
        sock.sendall(request.encode("utf-8"))
        payload = _read_json_line(sock)
    finally:
        sock.close()
    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("error", "unknown server error")))
    data_obj = payload.get("data", {})
    return data_obj if isinstance(data_obj, dict) else {}


def _tcp_connect_hosts(tcp_host: str) -> list[str]:
    host = str(tcp_host or "").strip()
    if not host or host == "0.0.0.0":
        return ["127.0.0.1", "localhost"]
    if host == "::":
        return ["::1", "127.0.0.1", "localhost"]
    return [host]


def _send_tcp_request(
    tcp_host: str,
    tcp_port: int,
    cmd: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
    last_error: Exception | None = None
    for host in _tcp_connect_hosts(tcp_host):
        try:
            sock = socket.create_connection((host, int(tcp_port)), timeout=10.0)
        except Exception as exc:
            last_error = exc
            continue
        try:
            sock.settimeout(10.0)
            sock.sendall(request.encode("utf-8"))
            payload = _read_json_line(sock)
        finally:
            sock.close()
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error", "unknown server error")))
        data_obj = payload.get("data", {})
        return data_obj if isinstance(data_obj, dict) else {}
    if last_error is not None:
        raise RuntimeError(f"tcp connection failed for {tcp_host}:{tcp_port}: {last_error!r}")
    raise RuntimeError(f"tcp connection failed for {tcp_host}:{tcp_port}")


def send_control_request(
    cmd: str,
    args: dict[str, Any] | None = None,
    *,
    socket_path: str | None = None,
    tcp_host: str | None = None,
    tcp_port: int | None = None,
) -> dict[str, Any]:
    unix_path = socket_path or get_socket_path()
    resolved_tcp_host = tcp_host or get_tcp_host()
    resolved_tcp_port = int(get_tcp_port() if tcp_port is None else tcp_port)

    unix_error: Exception | None = None
    if unix_path:
        try:
            return _send_unix_socket_request(unix_path, cmd, args)
        except Exception as exc:
            unix_error = exc

    if resolved_tcp_port > 0:
        try:
            return _send_tcp_request(resolved_tcp_host, resolved_tcp_port, cmd, args)
        except Exception as exc:
            if unix_error is not None:
                raise RuntimeError(
                    f"unix socket request failed ({unix_path}): {unix_error}; "
                    f"tcp request failed ({resolved_tcp_host}:{resolved_tcp_port}): {exc}"
                ) from exc
            raise

    if unix_error is not None:
        raise RuntimeError(f"unix socket request failed ({unix_path}): {unix_error}") from unix_error
    raise RuntimeError("no A1Z control transport configured")
