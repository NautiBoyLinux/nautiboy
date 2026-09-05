"""Durable, app-owned storage for GIFs explicitly selected by the user."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from nautiboy.branding import APP_ID
from nautiboy.gif.decoder import DEFAULT_LIMITS, GifProcessingError, inspect_gif

SCHEMA_VERSION = 1
_SLOT_PATTERN = re.compile(r"^(gif-profile|creative-preset_[1-4]|last-active-display)$")


class SelectedMediaStoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SelectedGiphyMedia:
    data: bytes
    title: str
    provider: str = "giphy"
    provider_id: str | None = None
    creator: str | None = None
    source_url: str | None = None
    attribution: str = "Powered by GIPHY"


def data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured) if configured else Path.home() / ".local" / "share"


def selected_media_root() -> Path:
    return data_home() / APP_ID / "selected-media"


class SelectedMediaStore:
    """Own fixed-purpose slots; never acts as a generic provider response cache."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or selected_media_root()

    @staticmethod
    def _validate_slot(slot: str) -> None:
        if not _SLOT_PATTERN.fullmatch(slot):
            raise ValueError(f"unsupported selected-media slot: {slot}")

    def _paths(self, slot: str) -> tuple[Path, Path]:
        self._validate_slot(slot)
        return self.root / f"{slot}.gif", self.root / f"{slot}.json"

    def save(self, slot: str, selection: SelectedGiphyMedia) -> None:
        gif_path, metadata_path = self._paths(slot)
        try:
            inspect_gif(selection.data)
        except GifProcessingError as error:
            raise SelectedMediaStoreError(str(error)) from error
        if len(selection.data) > DEFAULT_LIMITS.max_encoded_bytes:
            raise SelectedMediaStoreError("selected GIF exceeds the storage size limit")
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "slot": slot,
            "provider": selection.provider,
            "provider_id": selection.provider_id,
            "title": selection.title,
            "creator": selection.creator,
            "source_url": selection.source_url,
            "attribution": selection.attribution,
            "media_filename": gif_path.name,
            "sha256": hashlib.sha256(selection.data).hexdigest(),
            "byte_size": len(selection.data),
        }
        gif_tmp = gif_path.with_suffix(".gif.tmp")
        metadata_tmp = metadata_path.with_suffix(".json.tmp")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            gif_tmp.write_bytes(selection.data)
            gif_tmp.chmod(0o600)
            metadata_tmp.write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            metadata_tmp.chmod(0o600)
            gif_tmp.replace(gif_path)
            metadata_tmp.replace(metadata_path)
        except OSError as error:
            for temporary in (gif_tmp, metadata_tmp):
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            raise SelectedMediaStoreError(f"cannot persist selected GIF: {error}") from error

    def load(self, slot: str) -> SelectedGiphyMedia | None:
        gif_path, metadata_path = self._paths(slot)
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            data = gif_path.read_bytes()
            if (
                not isinstance(metadata, dict)
                or metadata.get("schema_version") != SCHEMA_VERSION
                or metadata.get("slot") != slot
                or metadata.get("media_filename") != gif_path.name
                or metadata.get("byte_size") != len(data)
                or metadata.get("sha256") != hashlib.sha256(data).hexdigest()
                or not isinstance(metadata.get("title"), str)
            ):
                return None
            inspect_gif(data)
        except (OSError, UnicodeError, json.JSONDecodeError, GifProcessingError):
            return None
        return SelectedGiphyMedia(
            data=data,
            title=metadata["title"],
            provider=metadata.get("provider") if isinstance(metadata.get("provider"), str) else "giphy",
            provider_id=metadata.get("provider_id") if isinstance(metadata.get("provider_id"), str) else None,
            creator=metadata.get("creator") if isinstance(metadata.get("creator"), str) else None,
            source_url=metadata.get("source_url") if isinstance(metadata.get("source_url"), str) else None,
            attribution=metadata.get("attribution") if isinstance(metadata.get("attribution"), str) else "Powered by GIPHY",
        )

    def remove(self, slot: str) -> None:
        for path in self._paths(slot):
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                raise SelectedMediaStoreError(f"cannot remove selected GIF: {error}") from error
