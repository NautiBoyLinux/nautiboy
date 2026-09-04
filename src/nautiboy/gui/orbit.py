"""Backlog-free, time-based Orbit LCD scheduling."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from nautiboy.telemetry.orbit import ORBIT_PERIOD_SECONDS, phase_at

ORBIT_LCD_INTERVAL_MS = 100
ORBIT_PREVIEW_INTERVAL_MS = 100


class OrbitPlaybackController(QObject):
    frame_requested = Signal(float)

    def __init__(self, parent=None, *, clock: Callable[[], float] = time.monotonic, timer=None):
        super().__init__(parent)
        self._clock = clock
        self._timer = timer or QTimer(self)
        self._timer.setInterval(ORBIT_LCD_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timeout)
        self._started = 0.0
        self._active = False
        self._in_flight = False
        self._dropped = 0
        self._completed = 0

    @property
    def active(self):
        return self._active

    @property
    def in_flight(self):
        return self._in_flight

    @property
    def dropped_frames(self):
        return self._dropped

    @property
    def completed_frames(self):
        return self._completed

    def start(self):
        self.stop()
        self._active = True
        self._started = self._clock()
        self._timer.start()
        self._request()

    @Slot()
    def _on_timeout(self):
        if self._in_flight:
            self._dropped += 1
            return
        self._request()

    def _request(self):
        if not self._active or self._in_flight:
            return
        self._in_flight = True
        self.frame_requested.emit(phase_at(self._clock(), self._started, ORBIT_PERIOD_SECONDS))

    def transfer_completed(self):
        self._in_flight = False
        self._completed += 1

    def stop(self):
        self._timer.stop()
        self._active = False
        self._in_flight = False
        self._dropped = 0
        self._completed = 0
