"""Minimal Qt Widgets GUI; contains no USB protocol construction."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nautiboy.application import control_policy, state_after_image_error
from nautiboy.branding import APP_NAME, DISCLAIMER, asset_path
from nautiboy.device.discovery import DeviceMonitor, discover_supported_devices
from nautiboy.device.identity import DeviceIdentity
from nautiboy.imaging.processor import ImageProcessingError, ResizeStrategy, prepare_image
from nautiboy.models import BUSY_STATES, AppState

from .refresh import StaticImageRefresher
from .worker import DeviceWorker

LOG = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    configure_backend = Signal(object)
    read_firmware_requested = Signal()
    send_requested = Signal(bytes)
    refresh_requested = Signal(bytes)
    restore_requested = Signal()
    rescan_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(760, 680)
        self.setMinimumSize(700, 620)
        self._state = AppState.DISCONNECTED
        self._identity: DeviceIdentity | None = None
        self._selected_path: Path | None = None
        self._prepared_jpeg: bytes | None = None
        self._session_touched_display = False
        self._close_pending = False
        self._initial_send_jpeg: bytes | None = None

        self._build_ui()
        self._refresher = StaticImageRefresher(self)
        self._refresher.refresh_requested.connect(self._queue_refresh)
        self._thread = QThread(self)
        self._worker = DeviceWorker()
        self._worker.moveToThread(self._thread)
        self.configure_backend.connect(self._worker.configure)
        self.read_firmware_requested.connect(self._worker.read_firmware)
        self.send_requested.connect(self._worker.send_image)
        self.refresh_requested.connect(self._worker.refresh_image)
        self.restore_requested.connect(self._worker.restore)
        self._worker.configured.connect(self._backend_configured)
        self._worker.firmware_ready.connect(self._firmware_ready)
        self._worker.image_sent.connect(self._image_sent)
        self._worker.image_refreshed.connect(self._image_refreshed)
        self._worker.restored.connect(self._restored)
        self._worker.failed.connect(self._operation_failed)
        self._thread.start()

        self.rescan_requested.connect(self._rescan)
        self._monitor = DeviceMonitor(self.rescan_requested.emit)
        self._poll_timer: QTimer | None = None
        try:
            self._monitor.start()
        except OSError as error:
            LOG.warning("udev monitor unavailable; using read-only polling: %s", error)
            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(2000)
            self._poll_timer.timeout.connect(self._rescan)
            self._poll_timer.start()
        self._rescan()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 11, 14, 11)
        logo = QLabel()
        logo.setFixedSize(56, 56)
        logo.setPixmap(
            QPixmap(str(asset_path("nautiboy-icon-development-source.png"))).scaled(
                56,
                56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        header_layout.addWidget(logo)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setSpacing(0)
        title = QLabel("Nauti")
        title.setObjectName("brandTitle")
        accent = QLabel("Boy")
        accent.setObjectName("brandAccent")
        title_row.addWidget(title)
        title_row.addWidget(accent)
        title_row.addStretch()
        subtitle = QLabel("NAUTILUS LCD CONTROLLER")
        subtitle.setObjectName("subtitle")
        brand.addLayout(title_row)
        brand.addWidget(subtitle)
        header_layout.addLayout(brand)
        header_layout.addStretch()
        self.details_button = QPushButton("View Details")
        self.details_button.setObjectName("detailsButton")
        self.details_button.setCheckable(True)
        header_layout.addWidget(self.details_button)
        layout.addWidget(header)

        content = QHBoxLayout()
        content.setSpacing(14)
        preview_card = QFrame()
        preview_card.setObjectName("contentCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 13)
        preview_layout.setSpacing(11)
        self.preview = QLabel("Select a JPEG or PNG")
        self.preview.setObjectName("previewSurface")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(330, 330)
        preview_layout.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignCenter)
        preview_caption = QLabel("PREVIEW  •  480 × 480")
        preview_caption.setObjectName("previewCaption")
        preview_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(preview_caption)
        content.addWidget(preview_card)

        actions = QVBoxLayout()
        actions.setSpacing(14)
        self.select_button = QPushButton("Select Image")
        self.select_button.setObjectName("selectButton")
        self.mode_combo = QComboBox()
        # Store strings because QVariant does not preserve Python Enum identity.
        self.mode_combo.addItem("Fit (Keep Aspect Ratio)", ResizeStrategy.FIT.value)
        self.mode_combo.addItem("Center Crop", ResizeStrategy.CENTER_CROP.value)
        self.send_button = QPushButton("Send to LCD")
        self.send_button.setObjectName("sendButton")
        self.restore_button = QPushButton("Restore Hardware Mode")
        self.restore_button.setObjectName("restoreButton")
        actions.addWidget(self.select_button)
        actions.addWidget(self.mode_combo)
        actions.addWidget(self.send_button)
        actions.addWidget(self.restore_button)
        actions.addStretch()
        content.addLayout(actions, 1)
        layout.addLayout(content)

        device_card = QFrame()
        device_card.setObjectName("deviceCard")
        device_layout = QHBoxLayout(device_card)
        device_layout.setContentsMargins(16, 13, 16, 13)
        self.connection_dot = QLabel()
        self.connection_dot.setObjectName("connectionDot")
        self.connection_dot.setFixedSize(16, 16)
        self.connection_dot.setProperty("connected", False)
        device_layout.addWidget(self.connection_dot)
        self.device_name = QLabel("Nautilus LCD Cap")
        device_layout.addWidget(self.device_name)
        self.device_connection = QLabel("Disconnected")
        self.device_connection.setObjectName("deviceMeta")
        device_layout.addWidget(self.device_connection)
        device_layout.addStretch()
        self.device_vid = QLabel("VID:PID —")
        self.device_vid.setObjectName("deviceMeta")
        device_layout.addWidget(self.device_vid)
        separator = QLabel("|")
        separator.setObjectName("deviceMeta")
        device_layout.addWidget(separator)
        self.device_firmware = QLabel("Firmware —")
        self.device_firmware.setObjectName("deviceMeta")
        device_layout.addWidget(self.device_firmware)
        device_layout.addStretch()
        self.state_label = QLabel("DISCONNECTED")
        self.state_label.setObjectName("statusBadge")
        self.state_label.setProperty("state", AppState.DISCONNECTED.value)
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        device_layout.addWidget(self.state_label)
        layout.addWidget(device_card)

        self.details_card = QFrame()
        self.details_card.setObjectName("detailsCard")
        details_layout = QVBoxLayout(self.details_card)
        details_layout.setContentsMargins(12, 10, 12, 12)
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setMaximumHeight(125)
        self.messages.setMaximumBlockCount(100)
        self.messages.setPlaceholderText("Status messages")
        details_layout.addWidget(self.messages)
        self.details_card.setVisible(False)
        layout.addWidget(self.details_card)

        footer = QLabel(DISCLAIMER.upper())
        footer.setObjectName("footerLabel")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(footer)
        self.setCentralWidget(central)

        self.select_button.clicked.connect(self._select_image)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.send_button.clicked.connect(self._send)
        self.restore_button.clicked.connect(self._restore)
        self.details_button.toggled.connect(self._toggle_details)

    @Slot(bool)
    def _toggle_details(self, visible: bool) -> None:
        self.details_card.setVisible(visible)
        self.details_button.setText("Hide Details" if visible else "View Details")

    @staticmethod
    def _refresh_widget_style(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _message(self, text: str) -> None:
        LOG.info(text)
        self.messages.appendPlainText(text)

    def _set_state(self, state: AppState) -> None:
        self._state = state
        self.state_label.setText(state.value.upper())
        self.state_label.setProperty("state", state.value)
        self._refresh_widget_style(self.state_label)
        policy = control_policy(
            state,
            has_device=self._identity is not None,
            has_image=self._prepared_jpeg is not None,
            session_touched_display=self._session_touched_display,
        )
        self.select_button.setEnabled(policy.select_image)
        self.mode_combo.setEnabled(policy.select_image)
        self.send_button.setEnabled(policy.send)
        self.restore_button.setEnabled(policy.restore)

    @Slot()
    def _rescan(self) -> None:
        if self._state in BUSY_STATES:
            return
        devices = discover_supported_devices()
        if not devices:
            self._refresher.stop()
            self._identity = None
            self.device_name.setText("Nautilus LCD Cap")
            self.device_vid.setText("VID:PID —")
            self.device_firmware.setText("Firmware —")
            self.device_connection.setText("Disconnected")
            self.connection_dot.setProperty("connected", False)
            self._refresh_widget_style(self.connection_dot)
            self.configure_backend.emit(None)
            self._set_state(AppState.DISCONNECTED)
            return
        identity = devices[0]
        changed = self._identity != identity
        self._identity = identity
        self.device_name.setText(identity.display_name)
        self.device_vid.setText(f"VID:PID {identity.vid:04x}:{identity.pid:04x}")
        self.device_connection.setText("Connected")
        self.connection_dot.setProperty("connected", True)
        self._refresh_widget_style(self.connection_dot)
        if changed:
            self.device_firmware.setText("Firmware reading…")
            self.configure_backend.emit(identity)
        else:
            self._set_state(AppState.DISPLAYING if self._refresher.active else AppState.READY)

    @Slot()
    def _backend_configured(self) -> None:
        if self._identity is None:
            return
        self._set_state(AppState.READY)
        self.read_firmware_requested.emit()

    @Slot(str)
    def _firmware_ready(self, version: str) -> None:
        self.device_firmware.setText(f"Firmware {version}")
        self._set_state(AppState.READY)
        self._message(f"Connected to {self._identity.display_name if self._identity else 'device'}")

    @Slot(str, str)
    def _operation_failed(self, action: str, message: str) -> None:
        self._refresher.stop()
        self._initial_send_jpeg = None
        self._set_state(AppState.ERROR)
        self._message(f"{action.capitalize()} failed: {message}")
        if action == "firmware":
            self.device_firmware.setText("Firmware unavailable")
        if self._close_pending:
            self._close_pending = False
            QMessageBox.warning(self, "Restore failed", "Hardware mode could not be restored. The window will remain open so you can retry.")

    @Slot()
    def _select_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select image", str(Path.home()), "Images (*.jpg *.jpeg *.png)"
        )
        if filename:
            self._selected_path = Path(filename)
            self._prepare_selected()

    @Slot()
    def _mode_changed(self) -> None:
        if self._selected_path is not None:
            self._prepare_selected()

    def _prepare_selected(self) -> None:
        assert self._selected_path is not None
        strategy = self.mode_combo.currentData()
        try:
            _rendered, jpeg = prepare_image(self._selected_path, strategy)
        except ImageProcessingError as error:
            self._prepared_jpeg = None
            self.preview.setText("Invalid image")
            self._message(str(error))
            self._set_state(state_after_image_error(has_device=self._identity is not None))
            return
        self._prepared_jpeg = jpeg
        pixmap = QPixmap()
        pixmap.loadFromData(jpeg, "JPEG")
        self.preview.setPixmap(
            pixmap.scaled(330, 330, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        self._message(f"Prepared {self._selected_path.name} using {ResizeStrategy(strategy).value}")
        if self._identity is not None:
            self._set_state(AppState.DISPLAYING if self._session_touched_display else AppState.READY)

    @Slot()
    def _send(self) -> None:
        if self._prepared_jpeg is None or self._identity is None:
            return
        self._refresher.stop()
        self._initial_send_jpeg = self._prepared_jpeg
        self._session_touched_display = True
        self._set_state(AppState.SENDING)
        self._message("Sending one volatile image…")
        self.send_requested.emit(self._prepared_jpeg)

    @Slot(int)
    def _image_sent(self, report_count: int) -> None:
        if self._initial_send_jpeg is None:
            self._operation_failed("send", "completed without a prepared refresh image")
            return
        self._refresher.start_after_initial_success(self._initial_send_jpeg)
        self._initial_send_jpeg = None
        self._set_state(AppState.DISPLAYING)
        self._message(f"Image displayed successfully ({report_count} reports)")

    @Slot(bytes)
    def _queue_refresh(self, jpeg: bytes) -> None:
        self.refresh_requested.emit(jpeg)

    @Slot(int)
    def _image_refreshed(self, _report_count: int) -> None:
        self._refresher.transfer_completed()

    @Slot()
    def _restore(self) -> None:
        if self._identity is None or not self._session_touched_display:
            return
        self._refresher.stop()
        self._initial_send_jpeg = None
        self._set_state(AppState.RESTORING)
        self._message("Restoring hardware mode…")
        self.restore_requested.emit()

    @Slot()
    def _restored(self) -> None:
        self._session_touched_display = False
        self._set_state(AppState.READY)
        self._message("Hardware mode restored")
        if self._close_pending:
            self._close_pending = False
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._refresher.stop()
        self._initial_send_jpeg = None
        if self._session_touched_display and self._identity is not None:
            event.ignore()
            if self._state is not AppState.RESTORING:
                self._close_pending = True
                self._restore()
            return
        self._monitor.stop()
        if self._poll_timer is not None:
            self._poll_timer.stop()
        self._thread.quit()
        self._thread.wait(3000)
        event.accept()
