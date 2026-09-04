from __future__ import annotations

import io
import math

from PIL import Image, ImageChops

from nautiboy.gui.orbit import ORBIT_LCD_INTERVAL_MS, OrbitPlaybackController
from nautiboy.telemetry.orbit import (
    ORBIT_JPEG_QUALITY,
    ORBIT_INNER_RADIUS,
    OrbitFrame,
    OrbitItem,
    phase_at,
    render_orbit,
    render_orbit_jpeg,
    telemetry_regions,
)


def test_rendering_is_deterministic_at_specified_phase() -> None:
    frame = OrbitFrame((OrbitItem("CPU", 52.0, "#9B30FF"), OrbitItem("GPU", 41.0, "#00D9FF")), 0.25)
    assert render_orbit_jpeg(frame) == render_orbit_jpeg(frame)


def test_orbit_uses_bounded_baseline_jpeg_and_named_lcd_interval() -> None:
    frame = OrbitFrame((OrbitItem("CPU", 52.0, "#9B30FF"),), 0.25)
    jpeg = render_orbit_jpeg(frame)
    with Image.open(io.BytesIO(jpeg)) as decoded:
        assert decoded.size == (480, 480)
        assert decoded.format == "JPEG"
        assert not decoded.info.get("progressive", False)
    assert len(jpeg) < 100_000
    assert ORBIT_JPEG_QUALITY == 86
    assert ORBIT_LCD_INTERVAL_MS == 100


def test_one_and_two_sensor_layouts_custom_labels_and_colors() -> None:
    one = render_orbit(OrbitFrame((OrbitItem("Processor", 50.0, "#00FF00"),), 0.0))
    two = render_orbit(
        OrbitFrame((OrbitItem("Package", 51.0, "#FF0000"), OrbitItem("Graphics", 39.0, "#0000FF")), 0.0)
    )
    assert one.size == two.size == (480, 480)
    assert ImageChops.difference(one, two).getbbox() is not None
    assert max(pixel[1] for pixel in one.get_flattened_data()) > 200
    assert max(pixel[0] for pixel in two.get_flattened_data()) > 200
    assert max(pixel[2] for pixel in two.get_flattened_data()) > 200


def test_live_and_unavailable_values_change_rendered_frame() -> None:
    current = render_orbit(OrbitFrame((OrbitItem("CPU", 52.0, "#9B30FF"),), 0.1))
    changed = render_orbit(OrbitFrame((OrbitItem("CPU", 61.0, "#9B30FF"),), 0.1))
    unavailable = render_orbit(
        OrbitFrame((OrbitItem("CPU", None, "#9B30FF", "unavailable"),), 0.1)
    )
    assert ImageChops.difference(current, changed).getbbox() is not None
    assert ImageChops.difference(current, unavailable).getbbox() is not None


def test_orbit_geometry_is_outside_telemetry_regions() -> None:
    center = 240
    for region in telemetry_regions(2):
        for x in (region[0], region[2]):
            for y in (region[1], region[3]):
                assert math.hypot(x - center, y - center) < ORBIT_INNER_RADIUS


def test_phase_is_monotonic_time_based_and_wraps() -> None:
    assert phase_at(13.0, 10.0, 12.0) == 0.25
    assert phase_at(25.0, 10.0, 12.0) == 0.25


class FakeTimeout:
    def connect(self, callback):
        self.callback = callback


class FakeTimer:
    def __init__(self):
        self.timeout = FakeTimeout()
        self.active = False

    def setInterval(self, interval):
        self.interval = interval

    def start(self):
        self.active = True

    def stop(self):
        self.active = False


def test_scheduler_has_one_in_flight_no_backlog_and_time_based_drop() -> None:
    now = [100.0]
    timer = FakeTimer()
    controller = OrbitPlaybackController(clock=lambda: now[0], timer=timer)
    phases = []
    controller.frame_requested.connect(phases.append)
    controller.start()
    assert phases == [0.0] and controller.in_flight
    now[0] = 103.0
    timer.timeout.callback()
    timer.timeout.callback()
    assert phases == [0.0] and controller.dropped_frames == 2
    controller.transfer_completed()
    timer.timeout.callback()
    assert phases[-1] == 0.25 and len(phases) == 2
