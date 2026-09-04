"""Per-user XDG graphical-session autostart ownership."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from .branding import APP_ID, APP_NAME

AUTOSTART_FILENAME = f"{APP_ID}.desktop"
SETTINGS_FILENAME = "settings.ini"


class AutostartError(RuntimeError):
    pass


def config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured else Path.home() / ".config"


def autostart_path() -> Path:
    return config_home() / "autostart" / AUTOSTART_FILENAME


def settings_path() -> Path:
    return config_home() / "nautiboy" / SETTINGS_FILENAME


def desktop_entry(*, background: bool) -> str:
    command = "nautiboy --background" if background else "nautiboy"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec={command}\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "NoDisplay=true\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-NautiBoy-Autostart=true\n"
    )


class AutostartManager:
    @property
    def path(self) -> Path:
        return autostart_path()

    def enabled(self) -> bool:
        try:
            content = self.path.read_text(encoding="utf-8")
        except OSError:
            return False
        return (
            content.startswith("[Desktop Entry]\n")
            and "X-NautiBoy-Autostart=true\n" in content
            and ("Exec=nautiboy --background\n" in content or "Exec=nautiboy\n" in content)
        )

    def entry_starts_in_background(self) -> bool | None:
        if not self.enabled():
            return None
        try:
            return "Exec=nautiboy --background\n" in self.path.read_text(encoding="utf-8")
        except OSError:
            return None

    def enable(self, *, background: bool = True) -> None:
        path = self.path
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(desktop_entry(background=background), encoding="utf-8")
            temporary.chmod(0o644)
            temporary.replace(path)
        except OSError as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise AutostartError(f"cannot enable autostart: {error}") from error

    def disable(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as error:
            raise AutostartError(f"cannot disable autostart: {error}") from error


class UserPreferences:
    """Store only the background-start preference; autostart state is not cached."""

    def start_minimized(self) -> bool:
        path = settings_path()
        parser = configparser.ConfigParser()
        try:
            parser.read(path, encoding="utf-8")
            return parser.getboolean("autostart", "start_minimized", fallback=True)
        except (OSError, configparser.Error, ValueError):
            return True

    def set_start_minimized(self, enabled: bool) -> None:
        path = settings_path()
        temporary = path.with_name(f".{path.name}.tmp")
        parser = configparser.ConfigParser()
        parser["autostart"] = {"start_minimized": "true" if enabled else "false"}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8") as stream:
                parser.write(stream)
            temporary.chmod(0o600)
            temporary.replace(path)
        except OSError as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise AutostartError(f"cannot save preference: {error}") from error
