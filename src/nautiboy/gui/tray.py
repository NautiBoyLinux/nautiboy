"""System-tray ownership and actions."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from nautiboy.branding import APP_NAME, application_icon


class TrayController:
    def __init__(self, window, app: QApplication) -> None:
        if app.property("nautiboyTrayCreated"):
            raise RuntimeError("NautiBoy tray icon already exists")
        app.setProperty("nautiboyTrayCreated", True)
        self.window = window
        self.app = app
        self._notified = False
        self.icon = QSystemTrayIcon(application_icon(), app)
        self.icon.setToolTip(APP_NAME)
        menu = QMenu()
        title = QAction(APP_NAME, menu)
        title.setEnabled(False)
        self.status = QAction("Status: Hardware mode", menu)
        self.status.setEnabled(False)
        self.open_action = menu.addAction("Open NautiBoy")
        self.restore_action = menu.addAction("Restore Hardware Mode")
        self.quit_action = menu.addAction("Quit NautiBoy")
        menu.insertAction(self.open_action, self.status)
        menu.insertAction(self.status, title)
        menu.insertSeparator(self.open_action)
        self.icon.setContextMenu(menu)
        self.open_action.triggered.connect(self.open_window)
        self.restore_action.triggered.connect(window.restore_hardware_mode)
        self.quit_action.triggered.connect(window.request_quit)
        self.icon.activated.connect(self._activated)
        window.hidden_to_tray.connect(self._hidden)
        window.tray_status_changed.connect(self.set_status)
        window.shutdown_ready.connect(self._shutdown_ready)
        window.enable_close_to_tray()
        self.set_status(window.playback_status())
        self.icon.show()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick}:
            self.open_window()

    def open_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _hidden(self) -> None:
        if self._notified:
            return
        self._notified = True
        self.icon.showMessage(
            APP_NAME,
            "NautiBoy is still running in the background. LCD playback will continue.",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def set_status(self, status: str) -> None:
        self.status.setText(f"Status: {status}")
        self.restore_action.setEnabled(
            status in {"GIF playing", "Thermals playing", "Static image", "Volatile display active"}
        )

    def _shutdown_ready(self) -> None:
        self.icon.hide()
        self.icon.setContextMenu(None)
        self.app.setProperty("nautiboyTrayCreated", False)
        self.app.quit()
