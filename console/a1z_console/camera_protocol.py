"""Profile-isolated client for the ROS RGB-D console bridge."""

from __future__ import annotations

import json
import socket
from typing import Any

from .profiles import RuntimeProfile


class CameraProtocolError(RuntimeError):
    """The camera bridge could not be reached or returned invalid data."""


class CameraProfileMismatchError(CameraProtocolError):
    """A camera bridge answered on the endpoint for another runtime profile."""


def _read_json_line(
    sock: socket.socket,
    *,
    limit: int = 8 * 1024 * 1024,
) -> dict[str, Any]:
    data = bytearray()
    while b"\n" not in data:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > limit:
            raise CameraProtocolError("相机桥响应超过 8 MiB 上限")
    if not data:
        raise CameraProtocolError("相机桥未返回响应")
    try:
        payload = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CameraProtocolError(f"相机桥返回了无效 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise CameraProtocolError(
            f"相机桥响应类型错误：{type(payload).__name__}"
        )
    return payload


class CameraProtocolClient:
    def __init__(self, profile: RuntimeProfile) -> None:
        self.profile = profile

    def request(
        self,
        command: str,
        args: dict[str, Any] | None = None,
        *,
        timeout_s: float = 3.0,
    ) -> dict[str, Any]:
        if self.profile.camera_port <= 0:
            raise CameraProtocolError(
                f"{self.profile.label}配置没有有效的相机桥端口"
            )
        request = (
            json.dumps({"cmd": command, "args": args or {}}, ensure_ascii=True)
            + "\n"
        ).encode("utf-8")
        try:
            sock = socket.create_connection(
                (self.profile.camera_host, self.profile.camera_port),
                timeout=float(timeout_s),
            )
        except OSError as exc:
            raise CameraProtocolError(
                "无法连接相机桥 "
                f"{self.profile.camera_host}:{self.profile.camera_port}：{exc}"
            ) from exc

        try:
            sock.settimeout(float(timeout_s))
            sock.sendall(request)
            payload = _read_json_line(sock)
        except (TimeoutError, socket.timeout, EOFError, ConnectionError, OSError) as exc:
            raise CameraProtocolError(f"{command} 请求失败：{exc}") from exc
        finally:
            sock.close()

        if not payload.get("ok"):
            raise CameraProtocolError(
                str(payload.get("error", "相机桥返回未知错误"))
            )
        data = payload.get("data", {})
        if not isinstance(data, dict):
            raise CameraProtocolError(f"{command} 的 data 字段不是对象")
        actual_profile = str(data.get("profile", ""))
        if actual_profile != self.profile.name:
            raise CameraProfileMismatchError(
                f"相机桥配置不匹配：期望 {self.profile.name}，"
                f"实际 {actual_profile or 'unknown'}"
            )
        return data
