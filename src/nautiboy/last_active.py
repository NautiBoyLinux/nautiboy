"""Versioned record of the last display that completed a hardware transfer."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from nautiboy.autostart import config_home

SCHEMA_VERSION = 1
VALID_MODES = frozenset({"thermals", "image", "gif", "creative"})


@dataclass(frozen=True, slots=True)
class LastActiveDisplay:
    mode: str
    resize_strategy: str | None = None
    media: dict[str, Any] | None = None
    creative_preset_id: str | None = None
    creative_settings: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": self.mode,
            "resize_strategy": self.resize_strategy,
            "media": deepcopy(self.media),
            "creative_preset_id": self.creative_preset_id,
            "creative_settings": deepcopy(self.creative_settings),
        }


class LastActiveDisplayStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_home() / "nautiboy" / "last-active-display.json"

    def load(self) -> LastActiveDisplay | None:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
            return None
        mode = value.get("mode")
        strategy = value.get("resize_strategy")
        media = value.get("media")
        if mode not in VALID_MODES or strategy not in {None, "fit", "center-crop"}:
            return None
        if media is not None:
            if not isinstance(media, dict) or media.get("kind") not in {"local", "giphy"}:
                return None
            key = "path" if media["kind"] == "local" else "slot"
            if not isinstance(media.get(key), str) or not media[key]:
                return None
        preset_id = value.get("creative_preset_id")
        creative = value.get("creative_settings")
        if mode == "creative" and (
            preset_id not in {"preset_1", "preset_2", "preset_3", "preset_4"}
            or not isinstance(creative, dict)
        ):
            return None
        return LastActiveDisplay(mode, strategy, deepcopy(media), preset_id, deepcopy(creative))

    def save(self, display: LastActiveDisplay) -> None:
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(display.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            temporary.chmod(0o600)
            temporary.replace(self.path)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"cannot save last active display: {error}") from error
