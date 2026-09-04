"""Minimal Qt Widgets GUI; contains no USB protocol construction."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QMovie, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
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
from nautiboy.branding import APP_NAME, DISCLAIMER, application_icon
from nautiboy.device.discovery import DeviceMonitor, discover_supported_devices
from nautiboy.device.identity import DeviceIdentity
from nautiboy.imaging.processor import ImageProcessingError, ResizeStrategy
from nautiboy.gif.playback import GifPlaybackController
from nautiboy.media import PreparedMedia, prepare_downloaded_gif, prepare_local_media
from nautiboy.models import BUSY_STATES, AppState
from nautiboy.providers.giphy import GiphyProvider
from nautiboy.profiles import (
    CREATIVE_PRESET_IDS,
    CREATIVE_PRESET_NAME_MAX_LENGTH,
    ProfileStore,
    ProfileStoreError,
    ProfileType,
)

from .gif_search_dialog import GifSearchDialog
from .preferences_dialog import PreferencesDialog
from .refresh import StaticImageRefresher
from .worker import DeviceWorker

LOG = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    configure_backend = Signal(object)
    read_firmware_requested = Signal()
    send_requested = Signal(bytes)
    refresh_requested = Signal(bytes)
    restore_requested = Signal()
    gif_frame_requested = Signal(object, int, str)
    rescan_requested = Signal()
    hidden_to_tray = Signal()
    tray_status_changed = Signal(str)
    shutdown_ready = Signal()

    def __init__(self, *, profile_store: ProfileStore | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(760, 680)
        self.setMinimumSize(700, 620)
        self._state = AppState.DISCONNECTED
        self._identity: DeviceIdentity | None = None
        self._selected_path: Path | None = None
        self._prepared_jpeg: bytes | None = None
        self._selected_media: PreparedMedia | None = None
        self._lcd_gif = None
        self._lcd_strategy = ResizeStrategy.FIT.value
        self._preview_movie: QMovie | None = None
        self._preview_buffer: QBuffer | None = None
        self._online_gif_data: bytes | None = None
        self._session_touched_display = False
        self._close_pending = False
        self._close_to_tray = False
        self._quit_requested = False
        self._workers_stopped = False
        self._search_dialog: GifSearchDialog | None = None
        self._initial_send_jpeg: bytes | None = None
        self._profile_store = profile_store or ProfileStore()
        self._profiles = self._profile_store.load()

        self._build_ui()
        self._refresher = StaticImageRefresher(self)
        self._refresher.refresh_requested.connect(self._queue_refresh)
        self._gif_playback = GifPlaybackController(self)
        self._gif_playback.frame_requested.connect(self._queue_gif_frame)
        self._thread = QThread(self)
        self._worker = DeviceWorker()
        self._worker.moveToThread(self._thread)
        self.configure_backend.connect(self._worker.configure)
        self.read_firmware_requested.connect(self._worker.read_firmware)
        self.send_requested.connect(self._worker.send_image)
        self.refresh_requested.connect(self._worker.refresh_image)
        self.restore_requested.connect(self._worker.restore)
        self.gif_frame_requested.connect(self._worker.send_gif_frame)
        self._worker.configured.connect(self._backend_configured)
        self._worker.firmware_ready.connect(self._firmware_ready)
        self._worker.image_sent.connect(self._image_sent)
        self._worker.image_refreshed.connect(self._image_refreshed)
        self._worker.gif_frame_sent.connect(self._gif_frame_sent)
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
        logo.setPixmap(application_icon().pixmap(56, 56))
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
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("detailsButton")
        header_layout.addWidget(self.settings_button)
        self.details_button = QPushButton("View Details")
        self.details_button.setObjectName("detailsButton")
        self.details_button.setCheckable(True)
        header_layout.addWidget(self.details_button)
        layout.addWidget(header)

        profile_bar = QFrame()
        profile_bar.setObjectName("profileBar")
        profile_layout = QHBoxLayout(profile_bar)
        profile_layout.setContentsMargins(8, 8, 8, 8)
        profile_layout.setSpacing(8)
        self.profile_group = QButtonGroup(self)
        self.profile_group.setExclusive(True)
        self.profile_buttons: dict[str, QPushButton] = {}
        for profile in self._profiles.profiles:
            button = QPushButton(profile.name)
            button.setObjectName("profileButton")
            button.setCheckable(True)
            self.profile_group.addButton(button)
            self.profile_group.setId(button, list(ProfileType).index(profile.profile_type))
            self.profile_buttons[profile.identifier] = button
            profile_layout.addWidget(button, 1)
        self.profile_group.idClicked.connect(self._profile_clicked)
        layout.addWidget(profile_bar)

        content = QHBoxLayout()
        content.setSpacing(14)
        preview_card = QFrame()
        preview_card.setObjectName("contentCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 13)
        preview_layout.setSpacing(11)
        self.preview = QLabel("Select a JPEG, PNG, or GIF")
        self.preview.setObjectName("previewSurface")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(330, 330)
        preview_layout.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignCenter)
        self.preview_caption = QLabel("PREVIEW  •  480 × 480")
        self.preview_caption.setObjectName("previewCaption")
        self.preview_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_caption.setWordWrap(True)
        preview_layout.addWidget(self.preview_caption)
        content.addWidget(preview_card)

        actions = QVBoxLayout()
        actions.setSpacing(14)
        select_row = QHBoxLayout()
        self.select_button = QPushButton("Select Local Media")
        self.select_button.setObjectName("selectButton")
        self.gif_search_button = QPushButton("GIF Search")
        select_row.addWidget(self.select_button)
        select_row.addWidget(self.gif_search_button)
        self.mode_combo = QComboBox()
        # Store strings because QVariant does not preserve Python Enum identity.
        self.mode_combo.addItem("Fit (Keep Aspect Ratio)", ResizeStrategy.FIT.value)
        self.mode_combo.addItem("Center Crop", ResizeStrategy.CENTER_CROP.value)
        self.send_button = QPushButton("Send to LCD")
        self.send_button.setObjectName("sendButton")
        self.restore_button = QPushButton("Restore Hardware Mode")
        self.restore_button.setObjectName("restoreButton")
        self.mode_placeholder = QLabel()
        self.mode_placeholder.setObjectName("modePlaceholder")
        self.mode_placeholder.setWordWrap(True)
        self.mode_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.creative_panel = QWidget()
        creative_layout = QVBoxLayout(self.creative_panel)
        creative_layout.setContentsMargins(0, 0, 0, 0)
        creative_layout.setSpacing(10)
        presets_heading = QLabel("Presets")
        presets_heading.setObjectName("presetsHeading")
        presets_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        creative_layout.addWidget(presets_heading)
        preset_bar = QFrame()
        preset_bar.setObjectName("profileBar")
        preset_layout = QHBoxLayout(preset_bar)
        preset_layout.setContentsMargins(8, 8, 8, 8)
        preset_layout.setSpacing(8)
        self.creative_preset_group = QButtonGroup(self)
        self.creative_preset_group.setExclusive(True)
        self.creative_preset_buttons: dict[str, QPushButton] = {}
        for index, identifier in enumerate(CREATIVE_PRESET_IDS):
            button = QPushButton()
            button.setObjectName("profileButton")
            button.setCheckable(True)
            self.creative_preset_group.addButton(button, index)
            self.creative_preset_buttons[identifier] = button
            preset_layout.addWidget(button, 1)
        self.creative_preset_group.idClicked.connect(self._creative_preset_clicked)
        creative_layout.addWidget(preset_bar)
        self.rename_preset_button = QPushButton("Rename Selected Preset")
        self.rename_preset_button.setObjectName("renamePresetButton")
        creative_layout.addWidget(
            self.rename_preset_button, alignment=Qt.AlignmentFlag.AlignHCenter
        )
        self.creative_placeholder = QLabel(
            "Creative editing will support background media, telemetry overlays, and custom layouts."
        )
        self.creative_placeholder.setObjectName("modePlaceholder")
        self.creative_placeholder.setWordWrap(True)
        self.creative_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        creative_layout.addWidget(self.creative_placeholder, 1)
        actions.addLayout(select_row)
        actions.addWidget(self.mode_combo)
        actions.addWidget(self.send_button)
        actions.addWidget(self.mode_placeholder, 1)
        actions.addWidget(self.creative_panel, 1)
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
        self.settings_button.clicked.connect(self._open_preferences)
        self.gif_search_button.clicked.connect(self._open_gif_search)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.send_button.clicked.connect(self._send)
        self.restore_button.clicked.connect(self._restore)
        self.rename_preset_button.clicked.connect(self._rename_creative_preset)
        self.details_button.toggled.connect(self._toggle_details)
        self._apply_profile_ui()

    @Slot(int)
    def _profile_clicked(self, index: int) -> None:
        self._switch_profile(list(ProfileType)[index].value)

    def _switch_profile(self, identifier: str) -> None:
        if identifier == self._profiles.active_profile_id:
            return
        self._profiles.active_profile_id = identifier
        try:
            self._profile_store.save(self._profiles)
        except ProfileStoreError as error:
            self._message(str(error))
        self._clear_selected_media()
        self._apply_profile_ui()

    @Slot(int)
    def _creative_preset_clicked(self, index: int) -> None:
        identifier = CREATIVE_PRESET_IDS[index]
        settings = self._profiles.profile(ProfileType.CREATIVE.value).settings
        if settings["active_preset_id"] == identifier:
            return
        try:
            self._profile_store.set_active_creative_preset(self._profiles, identifier)
        except ProfileStoreError as error:
            self._message(str(error))
        self._apply_creative_preset_ui()

    @Slot()
    def _rename_creative_preset(self) -> None:
        settings = self._profiles.profile(ProfileType.CREATIVE.value).settings
        identifier = settings["active_preset_id"]
        preset = next(item for item in settings["presets"] if item["id"] == identifier)
        name, accepted = QInputDialog.getText(
            self,
            "Rename Creative Preset",
            f"Preset name (maximum {CREATIVE_PRESET_NAME_MAX_LENGTH} characters):",
            text=preset["name"],
        )
        if not accepted:
            return
        try:
            self._profile_store.rename_creative_preset(self._profiles, identifier, name)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid Preset Name", str(error))
            return
        except ProfileStoreError as error:
            self._message(str(error))
            return
        self._apply_creative_preset_ui()

    def _apply_creative_preset_ui(self) -> None:
        settings = self._profiles.profile(ProfileType.CREATIVE.value).settings
        active = settings["active_preset_id"]
        presets = {preset["id"]: preset for preset in settings["presets"]}
        for identifier, button in self.creative_preset_buttons.items():
            name = presets[identifier]["name"]
            button.setText(button.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, 76))
            button.setToolTip(name)
            button.setChecked(identifier == active)

    def _clear_selected_media(self) -> None:
        self._selected_path = None
        self._online_gif_data = None
        self._selected_media = None
        self._prepared_jpeg = None
        self._stop_preview()
        self.preview.clear()
        self.preview.setText("Select media for this mode")
        self.preview_caption.setText("PREVIEW  •  480 × 480")

    def _apply_profile_ui(self) -> None:
        active = ProfileType(self._profiles.active_profile_id)
        for identifier, button in self.profile_buttons.items():
            button.setChecked(identifier == active.value)
        media_mode = active in {ProfileType.IMAGE, ProfileType.GIF}
        gif_mode = active is ProfileType.GIF
        self.select_button.setVisible(media_mode)
        self.gif_search_button.setVisible(gif_mode)
        self.mode_combo.setVisible(media_mode)
        self.send_button.setVisible(media_mode)
        creative_mode = active is ProfileType.CREATIVE
        self.mode_placeholder.setVisible(active is ProfileType.THERMALS)
        self.creative_panel.setVisible(creative_mode)
        if active is ProfileType.IMAGE:
            self.select_button.setText("Select Image")
        elif active is ProfileType.GIF:
            self.select_button.setText("Select GIF")
        elif active is ProfileType.THERMALS:
            self.mode_placeholder.setText(
                "Thermals mode is ready for future CPU/GPU telemetry. No sensor polling is enabled yet."
            )
        if creative_mode:
            self._apply_creative_preset_ui()
        if media_mode:
            strategy = self._profiles.profile(active.value).settings["resize_strategy"]
            combo_index = self.mode_combo.findData(strategy)
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(combo_index)
            self.mode_combo.blockSignals(False)
        self._set_state(self._state)

    @Slot(bool)
    def _toggle_details(self, visible: bool) -> None:
        self.details_card.setVisible(visible)
        self.details_button.setText("Hide Details" if visible else "View Details")

    @Slot()
    def _open_preferences(self) -> None:
        PreferencesDialog(self).exec()

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
        self.gif_search_button.setEnabled(policy.select_image)
        self.mode_combo.setEnabled(policy.select_image)
        self.send_button.setEnabled(policy.send)
        self.restore_button.setEnabled(policy.restore)
        self.tray_status_changed.emit(self.playback_status())

    def playback_status(self) -> str:
        if not self._session_touched_display:
            return "Hardware mode"
        if self._gif_playback.active:
            return "GIF playing"
        if self._refresher.active or self._state is AppState.SENDING:
            return "Static image"
        if self._state is AppState.RESTORING:
            return "Restoring hardware mode"
        return "Volatile display active"

    def enable_close_to_tray(self) -> None:
        self._close_to_tray = True

    @Slot()
    def _rescan(self) -> None:
        if self._state in BUSY_STATES:
            return
        devices = discover_supported_devices()
        if not devices:
            self._refresher.stop()
            self._gif_playback.stop()
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
            active = self._refresher.active or self._gif_playback.active
            self._set_state(AppState.DISPLAYING if active else AppState.READY)

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
        self._gif_playback.stop()
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
        active = ProfileType(self._profiles.active_profile_id)
        if active not in {ProfileType.IMAGE, ProfileType.GIF}:
            return
        media_filter = (
            "Images (*.jpg *.jpeg *.png)"
            if active is ProfileType.IMAGE
            else "GIF animation (*.gif)"
        )
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select local media", str(Path.home()), media_filter
        )
        if filename:
            self._selected_path = Path(filename)
            self._online_gif_data = None
            self._prepare_selected()

    @Slot()
    def _mode_changed(self) -> None:
        active = ProfileType(self._profiles.active_profile_id)
        if active in {ProfileType.IMAGE, ProfileType.GIF}:
            try:
                self._profile_store.set_resize_strategy(
                    self._profiles, active.value, str(self.mode_combo.currentData())
                )
            except (ProfileStoreError, ValueError) as error:
                self._message(str(error))
        if self._selected_path is not None:
            self._prepare_selected()
        elif self._online_gif_data is not None and self._selected_media is not None:
            try:
                self._set_selected_media(
                    prepare_downloaded_gif(
                        self._online_gif_data,
                        self._selected_media.title,
                        self.mode_combo.currentData(),
                    )
                )
            except ImageProcessingError as error:
                self._message(str(error))

    def _prepare_selected(self) -> None:
        assert self._selected_path is not None
        active = ProfileType(self._profiles.active_profile_id)
        is_gif = self._selected_path.suffix.lower() == ".gif"
        if (active is ProfileType.IMAGE and is_gif) or (
            active is ProfileType.GIF and not is_gif
        ):
            expected = "JPEG or PNG" if active is ProfileType.IMAGE else "GIF"
            self._prepared_jpeg = None
            self._selected_media = None
            self.preview.setText(f"Select a {expected} file")
            self._message(f"{active.value.capitalize()} mode accepts {expected} files only")
            self._set_state(state_after_image_error(has_device=self._identity is not None))
            return
        strategy = self.mode_combo.currentData()
        try:
            media = prepare_local_media(self._selected_path, strategy)
        except ImageProcessingError as error:
            self._prepared_jpeg = None
            self._selected_media = None
            self.preview.setText("Invalid image")
            self._message(str(error))
            self._set_state(state_after_image_error(has_device=self._identity is not None))
            return
        self._set_selected_media(media)
        self._message(f"Prepared {self._selected_path.name} using {ResizeStrategy(strategy).value}")
        if self._identity is not None:
            self._set_state(AppState.DISPLAYING if self._session_touched_display else AppState.READY)

    def _set_selected_media(self, media: PreparedMedia) -> None:
        self._selected_media = media
        self._prepared_jpeg = media.static_jpeg or media.preview_jpeg
        self._stop_preview()
        if media.animated and media.gif is not None:
            self._preview_buffer = QBuffer(self)
            self._preview_buffer.setData(QByteArray(media.gif.data))
            self._preview_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self._preview_movie = QMovie(self._preview_buffer, b"GIF", self)
            width_ratio = self.preview.width() / media.width
            height_ratio = self.preview.height() / media.height
            strategy = ResizeStrategy(self.mode_combo.currentData())
            scale = min(width_ratio, height_ratio) if strategy is ResizeStrategy.FIT else max(width_ratio, height_ratio)
            self._preview_movie.setScaledSize(
                QSize(max(1, round(media.width * scale)), max(1, round(media.height * scale)))
            )
            self.preview.setMovie(self._preview_movie)
            self._preview_movie.start()
        else:
            pixmap = QPixmap()
            pixmap.loadFromData(media.preview_jpeg, "JPEG")
            self.preview.setPixmap(
                pixmap.scaled(330, 330, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        kind = "Animated" if media.animated else "Static"
        duration = f" • {media.duration_ms / 1000:.1f}s" if media.animated else ""
        self.preview_caption.setText(
            f"{media.title}\n{kind} • {media.width} × {media.height} • {media.frame_count} frame(s){duration}"
        )

    def _stop_preview(self) -> None:
        if self._preview_movie is not None:
            self._preview_movie.stop()
        self._preview_movie = None
        if self._preview_buffer is not None:
            self._preview_buffer.close()
        self._preview_buffer = None

    @Slot()
    def _open_gif_search(self) -> None:
        dialog = GifSearchDialog(GiphyProvider(), self)
        self._search_dialog = dialog
        dialog.media_selected.connect(self._online_gif_selected)
        dialog.exec()
        self._search_dialog = None

    @Slot(bytes, str)
    def _online_gif_selected(self, data: bytes, title: str) -> None:
        if self._profiles.active_profile_id != ProfileType.GIF.value:
            self._message("Online GIF selection is available only in GIF mode")
            return
        try:
            media = prepare_downloaded_gif(data, title, self.mode_combo.currentData())
        except ImageProcessingError as error:
            self._message(str(error))
            self._set_state(state_after_image_error(has_device=self._identity is not None))
            return
        self._selected_path = None
        self._online_gif_data = data
        self._set_selected_media(media)
        self._message(f"Prepared experimental online GIF: {title}")
        if self._identity is not None:
            self._set_state(AppState.DISPLAYING if self._session_touched_display else AppState.READY)

    @Slot()
    def _send(self) -> None:
        if self._selected_media is None or self._prepared_jpeg is None or self._identity is None:
            return
        self._refresher.stop()
        self._gif_playback.stop()
        if self._selected_media.animated and self._selected_media.gif is not None:
            self._lcd_gif = self._selected_media.gif
            self._lcd_strategy = str(self.mode_combo.currentData())
            self._initial_send_jpeg = None
            self._session_touched_display = True
            self._set_state(AppState.SENDING)
            self._message("Starting volatile GIF playback…")
            self._gif_playback.start(self._lcd_gif)
            return
        self._lcd_gif = None
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
    def _queue_gif_frame(self, index: int) -> None:
        if self._lcd_gif is not None:
            self.gif_frame_requested.emit(self._lcd_gif, index, self._lcd_strategy)

    @Slot(int, int, float)
    def _gif_frame_sent(self, index: int, report_count: int, duration_seconds: float) -> None:
        first = self._state is AppState.SENDING
        self._gif_playback.transfer_completed()
        self._set_state(AppState.DISPLAYING)
        frame_count = self._lcd_gif.frame_count if self._lcd_gif is not None else 0
        self._message(
            f"GIF frame {index + 1}/{frame_count}: {report_count} reports in "
            f"{duration_seconds * 1000:.1f} ms; "
            f"coalesced total {self._gif_playback.coalesced_frames}"
        )
        if first:
            self._message(f"GIF playback started ({report_count} reports)")

    @Slot(int)
    def _image_refreshed(self, _report_count: int) -> None:
        self._refresher.transfer_completed()

    @Slot()
    def _restore(self) -> None:
        if self._identity is None or not self._session_touched_display:
            return
        self._refresher.stop()
        self._gif_playback.stop()
        self._lcd_gif = None
        self._initial_send_jpeg = None
        self._set_state(AppState.RESTORING)
        self._message("Restoring hardware mode…")
        self.restore_requested.emit()

    @Slot()
    def restore_hardware_mode(self) -> None:
        """Public action shared by the main window and system tray."""
        self._restore()

    @Slot()
    def _restored(self) -> None:
        self._session_touched_display = False
        self._set_state(AppState.READY)
        self._message("Hardware mode restored")
        if self._quit_requested:
            self._finish_shutdown()
        elif self._close_pending:
            self._close_pending = False
            self.close()

    @Slot()
    def request_quit(self) -> None:
        """Perform the only true application shutdown path."""
        if self._quit_requested:
            return
        self._quit_requested = True
        self._close_to_tray = False
        self._refresher.stop()
        self._gif_playback.stop()
        self._lcd_gif = None
        self._initial_send_jpeg = None
        if self._search_dialog is not None:
            self._search_dialog.reject()
            self._search_dialog = None
        if self._session_touched_display and self._identity is not None:
            self._set_state(AppState.RESTORING)
            self._message("Restoring hardware mode before quit…")
            # Serialized behind any already-running operation in DeviceWorker.
            self.restore_requested.emit()
            return
        self._finish_shutdown()

    def _finish_shutdown(self) -> None:
        if self._workers_stopped:
            return
        self._workers_stopped = True
        self._monitor.stop()
        if self._poll_timer is not None:
            self._poll_timer.stop()
        self._thread.quit()
        self._thread.wait(3000)
        self.shutdown_ready.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._close_to_tray and not self._quit_requested:
            event.ignore()
            self.hide()
            self.hidden_to_tray.emit()
            return
        self._refresher.stop()
        self._gif_playback.stop()
        self._lcd_gif = None
        self._initial_send_jpeg = None
        if self._session_touched_display and self._identity is not None:
            event.ignore()
            if self._state is not AppState.RESTORING:
                self._close_pending = True
                self._restore()
            return
        self._finish_shutdown()
        event.accept()
