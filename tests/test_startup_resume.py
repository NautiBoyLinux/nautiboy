from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from nautiboy.autostart import UserPreferences
from nautiboy.gui import main_window
from nautiboy.last_active import LastActiveDisplay, LastActiveDisplayStore
from nautiboy.profiles import ProfileStore
from nautiboy.selected_media import SelectedGiphyMedia, SelectedMediaStore


def _gif(color="purple") -> bytes:
    frames = [Image.new("RGB", (20, 20), color), Image.new("RGB", (20, 20), "cyan")]
    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=150, loop=0)
    return output.getvalue()


class Preferences:
    def __init__(self, resume: bool): self.resume = resume
    def resume_last_display(self) -> bool: return self.resume


def _identity():
    return SimpleNamespace(display_name="Test Nautilus")


def _window(monkeypatch, root: Path, *, resume=False):
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    return main_window.MainWindow(
        profile_store=ProfileStore(root / "profiles.json"),
        selected_media_store=SelectedMediaStore(root / "media"),
        preferences=Preferences(resume),
        last_active_store=LastActiveDisplayStore(root / "last-active.json"),
    )


def test_resume_preference_defaults_off_and_preserves_other_setting(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    preferences = UserPreferences()
    assert not preferences.resume_last_display()
    preferences.set_start_minimized(False)
    preferences.set_resume_last_display(True)
    assert preferences.resume_last_display() and not preferences.start_minimized()


def test_last_used_modes_and_creative_preset_restore_in_ui(monkeypatch, tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    state = store.load()
    state.active_profile_id = "creative"
    state.profile("creative").settings["active_preset_id"] = "preset_3"
    store.save(state)
    window = _window(monkeypatch, tmp_path)
    try:
        assert window._profiles.active_profile_id == "creative"
        assert window._active_creative_preset()["id"] == "preset_3"
        assert window.profile_buttons["creative"].isChecked()
        assert window.creative_preset_buttons["preset_3"].isChecked()
    finally:
        window.close()


def test_thermals_image_and_gif_mode_state_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    for mode in ("thermals", "image", "gif"):
        state = store.load()
        store.set_active(state, mode)
        assert store.load().active_profile_id == mode


def test_resume_off_and_no_device_emit_zero_startup_hid(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "active.png"
    Image.new("RGB", (20, 20), "navy").save(image)
    active_store = LastActiveDisplayStore(tmp_path / "last-active.json")
    active_store.save(LastActiveDisplay("image", "fit", {"kind": "local", "path": str(image)}))
    off = _window(monkeypatch, tmp_path, resume=False)
    events = []
    off.send_requested.connect(events.append)
    try:
        off._identity = _identity()
        off._firmware_ready("0.3.0.5")
        assert events == []
    finally:
        off.close()
    no_device = _window(monkeypatch, tmp_path, resume=True)
    no_device.send_requested.connect(events.append)
    try:
        no_device._attempt_startup_resume()
        assert events == []
    finally:
        no_device.close()


def test_resume_on_sends_valid_static_once_after_firmware(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "active.png"
    Image.new("RGB", (20, 20), "navy").save(image)
    LastActiveDisplayStore(tmp_path / "last-active.json").save(
        LastActiveDisplay("image", "fit", {"kind": "local", "path": str(image)})
    )
    window = _window(monkeypatch, tmp_path, resume=True)
    events = []
    window.send_requested.connect(events.append)
    try:
        assert events == []
        window._identity = _identity()
        window._firmware_ready("0.3.0.5")
        window._firmware_ready("0.3.0.5")
        assert len(events) == 1
    finally:
        window._session_touched_display = False
        window.close()


def test_missing_and_corrupt_active_state_fail_without_send(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "last-active.json"
    path.write_text("{broken")
    window = _window(monkeypatch, tmp_path, resume=True)
    events = []
    window.send_requested.connect(events.append)
    try:
        window._identity = _identity()
        window._firmware_ready("0.3.0.5")
        assert events == []
    finally:
        window.close()
    LastActiveDisplayStore(path).save(
        LastActiveDisplay("image", "fit", {"kind": "local", "path": str(tmp_path / "missing.png")})
    )
    second = _window(monkeypatch, tmp_path, resume=True)
    second.send_requested.connect(events.append)
    try:
        second._identity = _identity()
        second._firmware_ready("0.3.0.5")
        assert events == [] and not second._session_touched_display
    finally:
        second.close()


def test_successful_giphy_send_snapshots_active_separately_from_later_selection(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        window._switch_profile("gif")
        window._online_gif_selected(_gif("red"), "Sent")
        window._identity = _identity()
        window._send()
        window._gif_frame_sent(0, 2, 0.01)
        saved = LastActiveDisplayStore(tmp_path / "last-active.json").load()
        assert saved is not None and saved.media == {"kind": "giphy", "slot": "last-active-display"}
        active_bytes = SelectedMediaStore(tmp_path / "media").load("last-active-display").data
        window._online_gif_selected(_gif("green"), "Selected but unsent")
        assert SelectedMediaStore(tmp_path / "media").load("last-active-display").data == active_bytes
        assert LastActiveDisplayStore(tmp_path / "last-active.json").load() == saved
    finally:
        window._session_touched_display = False
        window.close()


def test_giphy_resume_uses_local_snapshot_without_provider_or_network(monkeypatch, tmp_path: Path) -> None:
    media_store = SelectedMediaStore(tmp_path / "media")
    media_store.save("last-active-display", SelectedGiphyMedia(_gif(), "Offline GIPHY"))
    LastActiveDisplayStore(tmp_path / "last-active.json").save(
        LastActiveDisplay("gif", "fit", {"kind": "giphy", "slot": "last-active-display"})
    )
    monkeypatch.setattr(main_window, "GiphyProvider", lambda: (_ for _ in ()).throw(AssertionError("network provider used")))
    window = _window(monkeypatch, tmp_path, resume=True)
    frames = []
    window.gif_frame_requested.connect(lambda *_: frames.append(True))
    try:
        window._identity = _identity()
        window._firmware_ready("0.3.0.5")
        assert frames == [True]
        assert window._session_touched_display
    finally:
        window._session_touched_display = False
        window.close()


def test_selected_but_unsent_never_creates_active_record(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        window._switch_profile("gif")
        window._online_gif_selected(_gif(), "Only selected")
        assert LastActiveDisplayStore(tmp_path / "last-active.json").load() is None
    finally:
        window.close()


def test_creative_resume_uses_saved_preset_and_media_once(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "creative.png"
    Image.new("RGB", (30, 30), "orange").save(image)
    state = ProfileStore(tmp_path / "profiles.json").load()
    preset = state.profile("creative").settings["presets"][0]
    preset["background"].update({"media_kind": "image", "source_path": str(image)})
    preset["orbit_overlay"]["enabled"] = True
    LastActiveDisplayStore(tmp_path / "last-active.json").save(
        LastActiveDisplay(
            "creative", "fit", {"kind": "local", "path": str(image)},
            "preset_1", preset,
        )
    )
    window = _window(monkeypatch, tmp_path, resume=True)
    frames = []
    window.creative_frame_requested.connect(frames.append)
    try:
        window._identity = _identity()
        window._firmware_ready("0.3.0.5")
        window._firmware_ready("0.3.0.5")
        assert len(frames) == 1
        assert window._creative_lcd_preset["id"] == "preset_1"
        assert window._creative_lcd_preset["orbit_overlay"]["enabled"]
    finally:
        window._session_touched_display = False
        window.close()


def test_thermals_resume_is_one_shot_and_uses_existing_scheduler(monkeypatch, tmp_path: Path) -> None:
    LastActiveDisplayStore(tmp_path / "last-active.json").save(LastActiveDisplay("thermals"))
    window = _window(monkeypatch, tmp_path, resume=True)
    starts = []
    monkeypatch.setattr(window, "_orbit_frame", lambda _phase: object())
    monkeypatch.setattr(window._orbit_playback, "start", lambda: starts.append(True))
    try:
        window._identity = _identity()
        window._firmware_ready("0.3.0.5")
        window._firmware_ready("0.3.0.5")
        assert starts == [True]
    finally:
        window._session_touched_display = False
        window.close()
