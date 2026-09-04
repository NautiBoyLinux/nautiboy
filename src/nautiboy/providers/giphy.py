"""Experimental GIPHY development adapter; contains no embedded credential."""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from .base import GifResult, SearchPage


class GiphyProvider:
    name = "GIPHY (experimental)"
    attribution = "Powered by GIPHY"
    endpoint = "https://api.giphy.com/v1/gifs"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("NAUTIBOY_GIPHY_API_KEY", "")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _url(self, operation: str, *, query: str | None, page: str | None) -> str:
        if not self.available:
            raise RuntimeError("online GIF search is not configured")
        try:
            offset = max(0, int(page or "0"))
        except ValueError as error:
            raise ValueError("invalid pagination token") from error
        parameters: dict[str, object] = {
            "api_key": self._api_key,
            "limit": 20,
            "offset": offset,
            "rating": "pg",
        }
        if query is not None:
            parameters["q"] = query
        return f"{self.endpoint}/{operation}?{urlencode(parameters)}"

    def search_url(self, query: str, page: str | None = None) -> str:
        query = query.strip()
        if not query:
            raise ValueError("search query is empty")
        return self._url("search", query=query, page=page)

    def trending_url(self, page: str | None = None) -> str:
        return self._url("trending", query=None, page=page)

    def parse_page(self, payload: bytes) -> SearchPage:
        try:
            root = json.loads(payload)
            records = root["data"]
            pagination = root.get("pagination", {})
            results = []
            for record in records:
                images = record["images"]
                preview = images.get("fixed_width", images.get("downsized"))["url"]
                original = images.get("downsized", images["original"])["url"]
                user = record.get("user") or {}
                results.append(
                    GifResult(
                        provider=self.name,
                        identifier=str(record["id"]),
                        title=str(record.get("title") or "Untitled GIF"),
                        creator=user.get("display_name") or user.get("username"),
                        source_url=record.get("url"),
                        preview_url=str(preview),
                        original_url=str(original),
                    )
                )
            offset = int(pagination.get("offset", 0))
            count = int(pagination.get("count", len(results)))
            total = int(pagination.get("total_count", offset + count))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("malformed provider response") from error
        next_page = str(offset + count) if count and offset + count < total else None
        return SearchPage(tuple(results), next_page)
