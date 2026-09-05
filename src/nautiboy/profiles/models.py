"""Versioned profile models with conservative recovery."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = 1
CREATIVE_PRESET_IDS = ("preset_1", "preset_2", "preset_3", "preset_4")
CREATIVE_PRESET_NAME_MAX_LENGTH = 20


class ProfileType(str, Enum):
    THERMALS = "thermals"
    IMAGE = "image"
    GIF = "gif"
    CREATIVE = "creative"


PROFILE_ORDER = tuple(ProfileType)
PROFILE_NAMES = {
    ProfileType.THERMALS: "Thermals",
    ProfileType.IMAGE: "Image",
    ProfileType.GIF: "GIF",
    ProfileType.CREATIVE: "Creative",
}


def default_creative_preset(identifier: str) -> dict[str, Any]:
    number = CREATIVE_PRESET_IDS.index(identifier) + 1
    return {
        "id": identifier,
        "name": f"Preset {number}",
        "background": {
            "media_kind": None,
            "source_path": None,
            "resize_strategy": "fit",
            "selected_giphy_slot": None,
        },
        "orbit_overlay": {
            "enabled": False,
            "animation_enabled": True,
            "follow_telemetry_colors": True,
            "primary_color": "#9B30FF",
            "secondary_color": "#00D9FF",
        },
        "telemetry_overlay": {
            "enabled": False,
            "fields": [],
            "layout": {},
            "style": {},
        },
    }


DEFAULT_SETTINGS: dict[ProfileType, dict[str, Any]] = {
    ProfileType.THERMALS: {},
    ProfileType.IMAGE: {"resize_strategy": "fit"},
    ProfileType.GIF: {"resize_strategy": "fit", "selected_giphy_slot": None},
    ProfileType.CREATIVE: {
        "active_preset_id": "preset_1",
        "presets": [default_creative_preset(identifier) for identifier in CREATIVE_PRESET_IDS],
    },
}
_PROFILE_FIELDS = frozenset({"id", "name", "type", "settings"})
_ROOT_FIELDS = frozenset({"schema_version", "active_profile_id", "profiles"})


def _merge_defaults(defaults: Mapping[str, Any], supplied: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(supplied))
    for key, default in defaults.items():
        current = merged.get(key)
        if isinstance(default, dict):
            merged[key] = _merge_defaults(default, current if isinstance(current, dict) else {})
        elif key not in merged or (
            not isinstance(current, type(default)) and default is not None
        ):
            merged[key] = deepcopy(default)
    return merged


def _settings(profile_type: ProfileType, value: object) -> dict[str, Any]:
    supplied = value if isinstance(value, dict) else {}
    if profile_type is ProfileType.CREATIVE:
        return _creative_settings(supplied)
    result = _merge_defaults(DEFAULT_SETTINGS[profile_type], supplied)
    if profile_type in {ProfileType.IMAGE, ProfileType.GIF}:
        if result.get("resize_strategy") not in {"fit", "center-crop"}:
            result["resize_strategy"] = "fit"
    if profile_type is ProfileType.GIF and result.get("selected_giphy_slot") not in {
        None, "gif-profile"
    }:
        result["selected_giphy_slot"] = None
    return result


def _creative_preset(identifier: str, supplied: object) -> dict[str, Any]:
    raw = supplied if isinstance(supplied, dict) else {}
    preset = _merge_defaults(default_creative_preset(identifier), raw)
    preset["id"] = identifier
    name = preset.get("name")
    if not isinstance(name, str) or not name.strip():
        preset["name"] = default_creative_preset(identifier)["name"]
    else:
        preset["name"] = name.strip()[:CREATIVE_PRESET_NAME_MAX_LENGTH]
    background = preset["background"]
    if background.get("media_kind") not in {None, "image", "gif"}:
        background["media_kind"] = None
    if not isinstance(background.get("source_path"), str) or not background["source_path"].strip():
        background["source_path"] = None
    if background.get("resize_strategy") not in {"fit", "center-crop"}:
        background["resize_strategy"] = "fit"
    expected_slot = f"creative-{identifier}"
    if background.get("selected_giphy_slot") not in {None, expected_slot}:
        background["selected_giphy_slot"] = None
    overlay = preset["telemetry_overlay"]
    if not isinstance(overlay.get("enabled"), bool):
        overlay["enabled"] = False
    if not isinstance(overlay.get("fields"), list):
        overlay["fields"] = []
    for key in ("layout", "style"):
        if not isinstance(overlay.get(key), dict):
            overlay[key] = {}
    orbit = preset["orbit_overlay"]
    for key, default in (
        ("enabled", False),
        ("animation_enabled", True),
        ("follow_telemetry_colors", True),
    ):
        if not isinstance(orbit.get(key), bool):
            orbit[key] = default
    for key, default in (("primary_color", "#9B30FF"), ("secondary_color", "#00D9FF")):
        value = orbit.get(key)
        if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
            orbit[key] = default
            continue
        try:
            int(value[1:], 16)
        except ValueError:
            orbit[key] = default
        else:
            orbit[key] = value.upper()
    return preset


def _creative_settings(supplied: Mapping[str, Any]) -> dict[str, Any]:
    raw_presets = supplied.get("presets")
    by_id = (
        {
            value.get("id"): value
            for value in raw_presets
            if isinstance(value, dict) and isinstance(value.get("id"), str)
        }
        if isinstance(raw_presets, list)
        else {}
    )
    # Preserve the earlier development schema by treating its Creative values as preset 1.
    if not by_id and ("background" in supplied or "telemetry_overlay" in supplied):
        by_id["preset_1"] = {
            "background": supplied.get("background"),
            "telemetry_overlay": supplied.get("telemetry_overlay"),
        }
    result = {
        key: deepcopy(value)
        for key, value in supplied.items()
        if key not in {"active_preset_id", "presets", "background", "telemetry_overlay"}
    }
    result["active_preset_id"] = (
        supplied.get("active_preset_id")
        if supplied.get("active_preset_id") in CREATIVE_PRESET_IDS
        else "preset_1"
    )
    result["presets"] = [
        _creative_preset(identifier, by_id.get(identifier))
        for identifier in CREATIVE_PRESET_IDS
    ]
    return result


@dataclass(slots=True)
class Profile:
    identifier: str
    name: str
    profile_type: ProfileType
    settings: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **deepcopy(self.extra),
            "id": self.identifier,
            "name": self.name,
            "type": self.profile_type.value,
            "settings": deepcopy(self.settings),
        }


@dataclass(slots=True)
class ProfileState:
    schema_version: int
    active_profile_id: str
    profiles: list[Profile]
    extra: dict[str, Any] = field(default_factory=dict)
    writable: bool = True

    @property
    def active_profile(self) -> Profile:
        return self.profile(self.active_profile_id)

    def profile(self, identifier: str) -> Profile:
        return next(profile for profile in self.profiles if profile.identifier == identifier)

    def is_active(self, identifier: str) -> bool:
        return self.active_profile_id == identifier

    def to_dict(self) -> dict[str, Any]:
        return {
            **deepcopy(self.extra),
            "schema_version": self.schema_version,
            "active_profile_id": self.active_profile_id,
            "profiles": [profile.to_dict() for profile in self.profiles],
        }


def default_profile(profile_type: ProfileType) -> Profile:
    return Profile(
        profile_type.value,
        PROFILE_NAMES[profile_type],
        profile_type,
        deepcopy(DEFAULT_SETTINGS[profile_type]),
    )


def default_profile_state() -> ProfileState:
    return ProfileState(
        SCHEMA_VERSION,
        ProfileType.IMAGE.value,
        [default_profile(kind) for kind in PROFILE_ORDER],
    )


def profile_state_from_dict(document: object) -> ProfileState:
    if (
        isinstance(document, dict)
        and isinstance(document.get("schema_version"), int)
        and document["schema_version"] > SCHEMA_VERSION
    ):
        state = default_profile_state()
        state.writable = False
        return state
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        return default_profile_state()
    raw_profiles = document.get("profiles")
    if not isinstance(raw_profiles, list):
        return default_profile_state()
    by_id = {
        value.get("id"): value
        for value in raw_profiles
        if isinstance(value, dict) and isinstance(value.get("id"), str)
    }
    profiles: list[Profile] = []
    for kind in PROFILE_ORDER:
        raw = by_id.get(kind.value)
        if not isinstance(raw, dict) or raw.get("type") != kind.value:
            profiles.append(default_profile(kind))
            continue
        profiles.append(
            Profile(
                kind.value,
                PROFILE_NAMES[kind],
                kind,
                _settings(kind, raw.get("settings")),
                {key: deepcopy(value) for key, value in raw.items() if key not in _PROFILE_FIELDS},
            )
        )
    active = document.get("active_profile_id")
    if active not in {kind.value for kind in PROFILE_ORDER}:
        active = ProfileType.IMAGE.value
    return ProfileState(
        SCHEMA_VERSION,
        active,
        profiles,
        {key: deepcopy(value) for key, value in document.items() if key not in _ROOT_FIELDS},
    )
