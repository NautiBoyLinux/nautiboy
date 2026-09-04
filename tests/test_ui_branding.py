from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QMovie
import io

from nautiboy.branding import (
    APP_DESCRIPTION,
    APP_ID,
    APP_NAME,
    DISCLAIMER,
    application_icon,
    application_icon_paths,
    asset_path,
)
from nautiboy.gui import main_window
from nautiboy.gui.theme import STYLESHEET
from nautiboy.models import AppState
from nautiboy.providers.giphy import GiphyProvider
from nautiboy.gui.gif_search_dialog import GifSearchDialog
from nautiboy.credentials import GiphyCredentialStore
from nautiboy.gui.preferences_dialog import (
    PREFERENCES_MINIMUM_HEIGHT,
    PREFERENCES_MINIMUM_WIDTH,
    PreferencesDialog,
)
from test_credentials import FakeKeyring


def test_public_brand_identity() -> None:
    assert APP_NAME == "NautiBoy"
    assert APP_ID == "io.github.nautiboy.nautiboy"
    assert APP_DESCRIPTION == (
        "NautiBoy is an open-source Linux controller for Corsair NAUTILUS RS LCD displays."
    )
    assert "unofficial community project" in DISCLAIMER
    assert "not affiliated with, endorsed by, or supported by Corsair" in DISCLAIMER


def test_theme_is_separate_and_contains_semantic_states() -> None:
    assert "#7427e8" in STYLESHEET
    for state in AppState:
        assert f'state="{state.value}"' in STYLESHEET


def test_development_icon_source_and_desktop_sizes() -> None:
    source = asset_path("nautiboy-icon-development-source.png")
    assert source.is_file()
    with Image.open(source) as image:
        assert image.size == (345, 345)

    root = Path(__file__).resolve().parents[1]
    for size in (16, 32, 48, 64, 128, 256):
        icon = root / f"packaging/icons/hicolor/{size}x{size}/apps/{APP_ID}.png"
        with Image.open(icon) as image:
            assert image.size == (size, size)


def test_canonical_bundled_icon_is_non_null_at_tray_sizes() -> None:
    icon = application_icon()
    assert not icon.isNull()
    assert all(path.is_file() for path in application_icon_paths())
    for size in (16, 22, 24, 32):
        pixmap = icon.pixmap(size, size)
        assert not pixmap.isNull()
        assert pixmap.width() <= size and pixmap.height() <= size


def test_bundled_icon_loading_does_not_require_desktop_metadata(monkeypatch) -> None:
    from PySide6.QtCore import QStandardPaths
    monkeypatch.setattr(
        QStandardPaths,
        "locate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("desktop lookup used")),
    )
    application_icon.cache_clear()
    assert not application_icon().isNull()


def test_desktop_metadata_uses_final_executable() -> None:
    root = Path(__file__).resolve().parents[1]
    desktop = (root / f"packaging/{APP_ID}.desktop").read_text(encoding="utf-8")
    assert "Name=NautiBoy" in desktop
    assert "Exec=nautiboy" in desktop
    assert f"Icon={APP_ID}" in desktop


def test_public_readme_records_exact_validated_scope() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for value in (
        "CORSAIR Nautilus LCD Cap",
        "`1b1c:0c57`",
        "`0.3.0.5`",
        "Fedora KDE Plasma 44",
        "currently unverified",
        "not affiliated with, endorsed",
    ):
        assert value in readme


def test_disconnected_window_keeps_controls_safe(monkeypatch) -> None:
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)

    window = main_window.MainWindow()
    try:
        assert window.windowTitle() == APP_NAME
        assert window.state_label.text() == "DISCONNECTED"
        assert not window.details_card.isVisible()
        assert window.select_button.isEnabled() is False
        assert window.send_button.isEnabled() is False
        assert window.restore_button.isEnabled() is False
        window.details_button.setChecked(True)
        assert not window.details_card.isHidden()
    finally:
        window.close()


def _animated_gif() -> bytes:
    output = io.BytesIO()
    first = Image.new("RGB", (24, 12), "red")
    second = Image.new("RGB", (24, 12), "blue")
    first.save(output, format="GIF", save_all=True, append_images=[second], duration=[100, 150], loop=0)
    return output.getvalue()


def _disconnected_window(monkeypatch):
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    return main_window.MainWindow()


def _use_gif_mode(window) -> None:
    window._profiles.active_profile_id = "gif"
    window._apply_profile_ui()


