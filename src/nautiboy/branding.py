"""Public application identity and bundled asset locations."""

from pathlib import Path
from functools import lru_cache

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

APP_NAME = "NautiBoy"
APP_ID = "io.github.nautiboylinux.nautiboy"
ORGANIZATION_DOMAIN = "io.github.nautiboylinux"
LEGACY_APP_IDS = ("io.github.nautiboy.nautiboy",)
PROJECT_URL = "https://github.com/NautiBoyLinux/nautiboy"
ISSUES_URL = f"{PROJECT_URL}/issues"
APP_DESCRIPTION = "NautiBoy is an open-source Linux controller for Corsair NAUTILUS RS LCD displays."
DISCLAIMER = (
    "NautiBoy is an unofficial community project and is not affiliated with, "
    "endorsed by, or supported by Corsair."
)


def asset_path(name: str) -> Path:
    return Path(__file__).with_name("assets") / name


def application_icon_paths() -> tuple[Path, ...]:
    """Bundled icon sources, ordered for small tray slots through large windows."""
    return (
        asset_path("nautiboy-icon-32.png"),
        asset_path("nautiboy-icon-48.png"),
        asset_path("nautiboy-icon-1024.png"),
    )


@lru_cache(maxsize=1)
def application_icon() -> QIcon:
    """Canonical bundled icon used without relying on desktop installation."""
    icon = QIcon()
    for path, size in zip(application_icon_paths(), (32, 48, 1024), strict=True):
        icon.addFile(str(path), QSize(size, size))
    return icon
