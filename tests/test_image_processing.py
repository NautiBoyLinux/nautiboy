from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from nautiboy.imaging.processor import ImageProcessingError, ResizeStrategy, prepare_image


def save_image(path: Path, image: Image.Image, **kwargs: object) -> None:
    image.save(path, **kwargs)


def test_fit_preserves_aspect_ratio_with_letterbox(tmp_path: Path) -> None:
    path = tmp_path / "wide.png"
    save_image(path, Image.new("RGB", (800, 400), "red"), format="PNG")
    rendered, jpeg = prepare_image(path, ResizeStrategy.FIT)
    assert rendered.size == (480, 480)
    assert rendered.getpixel((240, 20)) == (0, 0, 0)
    assert rendered.getpixel((240, 240))[0] > 240
    assert jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9")


def test_center_crop_fills_display_from_center(tmp_path: Path) -> None:
    path = tmp_path / "bands.png"
    image = Image.new("RGB", (960, 480), "green")
    for x in range(0, 240):
        for y in range(480):
            image.putpixel((x, y), (255, 0, 0))
    for x in range(720, 960):
        for y in range(480):
            image.putpixel((x, y), (0, 0, 255))
    save_image(path, image, format="PNG")
    rendered, _ = prepare_image(path, ResizeStrategy.CENTER_CROP)
    assert rendered.size == (480, 480)
    assert rendered.getpixel((240, 240)) == (0, 128, 0)
    assert rendered.getpixel((20, 240))[1] > rendered.getpixel((20, 240))[0]


def test_exif_orientation_is_applied(tmp_path: Path) -> None:
    path = tmp_path / "oriented.jpg"
    image = Image.new("RGB", (100, 200), "red")
    exif = Image.Exif()
    exif[274] = 6
    save_image(path, image, format="JPEG", exif=exif)
    rendered, _ = prepare_image(path, ResizeStrategy.FIT)
    # Orientation 6 becomes landscape, producing top/bottom rather than side bars.
    assert rendered.getpixel((240, 20)) == (0, 0, 0)
    assert rendered.getpixel((20, 240))[0] > 200


def test_png_transparency_is_composited_on_black(tmp_path: Path) -> None:
    path = tmp_path / "alpha.png"
    image = Image.new("RGBA", (480, 480), (255, 0, 0, 0))
    image.putpixel((240, 240), (255, 255, 255, 255))
    save_image(path, image, format="PNG")
    rendered, _ = prepare_image(path, ResizeStrategy.FIT)
    assert rendered.getpixel((0, 0)) == (0, 0, 0)
    assert rendered.getpixel((240, 240)) == (255, 255, 255)


@pytest.mark.parametrize("content", [b"", b"not-an-image"])
def test_invalid_image_rejected(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "invalid.jpg"
    path.write_bytes(content)
    with pytest.raises(ImageProcessingError):
        prepare_image(path, ResizeStrategy.FIT)


def test_unsupported_decoded_format_rejected(tmp_path: Path) -> None:
    path = tmp_path / "image.bmp"
    save_image(path, Image.new("RGB", (10, 10)), format="BMP")
    with pytest.raises(ImageProcessingError, match="only JPEG and PNG"):
        prepare_image(path, ResizeStrategy.FIT)


def test_qt_string_fit_strategy_is_accepted(tmp_path: Path) -> None:
    """Regression: QComboBox returned 'fit', which failed Enum identity checks."""
    path = tmp_path / "known-good.jpg"
    save_image(path, Image.new("RGB", (480, 480), "red"), format="JPEG")

    rendered, jpeg = prepare_image(path, "fit")

    assert rendered.size == (480, 480)
    assert jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9")
