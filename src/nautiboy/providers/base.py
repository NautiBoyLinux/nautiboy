"""Provider-neutral online GIF search contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GifResult:
    provider: str
    identifier: str
    title: str
    creator: str | None
    source_url: str | None
    preview_url: str
    original_url: str


@dataclass(frozen=True, slots=True)
class SelectedGif:
    """A provider result explicitly chosen and downloaded by the user."""

    data: bytes
    result: GifResult
    attribution: str


@dataclass(frozen=True, slots=True)
class SearchPage:
    results: tuple[GifResult, ...]
    next_page: str | None = None


class GifProvider(Protocol):
    name: str
    attribution: str

    @property
    def available(self) -> bool: ...
    def search_url(self, query: str, page: str | None = None) -> str: ...
    def trending_url(self, page: str | None = None) -> str: ...
    def parse_page(self, payload: bytes) -> SearchPage: ...
