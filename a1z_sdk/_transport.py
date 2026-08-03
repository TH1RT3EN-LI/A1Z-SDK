"""Newline-delimited JSON transport used by all public SDK clients."""

from __future__ import annotations

import json
import math
import socket
from collections.abc import Mapping
from typing import Any

from .errors import (
    A1ZCommandRejected,
    A1ZCommandSuperseded,
    A1ZCommandUnverified,
    A1ZConnectionError,
    A1ZProtocolError,
)
from .models import Endpoint


_MAX_RESPONSE_BYTES = 1024 * 1024


class JsonLineTransport:
    """One-request-per-connection transport with deterministic fallback."""

    def __init__(self, endpoint: Endpoint) -> None:
        self.endpoint = endpoint

    @staticmethod
    def _read_response(sock: socket.socket) -> Mapping[str, Any]:
        data = bytearray()
        while b"\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > _MAX_RESPONSE_BYTES:
                raise A1ZProtocolError("control response exceeds 1 MiB")
        if not data:
            raise A1ZProtocolError("control service closed without a response")
        try:
            decoded = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise A1ZProtocolError(f"invalid control response: {exc}") from exc
        if not isinstance(decoded, dict):
            raise A1ZProtocolError("control response must be a JSON object")
        return decoded

    @staticmethod
    def _decode(command: str, response: Mapping[str, Any]) -> dict[str, Any]:
        raw_data = response.get("data", {})
        if raw_data is None:
            raw_data = {}
        if not isinstance(raw_data, dict):
            raise A1ZProtocolError("control response data must be a JSON object")
        if response.get("ok") is True:
            return dict(raw_data)

        message = str(response.get("error", "unknown control service error"))
        execution_state = str(response.get("execution_state", "rejected"))
        error_type = {
            "submitted_unverified": A1ZCommandUnverified,
            "superseded": A1ZCommandSuperseded,
        }.get(execution_state, A1ZCommandRejected)
        raise error_type(
            message,
            command=command,
            execution_state=execution_state,
            data=raw_data,
        )

    def _roundtrip(
        self,
        sock: socket.socket,
        command: str,
        arguments: Mapping[str, Any],
        *,
        timeout_s: float,
    ) -> dict[str, Any]:
        request = json.dumps(
            {"cmd": command, "args": dict(arguments)},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        sock.settimeout(timeout_s)
        sock.sendall(request)
        return self._decode(command, self._read_response(sock))

    def request(
        self,
        command: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        timeout = float(self.endpoint.timeout_s if timeout_s is None else timeout_s)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_s must be a positive finite number")
        errors: list[str] = []
        payload = arguments or {}

        if self.endpoint.socket_path:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(timeout)
                    sock.connect(self.endpoint.socket_path)
                    return self._roundtrip(
                        sock, command, payload, timeout_s=timeout
                    )
            except OSError as exc:
                errors.append(f"unix {self.endpoint.socket_path}: {exc}")

        if self.endpoint.tcp_port:
            host = self.endpoint.tcp_host.strip() or "127.0.0.1"
            connect_hosts = (
                ("127.0.0.1", "localhost")
                if host == "0.0.0.0"
                else (("::1", "127.0.0.1", "localhost") if host == "::" else (host,))
            )
            for connect_host in connect_hosts:
                try:
                    with socket.create_connection(
                        (connect_host, self.endpoint.tcp_port), timeout=timeout
                    ) as sock:
                        return self._roundtrip(
                            sock, command, payload, timeout_s=timeout
                        )
                except OSError as exc:
                    errors.append(
                        f"tcp {connect_host}:{self.endpoint.tcp_port}: {exc}"
                    )

        detail = "; ".join(errors) or "no transport attempted"
        raise A1ZConnectionError(f"cannot reach A1Z control service ({detail})")
