from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from nautiboy.gif.decoder import GifLimits, GifProcessingError, inspect_gif
from nautiboy.imaging.processor import ResizeStrategy
from nautiboy.media import prepare_local_media


def gif_bytes(frames: list[Image.Image], durations: int | list[int] = 100, **kwargs: object) -> bytes:
    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=durations, loop=0, **kwargs)
    return output.getvalue()


def test_single_frame_gif() -> None:
    document = inspect_gif(gif_bytes([Image.new("RGB", (12, 8), "red")]))
    assert document.frame_count == 1
    assert document.width == 12 and document.height == 8
    rendered, jpeg = document.render_frame(0, ResizeStrategy.FIT)
    assert rendered.size == (480, 480)
    assert jpeg.startswith(b"\xff\xd8")


def test_multiframe_variable_durations_are_preserved() -> None:
    data = gif_bytes([Image.new("RGB", (10, 10), color) for color in ("red", "green", "blue")], [40, 120, 250])
    document = inspect_gif(data)
    assert document.frame_count == 3
    assert document.durations_ms == (40, 120, 250)
    assert document.duration_ms == 410


def test_zero_or_tiny_delay_is_safely_clamped() -> None:
    data = gif_bytes([Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")], [0, 10])
    assert inspect_gif(data).durations_ms == (100, 20)


def test_transparency_is_composited_on_black() -> None:
    first = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    first.putpixel((10, 10), (255, 255, 255, 255))
    document = inspect_gif(gif_bytes([first], transparency=0))
    rendered, _jpeg = document.render_frame(0, ResizeStrategy.FIT)
    assert rendered.getpixel((0, 0)) == (0, 0, 0)


def test_disposal_frames_decode_independently() -> None:
    frames = [Image.new("RGBA", (20, 20), (255, 0, 0, 255)), Image.new("RGBA", (20, 20), (0, 0, 255, 255))]
    document = inspect_gif(gif_bytes(frames, disposal=[2, 2]))
    second, _ = document.render_frame(1, ResizeStrategy.CENTER_CROP)
    assert second.getpixel((240, 240))[2] > 200


@pytest.mark.parametrize("data", [b"", b"GIF89a broken", b"not a gif"])
def test_malformed_gif_rejected(data: bytes) -> None:
    with pytest.raises(GifProcessingError):
        inspect_gif(data)


def test_dimension_and_pixel_limits() -> None:
    data = gif_bytes([Image.new("RGB", (101, 100), "red")])
    with pytest.raises(GifProcessingError, match="dimensions"):
        inspect_gif(data, limits=GifLimits(max_width=100))
    with pytest.raises(GifProcessingError, match="pixels"):
        inspect_gif(data, limits=GifLimits(max_pixels=10_000))


def test_encoded_size_limit() -> None:
    data = gif_bytes([Image.new("RGB", (10, 10), "red")])
    with pytest.raises(GifProcessingError, match="input bytes"):
        inspect_gif(data, limits=GifLimits(max_encoded_bytes=len(data) - 1))


def test_memory_limit() -> None:
    data = gif_bytes([Image.new("RGB", (20, 20), "red")])
    with pytest.raises(GifProcessingError, match="memory limit"):
        inspect_gif(data, limits=GifLimits(max_cache_bytes=100))


def test_frame_count_and_duration_limits() -> None:
    data = gif_bytes([Image.new("RGB", (10, 10), color) for color in ("red", "green", "blue")], [100, 100, 100])
    with pytest.raises(GifProcessingError, match="too many frames"):
        inspect_gif(data, limits=GifLimits(max_frames=2))
    with pytest.raises(GifProcessingError, match="duration"):
        inspect_gif(data, limits=GifLimits(max_duration_ms=250))


@pytest.mark.parametrize("strategy", [ResizeStrategy.FIT, ResizeStrategy.CENTER_CROP])
def test_gif_reuses_static_render_strategies(strategy: ResizeStrategy) -> None:
    document = inspect_gif(gif_bytes([Image.new("RGB", (80, 40), "red")]))
    rendered, _ = document.render_frame(0, strategy)
    assert rendered.size == (480, 480)
    if strategy is ResizeStrategy.FIT:
        assert rendered.getpixel((240, 20)) == (0, 0, 0)
    else:
        assert rendered.getpixel((240, 20))[0] == 255


def test_local_gif_has_no_provider_dependency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NAUTIBOY_GIPHY_API_KEY", raising=False)
    path = tmp_path / "local.gif"
    path.write_bytes(gif_bytes([Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")]))
    media = prepare_local_media(path, ResizeStrategy.FIT)
    assert media.animated and media.frame_count == 2


def test_static_jpeg_and_png_paths_remain_static(tmp_path: Path) -> None:
    for suffix, format_name in (("jpg", "JPEG"), ("png", "PNG")):
        path = tmp_path / f"static.{suffix}"
        Image.new("RGB", (30, 20), "purple").save(path, format=format_name)
        media = prepare_local_media(path, ResizeStrategy.FIT)
        assert not media.animated
        assert media.static_jpeg is not None
