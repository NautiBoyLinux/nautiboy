from __future__ import annotations

from pathlib import Path

import pytest

from nautiboy.cache.media_cache import MediaCache
from nautiboy.network.worker import MEDIA_MAX_BYTES, NetworkValidationError, NetworkWorker, _Transfer, validate_response


def test_valid_json_and_gif_responses() -> None:
    validate_response(200, "application/json; charset=utf-8", b"{}", kind="json")
    validate_response(200, "image/gif", b"GIF89a", kind="gif")


@pytest.mark.parametrize("status", [None, 301, 404, 500])
def test_http_errors(status: int | None) -> None:
    with pytest.raises(NetworkValidationError, match="HTTP"):
        validate_response(status, "image/gif", b"x", kind="gif")


def test_invalid_mime_type() -> None:
    with pytest.raises(NetworkValidationError, match="content type"):
        validate_response(200, "text/html", b"GIF89a", kind="gif")


def test_oversized_download() -> None:
    with pytest.raises(NetworkValidationError, match="size limit"):
        validate_response(200, "image/gif", b"x" * (MEDIA_MAX_BYTES + 1), kind="gif")


class _FakeReply:
    def __init__(self) -> None:
        self.aborted = False
        self.deleted = False
    def abort(self) -> None:
        self.aborted = True
    def deleteLater(self) -> None:
        self.deleted = True


class _FakeTimer:
    def __init__(self) -> None:
        self.stopped = False
        self.deleted = False
    def stop(self) -> None:
        self.stopped = True
    def deleteLater(self) -> None:
        self.deleted = True


def test_cancelled_request_is_aborted_and_removed() -> None:
    worker = NetworkWorker()
    reply, timer = _FakeReply(), _FakeTimer()
    worker._transfers["one"] = _Transfer(reply, bytearray(), 10, ("image/gif",), timer)  # type: ignore[arg-type]
    worker.cancel_all()
    assert reply.aborted and timer.stopped and not worker._transfers


def test_network_timeout_fails_once_without_retry() -> None:
    worker = NetworkWorker()
    reply, timer = _FakeReply(), _FakeTimer()
    failures = []
    worker.failed.connect(lambda request_id, message: failures.append((request_id, message)))
    worker._transfers["one"] = _Transfer(reply, bytearray(), 10, ("image/gif",), timer)  # type: ignore[arg-type]
    worker._timeout("one")
    assert failures == [("one", "network request timed out")]
    assert reply.aborted and not worker._transfers


def test_cache_hit_miss_and_corruption(tmp_path: Path) -> None:
    cache = MediaCache(tmp_path)
    assert cache.get("missing") is None
    digest = cache.put(b"valid")
    assert cache.get(digest) == b"valid"
    (tmp_path / digest).write_bytes(b"corrupt")
    assert cache.get(digest) is None


def test_cache_cleanup_is_size_bounded(tmp_path: Path) -> None:
    cache = MediaCache(tmp_path, maximum_bytes=5)
    cache.put(b"first")
    cache.put(b"second")
    assert sum(path.stat().st_size for path in tmp_path.iterdir()) <= 5


def test_cache_cleanup_removes_partial_downloads(tmp_path: Path) -> None:
    partial = tmp_path / ".interrupted.partial"
    partial.write_bytes(b"partial")
    MediaCache(tmp_path).cleanup()
    assert not partial.exists()


def test_giphy_session_policy_does_not_instantiate_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    from nautiboy.providers.giphy import GiphyProvider
    GiphyProvider("key").parse_page(b'{"data": [], "pagination": {"offset": 0, "count": 0, "total_count": 0}}')
    assert not (tmp_path / "nautiboy").exists()
