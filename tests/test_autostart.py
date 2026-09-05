from __future__ import annotations

from pathlib import Path

import pytest

import nautiboy.autostart as autostart
from nautiboy.__main__ import create_runtime
from nautiboy.autostart import AutostartError, AutostartManager, UserPreferences


def test_enable_creates_only_expected_per_user_entry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    unrelated = tmp_path / "autostart" / "other.desktop"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("unrelated")
    manager = AutostartManager()
    manager.enable(background=True)
    assert manager.path == tmp_path / "autostart" / autostart.AUTOSTART_FILENAME
    assert "Exec=nautiboy --background" in manager.path.read_text()
    assert unrelated.read_text() == "unrelated"


def test_disable_removes_only_nautiboy_entry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    manager = AutostartManager()
    manager.enable()
    unrelated = manager.path.parent / "other.desktop"
    unrelated.write_text("keep")
    manager.disable()
    assert not manager.path.exists()
    assert unrelated.read_text() == "keep"


def test_owned_legacy_autostart_is_migrated_without_touching_unrelated(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    manager = AutostartManager()
    legacy = manager.path.parent / autostart.LEGACY_AUTOSTART_FILENAMES[0]
    legacy.parent.mkdir(parents=True)
    legacy.write_text(autostart.desktop_entry(background=True))
    unrelated = legacy.parent / "other.desktop"
    unrelated.write_text("unrelated")

    assert manager.migrate_legacy()
    assert manager.enabled()
    assert not legacy.exists()
    assert unrelated.read_text() == "unrelated"


def test_unowned_legacy_autostart_is_left_untouched(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    manager = AutostartManager()
    legacy = manager.path.parent / autostart.LEGACY_AUTOSTART_FILENAMES[0]
    legacy.parent.mkdir(parents=True)
    legacy.write_text("unrelated")
    assert not manager.migrate_legacy()
    assert legacy.read_text() == "unrelated"


def test_xdg_config_home_and_default_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert autostart.config_home() == tmp_path
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert autostart.config_home() == Path.home() / ".config"


def test_state_reflects_actual_entry_and_manual_removal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    manager = AutostartManager()
    assert not manager.enabled()
    manager.enable()
    assert manager.enabled()
    manager.path.unlink()
    assert not manager.enabled()


def test_malformed_entry_is_not_reported_enabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    manager = AutostartManager()
    manager.path.parent.mkdir(parents=True)
    manager.path.write_text("not a desktop entry")
    assert not manager.enabled()


def test_unwritable_shape_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(blocker))
    with pytest.raises(AutostartError, match="cannot enable"):
        AutostartManager().enable()


def test_minimized_preference_defaults_on_and_round_trips(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    preferences = UserPreferences()
    assert preferences.start_minimized()
    preferences.set_start_minimized(False)
    assert not preferences.start_minimized()


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []
    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class FakeSingleInstance:
    def __init__(self, *, parent, owner=True) -> None:
        self.parent = parent
        self.owner = owner
        self.activated = FakeSignal()
        self.acquire_arguments = []
    def acquire(self, *, activate_existing: bool) -> bool:
        self.acquire_arguments.append(activate_existing)
        return self.owner
    def close(self) -> None:
        pass


class FakeWindow:
    def __init__(self) -> None:
        self.shown = False
        self.session_touched = False
    def show(self) -> None:
        self.shown = True


class FakeTray:
    def __init__(self, window, app) -> None:
        self.window = window
        self.app = app
    def open_window(self) -> None:
        self.window.show()


def test_background_primary_creates_tray_but_starts_hidden(qt_application) -> None:
    single = FakeSingleInstance(parent=qt_application)
    runtime = create_runtime(
        qt_application,
        background=True,
        single_instance_factory=lambda **_kwargs: single,
        window_factory=FakeWindow,
        tray_factory=FakeTray,
    )
    assert runtime is not None
    assert not runtime.window.shown
    assert isinstance(runtime.tray, FakeTray)
    assert not runtime.window.session_touched
    assert single.acquire_arguments == [False]


def test_manual_primary_shows_window(qt_application) -> None:
    single = FakeSingleInstance(parent=qt_application)
    runtime = create_runtime(
        qt_application,
        background=False,
        single_instance_factory=lambda **_kwargs: single,
        window_factory=FakeWindow,
        tray_factory=FakeTray,
    )
    assert runtime is not None and runtime.window.shown
    assert single.acquire_arguments == [True]


@pytest.mark.parametrize("background, expected_activate", [(True, False), (False, True)])
def test_secondary_never_constructs_hid_owner(
    qt_application, background: bool, expected_activate: bool
) -> None:
    single = FakeSingleInstance(parent=qt_application, owner=False)
    constructed = []
    runtime = create_runtime(
        qt_application,
        background=background,
        single_instance_factory=lambda **_kwargs: single,
        window_factory=lambda: constructed.append(True),
        tray_factory=FakeTray,
    )
    assert runtime is None
    assert constructed == []
    assert single.acquire_arguments == [expected_activate]
