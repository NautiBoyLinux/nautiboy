"""Per-user XDG graphical-session autostart ownership."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from .branding import APP_ID, APP_NAME, LEGACY_APP_IDS

AUTOSTART_FILENAME = f"{APP_ID}.desktop"
LEGACY_AUTOSTART_FILENAMES = tuple(f"{app_id}.desktop" for app_id in LEGACY_APP_IDS)
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

    def _legacy_paths(self) -> tuple[Path, ...]:
        return tuple(self.path.parent / filename for filename in LEGACY_AUTOSTART_FILENAMES)

    @staticmethod
    def _owned(path: Path) -> bool:
        try:
            return "X-NautiBoy-Autostart=true\n" in path.read_text(encoding="utf-8")
        except OSError:
            return False

    def _remove_owned_legacy_entries(self) -> None:
        for path in self._legacy_paths():
            if self._owned(path):
                path.unlink(missing_ok=True)

    def migrate_legacy(self) -> bool:
        """Rename an owned development autostart entry without touching others."""
        if self.path.exists():
            try:
                self._remove_owned_legacy_entries()
            except OSError as error:
                raise AutostartError(f"cannot migrate autostart: {error}") from error
            return False
        for path in self._legacy_paths():
            if not self._owned(path):
                continue
            try:
                background = "Exec=nautiboy --background\n" in path.read_text(encoding="utf-8")
                self.enable(background=background)
            except OSError as error:
                raise AutostartError(f"cannot migrate autostart: {error}") from error
            return True
        return False

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
            self._remove_owned_legacy_entries()
        except OSError as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise AutostartError(f"cannot enable autostart: {error}") from error

    def disable(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
            self._remove_owned_legacy_entries()
        except OSError as error:
            raise AutostartError(f"cannot disable autostart: {error}") from error


class UserPreferences:
    """Small atomic user preference document; autostart state itself is not cached."""

    @staticmethod
    def _read() -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        try:
            parser.read(settings_path(), encoding="utf-8")
        except (OSError, configparser.Error, ValueError):
            return configparser.ConfigParser()
        return parser

    @staticmethod
    def _write(parser: configparser.ConfigParser) -> None:
        path = settings_path()
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8") as stream:
                parser.write(stream)
            temporary.chmod(0o600)
            temporary.replace(path)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise AutostartError(f"cannot save preference: {error}") from error

    def start_minimized(self) -> bool:
        try:
            return self._read().getboolean("autostart", "start_minimized", fallback=True)
        except ValueError:
            return True

    def set_start_minimized(self, enabled: bool) -> None:
        parser = self._read()
        if not parser.has_section("autostart"):
            parser.add_section("autostart")
        parser.set("autostart", "start_minimized", "true" if enabled else "false")
        self._write(parser)

    def resume_last_display(self) -> bool:
        try:
            return self._read().getboolean("display", "resume_last_display", fallback=False)
        except ValueError:
            return False

    def set_resume_last_display(self, enabled: bool) -> None:
        parser = self._read()
        if not parser.has_section("display"):
            parser.add_section("display")
        parser.set("display", "resume_last_display", "true" if enabled else "false")
        self._write(parser)
