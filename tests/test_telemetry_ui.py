from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QGroupBox, QLineEdit, QPushButton

from nautiboy.gui import main_window
from nautiboy.profiles import ProfileStore
from nautiboy.telemetry import (
    Availability,
    Metric,
    SemanticRole,
    TelemetryDevice,
    TelemetryInventory,
    TelemetryPresentationStore,
    TelemetryReading,
    TelemetrySensor,
    TelemetrySnapshot,
    Unit,
)


class StaticTelemetryProvider:
    provider_id = "fake"

    def __init__(self) -> None:
        self.devices = (
            TelemetryDevice("fake:cpu", "fake", "cpu", "k10temp", "k10temp", "pci", "0", "CPU"),
            TelemetryDevice("fake:gpu", "fake", "gpu", "amdgpu", "amdgpu", "pci", "1", "Discrete GPU"),
        )
        self.sensors = (
            self._sensor("fake:cpu:temp1", "fake:cpu", "Tctl", SemanticRole.CPU_PACKAGE, "CPU"),
            self._sensor("fake:cpu:temp2", "fake:cpu", "Tccd1", SemanticRole.CPU_CCD, "CPU CCD"),
            self._sensor("fake:gpu:temp1", "fake:gpu", "edge", SemanticRole.GPU_EDGE, "GPU"),
            self._sensor("fake:gpu:temp2", "fake:gpu", "junction", SemanticRole.GPU_HOTSPOT, "GPU Hotspot"),
        )

    @staticmethod
    def _sensor(sensor_id, device_id, label, role, default_label):
        return TelemetrySensor(
            sensor_id, device_id, "fake", sensor_id.rsplit(":", 1)[-1], label,
            Metric.TEMPERATURE, role, Unit.CELSIUS, default_label,
        )

    def discover(self):
        return TelemetryInventory(self.devices, self.sensors)

    def sample(self, sensor):
        return 40.0

    def snapshot(self):
        return TelemetrySnapshot(
            10.0,
            self.devices,
            tuple(
                TelemetryReading(sensor, Availability.AVAILABLE, 40.0, 10.0, 40.0, 10.0)
                for sensor in self.sensors
            ),
        )


def _window(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main_window, "discover_supported_devices", lambda: ())
    monkeypatch.setattr(main_window.DeviceMonitor, "start", lambda _self: None)
    monkeypatch.setattr(main_window.DeviceMonitor, "stop", lambda _self: None)
    provider = StaticTelemetryProvider()
    window = main_window.MainWindow(
        profile_store=ProfileStore(tmp_path / "profiles.json"),
        telemetry_provider=provider,
        telemetry_store=TelemetryPresentationStore(tmp_path / "telemetry.json"),
    )
    window._apply_telemetry_snapshot(provider.snapshot())
    return window


