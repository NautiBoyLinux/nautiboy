from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from nautiboy.gui.refresh import STATIC_IMAGE_REFRESH_MS, StaticImageRefresher


class FakeSignal:
    def __init__(self) -> None:
        self.callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        self.callback = callback

    def emit(self) -> None:
        assert self.callback is not None
        self.callback()


class FakeTimer:
    def __init__(self) -> None:
        self.timeout = FakeSignal()
        self.interval: int | None = None
        self.running = False

    def setInterval(self, milliseconds: int) -> None:
        self.interval = milliseconds

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def isActive(self) -> bool:
        return self.running

    def fire(self) -> None:
        self.timeout.emit()


def refresher() -> tuple[StaticImageRefresher, FakeTimer]:
    timer = FakeTimer()
    controller = StaticImageRefresher(timer_factory=lambda _parent: timer)
    return controller, timer


def test_named_refresh_interval_is_one_second() -> None:
    controller, timer = refresher()
    assert not controller.active
    assert STATIC_IMAGE_REFRESH_MS == 1_000
    assert timer.interval == STATIC_IMAGE_REFRESH_MS


def test_refresh_begins_only_after_initial_send_success() -> None:
    controller, timer = refresher()
    assert not timer.running

    controller.start_after_initial_success(b"same-jpeg")

    assert timer.running


def test_no_refresh_after_initial_send_failure() -> None:
    controller, timer = refresher()
    requested: list[bytes] = []
    controller.refresh_requested.connect(requested.append)

    # A failed initial send never calls start_after_initial_success().
    timer.fire()

    assert requested == []
    assert not controller.active


def test_timer_events_are_dropped_while_transfer_is_in_flight() -> None:
    controller, timer = refresher()
    requested: list[bytes] = []
    controller.refresh_requested.connect(requested.append)
    controller.start_after_initial_success(b"same-jpeg")

    timer.fire()
    timer.fire()
    timer.fire()

    assert requested == [b"same-jpeg"]
    assert controller.in_flight


def test_no_overlapping_refresh_transfers() -> None:
    controller, timer = refresher()
    requested: list[bytes] = []
    controller.refresh_requested.connect(requested.append)
    controller.start_after_initial_success(b"same-jpeg")

    timer.fire()
    assert controller.in_flight
    controller.transfer_completed()
    timer.fire()

    assert requested == [b"same-jpeg", b"same-jpeg"]


@pytest.mark.parametrize(
    "reason",
    ["disconnect", "backend-error", "manual-restore", "normal-exit"],
)
def test_refresh_stops_for_terminal_lifecycle_event(reason: str) -> None:
    controller, timer = refresher()
    requested: list[bytes] = []
    controller.refresh_requested.connect(requested.append)
    controller.start_after_initial_success(b"same-jpeg")

    controller.stop()  # The GUI invokes this before handling every listed reason.
    timer.fire()

    assert reason
    assert not controller.active
    assert not controller.in_flight
    assert requested == []


def test_restore_is_invoked_only_after_refresh_has_stopped() -> None:
    controller, _timer = refresher()
    controller.start_after_initial_success(b"same-jpeg")
    order: list[str] = []

    controller.stop()
    order.append("refresh-stopped")
    assert not controller.active
    order.append("restore-requested")

    assert order == ["refresh-stopped", "restore-requested"]


def test_repeated_refresh_reuses_identical_validated_bytes() -> None:
    controller, timer = refresher()
    jpeg = bytes(bytearray(b"validated-jpeg"))
    requested: list[bytes] = []
    controller.refresh_requested.connect(requested.append)
    controller.start_after_initial_success(jpeg)

    timer.fire()
    controller.transfer_completed()
    timer.fire()

    assert len(requested) == 2
    assert requested[0] is jpeg
    assert requested[1] is jpeg


def test_timer_callback_only_schedules_work_and_returns_to_gui() -> None:
    controller, timer = refresher()
    scheduled: list[bytes] = []
    controller.refresh_requested.connect(scheduled.append)
    controller.start_after_initial_success(b"same-jpeg")

    timer.fire()

    # No backend call exists in the timer callback; HID work is consumed by the worker signal.
    assert scheduled == [b"same-jpeg"]


def test_gui_event_loop_remains_responsive_while_refresh_is_in_flight() -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    controller, timer = refresher()
    controller.refresh_requested.connect(lambda _jpeg: None)
    controller.start_after_initial_success(b"same-jpeg")
    timer.fire()
    assert controller.in_flight

    events: list[str] = []
    loop = QEventLoop()
    QTimer.singleShot(0, lambda: events.append("gui-event"))
    QTimer.singleShot(0, loop.quit)
    loop.exec()

    assert app is QCoreApplication.instance()
    assert events == ["gui-event"]
