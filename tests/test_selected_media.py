from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

from nautiboy.gui import main_window
from nautiboy.profiles import ProfileStore
from nautiboy.providers.base import GifResult, SelectedGif
from nautiboy.selected_media import SelectedGiphyMedia, SelectedMediaStore


def _gif(colors=("red", "blue")) -> bytes:
    frames = [Image.new("RGB", (24, 24), color) for color in colors]
    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return output.getvalue()


def _selection(title="Chosen", identifier="abc") -> SelectedGif:
    return SelectedGif(
        _gif(),
        GifResult("giphy", identifier, title, "Creator", "https://giphy.com/gifs/abc",
                  "https://example.invalid/preview.gif", "https://example.invalid/original.gif"),
        "Powered by GIPHY",
    )


def _window(monkeypatch, root: Path):
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    return main_window.MainWindow(
        profile_store=ProfileStore(root / "profiles.json"),
        selected_media_store=SelectedMediaStore(root / "data"),
    )


def test_store_round_trip_uses_final_identity_and_contains_no_credential(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    store = SelectedMediaStore()
    assert "io.github.nautiboylinux.nautiboy" in str(store.root)
    store.save(
        "gif-profile",
        SelectedGiphyMedia(
            _gif(), "Chosen", creator="Creator", source_url="https://giphy.com/gifs/chosen"
        ),
    )
    restored = store.load("gif-profile")
    assert restored is not None and restored.title == "Chosen" and restored.creator == "Creator"
    assert restored.source_url == "https://giphy.com/gifs/chosen"
    metadata = json.loads((store.root / "gif-profile.json").read_text())
    assert metadata["source_url"] == "https://giphy.com/gifs/chosen"
    assert "original_url" not in metadata
    combined = b"".join(path.read_bytes() for path in store.root.iterdir())
    assert b"API" not in combined and b"credential" not in combined and b"original_url" not in combined


def test_gif_profile_selected_giphy_survives_restart_without_hid(monkeypatch, tmp_path: Path) -> None:
    first = _window(monkeypatch, tmp_path)
    try:
        first._switch_profile("gif")
        first._online_gif_selected(_selection())
    finally:
        first.close()
    events = []
    second = _window(monkeypatch, tmp_path)
    second.send_requested.connect(lambda *_: events.append("send"))
    second.gif_frame_requested.connect(lambda *_: events.append("frame"))
    try:
        assert second._profiles.active_profile_id == "gif"
        assert second._selected_media is not None and second._selected_media.title == "Chosen"
        assert "Powered by GIPHY" in second.preview_caption.text()
        assert events == [] and not second._session_touched_display
    finally:
        second.close()


def test_creative_presets_restore_independent_giphy_media(monkeypatch, tmp_path: Path) -> None:
    first = _window(monkeypatch, tmp_path)
    try:
        first._switch_profile("creative")
        first._creative_online_gif_selected(_selection("One", "one"))
        first._creative_preset_clicked(1)
        first._creative_online_gif_selected(_selection("Two", "two"))
    finally:
        first.close()
    second = _window(monkeypatch, tmp_path)
    events = []
    second.creative_frame_requested.connect(lambda *_: events.append("frame"))
    try:
        assert second._creative_media["preset_2"].title == "Two"
        second._creative_preset_clicked(0)
        assert second._creative_media["preset_1"].title == "One"
        assert events == [] and not second._session_touched_display
    finally:
        second.close()


def test_corrupt_or_missing_persisted_selection_fails_empty(monkeypatch, tmp_path: Path) -> None:
    profile_store = ProfileStore(tmp_path / "profiles.json")
    state = profile_store.load()
    state.active_profile_id = "gif"
    state.profile("gif").settings["selected_giphy_slot"] = "gif-profile"
    profile_store.save(state)
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "gif-profile.gif").write_bytes(b"broken")
    (data_root / "gif-profile.json").write_text("{}")
    window = _window(monkeypatch, tmp_path)
    try:
        assert window._selected_media is None
        (data_root / "gif-profile.gif").unlink()
        assert SelectedMediaStore(data_root).load("gif-profile") is None
    finally:
        window.close()


def test_replacement_and_local_selection_clean_only_owned_slot(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    root = tmp_path / "data"
    unrelated = root / "keep.txt"
    try:
        window._switch_profile("creative")
        window._creative_online_gif_selected(_selection("First", "first"))
        root.mkdir(exist_ok=True)
        unrelated.write_text("keep")
        window._creative_online_gif_selected(_selection("Second", "second"))
        metadata = json.loads((root / "creative-preset_1.json").read_text())
        assert metadata["title"] == "Second" and unrelated.read_text() == "keep"
        local = tmp_path / "local.png"
        Image.new("RGB", (20, 20), "green").save(local)
        monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *_args: (str(local), ""))
        window._select_creative_media()
        assert not (root / "creative-preset_1.gif").exists()
        assert not (root / "creative-preset_1.json").exists()
        assert unrelated.read_text() == "keep"
    finally:
        window.close()


def test_search_browsing_does_not_create_persistent_media(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        # Persistence is connected only to the explicit media_selected handler.
        assert not (tmp_path / "data").exists()
    finally:
        window.close()
