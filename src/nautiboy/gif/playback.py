"""Backlog-free LCD GIF playback controller."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .decoder import GifDocument

LCD_KEEPALIVE_MS = 1_000


class Timer(Protocol):
    timeout: object
    def setSingleShot(self, enabled: bool) -> None: ...
    def start(self, milliseconds: int) -> None: ...
    def stop(self) -> None: ...


TimerFactory = Callable[[QObject], Timer]


def _qt_timer(parent: QObject) -> Timer:
    return QTimer(parent)


class GifPlaybackController(QObject):
    """Schedule one frame at a time and coalesce deadlines missed during HID I/O."""

    frame_requested = Signal(int)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        timer_factory: TimerFactory = _qt_timer,
    ) -> None:
        super().__init__(parent)
        self._timer = timer_factory(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._clock = clock
        self._document: GifDocument | None = None
        self._started = 0.0
        self._in_flight = False
        self._last_frame = -1
        self._last_serial = -1
        self._requested_frames = 0
        self._coalesced_frames = 0

    @property
    def active(self) -> bool:
        return self._document is not None

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    @property
    def requested_frames(self) -> int:
        return self._requested_frames

    @property
    def coalesced_frames(self) -> int:
        return self._coalesced_frames

    def start(self, document: GifDocument) -> None:
        self.stop()
        if not document.durations_ms:
            raise ValueError("animation must contain a frame")
        self._document = document
        self._started = self._clock()
        self._request_current_frame()

    def stop(self) -> None:
        self._timer.stop()
        self._document = None
        self._in_flight = False
        self._last_frame = -1
        self._last_serial = -1
        self._requested_frames = 0
        self._coalesced_frames = 0

    def _frame_for_elapsed(self, elapsed_ms: int) -> tuple[int, int, int]:
        assert self._document is not None
        cycle = self._document.duration_ms
        cycle_number = elapsed_ms // cycle
        position = elapsed_ms % cycle
        accumulated = 0
        for index, duration in enumerate(self._document.durations_ms):
            accumulated += duration
            if position < accumulated:
                return index, accumulated - position, cycle_number * self._document.frame_count + index
        return 0, self._document.durations_ms[0], cycle_number * self._document.frame_count

    def _request_current_frame(self) -> None:
        if self._document is None or self._in_flight:
            return
        elapsed = max(0, int((self._clock() - self._started) * 1000))
        index, _remaining, serial = self._frame_for_elapsed(elapsed)
        if self._last_serial >= 0 and serial > self._last_serial + 1:
            self._coalesced_frames += serial - self._last_serial - 1
        self._last_frame = index
        self._last_serial = serial
        self._requested_frames += 1
        self._in_flight = True
        self.frame_requested.emit(index)

    @Slot()
    def _on_timeout(self) -> None:
        self._request_current_frame()

    def transfer_completed(self) -> None:
        if self._document is None:
            return
        self._in_flight = False
        elapsed = max(0, int((self._clock() - self._started) * 1000))
        _index, remaining, _serial = self._frame_for_elapsed(elapsed)
        self._timer.start(max(1, min(remaining, LCD_KEEPALIVE_MS)))