def test_grouped_ui_shows_all_sensors_and_selection_count(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        window._switch_profile("thermals")
        groups = window.telemetry_container.findChildren(QGroupBox)
        assert [group.title() for group in groups] == ["CPU", "Discrete GPU"]
        assert len(window._telemetry_widgets) == 4
        assert window.telemetry_count.text() == "Selected: 0 / 2"
    finally:
        window.close()


def test_third_selection_disabled_and_deselect_reenables_without_replacement(
    monkeypatch, tmp_path: Path
) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        ids = list(window._telemetry_widgets)
        first = window._telemetry_widgets[ids[0]]["select"]
        second = window._telemetry_widgets[ids[1]]["select"]
        third = window._telemetry_widgets[ids[2]]["select"]
        assert isinstance(first, QCheckBox) and isinstance(second, QCheckBox)
        assert isinstance(third, QCheckBox)
        first.setChecked(True)
        second.setChecked(True)
        assert window.telemetry_count.text() == "Selected: 2 / 2"
        assert not third.isEnabled() and not third.isChecked()
        first.setChecked(False)
        assert third.isEnabled()
        third.setChecked(True)
        assert [item.sensor_id for item in window._telemetry_presentations.selected] == [ids[1], ids[2]]
        assert len(window._telemetry_widgets) == 4
    finally:
        window.close()


def test_label_and_color_ui_persist(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    sensor_id = next(iter(window._telemetry_widgets))
    widgets = window._telemetry_widgets[sensor_id]
    checkbox, label, color = widgets["select"], widgets["label"], widgets["color"]
    assert isinstance(checkbox, QCheckBox)
    assert isinstance(label, QLineEdit)
    assert isinstance(color, QPushButton)
    monkeypatch.setattr(main_window.QColorDialog, "getColor", lambda *_args: QColor("#a956ff"))
    try:
        checkbox.setChecked(True)
        label.setText("  Processor  ")
        label.editingFinished.emit()
        color.click()
        saved = TelemetryPresentationStore(tmp_path / "telemetry.json").load().sensor(sensor_id)
        assert saved.display_label == "Processor"
        assert saved.font_color == "#A956FF"
        assert saved.sensor_id == sensor_id
    finally:
        window.close()


def test_thermals_configuration_emits_no_hid_or_playback_actions(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    events = []
    window.send_requested.connect(lambda *_: events.append("send"))
    window.refresh_requested.connect(lambda *_: events.append("refresh"))
    window.gif_frame_requested.connect(lambda *_: events.append("gif"))
    window.restore_requested.connect(lambda: events.append("restore"))
    try:
        window._switch_profile("thermals")
        sensor_id = next(iter(window._telemetry_widgets))
        window._telemetry_selection_changed(sensor_id, True)
        field = window._telemetry_widgets[sensor_id]["label"]
        assert isinstance(field, QLineEdit)
        field.setText("CPU")
        window._telemetry_label_changed(sensor_id, field)
        monkeypatch.setattr(main_window.QColorDialog, "getColor", lambda *_args: QColor("#ffffff"))
        window._telemetry_color_requested(sensor_id)
        assert events == []
    finally:
        window.close()


def test_image_gif_and_creative_controls_remain_mode_specific(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    try:
        window._switch_profile("image")
        assert not window.select_button.isHidden() and window.creative_panel.isHidden()
        window._switch_profile("gif")
        assert not window.gif_search_button.isHidden() and window.thermals_panel.isHidden()
        window._switch_profile("creative")
        assert not window.creative_panel.isHidden() and window.thermals_panel.isHidden()
    finally:
        window.close()


def test_orbit_preview_uses_shared_renderer_and_emits_no_hid(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    sensor_id = next(iter(window._telemetry_widgets))
    window._telemetry_selection_changed(sensor_id, True)
    rendered = []
    original = main_window.render_orbit_jpeg
    monkeypatch.setattr(
        main_window, "render_orbit_jpeg", lambda frame: (rendered.append(frame), original(frame))[1]
    )
    events = []
    window.send_requested.connect(lambda *_: events.append("send"))
    window.refresh_requested.connect(lambda *_: events.append("refresh"))
    window.gif_frame_requested.connect(lambda *_: events.append("gif"))
    window.orbit_frame_requested.connect(lambda *_: events.append("orbit"))
    try:
        window._switch_profile("thermals")
        window._render_orbit_preview()
        assert rendered and rendered[-1].items[0].label == "CPU"
        assert window.preview.pixmap() is not None
        assert events == []
    finally:
        window.close()


def test_restore_stops_orbit_before_hardware_restore(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    events = []
    monkeypatch.setattr(window._orbit_playback, "stop", lambda: events.append("orbit-stop"))
    window.restore_requested.connect(lambda: events.append("restore"))
    try:
        window._identity = object()
        window._session_touched_display = True
        window._restore()
        assert events == ["orbit-stop", "restore"]
    finally:
        window._session_touched_display = False
        window.close()
