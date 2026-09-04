"""Small content-addressed cache for providers that permit persistence.

GIPHY deliberately bypasses this class because its standard API terms prohibit
persistent media caching without separate approval.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

DEFAULT_CACHE_LIMIT = 200 * 1024 * 1024


def default_cache_directory() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "nautiboy" / "gifs"


class MediaCache:
    def __init__(self, directory: Path | None = None, *, maximum_bytes: int = DEFAULT_CACHE_LIMIT) -> None:
        self.directory = directory or default_cache_directory()
        self.maximum_bytes = maximum_bytes

    @staticmethod
    def key(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def get(self, digest: str) -> bytes | None:
        path = self.directory / digest
        try:
            data = path.read_bytes()
        except OSError:
            return None
        if self.key(data) != digest:
            path.unlink(missing_ok=True)
            return None
        os.utime(path, None)
        return data

    def put(self, data: bytes) -> str:
        digest = self.key(data)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.directory / f".{digest}.partial"
        temporary.write_bytes(data)
        temporary.replace(self.directory / digest)
        self.cleanup()
        return digest

    def cleanup(self) -> None:
        try:
            entries = [item for item in self.directory.iterdir() if item.is_file()]
        except OSError:
            return
        for partial in (item for item in entries if item.name.endswith(".partial")):
            partial.unlink(missing_ok=True)
        files = [item for item in entries if not item.name.startswith(".")]
        total = sum(item.stat().st_size for item in files)
        for item in sorted(files, key=lambda path: path.stat().st_atime):
            if total <= self.maximum_bytes:
                break
            size = item.stat().st_size
            item.unlink(missing_ok=True)
            total -= size
