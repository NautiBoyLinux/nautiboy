"""Preview-first UI for saving a passive local hardware support bundle."""

from __future__ import annotations

import json
from html import escape
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from nautiboy.branding import HARDWARE_SUPPORT_EMAIL
from nautiboy.support_report import (
    ReportSnapshot, collect_hardware_report, render_human_report, write_support_bundle,
)


def complete_preview(snapshot: ReportSnapshot) -> str:
    structured = json.dumps(snapshot.as_dict(), indent=2, sort_keys=True, ensure_ascii=False)
    return f"{render_human_report(snapshot)}\nStructured JSON included in the bundle\n{'=' * 38}\n{structured}\n"


_STATUS_LABELS = {
    "supported": "Supported",
    "experimental": "Experimental",
    "protocol_known_unimplemented": "Known but not implemented",
    "identification_only": "Known but not implemented",
    "unsupported": "Known but not implemented",
}


def support_status_rows(snapshot: ReportSnapshot) -> tuple[tuple[str, str], ...]:
    """Return safe, plain-language device and support labels for the UI."""
    rows: list[tuple[str, str]] = []
    for device in snapshot.devices:
        catalog = device.get("catalog", {})
        raw_status = str(catalog.get("status", "unknown"))
        status = _STATUS_LABELS.get(raw_status, "Unknown")
        matches = catalog.get("matches", [])
        matching = next(
            (row for row in matches if row.get("interface_match") and row.get("name")),
            None,
        )
        name = (
            matching["name"] if matching else
            " ".join(str(value) for value in (device.get("manufacturer"), device.get("product")) if value)
        ) or f"USB device {device.get('vid', '????')}:{device.get('pid', '????')}"
        rows.append((str(name), status))
    return tuple(rows)


def support_status_html(snapshot: ReportSnapshot) -> str:
    rows = support_status_rows(snapshot)
    if not rows:
        return (
            "<b>Hardware status: Unknown</b><br>"
            "No known or HID/display-like USB device was detected. You can still generate a "
            "Hardware Report for troubleshooting."
        )
    rendered = "<br>".join(
        f"<b>{escape(status)}</b> — {escape(name)}" for name, status in rows
    )
    return f"<b>Hardware scan results</b><br>{rendered}"


class HardwareReportDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        collector: Callable[[], ReportSnapshot] = collect_hardware_report,
        writer: Callable[[Path, ReportSnapshot], Path] = write_support_bundle,
    ) -> None:
        super().__init__(parent)
        self._writer = writer
        self.snapshot = collector()
        self.saved_path: Path | None = None
        self.setWindowTitle("NautiBoy Hardware Report")
        self.resize(760, 700)
        layout = QVBoxLayout(self)
        self.status_summary = QLabel(support_status_html(self.snapshot))
        self.status_summary.setWordWrap(True)
        layout.addWidget(self.status_summary)
        notice = QLabel(
            "Review everything below before saving. The ZIP contains this report as text and JSON. "
            "Serial numbers are hashed for this report. NautiBoy will save locally only and will "
            "not upload or transmit the bundle. Hardware is not opened or commanded."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        submission_note = QLabel(
            "If your hardware is unsupported or not detected correctly, save and review the ZIP, "
            f"then email it yourself to {HARDWARE_SUPPORT_EMAIL}. NautiBoy never sends it for you."
        )
        submission_note.setWordWrap(True)
        layout.addWidget(submission_note)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(complete_preview(self.snapshot))
        layout.addWidget(self.preview, 1)
        self.save_button = QPushButton("Generate Hardware Report ZIP…")
        self.close_button = QPushButton("Close")
        layout.addWidget(self.save_button)
        layout.addWidget(self.close_button)
        self.save_button.clicked.connect(self._save)
        self.close_button.clicked.connect(self.reject)

    def _save(self) -> None:
        downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        suggested = str(Path(downloads or str(Path.home())) / "nautiboy-hardware-report.zip")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save NautiBoy Support Bundle", suggested, "ZIP archives (*.zip)"
        )
        if not filename:
            return
        try:
            self.saved_path = self._writer(Path(filename), self.snapshot)
        except OSError as error:
            QMessageBox.warning(self, "Hardware report could not be saved", str(error))
            return
        QMessageBox.information(
            self,
            "Hardware report saved",
            f"Saved locally to:\n{self.saved_path}\n\nNothing was uploaded automatically.",
        )
