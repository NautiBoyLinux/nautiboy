"""Application-level state independent of Qt widgets and USB details."""

from __future__ import annotations

from enum import Enum


class AppState(str, Enum):
    DISCONNECTED = "disconnected"
    READY = "ready"
    SENDING = "sending"
    DISPLAYING = "displaying"
    RESTORING = "restoring"
    ERROR = "error"


BUSY_STATES = frozenset({AppState.SENDING, AppState.RESTORING})
