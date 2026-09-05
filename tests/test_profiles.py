from __future__ import annotations

import json
import stat
from pathlib import Path

from nautiboy.profiles.models import (
    CREATIVE_PRESET_IDS,
    CREATIVE_PRESET_NAME_MAX_LENGTH,
    PROFILE_NAMES,
    PROFILE_ORDER,
    SCHEMA_VERSION,
    ProfileType,
    default_profile_state,
    profile_state_from_dict,
)
from nautiboy.profiles.store import ProfileStore, profiles_path


def test_default_schema_ids_types_names_order_and_active_profile() -> None:
    state = default_profile_state()
    assert state.schema_version == SCHEMA_VERSION == 1
    assert state.active_profile_id == "image"
    assert [profile.identifier for profile in state.profiles] == [kind.value for kind in PROFILE_ORDER]
    assert [profile.profile_type for profile in state.profiles] == list(PROFILE_ORDER)
    assert [profile.name for profile in state.profiles] == [PROFILE_NAMES[kind] for kind in PROFILE_ORDER]


def test_default_schema_has_approved_independent_settings() -> None:
    state = default_profile_state()
    assert state.profile("thermals").settings == {}
    assert state.profile("image").settings == {"resize_strategy": "fit"}
    assert state.profile("gif").settings == {"resize_strategy": "fit"}
    creative = state.profile("creative").settings
    assert creative["active_preset_id"] == "preset_1"
    assert [preset["id"] for preset in creative["presets"]] == list(CREATIVE_PRESET_IDS)
    assert [preset["name"] for preset in creative["presets"]] == [
        "Preset 1", "Preset 2", "Preset 3", "Preset 4"
    ]
    for preset in creative["presets"]:
        assert preset["background"] == {
            "media_kind": None, "source_path": None, "resize_strategy": "fit"
        }
        assert preset["orbit_overlay"]["enabled"] is False
        assert preset["telemetry_overlay"] == {
            "enabled": False, "fields": [], "layout": {}, "style": {}
        }


def test_creative_active_preset_rename_and_independent_settings_persist(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    state = store.load()
    creative = state.profile("creative").settings
    creative["presets"][1]["background"]["resize_strategy"] = "center-crop"
    store.rename_creative_preset(state, "preset_1", "  Cyberpunk  ")
    store.set_active_creative_preset(state, "preset_2")
    loaded = store.load().profile("creative").settings
    assert loaded["active_preset_id"] == "preset_2"
    assert loaded["presets"][0]["id"] == "preset_1"
    assert loaded["presets"][0]["name"] == "Cyberpunk"
    assert loaded["presets"][0]["background"]["resize_strategy"] == "fit"
    assert loaded["presets"][1]["background"]["resize_strategy"] == "center-crop"


def test_creative_preset_names_reject_empty_and_excessive_length(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    state = store.load()
    for invalid in ("   ", "x" * (CREATIVE_PRESET_NAME_MAX_LENGTH + 1)):
        try:
            store.rename_creative_preset(state, "preset_1", invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid preset name was accepted")


def test_duplicate_creative_preset_names_are_safe(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    state = store.load()
    store.rename_creative_preset(state, "preset_1", "Purple")
    store.rename_creative_preset(state, "preset_2", "Purple")
    presets = store.load().profile("creative").settings["presets"]
    assert [(preset["id"], preset["name"]) for preset in presets[:2]] == [
        ("preset_1", "Purple"), ("preset_2", "Purple")
    ]


def test_malformed_creative_presets_and_active_id_recover_safely() -> None:
    document = default_profile_state().to_dict()
    creative = document["profiles"][3]["settings"]
    creative["active_preset_id"] = "missing"
    creative["presets"] = [
        {"id": "preset_1", "name": "", "background": "bad"},
        {"id": "preset_3", "name": "Christmas", "telemetry_overlay": {"fields": "bad"}},
    ]
    recovered = profile_state_from_dict(document).profile("creative").settings
    assert recovered["active_preset_id"] == "preset_1"
    assert [preset["id"] for preset in recovered["presets"]] == list(CREATIVE_PRESET_IDS)
    assert recovered["presets"][0]["name"] == "Preset 1"
    assert recovered["presets"][2]["name"] == "Christmas"
    assert recovered["presets"][2]["telemetry_overlay"]["fields"] == []


def test_previous_creative_development_shape_migrates_to_first_preset() -> None:
    document = default_profile_state().to_dict()
    document["profiles"][3]["settings"] = {
        "background": {"media_kind": "gif", "resize_strategy": "center-crop"},
        "telemetry_overlay": {"enabled": True, "fields": ["cpu_temperature"]},
    }
    creative = profile_state_from_dict(document).profile("creative").settings
    assert creative["presets"][0]["background"]["media_kind"] == "gif"
    assert creative["presets"][0]["telemetry_overlay"]["fields"] == ["cpu_temperature"]


def test_active_profile_and_independent_resize_settings_persist(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    state = store.load()
    store.set_resize_strategy(state, "image", "center-crop")
    store.set_active(state, "gif")
    loaded = store.load()
    assert loaded.active_profile_id == "gif"
    assert loaded.profile("image").settings["resize_strategy"] == "center-crop"
    assert loaded.profile("gif").settings["resize_strategy"] == "fit"


def test_xdg_path_and_config_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert profiles_path() == tmp_path / "nautiboy/profiles.json"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert profiles_path() == Path.home() / ".config/nautiboy/profiles.json"


def test_malformed_whole_document_recovers_defaults(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text("not json", encoding="utf-8")
    assert ProfileStore(path).load().to_dict() == default_profile_state().to_dict()


def test_malformed_individual_profile_recovers_only_that_profile() -> None:
    document = default_profile_state().to_dict()
    document["profiles"][1]["settings"] = {"resize_strategy": "center-crop", "future": 1}
    document["profiles"][2]["type"] = "broken"
    state = profile_state_from_dict(document)
    assert state.profile("image").settings == {"resize_strategy": "center-crop", "future": 1}
    assert state.profile("gif").settings == {"resize_strategy": "fit"}


def test_invalid_active_profile_recovers_to_image() -> None:
    document = default_profile_state().to_dict()
    document["active_profile_id"] = "unknown"
    assert profile_state_from_dict(document).active_profile_id == ProfileType.IMAGE.value


def test_unknown_fields_are_preserved() -> None:
    document = default_profile_state().to_dict()
    document["future_root"] = {"value": 1}
    document["profiles"][1]["future_profile"] = True
    document["profiles"][1]["settings"]["future_setting"] = "kept"
    serialized = profile_state_from_dict(document).to_dict()
    assert serialized["future_root"] == {"value": 1}
    assert serialized["profiles"][1]["future_profile"] is True
    assert serialized["profiles"][1]["settings"]["future_setting"] == "kept"


def test_future_schema_is_read_conservatively_without_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    future = {"schema_version": 99, "active_profile_id": "creative", "profiles": []}
    path.write_text(json.dumps(future), encoding="utf-8")
    loaded = ProfileStore(path).load()
    assert loaded.to_dict() == default_profile_state().to_dict()
    assert not loaded.writable
    assert json.loads(path.read_text(encoding="utf-8")) == future


def test_save_is_atomic_private_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    path = tmp_path / "config/profiles.json"
    store = ProfileStore(path)
    store.save(default_profile_state())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not path.with_name(".profiles.json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
