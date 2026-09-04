from __future__ import annotations

from pathlib import Path

from PIL import Image

from nautiboy.branding import APP_DESCRIPTION, APP_ID, APP_NAME, DISCLAIMER, asset_path
from nautiboy.gui import main_window
from nautiboy.gui.theme import STYLESHEET
from nautiboy.models import AppState


def test_public_brand_identity() -> None:
    assert APP_NAME == "NautiBoy"
    assert APP_ID == "io.github.nautiboy.NautiBoy"
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
