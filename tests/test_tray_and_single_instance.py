from __future__ import annotations

import uuid

import pytest
from PySide6.QtCore import QCoreApplication

from nautiboy.gui import main_window
from nautiboy.gui.tray import TrayController
from nautiboy.single_instance import SingleInstance
from nautiboy.branding import application_icon


def window(monkeypatch):
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    return main_window.MainWindow()


def test_window_close_hides_without_restore_or_stopping_playback(monkeypatch) -> None:
    subject = window(monkeypatch)
    subject.enable_close_to_tray()
    subject.show()
    calls = []
    monkeypatch.setattr(subject._refresher, "stop", lambda: calls.append("static-stop"))
    monkeypatch.setattr(subject._gif_playback, "stop", lambda: calls.append("gif-stop"))
    subject.restore_requested.connect(lambda: calls.append("restore"))
    subject.close()
    assert not subject.isVisible()
    assert calls == []
    subject._close_to_tray = False
    subject.close()


def test_tray_open_restores_the_same_window(monkeypatch, qt_application) -> None:
    subject = window(monkeypatch)
    qt_application.setProperty("nautiboyTrayCreated", False)
    controller = TrayController(subject, qt_application)
    assert not controller.icon.icon().isNull()
    assert controller.icon.icon().cacheKey() == application_icon().cacheKey()
    subject.hide()
    controller.open_window()
    assert subject.isVisible()
    assert controller.window is subject
    subject.request_quit()


def test_window_and_tray_share_canonical_icon(monkeypatch, qt_application) -> None:
    subject = window(monkeypatch)
    qt_application.setProperty("nautiboyTrayCreated", False)
    qt_application.setWindowIcon(application_icon())
    controller = TrayController(subject, qt_application)
    assert subject.windowIcon().cacheKey() == controller.icon.icon().cacheKey()
    subject.request_quit()


def test_tray_restore_stops_schedulers_before_restore_and_keeps_running(monkeypatch) -> None:
    subject = window(monkeypatch)
    subject._identity = object()
    subject._session_touched_display = True
    order = []
    monkeypatch.setattr(subject._refresher, "stop", lambda: order.append("static-stop"))
    monkeypatch.setattr(subject._gif_playback, "stop", lambda: order.append("gif-stop"))
    subject.restore_requested.connect(lambda: order.append("restore"))
    subject.restore_hardware_mode()
    assert order == ["static-stop", "gif-stop", "restore"]
    assert not subject._quit_requested
    subject._session_touched_display = False
    subject.close()


def test_actual_quit_stops_worker_thread(monkeypatch) -> None:
    subject = window(monkeypatch)
    ready = []
    subject.shutdown_ready.connect(lambda: ready.append(True))
    assert subject._thread.isRunning()
    subject.request_quit()
    assert ready == [True]
    assert not subject._thread.isRunning()


def test_quit_queues_restore_after_both_schedulers_stop(monkeypatch) -> None:
    subject = window(monkeypatch)
    subject._identity = object()
    subject._session_touched_display = True
    order = []
    monkeypatch.setattr(subject._refresher, "stop", lambda: order.append("static-stop"))
    monkeypatch.setattr(subject._gif_playback, "stop", lambda: order.append("gif-stop"))
    subject.restore_requested.connect(lambda: order.append("restore"))
    subject.request_quit()
    assert order == ["static-stop", "gif-stop", "restore"]
    assert subject._thread.isRunning()
    subject._restored()
    assert not subject._thread.isRunning()


def test_first_hide_notification_is_emitted_once(monkeypatch, qt_application) -> None:
    subject = window(monkeypatch)
    qt_application.setProperty("nautiboyTrayCreated", False)
    controller = TrayController(subject, qt_application)
    notifications = []
    monkeypatch.setattr(controller.icon, "showMessage", lambda *args: notifications.append(args))
    controller._hidden()
    controller._hidden()
    assert len(notifications) == 1
    subject.request_quit()


def test_duplicate_tray_controller_is_rejected(monkeypatch, qt_application) -> None:
    subject = window(monkeypatch)
    qt_application.setProperty("nautiboyTrayCreated", False)
    TrayController(subject, qt_application)
    with pytest.raises(RuntimeError, match="already exists"):
        TrayController(subject, qt_application)
    subject.request_quit()


def test_second_instance_exits_before_creating_an_owner(monkeypatch) -> None:
    secondary = SingleInstance(f"nautiboy-test-{uuid.uuid4().hex}")
    notifications = []
    monkeypatch.setattr(
        secondary,
        "_notify_existing",
        lambda *, activate, timeout_ms=300: notifications.append((activate, timeout_ms)) or True,
    )
    assert not secondary.acquire()
    assert notifications == [(True, 300)]
    assert secondary._server is None
