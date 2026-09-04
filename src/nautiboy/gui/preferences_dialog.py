"""Small preferences dialog for per-user session startup."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout, QWidget

from nautiboy.autostart import AutostartError, AutostartManager, UserPreferences


class PreferencesDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        manager: AutostartManager | None = None,
        preferences: UserPreferences | None = None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager or AutostartManager()
        self.preferences = preferences or UserPreferences()
        self.setWindowTitle("NautiBoy Preferences")
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
            "Background startup performs device discovery but never sends media or changes the LCD."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        try:
            minimized = self.start_minimized.isChecked()
            self.preferences.set_start_minimized(minimized)
            if self.launch_at_login.isChecked():
                self.manager.enable(background=minimized)
            else:
                self.manager.disable()
        except AutostartError as error:
            QMessageBox.warning(self, "Autostart could not be changed", str(error))
            return
        self.accept()
