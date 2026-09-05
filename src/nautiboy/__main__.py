"""Application entry point."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from .branding import APP_ID, APP_NAME, ORGANIZATION_DOMAIN, application_icon
from .desktop_shortcut import DesktopShortcutError, DesktopShortcutManager
from .gui.main_window import MainWindow
from .gui.tray import TrayController
from .gui.theme import STYLESHEET
from .logging_config import configure_logging
from .single_instance import SingleInstance


@dataclass(slots=True)
class ApplicationRuntime:
    single_instance: SingleInstance
    window: MainWindow
    tray: TrayController


def create_runtime(
    app: QApplication,
    *,
    background: bool,
    single_instance_factory: Callable[..., SingleInstance] = SingleInstance,
    window_factory: Callable[[], MainWindow] = MainWindow,
    tray_factory: Callable[[MainWindow, QApplication], TrayController] = TrayController,
) -> ApplicationRuntime | None:
    """Create hardware-owning objects only after winning single-instance ownership."""
    single_instance = single_instance_factory(parent=app)
    if not single_instance.acquire(activate_existing=not background):
        return None
    window = window_factory()
    tray = tray_factory(window, app)
    single_instance.activated.connect(tray.open_window)
    app.aboutToQuit.connect(single_instance.close)
    if not background:
        window.show()
    return ApplicationRuntime(single_instance, window, tray)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    raw_arguments = list(sys.argv if argv is None else argv)
    create_shortcut = "--create-desktop-shortcut" in raw_arguments[1:]
    remove_shortcut = "--remove-desktop-shortcut" in raw_arguments[1:]
    if create_shortcut or remove_shortcut:
        if create_shortcut and remove_shortcut:
            print("choose only one Desktop shortcut operation", file=sys.stderr)
            return 2
        manager = DesktopShortcutManager()
        try:
            if create_shortcut:
                print(f"Created NautiBoy Desktop shortcut: {manager.create()}")
            elif manager.remove():
                print(f"Removed NautiBoy Desktop shortcut: {manager.path}")
            else:
                print("NautiBoy Desktop shortcut was not present")
        except DesktopShortcutError as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    background = "--background" in raw_arguments[1:]
    qt_arguments = [argument for argument in raw_arguments if argument != "--background"]
    app = QApplication(qt_arguments)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("NautiBoy community")
    app.setOrganizationDomain(ORGANIZATION_DOMAIN)
    desktop_file = QStandardPaths.locate(
        QStandardPaths.StandardLocation.ApplicationsLocation,
        f"{APP_ID}.desktop",
    )
    if desktop_file:
        app.setDesktopFileName(APP_ID)
    app.setWindowIcon(application_icon())
    app.setStyleSheet(STYLESHEET)
    runtime = create_runtime(app, background=background)
    if runtime is None:
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
