"""Structured errors raised by the public SDK."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class A1ZError(RuntimeError):
    """Base class for all public SDK errors."""


class A1ZConnectionError(A1ZError):
    """The control service could not be reached."""


class A1ZProtocolError(A1ZError):
    """The control service returned an invalid wire response."""


class A1ZCommandError(A1ZError):
    """A command was not completed successfully.

    ``execution_state`` deliberately distinguishes a command rejected before
    motion from a command that was submitted but could not be verified from
    feedback.  Callers must not collapse those two safety-relevant outcomes.
    """

    def __init__(
        self,
        message: str,
        *,
        command: str,
        execution_state: str,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.execution_state = execution_state
        self.data = dict(data or {})


class A1ZCommandRejected(A1ZCommandError):
    """The service rejected a command before it was executed."""


class A1ZCommandUnverified(A1ZCommandError):
    """A command may have moved hardware but feedback did not verify it."""


class A1ZCommandSuperseded(A1ZCommandError):
    """A valid newer target intentionally replaced this command."""
