from __future__ import annotations

from pathlib import Path

from PIL import Image

from nautiboy.gui import main_window
from nautiboy.profiles import ProfileStore


def _window(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    return main_window.MainWindow(profile_store=ProfileStore(tmp_path / "profiles.json"))


def test_profile_selector_defaults_to_image_and_has_fixed_order(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        assert list(window.profile_buttons) == ["thermals", "image", "gif", "creative"]
        assert [button.text() for button in window.profile_buttons.values()] == [
            "Thermals", "Image", "GIF", "Creative"
        ]
        assert window.profile_buttons["image"].isChecked()
    finally:
        window.close()


def test_mode_specific_controls_and_placeholders(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        assert not window.select_button.isHidden()
        assert window.select_button.text() == "Select Image"
        assert window.gif_search_button.isHidden()
        window._switch_profile("gif")
        assert window.select_button.text() == "Select GIF"
        assert not window.gif_search_button.isHidden()
        window._switch_profile("thermals")
        assert window.select_button.isHidden() and not window.send_button.isHidden()
        assert window.send_button.text() == "Send Thermals to LCD"
        assert not window.thermals_panel.isHidden()
        assert not window.restore_button.isHidden()
        window._switch_profile("creative")
        assert not window.creative_panel.isHidden()
        assert "background media" in window.creative_placeholder.text()
        assert not window.restore_button.isHidden()
    finally:
        window.close()


def test_switching_persists_but_never_emits_hid_or_stops_playback(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    events = []
    window.send_requested.connect(lambda *_: events.append("send"))
    window.refresh_requested.connect(lambda *_: events.append("refresh"))
    window.gif_frame_requested.connect(lambda *_: events.append("gif"))
    window.restore_requested.connect(lambda: events.append("restore"))
    monkeypatch.setattr(window._refresher, "stop", lambda: events.append("static-stop"))
    monkeypatch.setattr(window._gif_playback, "stop", lambda: events.append("gif-stop"))
    try:
        window._switch_profile("creative")
        assert events == []
        assert ProfileStore(tmp_path / "profiles.json").load().active_profile_id == "creative"
    finally:
        window.close()


def test_image_and_gif_resize_controls_persist_independently(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    window = _window(monkeypatch, tmp_path)
    try:
        window.mode_combo.setCurrentIndex(window.mode_combo.findData("center-crop"))
        window._switch_profile("gif")
        assert window.mode_combo.currentData() == "fit"
        window.mode_combo.setCurrentIndex(window.mode_combo.findData("center-crop"))
        saved = ProfileStore(path).load()
        assert saved.profile("image").settings["resize_strategy"] == "center-crop"
        assert saved.profile("gif").settings["resize_strategy"] == "center-crop"
    finally:
        window.close()


def test_existing_static_send_path_is_unchanged_in_image_mode(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    Image.new("RGB", (32, 32), "purple").save(image_path)
    window = _window(monkeypatch, tmp_path)
    sent = []
    window.send_requested.connect(sent.append)
    try:
        window._selected_path = image_path
        window._prepare_selected()
        window._identity = object()
        window._send()
        assert len(sent) == 1 and sent[0].startswith(b"\xff\xd8")
    finally:
        window._session_touched_display = False
        window.close()


def test_creative_preset_selector_only_appears_in_creative_mode(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        assert window.creative_panel.isHidden()
        window._switch_profile("creative")
        assert not window.creative_panel.isHidden()
        assert list(window.creative_preset_buttons) == [
            "preset_1", "preset_2", "preset_3", "preset_4"
        ]
        assert window.creative_preset_buttons["preset_1"].isChecked()
        window._switch_profile("image")
        assert window.creative_panel.isHidden()
    finally:
        window.close()


def test_selecting_creative_preset_persists_without_hid(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    events = []
    window.send_requested.connect(lambda *_: events.append("send"))
    window.refresh_requested.connect(lambda *_: events.append("refresh"))
    window.gif_frame_requested.connect(lambda *_: events.append("gif"))
    window.restore_requested.connect(lambda: events.append("restore"))
    try:
        window._switch_profile("creative")
        window._creative_preset_clicked(2)
        assert events == []
        settings = ProfileStore(tmp_path / "profiles.json").load().profile("creative").settings
        assert settings["active_preset_id"] == "preset_3"
        assert window.creative_preset_buttons["preset_3"].isChecked()
    finally:
        window.close()


def test_rename_creative_preset_updates_ui_and_persists_without_hid(
    monkeypatch, tmp_path: Path
) -> None:
    window = _window(monkeypatch, tmp_path)
    events = []
    window.send_requested.connect(lambda *_: events.append("send"))
    window.refresh_requested.connect(lambda *_: events.append("refresh"))
    window.gif_frame_requested.connect(lambda *_: events.append("gif"))
    window.restore_requested.connect(lambda: events.append("restore"))
    monkeypatch.setattr(main_window.QInputDialog, "getText", lambda *_args, **_kwargs: ("Purple", True))
    try:
        window._switch_profile("creative")
        window._rename_creative_preset()
        assert events == []
        assert window.creative_preset_buttons["preset_1"].text() == "Purple"
        assert window.creative_preset_buttons["preset_1"].toolTip() == "Purple"
        preset = ProfileStore(tmp_path / "profiles.json").load().profile("creative").settings["presets"][0]
        assert preset == window._profiles.profile("creative").settings["presets"][0]
        assert preset["id"] == "preset_1" and preset["name"] == "Purple"
    finally:
        window.close()


def test_long_valid_preset_name_is_elided_but_preserved_in_tooltip(
    monkeypatch, tmp_path: Path
) -> None:
    window = _window(monkeypatch, tmp_path)
    full_name = "Twenty Character Name"[:20]
    monkeypatch.setattr(
        main_window.QInputDialog, "getText", lambda *_args, **_kwargs: (full_name, True)
    )
    try:
        window._switch_profile("creative")
        window._rename_creative_preset()
        button = window.creative_preset_buttons["preset_1"]
        assert button.toolTip() == full_name
        assert len(button.text()) <= len(full_name)
        assert window._profiles.profile("creative").settings["presets"][0]["name"] == full_name
    finally:
        window.close()
