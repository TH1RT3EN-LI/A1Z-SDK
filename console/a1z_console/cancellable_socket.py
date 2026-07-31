"""Cooperative cancellation for one active blocking socket request."""

from __future__ import annotations

import ipaddress
import socket
import threading
import time
from queue import Empty, Queue


_DNS_RESOLVER_SLOT = threading.BoundedSemaphore(1)


class SocketRequestCancelledError(OSError):
    """A request socket was closed by its lifecycle owner."""


class CancellableSocket:
    """Own at most one socket and make connect/recv interruptible on shutdown."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: socket.socket | None = None
        self._cancelled = False

    def open_connection(
        self,
        host: str,
        port: int,
        *,
        timeout_s: float,
    ) -> socket.socket:
        timeout = max(0.001, float(timeout_s))
        deadline = time.monotonic() + timeout
        addresses = self._resolve_addresses(host, int(port), deadline=deadline)
        last_error: OSError | None = None

        for family, sock_type, protocol, _name, address in addresses:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise TimeoutError("socket connection timed out")
            candidate = socket.socket(family, sock_type, protocol)
            candidate.settimeout(remaining)
            with self._lock:
                if self._cancelled:
                    candidate.close()
                    raise SocketRequestCancelledError(
                        "socket request was cancelled"
                    )
                if self._active is not None:
                    candidate.close()
                    raise RuntimeError(
                        "CancellableSocket already owns an active request"
                    )
                self._active = candidate
            try:
                candidate.connect(address)
                candidate.settimeout(timeout)
                return candidate
            except OSError as exc:
                last_error = exc
                self.release(candidate)
                with self._lock:
                    if self._cancelled:
                        raise SocketRequestCancelledError(
                            "socket request was cancelled"
                        ) from exc

        if last_error is not None:
            raise last_error
        raise OSError(f"no socket address resolved for {host}:{port}")

    def _resolve_addresses(
        self,
        host: str,
        port: int,
        *,
        deadline: float,
    ) -> list[tuple[int, int, int, str, tuple[object, ...]]]:
        """Resolve without letting a stuck NSS lookup pin the owning worker."""

        try:
            ipaddress.ip_address(host)
        except ValueError:
            numeric_host = False
        else:
            numeric_host = True

        if numeric_host:
            return socket.getaddrinfo(
                host,
                port,
                type=socket.SOCK_STREAM,
                flags=socket.AI_NUMERICHOST,
            )

        while True:
            with self._lock:
                if self._cancelled:
                    raise SocketRequestCancelledError(
                        "socket request was cancelled"
                    )
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise TimeoutError("socket name resolution timed out")
            if _DNS_RESOLVER_SLOT.acquire(timeout=min(0.05, remaining)):
                break

        with self._lock:
            cancelled_after_claim = self._cancelled
        if cancelled_after_claim:
            _DNS_RESOLVER_SLOT.release()
            raise SocketRequestCancelledError("socket request was cancelled")

        result_queue: Queue[
            tuple[
                list[tuple[int, int, int, str, tuple[object, ...]]] | None,
                BaseException | None,
            ]
        ] = Queue(maxsize=1)

        def resolve() -> None:
            try:
                result_queue.put(
                    (
                        socket.getaddrinfo(
                            host,
                            port,
                            type=socket.SOCK_STREAM,
                        ),
                        None,
                    )
                )
            except BaseException as exc:
                result_queue.put((None, exc))
            finally:
                _DNS_RESOLVER_SLOT.release()

        try:
            threading.Thread(
                target=resolve,
                name="a1z-console-dns-resolver",
                daemon=True,
            ).start()
        except BaseException:
            _DNS_RESOLVER_SLOT.release()
            raise
        while True:
            with self._lock:
                if self._cancelled:
                    raise SocketRequestCancelledError(
                        "socket request was cancelled"
                    )
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise TimeoutError("socket name resolution timed out")
            try:
                addresses, error = result_queue.get(
                    timeout=min(0.05, remaining)
                )
            except Empty:
                continue
            if error is not None:
                raise error
            if addresses is None:
                raise OSError(f"no socket address resolved for {host}:{port}")
            return addresses

    def release(self, active_socket: socket.socket) -> None:
        with self._lock:
            if self._active is active_socket:
                self._active = None
        try:
            active_socket.close()
        except OSError:
            pass

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            active_socket = self._active
            self._active = None
        if active_socket is None:
            return
        try:
            active_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            active_socket.close()
        except OSError:
            pass
