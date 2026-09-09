from __future__ import annotations

from nautiboy.gui.hardware_report_dialog import HardwareReportDialog, complete_preview
from nautiboy.support_report.models import ReportSnapshot


def _snapshot() -> ReportSnapshot:
    return ReportSnapshot(
        1, "2026-09-09T00:00:00+00:00",
        {"serial_numbers": "hashed", "automatic_upload": False},
        {"kernel": "test", "architecture": "x86_64", "python": "3", "distribution": {}},
        (),
    )


def test_dialog_shows_complete_payload_before_save(qt_application) -> None:
    written = []
    dialog = HardwareReportDialog(collector=_snapshot, writer=lambda path, snapshot: written.append((path, snapshot)) or path)
    try:
        preview = dialog.preview.toPlainText()
        assert "Hardware Report" in preview
        assert "Structured JSON included" in preview
        assert '"automatic_upload": false' in preview
        assert written == []
    finally:
        dialog.close()


def test_preview_contains_the_exact_structured_device_data() -> None:
    snapshot = _snapshot()
    assert '"schema_version": 1' in complete_preview(snapshot)
