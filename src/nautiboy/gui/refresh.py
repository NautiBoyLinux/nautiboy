"""Bounded scheduling for a single volatile static LCD image."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Signal, Slot

STATIC_IMAGE_REFRESH_MS = 1_000


class Timer(Protocol):
    timeout: object

    def setInterval(self, milliseconds: int) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def isActive(self) -> bool: ...


TimerFactory = Callable[[QObject], Timer]


def _qt_timer(parent: QObject) -> Timer:
    return QTimer(parent)


class StaticImageRefresher(QObject):
    """Emit at most one refresh request until that request completes."""

    refresh_requested = Signal(bytes)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        timer_factory: TimerFactory = _qt_timer,
    ) -> None:
        super().__init__(parent)
        self._timer = timer_factory(self)
        self._timer.setInterval(STATIC_IMAGE_REFRESH_MS)
        self._timer.timeout.connect(self._on_timeout)  # type: ignore[attr-defined]
        self._jpeg: bytes | None = None
        self._in_flight = False

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    def start_after_initial_success(self, jpeg: bytes) -> None:
        if not isinstance(jpeg, bytes) or not jpeg:
            raise ValueError("refresh image must be non-empty bytes")
        self.stop()
        self._jpeg = jpeg
        self._timer.start()

    @Slot()
    def _on_timeout(self) -> None:
        if not self.active or self._in_flight or self._jpeg is None:
            return
        self._in_flight = True
        self.refresh_requested.emit(self._jpeg)

    def transfer_completed(self) -> None:
        self._in_flight = False

    def stop(self) -> None:
        self._timer.stop()
        self._in_flight = False
        self._jpeg = None
