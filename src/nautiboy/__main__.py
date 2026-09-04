"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .branding import APP_ID, APP_NAME, asset_path
from .gui.main_window import MainWindow
from .gui.theme import STYLESHEET
from .logging_config import configure_logging


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("NautiBoy community")
    app.setOrganizationDomain("io.github.nautiboy")
    desktop_file = QStandardPaths.locate(
        QStandardPaths.StandardLocation.ApplicationsLocation,
        f"{APP_ID}.desktop",
    )
    if desktop_file:
        app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon(str(asset_path("nautiboy-icon-development-source.png"))))
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
