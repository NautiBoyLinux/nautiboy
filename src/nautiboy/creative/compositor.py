"""Compose media, Orbit perimeter, and telemetry into a bounded LCD frame."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from nautiboy.imaging.processor import encode_baseline_jpeg
from nautiboy.protocol.constants import DISPLAY_HEIGHT, DISPLAY_WIDTH
from nautiboy.telemetry.orbit import OrbitItem, apply_orbit_perimeter, apply_telemetry_foreground


@dataclass(frozen=True, slots=True)
class CreativeComposition:
    background: Image.Image | None
    telemetry_items: tuple[OrbitItem, ...] = ()
    telemetry_enabled: bool = False
    orbit_enabled: bool = False
    orbit_animated: bool = True
    follow_telemetry_colors: bool = True
    primary_color: str = "#9B30FF"
    secondary_color: str = "#00D9FF"
    orbit_phase: float = 0.0


@dataclass(frozen=True, slots=True)
class CreativeFrameRequest:
    """A renderer request passed to the device worker; contains no HID details."""

    composition: CreativeComposition
    static_background: Image.Image | None = None
    gif_document: object | None = None
    gif_frame_index: int = 0
    resize_strategy: str = "fit"


def _orbit_colors(spec: CreativeComposition) -> tuple[str, ...]:
    if spec.follow_telemetry_colors and spec.telemetry_items:
        return tuple(item.color for item in spec.telemetry_items[:2])
    return (spec.primary_color, spec.secondary_color)


def compose_creative(spec: CreativeComposition) -> Image.Image:
    """Apply the strict background -> Orbit -> telemetry rendering order."""
    if len(spec.telemetry_items) > 2:
        raise ValueError("Creative supports at most two telemetry items")
    if spec.background is None:
        image = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), "black")
    else:
        if spec.background.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
            raise ValueError("Creative background must already be 480x480")
        image = spec.background.convert("RGB").copy()
    if spec.orbit_enabled:
        image = apply_orbit_perimeter(
            image,
            _orbit_colors(spec),
            spec.orbit_phase,
            animated=spec.orbit_animated,
        ).convert("RGB")
    if spec.telemetry_enabled and spec.telemetry_items:
        image = apply_telemetry_foreground(image, spec.telemetry_items)
    return image.convert("RGB")


def compose_creative_jpeg(spec: CreativeComposition) -> bytes:
    return encode_baseline_jpeg(compose_creative(spec))