def test_no_provider_dialog_explains_local_media_remains_available(monkeypatch) -> None:
    monkeypatch.delenv("NAUTIBOY_GIPHY_API_KEY", raising=False)
    dialog = GifSearchDialog(GiphyProvider())
    try:
        assert "not configured" in dialog.status.text()
        assert "Local JPEG, PNG, and GIF" in dialog.status.text()
        assert not dialog.search_button.isEnabled()
    finally:
        dialog.reject()


def test_local_gif_populates_animated_preview_without_hid(monkeypatch, tmp_path: Path) -> None:
    window = _disconnected_window(monkeypatch)
    _use_gif_mode(window)
    sent = []
    window.send_requested.connect(sent.append)
    window.gif_frame_requested.connect(lambda *args: sent.append(args))
    path = tmp_path / "preview.gif"
    path.write_bytes(_animated_gif())
    try:
        window._selected_path = path
        window._prepare_selected()
        assert window._selected_media is not None and window._selected_media.animated
        assert window._preview_movie is not None
        assert window._preview_movie.state() is QMovie.MovieState.Running
        assert "Animated" in window.preview_caption.text()
        assert sent == []
    finally:
        window.close()


def test_online_selection_populates_preview_but_never_auto_sends(monkeypatch) -> None:
    window = _disconnected_window(monkeypatch)
    _use_gif_mode(window)
    sent = []
    window.send_requested.connect(sent.append)
    window.gif_frame_requested.connect(lambda *args: sent.append(args))
    try:
        window._online_gif_selected(_animated_gif(), "Selected result")
        assert window._selected_media is not None
        assert window._selected_media.title == "Selected result"
        assert sent == []
    finally:
        window.close()


def test_restore_stops_both_schedulers_before_request(monkeypatch) -> None:
    window = _disconnected_window(monkeypatch)
    order = []
    window._identity = object()
    window._session_touched_display = True
    monkeypatch.setattr(window._refresher, "stop", lambda: order.append("static-stop"))
    monkeypatch.setattr(window._gif_playback, "stop", lambda: order.append("gif-stop"))
    window.restore_requested.connect(lambda: order.append("restore"))
    try:
        window._restore()
        assert order[:3] == ["static-stop", "gif-stop", "restore"]
        window._session_touched_display = False
    finally:
        window.close()


def test_provider_failure_does_not_break_later_local_media(monkeypatch, tmp_path: Path) -> None:
    window = _disconnected_window(monkeypatch)
    _use_gif_mode(window)
    path = tmp_path / "local.gif"
    path.write_bytes(_animated_gif())
    try:
        window._online_gif_selected(b"broken", "Broken provider result")
        window._selected_path = path
        window._prepare_selected()
        assert window._selected_media is not None and window._selected_media.animated
    finally:
        window.close()


def test_send_is_explicit_animation_transition(monkeypatch) -> None:
    window = _disconnected_window(monkeypatch)
    _use_gif_mode(window)
    starts = []
    try:
        window._online_gif_selected(_animated_gif(), "Ready but not sent")
        window._identity = object()
        monkeypatch.setattr(window._gif_playback, "start", starts.append)
        assert starts == [] and not window._session_touched_display
        window._send()
        assert len(starts) == 1 and window._session_touched_display
        window._session_touched_display = False
    finally:
        window.close()


def test_new_preview_does_not_replace_active_lcd_snapshot(monkeypatch) -> None:
    window = _disconnected_window(monkeypatch)
    _use_gif_mode(window)
    try:
        window._online_gif_selected(_animated_gif(), "First")
        active = window._selected_media.gif
        window._lcd_gif = active
        window._online_gif_selected(_animated_gif(), "Second")
        assert window._selected_media.title == "Second"
        assert window._lcd_gif is active
    finally:
        window.close()


def test_backend_animation_failure_stops_playback(monkeypatch) -> None:
    window = _disconnected_window(monkeypatch)
    stopped = []
    monkeypatch.setattr(window._gif_playback, "stop", lambda: stopped.append(True))
    try:
        window._operation_failed("animation", "short write")
        assert stopped == [True]
        assert window._state is AppState.ERROR
    finally:
        window.close()


def test_gif_search_button_opens_dialog(monkeypatch) -> None:
    window = _disconnected_window(monkeypatch)
    calls = []

    class FakeDialog:
        media_selected = type("Selection", (), {"connect": lambda self, callback: calls.append(callback)})()
        def __init__(self, provider, parent):
            calls.append((provider, parent))
        def exec(self):
            calls.append("opened")

    monkeypatch.setattr(main_window, "GifSearchDialog", FakeDialog)
    try:
        window._open_gif_search()
        assert calls[-1] == "opened"
    finally:
        window.close()


