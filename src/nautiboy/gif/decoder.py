"""Validate untrusted GIF data and render one composited frame at a time."""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from nautiboy.imaging.processor import ResizeStrategy, encode_baseline_jpeg, render_image


@dataclass(frozen=True, slots=True)
class GifLimits:
    max_encoded_bytes: int = 25 * 1024 * 1024
    max_width: int = 4096
    max_height: int = 4096
    max_pixels: int = 16_000_000
    max_frames: int = 500
    max_duration_ms: int = 10 * 60 * 1000
    max_cache_bytes: int = 64 * 1024 * 1024


DEFAULT_LIMITS = GifLimits()
MIN_SOURCE_DELAY_MS = 20
DEFAULT_FRAME_DELAY_MS = 100


class GifProcessingError(ValueError):
    """The GIF is malformed, unsupported, or exceeds a safety limit."""


@dataclass(frozen=True, slots=True)
class GifDocument:
    data: bytes
    width: int
    height: int
    durations_ms: tuple[int, ...]
    loop: int

    @property
    def frame_count(self) -> int:
        return len(self.durations_ms)

    @property
    def duration_ms(self) -> int:
        return sum(self.durations_ms)

    def render_frame(self, index: int, strategy: ResizeStrategy | str) -> tuple[Image.Image, bytes]:
        if not 0 <= index < self.frame_count:
            raise GifProcessingError(f"GIF frame index out of range: {index}")
        try:
            with Image.open(io.BytesIO(self.data)) as source:
                source.seek(index)
                # Pillow applies GIF disposal while seeking; copying freezes the composed canvas.
                composed = source.convert("RGBA")
                background = Image.new("RGBA", composed.size, (0, 0, 0, 255))
                rgb = Image.alpha_composite(background, composed).convert("RGB")
            rendered = render_image(rgb, strategy)
            return rendered, encode_baseline_jpeg(rendered)
        except (OSError, SyntaxError, ValueError, EOFError) as error:
            raise GifProcessingError(f"cannot decode GIF frame {index}: {error}") from error


def _bounded_data(source: str | Path | bytes, limits: GifLimits) -> bytes:
    if isinstance(source, bytes):
        data = source
    else:
        path = Path(source)
        try:
            size = path.stat().st_size
            if size > limits.max_encoded_bytes:
                raise GifProcessingError(f"GIF exceeds {limits.max_encoded_bytes} input bytes")
            data = path.read_bytes()
        except GifProcessingError:
            raise
        except OSError as error:
            raise GifProcessingError(f"cannot read GIF: {error}") from error
    if not data:
        raise GifProcessingError("GIF is empty")
    if len(data) > limits.max_encoded_bytes:
        raise GifProcessingError(f"GIF exceeds {limits.max_encoded_bytes} input bytes")
    return data


def inspect_gif(
    source: str | Path | bytes, *, limits: GifLimits = DEFAULT_LIMITS
) -> GifDocument:
    """Fully validate metadata without retaining decoded source-sized frames."""
    data = _bounded_data(source, limits)
    durations: list[int] = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "GIF":
                    raise GifProcessingError("selected media is not a GIF")
                width, height = image.size
                if width > limits.max_width or height > limits.max_height:
                    raise GifProcessingError("GIF dimensions exceed the configured limit")
                if width * height > limits.max_pixels:
                    raise GifProcessingError("GIF frame contains too many pixels")
                working_set = width * height * 4 + 2 * 480 * 480 * 3
                if working_set > limits.max_cache_bytes:
                    raise GifProcessingError("GIF decoding would exceed the memory limit")
                frame_count = int(getattr(image, "n_frames", 1))
                if frame_count > limits.max_frames:
                    raise GifProcessingError("GIF contains too many frames")
                for index in range(frame_count):
                    image.seek(index)
                    # Force decoding now, but immediately release each frame-sized copy.
                    image.convert("RGBA").getbbox()
                    raw_delay = int(image.info.get("duration", DEFAULT_FRAME_DELAY_MS) or DEFAULT_FRAME_DELAY_MS)
                    durations.append(max(MIN_SOURCE_DELAY_MS, raw_delay))
                    if sum(durations) > limits.max_duration_ms:
                        raise GifProcessingError("GIF duration exceeds the configured limit")
                loop = int(image.info.get("loop", 0) or 0)
    except GifProcessingError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError, EOFError) as error:
        raise GifProcessingError(f"invalid GIF: {error}") from error
    return GifDocument(data, width, height, tuple(durations), loop)
