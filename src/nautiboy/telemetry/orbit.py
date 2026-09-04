"""Programmatic 480x480 Orbit telemetry theme."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import io
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from nautiboy.protocol.constants import DISPLAY_HEIGHT, DISPLAY_WIDTH, MAX_JPEG_BYTES

ORBIT_PERIOD_SECONDS = 12.0
ORBIT_INNER_RADIUS = 190
ORBIT_JPEG_QUALITY = 86
BACKGROUND = (0, 0, 3)
LABEL_COLOR = (236, 238, 246, 255)
STATUS_COLOR = (135, 143, 166, 255)


@dataclass(frozen=True, slots=True)
class OrbitItem:
    label: str
    value: float | None
    color: str
    availability: str = "available"


@dataclass(frozen=True, slots=True)
class OrbitFrame:
    items: tuple[OrbitItem, ...]
    phase: float


@dataclass(frozen=True, slots=True)
class OrbitTransferStats:
    report_count: int
    jpeg_bytes: int
    render_seconds: float
    encode_seconds: float
    transfer_seconds: float
    total_seconds: float


def phase_at(now: float, started_at: float, period: float = ORBIT_PERIOD_SECONDS) -> float:
    return ((now - started_at) % period) / period


def telemetry_regions(item_count: int) -> tuple[tuple[int, int, int, int], ...]:
    if item_count == 1:
        return ((100, 145, 380, 335),)
    return ((135, 90, 345, 210), (135, 270, 345, 390))


def _font(size: int, bold: bool = False):
    names = (
        ("/usr/share/fonts/google-noto/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if bold
        else ("/usr/share/fonts/google-noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid Orbit color: {hex_color!r}")
    try:
        return tuple(int(value[offset : offset + 2], 16) for offset in (0, 2, 4)) + (alpha,)
    except ValueError as error:
        raise ValueError(f"invalid Orbit color: {hex_color!r}") from error


@lru_cache(maxsize=1)
def _static_background() -> Image.Image:
    """Cache all geometry that does not change with phase or telemetry."""
    image = Image.new("RGBA", (DISPLAY_WIDTH, DISPLAY_HEIGHT), BACKGROUND + (255,))
    draw = ImageDraw.Draw(image)
    center = DISPLAY_WIDTH // 2
    for radius, color, width in (
        (227, (27, 24, 45, 255), 2),
        (220, (13, 24, 49, 255), 1),
        (210, (20, 22, 43, 255), 1),
        (198, (9, 14, 29, 255), 1),
    ):
        draw.ellipse((center-radius, center-radius, center+radius, center+radius), outline=color, width=width)
    for angle in range(0, 360, 15):
        radians = math.radians(angle)
        major = angle % 45 == 0
        inner, outer = (207, 216) if major else (211, 215)
        points = tuple(
            (center + math.cos(radians) * radius, center + math.sin(radians) * radius)
            for radius in (inner, outer)
        )
        draw.line(points, fill=(42, 43, 69, 255) if major else (25, 27, 46, 255), width=1)
    detail_box = (32, 32, 448, 448)
    for start, end in ((198, 248), (275, 309), (332, 357), (30, 68), (101, 145)):
        draw.arc(detail_box, start=start, end=end, fill=(26, 34, 66, 255), width=2)
    return image


@lru_cache(maxsize=1)
def _mascot() -> Image.Image:
    """Extract the mascot from the bundled canonical artwork, without its frame."""
    asset = Path(__file__).parents[1] / "assets" / "nautiboy-icon-development-source.png"
    with Image.open(asset) as source:
        # The canonical asset is 352 square. This crop isolates the existing cat
        # silhouette and its neon outline, excluding the rounded application frame.
        mascot = source.convert("RGBA").crop((62, 69, 282, 286))
        red, green, blue, _alpha = mascot.split()
        luminance = ImageChops.lighter(red, ImageChops.lighter(green, blue))
        mascot.putalpha(luminance.point(lambda value: 0 if value < 150 else min(255, value + 25)))
        mascot.thumbnail((58, 58), Image.Resampling.LANCZOS)
        return mascot.copy()


def _fit_label(label: str, maximum_width: int, normal_size: int = 24):
    size = normal_size
    while size > 15:
        font = _font(size, True)
        box = font.getbbox(label)
        if box[2] - box[0] <= maximum_width:
            return font
        size -= 1
    return _font(size, True)


def _centered(draw: ImageDraw.ImageDraw, text: str, center_y: int, font, fill) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    draw.text(((DISPLAY_WIDTH-width)/2-box[0], center_y-height/2-box[1]), text, font=font, fill=fill)


def _draw_dynamic_arcs(image: Image.Image, frame: OrbitFrame) -> Image.Image:
    phase_degrees = (frame.phase % 1.0) * 360.0
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    core = Image.new("RGBA", image.size, (0, 0, 0, 0))
    core_draw = ImageDraw.Draw(core)
    segment_sets = (
        ((-82, 48), (-17, 25), (39, 38), (108, 20), (151, 42)),
        ((103, 45), (166, 24), (216, 39), (278, 19), (321, 44)),
    )
    boxes = ((15, 15, 465, 465), (23, 23, 457, 457))
    for index, item in enumerate(frame.items):
        segments = segment_sets[index if len(frame.items) == 2 else 0]
        color, glow_color = _rgba(item.color), _rgba(item.color, 115)
        box = boxes[index if len(frame.items) == 2 else 0]
        for offset, length in segments:
            start = phase_degrees + offset
            glow_draw.arc(box, start=start, end=start+length, fill=glow_color, width=9)
            core_draw.arc(box, start=start, end=start+length, fill=color, width=5)
            core_draw.arc(box, start=start, end=start+min(5, length), fill=(245, 247, 255, 235), width=4)

        # A sparser inner detail ring moves more slowly in reverse. It supplies
        # layered motion without making the perimeter uniformly bright.
        secondary_box = (34 + index * 5, 34 + index * 5, 446 - index * 5, 446 - index * 5)
        reverse_phase = -phase_degrees * 0.62
        for offset, length in ((-54 + index * 113, 29), (78 + index * 97, 18), (181 + index * 73, 34)):
            start = reverse_phase + offset
            core_draw.arc(secondary_box, start=start, end=start+length, fill=_rgba(item.color, 165), width=3)
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(2.2)))
    return Image.alpha_composite(image, core)


def _draw_divider(image: Image.Image, frame: OrbitFrame, center_y: int) -> None:
    colors = [_rgba(item.color) for item in frame.items]
    left_color = colors[0]
    right_color = colors[-1]
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    core = Image.new("RGBA", image.size, (0, 0, 0, 0))
    core_draw = ImageDraw.Draw(core)
    for layer, width, alpha in ((glow_draw, 4, 115), (core_draw, 1, 235)):
        layer.line((130, center_y, 204, center_y), fill=left_color[:3] + (alpha,), width=width)
        layer.line((276, center_y, 350, center_y), fill=right_color[:3] + (alpha,), width=width)
    image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2.0)))
    image.alpha_composite(core)

    mascot = _mascot()
    mascot_glow = mascot.filter(ImageFilter.GaussianBlur(2.0))
    x, y = (DISPLAY_WIDTH - mascot.width) // 2, center_y - mascot.height // 2
    image.alpha_composite(mascot_glow, (x, y))
    image.alpha_composite(mascot, (x, y))


def _draw_reading(image: Image.Image, item: OrbitItem, label_y: int, value_y: int, status_y: int, value_size: int) -> None:
    draw = ImageDraw.Draw(image)
    _centered(draw, item.label, label_y, _fit_label(item.label, 245, 29), LABEL_COLOR)
    value = "--°" if item.value is None else f"{round(item.value):.0f}°"
    value_font = _font(value_size, True)
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    _centered(ImageDraw.Draw(glow), value, value_y, value_font, _rgba(item.color, 110))
    image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2.0)))
    _centered(ImageDraw.Draw(image), value, value_y, value_font, _rgba(item.color))
    if item.availability != "available":
        _centered(draw, item.availability.upper(), status_y, _font(12, True), STATUS_COLOR)


def render_orbit(frame: OrbitFrame) -> Image.Image:
    if not 1 <= len(frame.items) <= 2:
        raise ValueError("Orbit requires one or two telemetry items")
    image = _draw_dynamic_arcs(_static_background().copy(), frame)
    if len(frame.items) == 1:
        placements, value_size, divider_y = ((148, 220, 283),), 96, 334
    else:
        placements, value_size, divider_y = ((89, 151, 205), (287, 349, 403)), 91, 240
    _draw_divider(image, frame, divider_y)
    for item, (label_y, value_y, status_y) in zip(frame.items, placements):
        _draw_reading(image, item, label_y, value_y, status_y, value_size)
    return image.convert("RGB")


def encode_orbit_jpeg(image: Image.Image) -> bytes:
    """Encode a bounded baseline JPEG tuned for the mostly-black Orbit scene."""
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=ORBIT_JPEG_QUALITY, subsampling=0, optimize=False, progressive=False)
    jpeg = output.getvalue()
    if len(jpeg) > MAX_JPEG_BYTES:
        raise ValueError(f"Orbit JPEG is {len(jpeg)} bytes; protocol maximum is {MAX_JPEG_BYTES}")
    return jpeg


def render_orbit_jpeg(frame: OrbitFrame) -> bytes:
    return encode_orbit_jpeg(render_orbit(frame))