def test_search_network_worker_is_not_gui_thread(monkeypatch) -> None:
    monkeypatch.delenv("NAUTIBOY_GIPHY_API_KEY", raising=False)
    dialog = GifSearchDialog(GiphyProvider())
    try:
        assert dialog._thread.isRunning()
        assert dialog._network.thread() is dialog._thread
        assert dialog._network.thread() is not dialog.thread()
    finally:
        dialog.reject()


def test_downloaded_thumbnail_is_animated(monkeypatch) -> None:
    monkeypatch.delenv("NAUTIBOY_GIPHY_API_KEY", raising=False)
    from PySide6.QtWidgets import QPushButton
    dialog = GifSearchDialog(GiphyProvider())
    button = QPushButton()
    dialog._requests["preview"] = ("preview", button)
    try:
        dialog._completed("preview", _animated_gif(), "https://example.invalid/preview.gif")
        assert len(dialog._movies) == 1
        assert dialog._movies[0][1].state() is QMovie.MovieState.Running
    finally:
        dialog.reject()


def test_selected_search_result_shows_provider_creator_and_source(monkeypatch) -> None:
    monkeypatch.delenv("NAUTIBOY_GIPHY_API_KEY", raising=False)
    from nautiboy.providers.base import GifResult
    dialog = GifSearchDialog(GiphyProvider())
    result = GifResult(
        "GIPHY (experimental)", "id", "Title", "Creator",
        "https://giphy.com/gifs/id", "https://example.invalid/p.gif",
        "https://example.invalid/o.gif",
    )
    try:
        dialog._select(result)
        assert "Creator" in dialog.selected_details.text()
        assert "Powered by GIPHY" in dialog.selected_details.text()
        assert "View source" in dialog.selected_details.text()
        assert "Creator" not in dialog.status.text()
    finally:
        dialog.reject()


def test_search_grid_uses_image_only_tiles_with_title_tooltips(monkeypatch) -> None:
    monkeypatch.delenv("NAUTIBOY_GIPHY_API_KEY", raising=False)
    from nautiboy.providers.base import GifResult, SearchPage

    dialog = GifSearchDialog(GiphyProvider())
    result = GifResult(
        "GIPHY (experimental)", "id", "Dancing cat", "Creator",
        "https://giphy.com/gifs/id", "https://example.invalid/p.gif",
        "https://example.invalid/o.gif",
    )
    try:
        dialog._show_page(SearchPage((result,), None))
        card = dialog.grid.itemAt(0).widget()
        assert card is not None
        assert card.text() == ""
        assert card.toolTip() == "Dancing cat"
        assert card.accessibleName() == "Dancing cat"
    finally:
        dialog.reject()


def test_preferences_masks_saves_and_removes_giphy_key(monkeypatch, tmp_path) -> None:
    backend = FakeKeyring()
    store = GiphyCredentialStore(backend)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    dialog = PreferencesDialog(credential_store=store)
    try:
        assert dialog.giphy_key.echoMode() is dialog.giphy_key.EchoMode.Password
        assert "not configured" in dialog.giphy_status.text()
        dialog.giphy_key.setText("ui-fake-secret")
        dialog._save_giphy_key()
        assert dialog.giphy_key.text() == ""
        assert dialog.giphy_status.text() == "GIPHY API key configured"
        assert "ui-fake-secret" not in dialog.giphy_status.text()
        dialog._remove_giphy_key()
        assert "not configured" in dialog.giphy_status.text()
        assert store.retrieve() is None
    finally:
        dialog.reject()


def test_preferences_opens_large_enough_for_all_controls(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    dialog = PreferencesDialog(credential_store=GiphyCredentialStore(FakeKeyring()))
    try:
        assert dialog.minimumWidth() == PREFERENCES_MINIMUM_WIDTH
        assert dialog.minimumHeight() == PREFERENCES_MINIMUM_HEIGHT
        assert dialog.width() >= PREFERENCES_MINIMUM_WIDTH
        assert dialog.height() >= PREFERENCES_MINIMUM_HEIGHT
    finally:
        dialog.reject()


def test_local_media_does_not_depend_on_credential_store(monkeypatch, tmp_path: Path) -> None:
    class BrokenStore:
        def retrieve(self):
            raise AssertionError("local media attempted credential access")

    window = _disconnected_window(monkeypatch)
    _use_gif_mode(window)
    path = tmp_path / "local.gif"
    path.write_bytes(_animated_gif())
    try:
        window._selected_path = path
        window._prepare_selected()
        assert window._selected_media is not None
    finally:
        window.close()
