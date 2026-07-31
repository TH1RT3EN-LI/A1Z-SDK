"""One-request-per-connection A1Z console protocol client.

Motion callers deliberately get no retry path.  If a request was written but a
definitive response was not received, the result is marked ambiguous so the UI
can latch motion until an operator acknowledges the uncertainty.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any

from .cancellable_socket import CancellableSocket
from .profiles import RuntimeProfile


class ProtocolError(RuntimeError):
    """A deterministic connection, protocol, or server error."""


class BackendMismatchError(ProtocolError):
    """The endpoint is alive but owns the wrong robot backend."""


class AmbiguousCommandError(ProtocolError):
    """A command was sent but its final outcome could not be established."""


@dataclass(frozen=True)
class VerifiedEndpoint:
    backend: str
    control_mode: str
    info: dict[str, Any]


def _read_json_line(sock: socket.socket, *, limit: int = 4 * 1024 * 1024) -> dict[str, Any]:
    data = bytearray()
    while b"\n" not in data:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > limit:
            raise ProtocolError("A1Z 服务响应超过 4 MiB 上限")
    if not data:
        raise EOFError("A1Z 服务未返回响应")
    try:
        payload = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"A1Z 服务返回了无效 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError(f"A1Z 服务响应类型错误：{type(payload).__name__}")
    return payload


class A1ZProtocolClient:
    def __init__(self, profile: RuntimeProfile) -> None:
        self.profile = profile
        self._request_socket = CancellableSocket()

    def cancel_pending_requests(self) -> None:
        self._request_socket.cancel()

    def request(
        self,
        command: str,
        args: dict[str, Any] | None = None,
        *,
        timeout_s: float = 5.0,
        ambiguous_after_send: bool = False,
    ) -> dict[str, Any]:
        request = (
            json.dumps({"cmd": command, "args": args or {}}, ensure_ascii=True) + "\n"
        ).encode("utf-8")
        sent = False
        try:
            sock = self._request_socket.open_connection(
                self.profile.host,
                self.profile.port,
                timeout_s=timeout_s,
            )
        except OSError as exc:
            raise ProtocolError(
                f"无法连接 {self.profile.host}:{self.profile.port}：{exc}"
            ) from exc

        try:
            sock.settimeout(float(timeout_s))
            sent = True
            sock.sendall(request)
            payload = _read_json_line(sock)
        except (
            TimeoutError,
            socket.timeout,
            EOFError,
            ConnectionError,
            OSError,
            ProtocolError,
        ) as exc:
            if sent and ambiguous_after_send:
                raise AmbiguousCommandError(
                    f"{command} 已发出，但未收到确定响应；禁止自动重发：{exc}"
                ) from exc
            if isinstance(exc, ProtocolError):
                raise
            raise ProtocolError(f"{command} 请求失败：{exc}") from exc
        finally:
            self._request_socket.release(sock)

        response_ok = payload.get("ok")
        if response_ok is False:
            error = ProtocolError(
                str(payload.get("error", "A1Z 服务返回未知错误"))
            )
            execution_state = str(payload.get("execution_state", ""))
            if ambiguous_after_send and execution_state != "rejected":
                raise AmbiguousCommandError(
                    f"{command} 已发出，服务端未确认动作在执行前被拒绝：{error}"
                ) from error
            raise error
        if response_ok is not True:
            error = ProtocolError(f"{command} 响应缺少有效的 ok 字段")
            if ambiguous_after_send:
                raise AmbiguousCommandError(
                    f"{command} 已发出，但响应格式无法确认结果：{error}"
                ) from error
            raise error
        data = payload.get("data", {})
        if not isinstance(data, dict):
            error = ProtocolError(f"{command} 的 data 字段不是对象")
            if ambiguous_after_send:
                raise AmbiguousCommandError(
                    f"{command} 已发出，但响应格式无法确认结果：{error}"
                ) from error
            raise error
        return data

    def verify_backend(self, *, timeout_s: float = 3.0) -> VerifiedEndpoint:
        info = self.request("info", timeout_s=timeout_s)
        actual = str(info.get("backend", ""))
        expected = self.profile.expected_backend
        if actual != expected:
            raise BackendMismatchError(
                f"后端身份不匹配：界面选择 {self.profile.label}/{expected}，"
                f"端点实际为 {actual or 'unknown'}。运动命令已阻止。"
            )
        return VerifiedEndpoint(
            backend=actual,
            control_mode=str(info.get("control_mode", "unknown")),
            info=info,
        )

    def verified_request(
        self,
        command: str,
        args: dict[str, Any] | None = None,
        *,
        timeout_s: float,
        require_running: bool,
        ambiguous_after_send: bool,
    ) -> tuple[dict[str, Any], VerifiedEndpoint]:
        endpoint = self.verify_backend(timeout_s=min(5.0, timeout_s))
        if require_running:
            if endpoint.info.get("faulted"):
                detail = str(endpoint.info.get("fault_message", "")).strip()
                raise ProtocolError(
                    "机械臂控制循环已故障"
                    + (f"：{detail}" if detail else "；请重启控制服务")
                )
            if endpoint.info.get("running") is not True:
                raise ProtocolError("机械臂控制循环未运行；请重启控制服务")
        data = self.request(
            command,
            args,
            timeout_s=timeout_s,
            ambiguous_after_send=ambiguous_after_send,
        )
        return data, endpoint
