"""Latest-state-wins scheduling for dynamic Creative compositions."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from nautiboy.gif.decoder import GifDocument
from nautiboy.telemetry.orbit import ORBIT_PERIOD_SECONDS, phase_at

CREATIVE_DYNAMIC_INTERVAL_MS = 100
CREATIVE_TELEMETRY_INTERVAL_MS = 1_000


class CreativePlaybackController(QObject):
    frame_requested = Signal(float, int)

    def __init__(self, parent=None, *, clock: Callable[[], float] = time.monotonic, timer=None):
        super().__init__(parent)
        self._clock = clock
        self._timer = timer or QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._started = 0.0
        self._document: GifDocument | None = None
        self._active = False
        self._in_flight = False
        self._dropped = 0
        self._orbit_animated = False
        self._telemetry_enabled = False
        self._last_signature: tuple[int, int, int] | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def dropped_frames(self) -> int:
        return self._dropped

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    def start(self, document: GifDocument | None, *, orbit_animated: bool, telemetry_enabled: bool) -> None:
        self.stop()
        self._document = document
        self._orbit_animated = orbit_animated
        self._telemetry_enabled = telemetry_enabled
        dynamic = bool(document and document.frame_count > 1) or orbit_animated
        self._timer.setInterval(CREATIVE_DYNAMIC_INTERVAL_MS if dynamic else CREATIVE_TELEMETRY_INTERVAL_MS)
        self._started = self._clock()
        self._active = True
        self._timer.start()
        self._request()

    def stop(self) -> None:
        self._timer.stop()
        self._active = False
        self._in_flight = False
        self._document = None
        self._dropped = 0
        self._last_signature = None

    def _gif_index(self, elapsed_ms: int) -> int:
        if self._document is None:
            return 0
        position = elapsed_ms % self._document.duration_ms
        total = 0
        for index, duration in enumerate(self._document.durations_ms):
            total += duration
            if position < total:
                return index
        return 0

    def _request(self) -> None:
        if not self._active:
            return
        now = self._clock()
        elapsed_ms = max(0, int((now - self._started) * 1000))
        index = self._gif_index(elapsed_ms)
        signature = (
            index,
            elapsed_ms // CREATIVE_DYNAMIC_INTERVAL_MS if self._orbit_animated else 0,
            elapsed_ms // CREATIVE_TELEMETRY_INTERVAL_MS
            if (self._telemetry_enabled or self._document is not None) else 0,
        )
        if signature == self._last_signature:
            return
        if self._in_flight:
            self._dropped += 1
            return
        self._in_flight = True
        self._last_signature = signature
        self.frame_requested.emit(
            phase_at(now, self._started, ORBIT_PERIOD_SECONDS),
            index,
        )

    @Slot()
    def _on_timeout(self) -> None:
        self._request()

    def transfer_completed(self) -> None:
        self._in_flight = False
