"""Small preferences dialog for per-user session startup."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from nautiboy.autostart import AutostartError, AutostartManager, UserPreferences
from nautiboy.credentials import CredentialError, GiphyCredentialStore

from .hardware_report_dialog import HardwareReportDialog

PREFERENCES_MINIMUM_WIDTH = 420
PREFERENCES_MINIMUM_HEIGHT = 650


class PreferencesDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        manager: AutostartManager | None = None,
        preferences: UserPreferences | None = None,
        credential_store: GiphyCredentialStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager or AutostartManager()
        self.preferences = preferences or UserPreferences()
        self.credential_store = credential_store or GiphyCredentialStore()
        self.setWindowTitle("NautiBoy Preferences")
        self.setMinimumSize(PREFERENCES_MINIMUM_WIDTH, PREFERENCES_MINIMUM_HEIGHT)
        self.resize(PREFERENCES_MINIMUM_WIDTH, PREFERENCES_MINIMUM_HEIGHT)
        try:
            self.manager.migrate_legacy()
        except AutostartError:
            # Leave an inaccessible legacy entry untouched; saving preferences
            # will surface a concrete error through the normal UI path.
            pass
        layout = QVBoxLayout(self)
        self.launch_at_login = QCheckBox("Launch NautiBoy at login")
        self.start_minimized = QCheckBox("Start minimized to system tray")
        actual_background = self.manager.entry_starts_in_background()
        self.launch_at_login.setChecked(self.manager.enabled())
        self.start_minimized.setChecked(
            self.preferences.start_minimized() if actual_background is None else actual_background
        )
        self.start_minimized.setEnabled(self.launch_at_login.isChecked())
        self.launch_at_login.toggled.connect(self.start_minimized.setEnabled)
        layout.addWidget(self.launch_at_login)
        layout.addWidget(self.start_minimized)
        note = QLabel(
            "Background startup performs safe device discovery. It changes the LCD only when "
            "Resume last display is separately enabled."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.resume_last_display = QCheckBox("Resume last display on launch")
        self.resume_last_display.setChecked(self.preferences.resume_last_display())
        layout.addWidget(self.resume_last_display)
        resume_note = QLabel(
            "After the supported LCD is detected, NautiBoy can restore the last display "
            "that was successfully sent. This is independent of login startup."
        )
        resume_note.setWordWrap(True)
        layout.addWidget(resume_note)
        giphy = QGroupBox("GIPHY (experimental)")
        giphy_layout = QVBoxLayout(giphy)
        self.giphy_status = QLabel()
        self.giphy_key = QLineEdit()
        self.giphy_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.giphy_key.setPlaceholderText("Enter API key")
        actions = QHBoxLayout()
        self.save_giphy_key = QPushButton("Save Key")
        self.remove_giphy_key = QPushButton("Remove Key")
        actions.addWidget(self.save_giphy_key)
        actions.addWidget(self.remove_giphy_key)
        giphy_layout.addWidget(self.giphy_status)
        giphy_layout.addWidget(self.giphy_key)
        giphy_layout.addLayout(actions)
        layout.addWidget(giphy)
        hardware_report = QGroupBox("Tester support")
        hardware_report_layout = QVBoxLayout(hardware_report)
        report_note = QLabel(
            "Generate a read-only USB/HID inventory. You can review every included field before "
            "saving a local ZIP; nothing is uploaded automatically."
        )
        report_note.setWordWrap(True)
        self.hardware_report_button = QPushButton("Generate Hardware Report")
        hardware_report_layout.addWidget(report_note)
        hardware_report_layout.addWidget(self.hardware_report_button)
        layout.addWidget(hardware_report)
        self.save_giphy_key.clicked.connect(self._save_giphy_key)
        self.remove_giphy_key.clicked.connect(self._remove_giphy_key)
        self.hardware_report_button.clicked.connect(self._open_hardware_report)
        self._refresh_giphy_status()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_hardware_report(self) -> None:
        HardwareReportDialog(self).exec()

    def _refresh_giphy_status(self) -> None:
        try:
            configured = self.credential_store.configured()
            text = "GIPHY API key configured" if configured else "GIPHY API key not configured"
        except CredentialError as error:
            configured = False
            text = f"Secret storage unavailable: {error}"
        self.giphy_status.setText(text)
        self.remove_giphy_key.setEnabled(configured)

    def _save_giphy_key(self) -> None:
        try:
            self.credential_store.save(self.giphy_key.text())
        except CredentialError as error:
            QMessageBox.warning(self, "GIPHY key could not be saved", str(error))
            return
        self.giphy_key.clear()
        self._refresh_giphy_status()

    def _remove_giphy_key(self) -> None:
        try:
            self.credential_store.delete()
        except CredentialError as error:
            QMessageBox.warning(self, "GIPHY key could not be removed", str(error))
            return
        self.giphy_key.clear()
        self._refresh_giphy_status()

    def _save(self) -> None:
        try:
            minimized = self.start_minimized.isChecked()
            self.preferences.set_start_minimized(minimized)
            self.preferences.set_resume_last_display(self.resume_last_display.isChecked())
            if self.launch_at_login.isChecked():
                self.manager.enable(background=minimized)
            else:
                self.manager.disable()
        except AutostartError as error:
            QMessageBox.warning(self, "Autostart could not be changed", str(error))
            return
        self.accept()
