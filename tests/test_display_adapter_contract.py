from __future__ import annotations

import pytest
from PIL import Image

from nautiboy.hardware.adapters import RenderedFrame


def test_rendered_frame_accepts_device_neutral_rgb() -> None:
    frame = RenderedFrame(Image.new("RGB", (640, 640)), 100)
    assert frame.image.size == (640, 640)


def test_rendered_frame_rejects_non_rgb() -> None:
    with pytest.raises(ValueError, match="RGB"):
        RenderedFrame(Image.new("RGBA", (480, 480)))


def test_rendered_frame_rejects_invalid_duration() -> None:
    with pytest.raises(ValueError, match="duration"):
        RenderedFrame(Image.new("RGB", (480, 480)), 0)
