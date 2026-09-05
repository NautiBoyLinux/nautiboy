"""Atomic XDG persistence for display profile state."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import (
    CREATIVE_PRESET_IDS,
    CREATIVE_PRESET_NAME_MAX_LENGTH,
    ProfileState,
    ProfileType,
    default_profile_state,
    profile_state_from_dict,
)

PROFILES_FILENAME = "profiles.json"


class ProfileStoreError(RuntimeError):
    pass


def config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured else Path.home() / ".config"


def profiles_path() -> Path:
    return config_home() / "nautiboy" / PROFILES_FILENAME


class ProfileStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or profiles_path()

    def load(self) -> ProfileState:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return default_profile_state()
        return profile_state_from_dict(document)

    def save(self, state: ProfileState) -> None:
        if not state.writable:
            raise ProfileStoreError(
                "profiles were created by a newer NautiBoy version and will not be overwritten"
            )
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            temporary.replace(self.path)
        except OSError as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ProfileStoreError(f"cannot save profiles: {error}") from error

    def set_active(self, state: ProfileState, identifier: str) -> None:
        if identifier not in {kind.value for kind in ProfileType}:
            raise ValueError(f"unknown profile: {identifier}")
        state.active_profile_id = identifier
        self.save(state)

    def set_resize_strategy(self, state: ProfileState, identifier: str, strategy: str) -> None:
        if identifier not in {ProfileType.IMAGE.value, ProfileType.GIF.value}:
            raise ValueError("resize strategy belongs only to Image or GIF profiles")
        if strategy not in {"fit", "center-crop"}:
            raise ValueError(f"unsupported resize strategy: {strategy}")
        state.profile(identifier).settings["resize_strategy"] = strategy
        self.save(state)

    def set_gif_selection_slot(self, state: ProfileState, slot: str | None) -> None:
        if slot not in {None, "gif-profile"}:
            raise ValueError("unsupported GIF profile selected-media slot")
        state.profile(ProfileType.GIF.value).settings["selected_giphy_slot"] = slot
        self.save(state)

    def set_active_creative_preset(self, state: ProfileState, identifier: str) -> None:
        if identifier not in CREATIVE_PRESET_IDS:
            raise ValueError(f"unknown Creative preset: {identifier}")
        state.profile(ProfileType.CREATIVE.value).settings["active_preset_id"] = identifier
        self.save(state)

    def rename_creative_preset(self, state: ProfileState, identifier: str, name: str) -> None:
        if identifier not in CREATIVE_PRESET_IDS:
            raise ValueError(f"unknown Creative preset: {identifier}")
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("preset name cannot be empty")
        if len(cleaned) > CREATIVE_PRESET_NAME_MAX_LENGTH:
            raise ValueError(
                f"preset name cannot exceed {CREATIVE_PRESET_NAME_MAX_LENGTH} characters"
            )
        settings = state.profile(ProfileType.CREATIVE.value).settings
        next(preset for preset in settings["presets"] if preset["id"] == identifier)["name"] = cleaned
        self.save(state)

    def update_creative_preset(
        self, state: ProfileState, identifier: str, section: str, values: dict[str, object]
    ) -> None:
        if identifier not in CREATIVE_PRESET_IDS:
            raise ValueError(f"unknown Creative preset: {identifier}")
        if section not in {"background", "orbit_overlay", "telemetry_overlay"}:
            raise ValueError(f"unsupported Creative section: {section}")
        settings = state.profile(ProfileType.CREATIVE.value).settings
        preset = next(item for item in settings["presets"] if item["id"] == identifier)
        preset[section].update(values)
        # Round-trip through normalization before writing malformed UI state.
        normalized = profile_state_from_dict(state.to_dict())
        state.profiles = normalized.profiles
        self.save(state)
