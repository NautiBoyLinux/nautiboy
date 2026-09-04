"""Explicit, user-owned XDG Desktop shortcut management."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from .branding import APP_ID

SHORTCUT_FILENAME = f"{APP_ID}.desktop"
OWNERSHIP_MARKER = "X-NautiBoy-DesktopShortcut=true"


class DesktopShortcutError(RuntimeError):
    pass


def desktop_directory() -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    if not location:
        raise DesktopShortcutError("the desktop environment did not provide an XDG Desktop directory")
    path = Path(location)
    if not path.is_dir():
        raise DesktopShortcutError(f"the XDG Desktop directory does not exist: {path}")
    return path


def installed_desktop_entry() -> Path:
    location = QStandardPaths.locate(
        QStandardPaths.StandardLocation.ApplicationsLocation,
        f"{APP_ID}.desktop",
    )
    if not location:
        raise DesktopShortcutError("the installed NautiBoy desktop entry could not be found")
    return Path(location)


class DesktopShortcutManager:
    @property
    def path(self) -> Path:
        return desktop_directory() / SHORTCUT_FILENAME

    def create(self) -> Path:
        source = installed_desktop_entry()
        destination = self.path
        temporary: Path | None = None
        try:
            if destination.exists() and OWNERSHIP_MARKER not in destination.read_text(encoding="utf-8"):
                raise DesktopShortcutError(f"refusing to replace an unowned shortcut: {destination}")
            content = source.read_text(encoding="utf-8").rstrip() + f"\n{OWNERSHIP_MARKER}\n"
            descriptor, temporary_name = tempfile.mkstemp(
                dir=destination.parent,
                prefix=f".{destination.name}.",
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
            temporary.chmod(0o755)
            temporary.replace(destination)
            return destination
        except DesktopShortcutError:
            raise
        except OSError as error:
            raise DesktopShortcutError(f"cannot create Desktop shortcut: {error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def remove(self) -> bool:
        destination = self.path
        if not destination.exists():
            return False
        try:
            if OWNERSHIP_MARKER not in destination.read_text(encoding="utf-8"):
                raise DesktopShortcutError(f"refusing to remove an unowned shortcut: {destination}")
            destination.unlink()
            return True
        except DesktopShortcutError:
            raise
        except OSError as error:
            raise DesktopShortcutError(f"cannot remove Desktop shortcut: {error}") from error


def is_executable_by_user(path: Path) -> bool:
    """Expose the launchability condition for documentation and tests."""
    return os.access(path, os.X_OK)
