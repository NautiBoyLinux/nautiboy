from __future__ import annotations

from pathlib import Path
import io

from PIL import Image
from PySide6.QtCore import Qt

from nautiboy.gui import main_window
from nautiboy.profiles import ProfileStore


def _window(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    return main_window.MainWindow(profile_store=ProfileStore(tmp_path / "profiles.json"))


def _install_media(window, tmp_path: Path):
    path = tmp_path / "background.png"
    Image.new("RGB", (64, 48), "navy").save(path)
    window._switch_profile("creative")
    preset = window._active_creative_preset()
    media = main_window.prepare_local_media(path, "fit")
    window._creative_media[preset["id"]] = media
    window._profile_store.update_creative_preset(
        window._profiles, preset["id"], "background",
        {"media_kind": "image", "source_path": str(path), "resize_strategy": "fit"},
    )
    window._apply_creative_preset_ui()
    return media


def _animated_gif() -> bytes:
    frames = [Image.new("RGB", (24, 24), color) for color in ("red", "blue")]
    stream = io.BytesIO()
    frames[0].save(stream, format="GIF", save_all=True, append_images=frames[1:],
                   duration=(120, 240), loop=0)
    return stream.getvalue()


def test_preview_and_profile_preset_changes_emit_zero_hid(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    events = []
    window.send_requested.connect(lambda *_: events.append("send"))
    window.creative_frame_requested.connect(lambda *_: events.append("creative"))
    window.restore_requested.connect(lambda *_: events.append("restore"))
    try:
        _install_media(window, tmp_path)
        window.creative_orbit_enabled.setChecked(True)
        window._render_creative_preview()
        window._creative_preset_clicked(1)
        window._switch_profile("image")
        assert events == []
    finally:
        window.close()


def test_creative_editor_has_explicit_vertical_scrollbar(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        assert window.creative_scroll.objectName() == "creativeScroll"
        assert (
            window.creative_scroll.verticalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        assert (
            window.creative_scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert window.creative_scroll.widgetResizable()
    finally:
        window.close()


def test_creative_giphy_button_uses_clean_label(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        assert window.creative_giphy_button.text() == "Search GIPHY"
    finally:
        window.close()


def test_main_window_opens_at_requested_height(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        assert window.width() == 760
        assert window.height() == 960
        assert window.minimumHeight() == 620
        assert window.maximumHeight() > 960
    finally:
        window.close()


def test_independent_preset_settings_and_media_reference_persist(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        _install_media(window, tmp_path)
        window.creative_orbit_enabled.setChecked(True)
        window.creative_orbit_animated.setChecked(False)
        window._creative_preset_clicked(1)
        assert not window.creative_orbit_enabled.isChecked()
        saved = ProfileStore(tmp_path / "profiles.json").load().profile("creative").settings
        first = saved["presets"][0]
        assert first["background"]["source_path"].endswith("background.png")
        assert first["orbit_overlay"]["enabled"] is True
        assert saved["presets"][1]["background"]["source_path"] is None
    finally:
        window.close()


def test_explicit_static_send_uses_existing_static_path(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    sent = []
    window.send_requested.connect(sent.append)
    try:
        _install_media(window, tmp_path)
        window._identity = object()
        window._send()
        assert len(sent) == 1 and sent[0].startswith(b"\xff\xd8")
        assert not window._creative_playback.active
    finally:
        window._session_touched_display = False
        window.close()


def test_explicit_dynamic_send_and_restore_stops_before_restore(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    order = []
    try:
        _install_media(window, tmp_path)
        window.creative_orbit_enabled.setChecked(True)
        window._identity = object()
        window._send()
        assert window._creative_playback.active
        monkeypatch.setattr(window._creative_playback, "stop", lambda: order.append("creative-stop"))
        window.restore_requested.connect(lambda: order.append("restore"))
        window._restore()
        assert order == ["creative-stop", "restore"]
    finally:
        window._session_touched_display = False
        window.close()


def test_creative_restore_reports_bounded_measurement_summary(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        window._creative_measurement_started = main_window.time.monotonic() - 1.0
        window._creative_measurements = [
            main_window.OrbitTransferStats(42, 40960, 0.020, 0.001, 0.011, 0.032),
            main_window.OrbitTransferStats(43, 43008, 0.030, 0.002, 0.013, 0.045),
        ]
        window._creative_playback._dropped = 3
        window._report_creative_measurements()
        report = window.messages.toPlainText().splitlines()[-1]
        assert "render min/avg/max 20.0/25.0/30.0 ms" in report
        assert "reports 42/42.5/43" in report
        assert "frames 2; coalesced 3" in report
    finally:
        window.close()


def test_creative_giphy_selection_is_persisted_isolated_and_zero_hid(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    events = []
    window.send_requested.connect(lambda *_: events.append("send"))
    window.creative_frame_requested.connect(lambda *_: events.append("creative"))
    try:
        window._switch_profile("creative")
        original_gif_selection = window._selected_media
        window._creative_online_gif_selected(_animated_gif(), "Neon Cat")
        first = window._creative_media["preset_1"]
        assert first.animated and first.title == "Neon Cat"
        assert window._profiles.active_profile_id == "creative"
        assert window._selected_media is original_gif_selection
        assert "Neon Cat" in window.creative_media_info.text()
        assert events == []
        window._creative_preset_clicked(1)
        assert "preset_2" not in window._creative_media
        document = (tmp_path / "profiles.json").read_text()
        assert "Neon Cat" not in document and "credential" not in document
        assert '"selected_giphy_slot": "creative-preset_1"' in document
    finally:
        window.close()


def test_creative_search_reuses_existing_provider_and_dialog(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    used = []

    class Connection:
        def connect(self, callback): used.append(("callback", callback))

    class Dialog:
        def __init__(self, provider, parent):
            used.append(("provider", provider, parent))
            self.media_selected = Connection()
        def exec(self): used.append(("exec",))
        def reject(self): pass

    provider = object()
    monkeypatch.setattr(main_window, "GiphyProvider", lambda: provider)
    monkeypatch.setattr(main_window, "GifSearchDialog", Dialog)
    try:
        window._switch_profile("creative")
        window._open_creative_gif_search()
        assert used[0] == ("provider", provider, window)
        assert used[-1] == ("exec",)
    finally:
        window.close()
