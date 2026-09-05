"""Minimal Qt Widgets GUI; contains no USB protocol construction."""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import replace
import io
from pathlib import Path
import time

from PIL import Image

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor, QMovie, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nautiboy.application import control_policy, state_after_image_error
from nautiboy.autostart import UserPreferences
from nautiboy.branding import APP_NAME, DISCLAIMER, application_icon
from nautiboy.creative import (
    CreativeComposition,
    CreativeFrameRequest,
    CreativePlaybackController,
    compose_creative_jpeg,
)
from nautiboy.device.discovery import DeviceMonitor, discover_supported_devices
from nautiboy.device.identity import DeviceIdentity
from nautiboy.imaging.processor import ImageProcessingError, ResizeStrategy
from nautiboy.gif.playback import GifPlaybackController
from nautiboy.media import PreparedMedia, prepare_downloaded_gif, prepare_local_media
from nautiboy.last_active import LastActiveDisplay, LastActiveDisplayStore
from nautiboy.models import BUSY_STATES, AppState
from nautiboy.providers.giphy import GiphyProvider
from nautiboy.providers.base import SelectedGif
from nautiboy.profiles import (
    CREATIVE_PRESET_IDS,
    CREATIVE_PRESET_NAME_MAX_LENGTH,
    ProfileStore,
    ProfileStoreError,
    ProfileType,
)
from nautiboy.telemetry import (
    LinuxHwmonProvider,
    MAX_SELECTED_SENSORS,
    OrbitFrame,
    OrbitItem,
    TelemetryPoller,
    TelemetryPresentationError,
    TelemetryPresentationStore,
    TelemetrySnapshot,
)
from nautiboy.telemetry.orbit import OrbitTransferStats, phase_at, render_orbit_jpeg
from nautiboy.telemetry.providers.base import TelemetryProvider
from nautiboy.selected_media import (
    SelectedGiphyMedia,
    SelectedMediaStore,
    SelectedMediaStoreError,
)

