"""Decode untrusted JPEG/PNG input and produce a bounded baseline JPEG."""

from __future__ import annotations

import io
import warnings
from enum import Enum
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from nautiboy.protocol.constants import DISPLAY_HEIGHT, DISPLAY_WIDTH, MAX_JPEG_BYTES

MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_DECODED_PIXELS = 40_000_000
JPEG_QUALITY = 90


class ResizeStrategy(str, Enum):
    """How decoded RGB pixels are placed on the LCD canvas."""

    FIT = "fit"
    CENTER_CROP = "center-crop"


class ImageProcessingError(ValueError):
    """The selected image is unsupported or unsafe to process."""


def _read_bounded(path: Path) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ImageProcessingError(f"cannot read image: {error}") from error
    if size <= 0:
        raise ImageProcessingError("image is empty")
    if size > MAX_INPUT_BYTES:
        raise ImageProcessingError(f"image exceeds {MAX_INPUT_BYTES} input bytes")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ImageProcessingError(f"cannot read image: {error}") from error


def _decode(data: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format not in {"JPEG", "PNG"}:
                    raise ImageProcessingError("only JPEG and PNG images are supported")
                if probe.width * probe.height > MAX_DECODED_PIXELS:
                    raise ImageProcessingError("decoded image dimensions are too large")
                probe.verify()
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
                    return Image.alpha_composite(background, rgba).convert("RGB")
                return oriented.convert("RGB")
    except ImageProcessingError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as error:
        raise ImageProcessingError(f"invalid image: {error}") from error


def _coerce_strategy(strategy: ResizeStrategy | str) -> ResizeStrategy:
    try:
        return ResizeStrategy(strategy)
    except (TypeError, ValueError) as error:
        raise ImageProcessingError(f"unsupported resize strategy: {strategy!r}") from error


def render_image(source: Image.Image, strategy: ResizeStrategy | str) -> Image.Image:
    strategy = _coerce_strategy(strategy)
    target = (DISPLAY_WIDTH, DISPLAY_HEIGHT)
    if strategy is ResizeStrategy.FIT:
        contained = ImageOps.contain(source, target, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", target, "black")
        offset = ((DISPLAY_WIDTH - contained.width) // 2, (DISPLAY_HEIGHT - contained.height) // 2)
        canvas.paste(contained, offset)
        return canvas
    if strategy is ResizeStrategy.CENTER_CROP:
        return ImageOps.fit(source, target, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    raise AssertionError("unreachable resize strategy")


def encode_baseline_jpeg(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.convert("RGB").save(
        output,
        format="JPEG",
        quality=JPEG_QUALITY,
        subsampling=0,
        optimize=False,
        progressive=False,
    )
    jpeg = output.getvalue()
    if len(jpeg) > MAX_JPEG_BYTES:
        raise ImageProcessingError(
            f"processed JPEG is {len(jpeg)} bytes; protocol maximum is {MAX_JPEG_BYTES}"
        )
    return jpeg


def prepare_image(
    path: str | Path, strategy: ResizeStrategy | str
) -> tuple[Image.Image, bytes]:
    source = _decode(_read_bounded(Path(path)))
    rendered = render_image(source, strategy)
    jpeg = encode_baseline_jpeg(rendered)
    return rendered, jpeg
