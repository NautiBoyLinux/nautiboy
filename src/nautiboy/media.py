"""Provider-independent selected media model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from nautiboy.gif.decoder import GifDocument, GifProcessingError, inspect_gif
from nautiboy.imaging.processor import ImageProcessingError, ResizeStrategy, prepare_image


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    title: str
    source: str
    width: int
    height: int
    preview_jpeg: bytes
    static_jpeg: bytes | None = None
    gif: GifDocument | None = None
    creator: str | None = None
    source_url: str | None = None
    attribution: str | None = None

    @property
    def animated(self) -> bool:
        return self.gif is not None and self.gif.frame_count > 1

    @property
    def frame_count(self) -> int:
        return self.gif.frame_count if self.gif is not None else 1

    @property
    def duration_ms(self) -> int:
        return self.gif.duration_ms if self.gif is not None else 0


def prepare_local_media(path: str | Path, strategy: ResizeStrategy | str) -> PreparedMedia:
    selected = Path(path)
    if selected.suffix.lower() == ".gif":
        try:
            document = inspect_gif(selected)
            _rendered, preview = document.render_frame(0, strategy)
        except GifProcessingError as error:
            raise ImageProcessingError(str(error)) from error
        return PreparedMedia(selected.name, str(selected), document.width, document.height, preview, gif=document)
    rendered, jpeg = prepare_image(selected, strategy)
    try:
        with Image.open(selected) as source:
            width, height = source.size
    except OSError as error:
        raise ImageProcessingError(f"cannot inspect image: {error}") from error
    return PreparedMedia(selected.name, str(selected), width, height, jpeg, static_jpeg=jpeg)


def prepare_downloaded_gif(
    data: bytes,
    title: str,
    strategy: ResizeStrategy | str,
    *,
    creator: str | None = None,
    source_url: str | None = None,
    attribution: str = "Powered by GIPHY",
) -> PreparedMedia:
    try:
        document = inspect_gif(data)
        _rendered, preview = document.render_frame(0, strategy)
    except GifProcessingError as error:
        raise ImageProcessingError(str(error)) from error
    return PreparedMedia(
        title, "GIPHY selected media", document.width, document.height, preview,
        gif=document, creator=creator, source_url=source_url, attribution=attribution,
    )
