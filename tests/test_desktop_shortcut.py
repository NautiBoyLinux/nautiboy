from __future__ import annotations

from pathlib import Path

import pytest

import nautiboy.desktop_shortcut as shortcut
from nautiboy.__main__ import main
from nautiboy.desktop_shortcut import (
    DesktopShortcutError,
    DesktopShortcutManager,
    OWNERSHIP_MARKER,
    is_executable_by_user,
)


@pytest.fixture
def shortcut_locations(tmp_path: Path, monkeypatch):
    applications = tmp_path / "applications"
    desktop = tmp_path / "Actual Desktop"
    applications.mkdir()
    desktop.mkdir()
    source = applications / shortcut.SHORTCUT_FILENAME
    source.write_text("[Desktop Entry]\nType=Application\nExec=nautiboy\n")
    monkeypatch.setattr(shortcut, "desktop_directory", lambda: desktop)
    monkeypatch.setattr(shortcut, "installed_desktop_entry", lambda: source)
    return desktop, source


def test_create_uses_xdg_location_and_marks_executable(shortcut_locations) -> None:
    desktop, _source = shortcut_locations
    path = DesktopShortcutManager().create()
    assert path == desktop / shortcut.SHORTCUT_FILENAME
    assert OWNERSHIP_MARKER in path.read_text()
    assert is_executable_by_user(path)


def test_remove_deletes_only_owned_shortcut(shortcut_locations) -> None:
    path = DesktopShortcutManager().create()
    assert DesktopShortcutManager().remove()
    assert not path.exists()
    assert not DesktopShortcutManager().remove()


def test_create_and_remove_refuse_unowned_file(shortcut_locations) -> None:
    desktop, _source = shortcut_locations
    path = desktop / shortcut.SHORTCUT_FILENAME
    path.write_text("unrelated")
    with pytest.raises(DesktopShortcutError, match="unowned"):
        DesktopShortcutManager().create()
    with pytest.raises(DesktopShortcutError, match="unowned"):
        DesktopShortcutManager().remove()
    assert path.read_text() == "unrelated"


def test_missing_desktop_or_installed_entry_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(shortcut.QStandardPaths, "writableLocation", lambda *_args: "")
    with pytest.raises(DesktopShortcutError, match="XDG Desktop"):
        shortcut.desktop_directory()
    monkeypatch.setattr(shortcut.QStandardPaths, "locate", lambda *_args: "")
    with pytest.raises(DesktopShortcutError, match="could not be found"):
        shortcut.installed_desktop_entry()


def test_cli_shortcut_actions_do_not_start_gui(shortcut_locations, monkeypatch, capsys) -> None:
    started = []
    monkeypatch.setattr("nautiboy.__main__.QApplication", lambda *_args: started.append(True))
    assert main(["nautiboy", "--create-desktop-shortcut"]) == 0
    assert "Created" in capsys.readouterr().out
    assert main(["nautiboy", "--remove-desktop-shortcut"]) == 0
    assert "Removed" in capsys.readouterr().out
    assert started == []


def test_cli_rejects_conflicting_shortcut_actions(capsys) -> None:
    assert main(["nautiboy", "--create-desktop-shortcut", "--remove-desktop-shortcut"]) == 2
    assert "only one" in capsys.readouterr().err
