"""Public API for the A1Z Control SDK.

Only symbols exported here are considered stable.  Hardware drivers and the
official Galaxea package remain behind the local control service boundary.
"""

from .client import A1ZClient
from .errors import (
    A1ZCommandError,
    A1ZCommandRejected,
    A1ZCommandSuperseded,
    A1ZCommandUnverified,
    A1ZConnectionError,
    A1ZError,
    A1ZProtocolError,
)
from .models import CommandResult, Completion, ControlMode, Endpoint, JointState

__all__ = [
    "A1ZClient",
    "A1ZCommandError",
    "A1ZCommandRejected",
    "A1ZCommandSuperseded",
    "A1ZCommandUnverified",
    "A1ZConnectionError",
    "A1ZError",
    "A1ZProtocolError",
    "CommandResult",
    "Completion",
    "ControlMode",
    "Endpoint",
    "JointState",
]

__version__ = "0.1.0"
