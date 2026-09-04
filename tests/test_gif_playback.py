from __future__ import annotations

from dataclasses import dataclass

from nautiboy.gif.decoder import GifDocument
from nautiboy.gif.playback import LCD_KEEPALIVE_MS, GifPlaybackController


class Signal:
    def __init__(self) -> None:
        self.callback = None
    def connect(self, callback):
        self.callback = callback
    def emit(self):
        self.callback()


class Timer:
    def __init__(self) -> None:
        self.timeout = Signal()
        self.delay = None
        self.running = False
    def setSingleShot(self, enabled: bool) -> None:
        assert enabled
    def start(self, milliseconds: int) -> None:
        self.delay = milliseconds
        self.running = True
    def stop(self) -> None:
        self.running = False
    def fire(self) -> None:
        self.running = False
        self.timeout.emit()


@dataclass
class Clock:
    value: float = 0
    def __call__(self) -> float:
        return self.value


def document(durations=(100, 100, 100)) -> GifDocument:
    return GifDocument(b"data", 10, 10, tuple(durations), 0)


def controller():
    timer = Timer()
    clock = Clock()
    playback = GifPlaybackController(clock=clock, timer_factory=lambda _parent: timer)
    return playback, timer, clock


def test_start_requests_exactly_one_frame_and_guards_overlap() -> None:
    playback, timer, _clock = controller()
    requested = []
    playback.frame_requested.connect(requested.append)
    playback.start(document())
    assert requested == [0] and playback.in_flight
    playback._on_timeout()
    assert requested == [0]


def test_missed_deadlines_coalesce_to_current_frame() -> None:
    playback, timer, clock = controller()
    requested = []
    playback.frame_requested.connect(requested.append)
    playback.start(document())
    clock.value = 0.250
    playback.transfer_completed()
    timer.fire()
    assert requested == [0, 2]
    assert playback.coalesced_frames == 1
    assert playback.requested_frames == 2


def test_long_frame_uses_one_second_keepalive() -> None:
    playback, timer, _clock = controller()
    playback.frame_requested.connect(lambda _index: None)
    playback.start(document((5000,)))
    playback.transfer_completed()
    assert timer.delay == LCD_KEEPALIVE_MS


def test_short_frame_uses_remaining_deadline() -> None:
    playback, timer, clock = controller()
    playback.frame_requested.connect(lambda _index: None)
    playback.start(document((250, 250)))
    clock.value = 0.050
    playback.transfer_completed()
    assert timer.delay == 200


def test_stop_cancels_timer_and_future_requests() -> None:
    playback, timer, _clock = controller()
    requested = []
    playback.frame_requested.connect(requested.append)
    playback.start(document())
    playback.transfer_completed()
    playback.stop()
    timer.fire()
    assert requested == [0]
    assert not playback.active and not playback.in_flight


def test_restore_order_can_stop_before_hardware_restore() -> None:
    playback, _timer, _clock = controller()
    playback.frame_requested.connect(lambda _index: None)
    playback.start(document())
    order = []
    playback.stop()
    order.append("playback-stopped")
    order.append("restore-requested")
    assert order == ["playback-stopped", "restore-requested"]
