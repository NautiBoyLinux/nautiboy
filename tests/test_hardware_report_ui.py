from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from nautiboy.gui.hardware_report_dialog import (
    HardwareReportDialog,
    complete_preview,
    support_status_rows,
)
from nautiboy.gui import main_window
from nautiboy.support_report.models import ReportSnapshot


def _snapshot() -> ReportSnapshot:
    return ReportSnapshot(
        1, "2026-09-09T00:00:00+00:00",
        {"serial_numbers": "hashed", "automatic_upload": False},
        {"kernel": "test", "architecture": "x86_64", "python": "3", "distribution": {}},
        (),
    )


def _device_snapshot(status: str) -> ReportSnapshot:
    return ReportSnapshot(
        1, "2026-09-09T00:00:00+00:00",
        {"serial_numbers": "hashed", "automatic_upload": False},
        {"kernel": "test", "architecture": "x86_64", "python": "3", "distribution": {}},
        ({
            "manufacturer": "Test Vendor", "product": "Test LCD", "vid": "1234", "pid": "5678",
            "catalog": {
                "status": status, "confidence": "test",
                "matches": ([{
                    "name": "Catalog LCD", "interface_match": True,
                }] if status != "unknown" else []),
            },
        },),
    )


def test_dialog_shows_complete_payload_before_save(qt_application) -> None:
    written = []
    dialog = HardwareReportDialog(collector=_snapshot, writer=lambda path, snapshot: written.append((path, snapshot)) or path)
    try:
        preview = dialog.preview.toPlainText()
        assert "Hardware Report" in preview
        assert "Structured JSON included" in preview
        assert '"automatic_upload": false' in preview
        labels = " ".join(label.text() for label in dialog.findChildren(QLabel))
        assert "hardware@nautiboy.dev" in labels
        assert "never sends it for you" in labels
        assert written == []
    finally:
        dialog.close()


def test_preview_contains_the_exact_structured_device_data() -> None:
    snapshot = _snapshot()
    assert '"schema_version": 1' in complete_preview(snapshot)


@pytest.mark.parametrize(
    ("raw_status", "visible_status"),
    (
        ("supported", "Supported"),
        ("experimental", "Experimental"),
        ("protocol_known_unimplemented", "Known but not implemented"),
        ("identification_only", "Known but not implemented"),
        ("unknown", "Unknown"),
    ),
)
def test_scan_uses_clear_public_support_categories(raw_status: str, visible_status: str) -> None:
    assert support_status_rows(_device_snapshot(raw_status)) == (
        (("Test Vendor Test LCD" if raw_status == "unknown" else "Catalog LCD"), visible_status),
    )


def test_empty_scan_is_unknown_and_still_offers_report(qt_application) -> None:
    dialog = HardwareReportDialog(collector=_snapshot)
    try:
        assert "Hardware status: Unknown" in dialog.status_summary.text()
        assert "Generate Hardware Report ZIP" in dialog.save_button.text()
        assert dialog.save_button.isEnabled()
    finally:
        dialog.close()


def test_main_window_scan_is_available_without_supported_hardware(monkeypatch) -> None:
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    opened = []

    class FakeReportDialog:
        def __init__(self, parent):
            opened.append(parent)

        def exec(self):
            opened.append("exec")

    monkeypatch.setattr(main_window, "HardwareReportDialog", FakeReportDialog)
    window = main_window.MainWindow()
    try:
        assert window.hardware_scan_button.text() == "CHECK MY HARDWARE"
        assert window.hardware_scan_button.isEnabled()
        window.hardware_scan_button.click()
        assert opened == [window, "exec"]
    finally:
        window.close()
