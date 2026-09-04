from __future__ import annotations

import json

import pytest

from nautiboy.providers.giphy import GiphyProvider


def payload(*, count: int = 1, total: int = 2, offset: int = 0) -> bytes:
    records = []
    for index in range(count):
        records.append({
            "id": f"id-{offset + index}",
            "title": "Dancing cat",
            "url": "https://giphy.com/gifs/id",
            "user": {"username": "creator"},
            "images": {
                "fixed_width": {"url": "https://media.giphy.com/preview.gif"},
                "downsized": {"url": "https://media.giphy.com/original.gif"},
                "original": {"url": "https://media.giphy.com/original.gif"},
            },
        })
    return json.dumps({"data": records, "pagination": {"offset": offset, "count": count, "total_count": total}}).encode()


def test_no_key_is_cleanly_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NAUTIBOY_GIPHY_API_KEY", raising=False)
    provider = GiphyProvider()
    assert not provider.available
    with pytest.raises(RuntimeError, match="not configured"):
        provider.trending_url()


def test_key_is_read_but_not_exposed_by_object_representation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAUTIBOY_GIPHY_API_KEY", "private-test-value")
    provider = GiphyProvider()
    assert provider.available
    assert "private-test-value" not in repr(provider)


def test_search_trending_rating_and_pagination() -> None:
    provider = GiphyProvider("test-key")
    assert "/search?" in provider.search_url("cat", "20")
    assert "rating=pg" in provider.search_url("cat")
    assert "offset=20" in provider.search_url("cat", "20")
    assert "/trending?" in provider.trending_url()


def test_mocked_search_results_are_provider_neutral() -> None:
    page = GiphyProvider("key").parse_page(payload())
    assert page.results[0].identifier == "id-0"
    assert page.results[0].creator == "creator"
    assert page.next_page == "1"


def test_empty_results_and_final_pagination() -> None:
    page = GiphyProvider("key").parse_page(payload(count=0, total=0))
    assert page.results == () and page.next_page is None


@pytest.mark.parametrize("content", [b"", b"{}", b"not-json"])
def test_malformed_or_provider_error_response(content: bytes) -> None:
    with pytest.raises(ValueError, match="malformed"):
        GiphyProvider("key").parse_page(content)


def test_provider_abstraction_does_not_leak_giphy_fields() -> None:
    result = GiphyProvider("key").parse_page(payload()).results[0]
    assert set(result.__dataclass_fields__) == {
        "provider", "identifier", "title", "creator", "source_url", "preview_url", "original_url"
    }