from .gif_search_dialog import GifSearchDialog
from .orbit import ORBIT_PREVIEW_INTERVAL_MS, OrbitPlaybackController
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
    orbit_frame_requested = Signal(object)
    creative_frame_requested = Signal(object)
    rescan_requested = Signal()
    hidden_to_tray = Signal()
    tray_status_changed = Signal(str)
    shutdown_ready = Signal()
    telemetry_snapshot_ready = Signal(object)

    def __init__(
        self,
        *,
        profile_store: ProfileStore | None = None,
        telemetry_provider: TelemetryProvider | None = None,
        telemetry_store: TelemetryPresentationStore | None = None,
        selected_media_store: SelectedMediaStore | None = None,
        preferences: UserPreferences | None = None,
        last_active_store: LastActiveDisplayStore | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(760, 960)
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
        self._gif_profile_media: PreparedMedia | None = None
        self._session_touched_display = False
        self._close_pending = False
        self._close_to_tray = False
        self._quit_requested = False
        self._workers_stopped = False
        self._search_dialog: GifSearchDialog | None = None
        self._initial_send_jpeg: bytes | None = None
        supplied_profile_store = profile_store
        self._profile_store = profile_store or ProfileStore()
        self._profiles = self._profile_store.load()
        self._selected_media_store = selected_media_store or (
            SelectedMediaStore(self._profile_store.path.parent / "selected-media")
            if supplied_profile_store is not None
            else SelectedMediaStore()
        )
        self._preferences = preferences or UserPreferences()
        self._last_active_store = last_active_store or LastActiveDisplayStore(
            self._profile_store.path.parent / "last-active-display.json"
            if supplied_profile_store is not None else None
        )
        self._last_active_display = self._last_active_store.load()
        self._pending_active_display: LastActiveDisplay | None = None
        self._startup_resume_attempted = False
        self._telemetry_store = telemetry_store or TelemetryPresentationStore()
        self._telemetry_presentations = self._telemetry_store.load()
        self._telemetry_snapshot: TelemetrySnapshot | None = None
        self._telemetry_signature: tuple[tuple[str, tuple[str, ...]], ...] = ()
        self._telemetry_widgets: dict[str, dict[str, QWidget]] = {}
        self._orbit_preview_started = time.monotonic()
        self._orbit_playback = OrbitPlaybackController(self)
        self._orbit_measurements: list[OrbitTransferStats] = []
        self._orbit_measurement_started = 0.0
        self._orbit_playback.frame_requested.connect(self._queue_orbit_frame)
        self._creative_media: dict[str, PreparedMedia] = {}
        self._creative_preview_started = time.monotonic()
        self._creative_lcd_preset: dict | None = None
        self._creative_lcd_media: PreparedMedia | None = None
        self._creative_lcd_presentations: tuple = ()
        self._creative_measurements: list[OrbitTransferStats] = []
        self._creative_measurement_started = 0.0
        self._creative_playback = CreativePlaybackController(self)
        self._creative_playback.frame_requested.connect(self._queue_creative_frame)

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
        self.orbit_frame_requested.connect(self._worker.send_orbit_frame)
        self.creative_frame_requested.connect(self._worker.send_creative_frame)
        self._worker.configured.connect(self._backend_configured)
        self._worker.firmware_ready.connect(self._firmware_ready)
        self._worker.image_sent.connect(self._image_sent)
        self._worker.image_refreshed.connect(self._image_refreshed)
        self._worker.gif_frame_sent.connect(self._gif_frame_sent)
        self._worker.orbit_frame_sent.connect(self._orbit_frame_sent)
        self._worker.creative_frame_sent.connect(self._creative_frame_sent)
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
        self.telemetry_snapshot_ready.connect(self._apply_telemetry_snapshot)
        self._telemetry_provider = telemetry_provider or LinuxHwmonProvider()
        self._telemetry_poller = TelemetryPoller(
            [self._telemetry_provider], self.telemetry_snapshot_ready.emit
        )
        self._telemetry_poller.start()
        self._orbit_preview_timer = QTimer(self)
        self._orbit_preview_timer.setInterval(ORBIT_PREVIEW_INTERVAL_MS)
        self._orbit_preview_timer.timeout.connect(self._render_dynamic_preview)
        self._orbit_preview_timer.start()
        self._restore_gif_profile_selection()
        self._restore_last_active_ui_media()
        self._apply_profile_ui()

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
        self.thermals_panel = QWidget()
        thermals_layout = QVBoxLayout(self.thermals_panel)
        thermals_layout.setContentsMargins(0, 0, 0, 0)
        thermals_layout.setSpacing(8)
        thermals_title = QLabel("Select up to 2 temperatures to display")
        thermals_title.setObjectName("telemetryTitle")
        thermals_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thermals_layout.addWidget(thermals_title)
        self.telemetry_count = QLabel("Selected: 0 / 2")
        self.telemetry_count.setObjectName("telemetryCount")
        self.telemetry_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thermals_layout.addWidget(self.telemetry_count)
        self.telemetry_scroll = QScrollArea()
        self.telemetry_scroll.setObjectName("telemetryScroll")
        self.telemetry_scroll.setWidgetResizable(True)
        self.telemetry_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.telemetry_container = QWidget()
        self.telemetry_groups_layout = QVBoxLayout(self.telemetry_container)
        self.telemetry_groups_layout.setContentsMargins(0, 0, 0, 0)
        self.telemetry_groups_layout.setSpacing(8)
        self.telemetry_empty = QLabel("Discovering temperature sensors…")
        self.telemetry_empty.setObjectName("modePlaceholder")
        self.telemetry_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.telemetry_groups_layout.addWidget(self.telemetry_empty)
        self.telemetry_groups_layout.addStretch()
        self.telemetry_scroll.setWidget(self.telemetry_container)
        thermals_layout.addWidget(self.telemetry_scroll, 1)
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
        self.creative_scroll = QScrollArea()
        self.creative_scroll.setObjectName("creativeScroll")
        self.creative_scroll.setWidgetResizable(True)
        self.creative_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.creative_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.creative_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(2, 2, 2, 2)
        background_group = QGroupBox("Background")
        background_layout = QVBoxLayout(background_group)
        self.creative_select_button = QPushButton("Select JPEG, PNG, or GIF")
        self.creative_giphy_button = QPushButton("Search GIPHY")
        self.creative_media_info = QLabel("No background selected")
        self.creative_media_info.setWordWrap(True)
        self.creative_resize_combo = QComboBox()
        self.creative_resize_combo.addItem("Fit (Keep Aspect Ratio)", "fit")
        self.creative_resize_combo.addItem("Center Crop", "center-crop")
        background_layout.addWidget(self.creative_select_button)
        background_layout.addWidget(self.creative_giphy_button)
        background_layout.addWidget(self.creative_media_info)
        background_layout.addWidget(self.creative_resize_combo)
        editor_layout.addWidget(background_group)
        orbit_group = QGroupBox("Orbit perimeter")
        orbit_layout = QVBoxLayout(orbit_group)
        self.creative_orbit_enabled = QCheckBox("Enable Orbit")
        self.creative_orbit_animated = QCheckBox("Animate Orbit")
        self.creative_follow_colors = QCheckBox("Follow telemetry colors")
        color_row = QHBoxLayout()
        self.creative_primary_color = QPushButton("Primary Color")
        self.creative_secondary_color = QPushButton("Secondary Color")
        color_row.addWidget(self.creative_primary_color)
        color_row.addWidget(self.creative_secondary_color)
        orbit_layout.addWidget(self.creative_orbit_enabled)
        orbit_layout.addWidget(self.creative_orbit_animated)
        orbit_layout.addWidget(self.creative_follow_colors)
        orbit_layout.addLayout(color_row)
        editor_layout.addWidget(orbit_group)
        telemetry_group = QGroupBox("Telemetry foreground")
        telemetry_layout = QVBoxLayout(telemetry_group)
        self.creative_telemetry_enabled = QCheckBox("Enable Telemetry")
        self.creative_telemetry_summary = QLabel("No telemetry selected")
        self.creative_telemetry_summary.setWordWrap(True)
        self.creative_configure_telemetry = QPushButton("Configure in Thermals")
        telemetry_layout.addWidget(self.creative_telemetry_enabled)
        telemetry_layout.addWidget(self.creative_telemetry_summary)
        telemetry_layout.addWidget(self.creative_configure_telemetry)
        editor_layout.addWidget(telemetry_group)
        editor_layout.addStretch()
        self.creative_scroll.setWidget(editor)
        creative_layout.addWidget(self.creative_scroll, 1)
        actions.addLayout(select_row)
        actions.addWidget(self.mode_combo)
        actions.addWidget(self.send_button)
        actions.addWidget(self.mode_placeholder, 1)
        actions.addWidget(self.thermals_panel, 1)
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
        self.creative_select_button.clicked.connect(self._select_creative_media)
        self.creative_giphy_button.clicked.connect(self._open_creative_gif_search)
        self.creative_resize_combo.currentIndexChanged.connect(self._creative_settings_changed)
        self.creative_orbit_enabled.toggled.connect(self._creative_settings_changed)
        self.creative_orbit_animated.toggled.connect(self._creative_settings_changed)
        self.creative_follow_colors.toggled.connect(self._creative_settings_changed)
        self.creative_telemetry_enabled.toggled.connect(self._creative_settings_changed)
        self.creative_primary_color.clicked.connect(lambda: self._creative_color_requested("primary_color"))
        self.creative_secondary_color.clicked.connect(lambda: self._creative_color_requested("secondary_color"))
        self.creative_configure_telemetry.clicked.connect(lambda: self._switch_profile("thermals"))
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
        self._render_creative_preview()

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
        preset = presets[active]
        background = preset["background"]
        orbit = preset["orbit_overlay"]
        telemetry = preset["telemetry_overlay"]
        widgets = (
            self.creative_resize_combo, self.creative_orbit_enabled,
            self.creative_orbit_animated, self.creative_follow_colors,
            self.creative_telemetry_enabled,
        )
        for widget in widgets:
            widget.blockSignals(True)
        self.creative_resize_combo.setCurrentIndex(
            self.creative_resize_combo.findData(background["resize_strategy"])
        )
        self.creative_orbit_enabled.setChecked(orbit["enabled"])
        self.creative_orbit_animated.setChecked(orbit["animation_enabled"])
        self.creative_follow_colors.setChecked(orbit["follow_telemetry_colors"])
        self.creative_telemetry_enabled.setChecked(telemetry["enabled"])
        for widget in widgets:
            widget.blockSignals(False)
        self.creative_orbit_animated.setEnabled(orbit["enabled"])
        self.creative_follow_colors.setEnabled(orbit["enabled"])
        custom_colors = orbit["enabled"] and not orbit["follow_telemetry_colors"]
        self.creative_primary_color.setEnabled(custom_colors)
        self.creative_secondary_color.setEnabled(custom_colors)
        self.creative_primary_color.setStyleSheet(f"color: {orbit['primary_color']};")
        self.creative_secondary_color.setStyleSheet(f"color: {orbit['secondary_color']};")
        selected = self._telemetry_presentations.selected
        self.creative_telemetry_summary.setText(
            ", ".join(item.display_label for item in selected) if selected else "No telemetry selected"
        )
        media = self._creative_media.get(active)
        selected_slot = background.get("selected_giphy_slot")
        if media is None and selected_slot:
            selection = self._selected_media_store.load(selected_slot)
            if selection is not None:
                try:
                    media = self._prepare_persisted_selection(
                        selection, background["resize_strategy"]
                    )
                    self._creative_media[active] = media
                except ImageProcessingError:
                    media = None
        if media is None and background.get("source_path"):
            try:
                media = prepare_local_media(background["source_path"], background["resize_strategy"])
                self._creative_media[active] = media
            except ImageProcessingError:
                media = None
        attribution = (
            f" • {media.creator + ' • ' if media.creator else ''}{media.attribution}"
            if media and media.attribution else ""
        )
        self.creative_media_info.setText(
            f"{media.title} • {'Animated GIF' if media and media.animated else 'Static image'}{attribution}"
            if media else ("Saved media unavailable" if background.get("source_path") else "No background selected")
        )

    def _active_creative_preset(self) -> dict:
        settings = self._profiles.profile(ProfileType.CREATIVE.value).settings
        return next(item for item in settings["presets"] if item["id"] == settings["active_preset_id"])

    @Slot()
    def _select_creative_media(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Creative background", str(Path.home()),
            "Media (*.jpg *.jpeg *.png *.gif)",
        )
        if not filename:
            return
        preset = self._active_creative_preset()
        strategy = str(self.creative_resize_combo.currentData())
        try:
            media = prepare_local_media(filename, strategy)
        except ImageProcessingError as error:
            self._message(str(error))
            return
        self._creative_media[preset["id"]] = media
        selected_slot = preset["background"].get("selected_giphy_slot")
        if selected_slot:
            try:
                self._selected_media_store.remove(selected_slot)
            except SelectedMediaStoreError as error:
                self._message(str(error))
        try:
            self._profile_store.update_creative_preset(
                self._profiles, preset["id"], "background",
                {"media_kind": "gif" if media.gif else "image", "source_path": filename,
                 "selected_giphy_slot": None,
                 "resize_strategy": strategy},
            )
        except ProfileStoreError as error:
            self._message(str(error))
        self._apply_creative_preset_ui()
        self._render_creative_preview()

    @Slot()
    def _open_creative_gif_search(self) -> None:
        """Reuse the provider-neutral GIF search for the active Creative preset."""
        dialog = GifSearchDialog(GiphyProvider(), self)
        self._search_dialog = dialog
        dialog.media_selected.connect(self._creative_online_gif_selected)
        dialog.exec()
        self._search_dialog = None

    @Slot(object)
    def _creative_online_gif_selected(self, selection: SelectedGif | bytes, title: str | None = None) -> None:
        if self._profiles.active_profile_id != ProfileType.CREATIVE.value:
            self._message("Creative GIPHY selection is available only in Creative mode")
            return
        preset = self._active_creative_preset()
        chosen = self._coerce_selected_gif(selection, title)
        try:
            media = prepare_downloaded_gif(
                chosen.data, chosen.title, preset["background"]["resize_strategy"],
                creator=chosen.creator, source_url=chosen.source_url,
                attribution=chosen.attribution,
            )
        except ImageProcessingError as error:
            self._message(str(error))
            return
        self._creative_media[preset["id"]] = media
        slot = f"creative-{preset['id']}"
        try:
            self._selected_media_store.save(slot, chosen)
            self._profile_store.update_creative_preset(
                self._profiles, preset["id"], "background",
                {"media_kind": "gif", "source_path": None, "selected_giphy_slot": slot},
            )
        except (ProfileStoreError, SelectedMediaStoreError) as error:
            self._message(str(error))
        self._apply_creative_preset_ui()
        self._render_creative_preview()
        self._message(f"Prepared GIPHY background: {chosen.title}")

    @Slot()
    def _creative_settings_changed(self) -> None:
        preset = self._active_creative_preset()
        try:
            self._profile_store.update_creative_preset(
                self._profiles, preset["id"], "background",
                {"resize_strategy": str(self.creative_resize_combo.currentData())},
            )
            self._profile_store.update_creative_preset(
                self._profiles, preset["id"], "orbit_overlay",
                {"enabled": self.creative_orbit_enabled.isChecked(),
                 "animation_enabled": self.creative_orbit_animated.isChecked(),
                 "follow_telemetry_colors": self.creative_follow_colors.isChecked()},
            )
            self._profile_store.update_creative_preset(
                self._profiles, preset["id"], "telemetry_overlay",
                {"enabled": self.creative_telemetry_enabled.isChecked()},
            )
        except ProfileStoreError as error:
            self._message(str(error))
        self._apply_creative_preset_ui()
        self._render_creative_preview()

    def _creative_color_requested(self, field: str) -> None:
        preset = self._active_creative_preset()
        current = preset["orbit_overlay"][field]
        chosen = QColorDialog.getColor(QColor(current), self, "Orbit Color")
        if not chosen.isValid():
            return
        try:
            self._profile_store.update_creative_preset(
                self._profiles, preset["id"], "orbit_overlay", {field: chosen.name().upper()}
            )
        except ProfileStoreError as error:
            self._message(str(error))
        self._apply_creative_preset_ui()
        self._render_creative_preview()

    @Slot(object)
    def _apply_telemetry_snapshot(self, snapshot: TelemetrySnapshot) -> None:
        self._telemetry_snapshot = snapshot
        signature = tuple(
            (
                device.device_id,
                tuple(
                    reading.sensor.sensor_id
                    for reading in snapshot.readings
                    if reading.sensor.device_id == device.device_id
                ),
            )
            for device in snapshot.devices
            if any(reading.sensor.device_id == device.device_id for reading in snapshot.readings)
        )
        for reading in snapshot.readings:
            self._telemetry_store.ensure_sensor(
                self._telemetry_presentations,
                reading.sensor.sensor_id,
                reading.sensor.default_label[:24],
            )
        if signature != self._telemetry_signature:
            self._telemetry_signature = signature
            self._rebuild_telemetry_groups()
        self._update_telemetry_controls()
        self._render_dynamic_preview()

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child = item.layout()
            if child is not None:
                self._clear_layout(child)  # type: ignore[arg-type]

    def _rebuild_telemetry_groups(self) -> None:
        self._clear_layout(self.telemetry_groups_layout)
        self._telemetry_widgets.clear()
        snapshot = self._telemetry_snapshot
        if snapshot is None or not snapshot.readings:
            self.telemetry_empty = QLabel("No readable temperature sensors found")
            self.telemetry_empty.setObjectName("modePlaceholder")
            self.telemetry_groups_layout.addWidget(self.telemetry_empty)
            self.telemetry_groups_layout.addStretch()
            return
        for device in snapshot.devices:
            readings = [
                reading for reading in snapshot.readings if reading.sensor.device_id == device.device_id
            ]
            if not readings:
                continue
            group = QGroupBox(device.display_name)
            group.setObjectName("telemetryDeviceGroup")
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(5)
            for reading in readings:
                sensor = reading.sensor
                row = QFrame()
                row.setObjectName("telemetrySensorRow")
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(7, 6, 7, 6)
                row_layout.setSpacing(5)
                top = QHBoxLayout()
                select = QCheckBox(sensor.raw_label or sensor.default_label)
                select.setToolTip(sensor.sensor_id)
                value = QLabel()
                value.setObjectName("telemetryValue")
                top.addWidget(select)
                top.addStretch()
                top.addWidget(value)
                row_layout.addLayout(top)
                editor = QHBoxLayout()
                label = QLineEdit()
                label.setMaxLength(24)
                label.setPlaceholderText("Display label")
                color = QPushButton("Color")
                color.setObjectName("telemetryColorButton")
                editor.addWidget(label, 1)
                editor.addWidget(color)
                row_layout.addLayout(editor)
                select.toggled.connect(
                    lambda checked, sensor_id=sensor.sensor_id: self._telemetry_selection_changed(
                        sensor_id, checked
                    )
                )
                label.editingFinished.connect(
                    lambda sensor_id=sensor.sensor_id, field=label: self._telemetry_label_changed(
                        sensor_id, field
                    )
                )
                color.clicked.connect(
                    lambda _checked=False, sensor_id=sensor.sensor_id: self._telemetry_color_requested(
                        sensor_id
                    )
                )
                self._telemetry_widgets[sensor.sensor_id] = {
                    "select": select,
                    "value": value,
                    "label": label,
                    "color": color,
                }
                group_layout.addWidget(row)
            self.telemetry_groups_layout.addWidget(group)
        self.telemetry_groups_layout.addStretch()

    def _update_telemetry_controls(self) -> None:
        selected_count = len(self._telemetry_presentations.selected)
        self.telemetry_count.setText(f"Selected: {selected_count} / {MAX_SELECTED_SENSORS}")
        readings = {
            reading.sensor.sensor_id: reading
            for reading in (self._telemetry_snapshot.readings if self._telemetry_snapshot else ())
        }
        for sensor_id, widgets in self._telemetry_widgets.items():
            presentation = self._telemetry_presentations.sensor(sensor_id)
            checkbox = widgets["select"]
            assert isinstance(checkbox, QCheckBox)
            checkbox.blockSignals(True)
            checkbox.setChecked(presentation.enabled)
            checkbox.blockSignals(False)
            checkbox.setEnabled(presentation.enabled or selected_count < MAX_SELECTED_SENSORS)
            label = widgets["label"]
            assert isinstance(label, QLineEdit)
            if not label.hasFocus():
                label.setText(presentation.display_label)
            label.setEnabled(presentation.enabled)
            color = widgets["color"]
            assert isinstance(color, QPushButton)
            color.setEnabled(presentation.enabled)
            color.setStyleSheet(f"color: {presentation.font_color};")
            value = widgets["value"]
            assert isinstance(value, QLabel)
            reading = readings.get(sensor_id)
            value.setText(
                f"{reading.value:.1f} °C"
                if reading is not None and reading.value is not None
                else (reading.availability.value.title() if reading is not None else "Unavailable")
            )

    @Slot(str, bool)
    def _telemetry_selection_changed(self, sensor_id: str, selected: bool) -> None:
        try:
            self._telemetry_store.set_selected(
                self._telemetry_presentations, sensor_id, selected
            )
        except (ValueError, TelemetryPresentationError) as error:
            self._message(str(error))
        self._update_telemetry_controls()
        self._render_orbit_preview()

    def _telemetry_label_changed(self, sensor_id: str, field: QLineEdit) -> None:
        try:
            self._telemetry_store.set_label(
                self._telemetry_presentations, sensor_id, field.text()
            )
        except (ValueError, TelemetryPresentationError) as error:
            self._message(str(error))
        self._update_telemetry_controls()
        self._render_orbit_preview()

    def _telemetry_color_requested(self, sensor_id: str) -> None:
        presentation = self._telemetry_presentations.sensor(sensor_id)
        chosen = QColorDialog.getColor(QColor(presentation.font_color), self, "Telemetry Font Color")
        if not chosen.isValid():
            return
        try:
            self._telemetry_store.set_color(
                self._telemetry_presentations, sensor_id, chosen.name().upper()
            )
        except (ValueError, TelemetryPresentationError) as error:
            self._message(str(error))
        self._update_telemetry_controls()
        self._render_orbit_preview()

    def _orbit_frame(self, phase: float) -> OrbitFrame | None:
        selected = self._telemetry_presentations.selected
        if not selected:
            return None
        readings = {
            reading.sensor.sensor_id: reading
            for reading in (self._telemetry_snapshot.readings if self._telemetry_snapshot else ())
        }
        items = []
        for presentation in selected:
            reading = readings.get(presentation.sensor_id)
            items.append(
                OrbitItem(
                    presentation.display_label,
                    reading.value if reading is not None else None,
                    presentation.font_color,
                    reading.availability.value if reading is not None else "unavailable",
                )
            )
        return OrbitFrame(tuple(items), phase)

    def _creative_items(self, presentations=None) -> tuple[OrbitItem, ...]:
        selected = presentations if presentations is not None else self._telemetry_presentations.selected
        readings = {
            reading.sensor.sensor_id: reading
            for reading in (self._telemetry_snapshot.readings if self._telemetry_snapshot else ())
        }
        return tuple(
            OrbitItem(
                item.display_label,
                readings[item.sensor_id].value if item.sensor_id in readings else None,
                item.font_color,
                readings[item.sensor_id].availability.value if item.sensor_id in readings else "unavailable",
            )
            for item in selected[:2]
        )

    def _creative_composition(self, preset: dict, phase: float, presentations=None) -> CreativeComposition:
        orbit = preset["orbit_overlay"]
        telemetry = preset["telemetry_overlay"]
        return CreativeComposition(
            None, self._creative_items(presentations), telemetry["enabled"], orbit["enabled"],
            orbit["animation_enabled"], orbit["follow_telemetry_colors"],
            orbit["primary_color"], orbit["secondary_color"], phase,
        )

    def _creative_background(self, media: PreparedMedia | None, strategy: str, index: int = 0):
        if media is None:
            return None
        if media.gif is not None:
            return media.gif.render_frame(index, strategy)[0]
        if media.static_jpeg is not None:
            with Image.open(io.BytesIO(media.static_jpeg)) as image:
                return image.convert("RGB").copy()
        return None

    @Slot()
    def _render_dynamic_preview(self) -> None:
        if self._profiles.active_profile_id == ProfileType.THERMALS.value:
            self._render_orbit_preview()
        elif self._profiles.active_profile_id == ProfileType.CREATIVE.value:
            self._render_creative_preview()

    def _render_creative_preview(self) -> None:
        if self._profiles.active_profile_id != ProfileType.CREATIVE.value:
            return
        preset = self._active_creative_preset()
        media = self._creative_media.get(preset["id"])
        elapsed = max(0.0, time.monotonic() - self._creative_preview_started)
        index = 0
        if media is not None and media.gif is not None:
            position = int(elapsed * 1000) % media.gif.duration_ms
            total = 0
            for candidate, duration in enumerate(media.gif.durations_ms):
                total += duration
                if position < total:
                    index = candidate
                    break
        phase = phase_at(time.monotonic(), self._creative_preview_started)
        try:
            background = self._creative_background(
                media, preset["background"]["resize_strategy"], index
            )
            jpeg = compose_creative_jpeg(
                CreativeComposition(
                    background,
                    self._creative_items(),
                    preset["telemetry_overlay"]["enabled"],
                    preset["orbit_overlay"]["enabled"],
                    preset["orbit_overlay"]["animation_enabled"],
                    preset["orbit_overlay"]["follow_telemetry_colors"],
                    preset["orbit_overlay"]["primary_color"],
                    preset["orbit_overlay"]["secondary_color"],
                    phase,
                )
            )
        except (ImageProcessingError, ValueError) as error:
            self.preview.setText("Creative preview unavailable")
            self._message(str(error))
            return
        pixmap = QPixmap()
        pixmap.loadFromData(jpeg, "JPEG")
        self.preview.setPixmap(pixmap.scaled(330, 330, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
        layers = ["Background" if media else "Black background"]
        if preset["orbit_overlay"]["enabled"]:
            layers.append("Orbit")
        if preset["telemetry_overlay"]["enabled"]:
            layers.append("Telemetry")
        self.preview_caption.setText("CREATIVE  •  " + " + ".join(layers) + "  •  480 × 480")

    @Slot()
    def _render_orbit_preview(self) -> None:
        if self._profiles.active_profile_id != ProfileType.THERMALS.value:
            return
        frame = self._orbit_frame(phase_at(time.monotonic(), self._orbit_preview_started))
        if frame is None:
            self.preview.clear()
            self.preview.setText("Select up to 2 temperatures")
            self.preview_caption.setText("ORBIT PREVIEW  •  480 × 480")
            return
        pixmap = QPixmap()
        pixmap.loadFromData(render_orbit_jpeg(frame), "JPEG")
        self.preview.setPixmap(
            pixmap.scaled(330, 330, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        self.preview_caption.setText("ORBIT  •  LIVE PREVIEW  •  480 × 480")

    @Slot(float)
    def _queue_orbit_frame(self, phase: float) -> None:
        frame = self._orbit_frame(phase)
        if frame is None:
            self._orbit_playback.stop()
            self._operation_failed("thermals", "no telemetry item is selected")
            return
        self.orbit_frame_requested.emit(frame)

    def _clear_selected_media(self) -> None:
        self._selected_path = None
        self._online_gif_data = None
        self._selected_media = None
        self._prepared_jpeg = None
        self._stop_preview()
        self.preview.clear()
        self.preview.setText("Select media for this mode")
        self.preview_caption.setText("PREVIEW  •  480 × 480")

    @staticmethod
    def _coerce_selected_gif(
        selection: SelectedGif | bytes, title: str | None = None
    ) -> SelectedGiphyMedia:
        if isinstance(selection, SelectedGif):
            result = selection.result
            return SelectedGiphyMedia(
                selection.data, result.title, result.provider, result.identifier,
                result.creator, result.source_url, selection.attribution,
            )
        return SelectedGiphyMedia(selection, title or "Selected GIPHY GIF")

    @staticmethod
    def _prepare_persisted_selection(
        selection: SelectedGiphyMedia, strategy: ResizeStrategy | str
    ) -> PreparedMedia:
        return prepare_downloaded_gif(
            selection.data, selection.title, strategy, creator=selection.creator,
            source_url=selection.source_url, attribution=selection.attribution,
        )

    def _restore_gif_profile_selection(self) -> None:
        settings = self._profiles.profile(ProfileType.GIF.value).settings
        slot = settings.get("selected_giphy_slot")
        if slot != "gif-profile":
            return
        selection = self._selected_media_store.load(slot)
        if selection is None:
            return
        try:
            media = self._prepare_persisted_selection(selection, settings["resize_strategy"])
        except ImageProcessingError:
            return
        self._online_gif_data = selection.data
        self._selected_path = None
        self._gif_profile_media = media
        if self._profiles.active_profile_id == ProfileType.GIF.value:
            self._set_selected_media(media)

    def _load_display_media(self, display: LastActiveDisplay) -> PreparedMedia | None:
        reference = display.media
        if reference is None or display.resize_strategy is None:
            return None
        try:
            if reference["kind"] == "local":
                return prepare_local_media(reference["path"], display.resize_strategy)
            selection = self._selected_media_store.load(reference["slot"])
            return (
                self._prepare_persisted_selection(selection, display.resize_strategy)
                if selection is not None else None
            )
        except (ImageProcessingError, KeyError, ValueError):
            return None

    def _restore_last_active_ui_media(self) -> None:
        display = self._last_active_display
        if display is None or display.mode != self._profiles.active_profile_id:
            return
        if display.mode not in {ProfileType.IMAGE.value, ProfileType.GIF.value}:
            return
        media = self._load_display_media(display)
        if media is None:
            return
        self._selected_media = media
        self._prepared_jpeg = media.static_jpeg or media.preview_jpeg
        if display.media and display.media["kind"] == "local":
            self._selected_path = Path(display.media["path"])
        else:
            self._online_gif_data = media.gif.data if media.gif else None
            self._gif_profile_media = media
        self._set_selected_media(media)

    def _media_reference(self, *, creative_preset: dict | None = None) -> dict | None:
        if creative_preset is not None:
            background = creative_preset["background"]
            if background.get("selected_giphy_slot"):
                return {"kind": "giphy", "slot": background["selected_giphy_slot"]}
            if background.get("source_path"):
                return {"kind": "local", "path": background["source_path"]}
            return None
        if self._selected_path is not None:
            return {"kind": "local", "path": str(self._selected_path)}
        if self._profiles.profile(ProfileType.GIF.value).settings.get("selected_giphy_slot"):
            return {"kind": "giphy", "slot": "gif-profile"}
        return None

    def _active_display_candidate(self, mode: ProfileType) -> LastActiveDisplay:
        if mode is ProfileType.CREATIVE:
            preset = deepcopy(self._active_creative_preset())
            return LastActiveDisplay(
                mode.value, preset["background"]["resize_strategy"],
                self._media_reference(creative_preset=preset), preset["id"], preset,
            )
        if mode in {ProfileType.IMAGE, ProfileType.GIF}:
            reference = (
                {"kind": "local", "path": str(self._selected_path)}
                if mode is ProfileType.IMAGE and self._selected_path is not None
                else self._media_reference()
            )
            return LastActiveDisplay(
                mode.value, str(self.mode_combo.currentData()), reference
            )
        return LastActiveDisplay(mode.value)

    def _record_successful_active_display(self) -> None:
        if self._pending_active_display is None:
            return
        display = self._pending_active_display
        try:
            if display.media and display.media.get("kind") == "giphy":
                active_media = (
                    self._creative_lcd_media
                    if display.mode == ProfileType.CREATIVE.value
                    else self._selected_media
                )
                if active_media is None or active_media.gif is None:
                    raise RuntimeError("cannot preserve active GIPHY media")
                self._selected_media_store.save(
                    "last-active-display",
                    SelectedGiphyMedia(
                        active_media.gif.data, active_media.title,
                        creator=active_media.creator, source_url=active_media.source_url,
                        attribution=active_media.attribution or "Powered by GIPHY",
                    ),
                )
                display = replace(
                    display, media={"kind": "giphy", "slot": "last-active-display"}
                )
            self._last_active_store.save(display)
        except (RuntimeError, SelectedMediaStoreError) as error:
            self._message(str(error))
            return
        self._last_active_display = display
        self._pending_active_display = None

    def _attempt_startup_resume(self) -> None:
        if self._startup_resume_attempted or self._identity is None:
            return
        self._startup_resume_attempted = True
        if not self._preferences.resume_last_display() or self._last_active_display is None:
            return
        display = self._last_active_display
        try:
            if display.mode in {ProfileType.IMAGE.value, ProfileType.GIF.value}:
                media = self._load_display_media(display)
                if media is None:
                    raise ValueError("saved media is unavailable or invalid")
                self._pending_active_display = display
                self._start_media_display(media, display.resize_strategy or "fit")
            elif display.mode == ProfileType.THERMALS.value:
                if self._orbit_frame(0.0) is None:
                    raise ValueError("saved telemetry selection is unavailable")
                self._pending_active_display = display
                self._session_touched_display = True
                self._set_state(AppState.SENDING)
                self._orbit_measurements.clear()
                self._orbit_measurement_started = time.monotonic()
                self._orbit_playback.start()
            elif display.mode == ProfileType.CREATIVE.value:
                preset = deepcopy(display.creative_settings)
                if not isinstance(preset, dict) or preset.get("id") != display.creative_preset_id:
                    raise ValueError("saved Creative state is invalid")
                media = self._load_display_media(display) if display.media else None
                if display.media and media is None:
                    raise ValueError("saved Creative media is unavailable or invalid")
                self._pending_active_display = display
                self._start_creative_display(preset, media)
            else:
                return
            self._message(f"Resuming last {display.mode} display…")
        except (KeyError, TypeError, ValueError) as error:
            self._pending_active_display = None
            self._message(f"Last display was not resumed: {error}")

    def _start_media_display(self, media: PreparedMedia, strategy: str) -> None:
        self._refresher.stop()
        self._gif_playback.stop()
        self._orbit_playback.stop()
        self._creative_playback.stop()
        self._session_touched_display = True
        self._set_state(AppState.SENDING)
        if media.animated and media.gif is not None:
            self._lcd_gif = media.gif
            self._lcd_strategy = strategy
            self._initial_send_jpeg = None
            self._gif_playback.start(self._lcd_gif)
        else:
            self._lcd_gif = None
            self._initial_send_jpeg = media.static_jpeg or media.preview_jpeg
            self.send_requested.emit(self._initial_send_jpeg)

    def _start_creative_display(self, preset: dict, media: PreparedMedia | None) -> None:
        if (media is None and not preset["orbit_overlay"]["enabled"]
                and not preset["telemetry_overlay"]["enabled"]):
            raise ValueError("saved Creative display has no content")
        self._refresher.stop()
        self._gif_playback.stop()
        self._orbit_playback.stop()
        self._creative_playback.stop()
        self._creative_lcd_preset = deepcopy(preset)
        self._creative_lcd_media = media
        self._creative_lcd_presentations = tuple(deepcopy(self._telemetry_presentations.selected))
        self._creative_measurements = []
        self._creative_measurement_started = time.monotonic()
        self._session_touched_display = True
        self._set_state(AppState.SENDING)
        dynamic = bool(media and media.animated) or (
            preset["orbit_overlay"]["enabled"] and preset["orbit_overlay"]["animation_enabled"]
        ) or preset["telemetry_overlay"]["enabled"]
        if dynamic:
            self._creative_playback.start(
                media.gif if media else None,
                orbit_animated=(preset["orbit_overlay"]["enabled"]
                                and preset["orbit_overlay"]["animation_enabled"]),
                telemetry_enabled=preset["telemetry_overlay"]["enabled"],
            )
            return
        background = self._creative_background(media, preset["background"]["resize_strategy"])
        self._initial_send_jpeg = compose_creative_jpeg(
            replace(self._creative_composition(preset, 0.0), background=background)
        )
        self.send_requested.emit(self._initial_send_jpeg)

    def _apply_profile_ui(self) -> None:
        active = ProfileType(self._profiles.active_profile_id)
        for identifier, button in self.profile_buttons.items():
            button.setChecked(identifier == active.value)
        media_mode = active in {ProfileType.IMAGE, ProfileType.GIF}
        gif_mode = active is ProfileType.GIF
        self.select_button.setVisible(media_mode)
        self.gif_search_button.setVisible(gif_mode)
        self.mode_combo.setVisible(media_mode)
        self.send_button.setVisible(media_mode or active in {ProfileType.THERMALS, ProfileType.CREATIVE})
        creative_mode = active is ProfileType.CREATIVE
        self.mode_placeholder.setVisible(False)
        self.thermals_panel.setVisible(active is ProfileType.THERMALS)
        self.creative_panel.setVisible(creative_mode)
        if active is ProfileType.IMAGE:
            self.select_button.setText("Select Image")
        elif active is ProfileType.GIF:
            self.select_button.setText("Select GIF")
        elif active is ProfileType.THERMALS:
            self.send_button.setText("Send Thermals to LCD")
            self._render_orbit_preview()
        if creative_mode:
            self.send_button.setText("Send Creative to LCD")
            self._apply_creative_preset_ui()
            self._render_creative_preview()
        if media_mode:
            strategy = self._profiles.profile(active.value).settings["resize_strategy"]
            combo_index = self.mode_combo.findData(strategy)
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(combo_index)
            self.mode_combo.blockSignals(False)
            if active is ProfileType.GIF and self._gif_profile_media is not None:
                self._set_selected_media(self._gif_profile_media)
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
        if self._profiles.active_profile_id == ProfileType.THERMALS.value:
            self.send_button.setEnabled(
                state in {AppState.READY, AppState.DISPLAYING}
                and self._identity is not None
                and bool(self._telemetry_presentations.selected)
            )
        elif self._profiles.active_profile_id == ProfileType.CREATIVE.value:
            preset = self._active_creative_preset()
            has_content = (
                preset["id"] in self._creative_media
                or preset["orbit_overlay"]["enabled"]
                or (preset["telemetry_overlay"]["enabled"] and bool(self._telemetry_presentations.selected))
            )
            self.send_button.setText("Send Creative to LCD")
            self.send_button.setEnabled(
                state in {AppState.READY, AppState.DISPLAYING}
                and self._identity is not None and has_content
            )
        else:
            self.send_button.setText("Send to LCD")
        self.restore_button.setEnabled(policy.restore)
        self.tray_status_changed.emit(self.playback_status())

    def playback_status(self) -> str:
        if not self._session_touched_display:
            return "Hardware mode"
        if self._gif_playback.active:
            return "GIF playing"
        if self._orbit_playback.active:
            return "Thermals playing"
        if self._creative_playback.active:
            return "Creative playing"
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
            self._orbit_playback.stop()
            self._creative_playback.stop()
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
            active = (self._refresher.active or self._gif_playback.active
                      or self._orbit_playback.active or self._creative_playback.active)
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
        self._attempt_startup_resume()

    @Slot(str, str)
    def _operation_failed(self, action: str, message: str) -> None:
        self._refresher.stop()
        self._gif_playback.stop()
        self._orbit_playback.stop()
        self._creative_playback.stop()
        self._creative_lcd_preset = None
        self._creative_lcd_media = None
        self._creative_lcd_presentations = ()
        self._initial_send_jpeg = None
        self._pending_active_display = None
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
            if active is ProfileType.GIF:
                try:
                    self._selected_media_store.remove("gif-profile")
                    self._profile_store.set_gif_selection_slot(self._profiles, None)
                except (SelectedMediaStoreError, ProfileStoreError) as error:
                    self._message(str(error))
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
                        creator=self._selected_media.creator,
                        source_url=self._selected_media.source_url,
                        attribution=self._selected_media.attribution or "Powered by GIPHY",
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
            + (
                f"\n{media.creator + ' • ' if media.creator else ''}{media.attribution}"
                if media.attribution else ""
            )
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

    @Slot(object)
    def _online_gif_selected(self, selection: SelectedGif | bytes, title: str | None = None) -> None:
        if self._profiles.active_profile_id != ProfileType.GIF.value:
            self._message("Online GIF selection is available only in GIF mode")
            return
        chosen = self._coerce_selected_gif(selection, title)
        try:
            media = self._prepare_persisted_selection(chosen, self.mode_combo.currentData())
        except ImageProcessingError as error:
            self._message(str(error))
            self._set_state(state_after_image_error(has_device=self._identity is not None))
            return
        self._selected_path = None
        self._online_gif_data = chosen.data
        self._gif_profile_media = media
        try:
            self._selected_media_store.save("gif-profile", chosen)
            self._profile_store.set_gif_selection_slot(self._profiles, "gif-profile")
        except (SelectedMediaStoreError, ProfileStoreError) as error:
            self._message(str(error))
        self._set_selected_media(media)
        self._message(f"Prepared GIPHY GIF: {chosen.title}")
        if self._identity is not None:
            self._set_state(AppState.DISPLAYING if self._session_touched_display else AppState.READY)

    @Slot()
    def _send(self) -> None:
        active = ProfileType(self._profiles.active_profile_id)
        if active is ProfileType.THERMALS:
            if self._identity is None or self._orbit_frame(0.0) is None:
                return
            self._refresher.stop()
            self._gif_playback.stop()
            self._creative_playback.stop()
            self._pending_active_display = self._active_display_candidate(active)
            self._session_touched_display = True
            self._set_state(AppState.SENDING)
            self._message("Starting volatile Orbit thermals…")
            self._orbit_measurements.clear()
            self._orbit_measurement_started = time.monotonic()
            self._orbit_playback.start()
            return
        if active is ProfileType.CREATIVE:
            if self._identity is None:
                return
            preset = deepcopy(self._active_creative_preset())
            media = self._creative_media.get(preset["id"])
            if (media is None and not preset["orbit_overlay"]["enabled"]
                    and not preset["telemetry_overlay"]["enabled"]):
                return
            self._pending_active_display = self._active_display_candidate(active)
            self._message("Starting volatile Creative playback…")
            self._start_creative_display(preset, media)
            return
        if self._selected_media is None or self._prepared_jpeg is None or self._identity is None:
            return
        self._pending_active_display = self._active_display_candidate(active)
        self._message(
            "Starting volatile GIF playback…" if self._selected_media.animated
            else "Sending one volatile image…"
        )
        self._start_media_display(self._selected_media, str(self.mode_combo.currentData()))

    @Slot(int)
    def _image_sent(self, report_count: int) -> None:
        if self._initial_send_jpeg is None:
            self._operation_failed("send", "completed without a prepared refresh image")
            return
        self._refresher.start_after_initial_success(self._initial_send_jpeg)
        self._record_successful_active_display()
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
            self._record_successful_active_display()
            self._message(f"GIF playback started ({report_count} reports)")

    @Slot(object)
    def _orbit_frame_sent(self, stats: OrbitTransferStats) -> None:
        first = self._state is AppState.SENDING
        self._orbit_playback.transfer_completed()
        self._orbit_measurements.append(stats)
        self._set_state(AppState.DISPLAYING)
        if first:
            self._record_successful_active_display()
            self._message(
                f"Orbit thermals started ({stats.report_count} reports, {stats.jpeg_bytes} bytes, "
                f"{stats.total_seconds * 1000:.1f} ms total)"
            )
        elif len(self._orbit_measurements) % 10 == 0:
            elapsed = max(time.monotonic() - self._orbit_measurement_started, 0.001)
            recent = self._orbit_measurements[-10:]
            average = lambda field: sum(getattr(item, field) for item in recent) / len(recent)
            self._message(
                f"Orbit: {len(self._orbit_measurements) / elapsed:.1f} FPS achieved; "
                f"render {average('render_seconds') * 1000:.1f} ms; "
                f"JPEG {average('encode_seconds') * 1000:.1f} ms / "
                f"{average('jpeg_bytes') / 1024:.1f} KiB; "
                f"HID {average('transfer_seconds') * 1000:.1f} ms; "
                f"coalesced {self._orbit_playback.dropped_frames}"
            )

    @Slot(float, int)
    def _queue_creative_frame(self, phase: float, gif_index: int) -> None:
        preset = self._creative_lcd_preset
        if preset is None:
            self._creative_playback.stop()
            return
        media = self._creative_lcd_media
        static_background = None
        gif_document = media.gif if media and media.gif else None
        if media is not None and gif_document is None:
            static_background = self._creative_background(
                media, preset["background"]["resize_strategy"]
            )
        self.creative_frame_requested.emit(
            CreativeFrameRequest(
                self._creative_composition(preset, phase, self._creative_lcd_presentations), static_background,
                gif_document, gif_index, preset["background"]["resize_strategy"],
            )
        )

    @Slot(object)
    def _creative_frame_sent(self, stats: OrbitTransferStats) -> None:
        first = self._state is AppState.SENDING
        self._creative_playback.transfer_completed()
        self._creative_measurements.append(stats)
        self._set_state(AppState.DISPLAYING)
        if first:
            self._record_successful_active_display()
            self._message(
                f"Creative playback started ({stats.report_count} reports, "
                f"{stats.total_seconds * 1000:.1f} ms)"
            )

    def _report_creative_measurements(self) -> None:
        measurements = self._creative_measurements
        if not measurements:
            return
        elapsed = max(time.monotonic() - self._creative_measurement_started, 0.001)

        def summary(field: str, scale: float = 1.0) -> str:
            values = [getattr(item, field) * scale for item in measurements]
            return f"{min(values):.1f}/{sum(values) / len(values):.1f}/{max(values):.1f}"

        report_counts = [item.report_count for item in measurements]
        self._message(
            f"Creative validation: {len(measurements) / elapsed:.2f} FPS; "
            f"render min/avg/max {summary('render_seconds', 1000)} ms; "
            f"JPEG {summary('encode_seconds', 1000)} ms, "
            f"{summary('jpeg_bytes', 1 / 1024)} KiB; "
            f"HID {summary('transfer_seconds', 1000)} ms; "
            f"generation-to-send {summary('total_seconds', 1000)} ms; "
            f"reports {min(report_counts)}/{sum(report_counts) / len(report_counts):.1f}/"
            f"{max(report_counts)}; frames {len(measurements)}; "
            f"coalesced {self._creative_playback.dropped_frames}"
        )

    @Slot(int)
    def _image_refreshed(self, _report_count: int) -> None:
        self._refresher.transfer_completed()

    @Slot()
    def _restore(self) -> None:
        if self._identity is None or not self._session_touched_display:
            return
        self._refresher.stop()
        self._gif_playback.stop()
        self._orbit_playback.stop()
        self._report_creative_measurements()
        self._creative_playback.stop()
        self._creative_lcd_preset = None
        self._creative_lcd_media = None
        self._creative_lcd_presentations = ()
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
        self._orbit_playback.stop()
        self._creative_playback.stop()
        self._creative_lcd_preset = None
        self._creative_lcd_media = None
        self._creative_lcd_presentations = ()
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
        self._telemetry_poller.stop()
        self._orbit_preview_timer.stop()
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
        self._orbit_playback.stop()
        self._creative_playback.stop()
        self._creative_lcd_preset = None
        self._creative_lcd_media = None
        self._creative_lcd_presentations = ()
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
    OrbitFrame,
    OrbitItem,
