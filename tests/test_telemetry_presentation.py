from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from nautiboy.telemetry import (
    DEFAULT_FONT_COLOR,
    MAX_DISPLAY_LABEL_LENGTH,
    MAX_SELECTED_SENSORS,
    TelemetryPresentationStore,
    telemetry_presentation_path,
)
from nautiboy.telemetry.presentation import presentation_state_from_dict


def _state_with_sensors(store: TelemetryPresentationStore, count: int = 4):
    state = store.load()
    for index in range(count):
        store.ensure_sensor(state, f"sensor-{index}", f"Temperature {index}")
    return state


def test_default_state_has_zero_selected_and_safe_defaults(tmp_path: Path) -> None:
    store = TelemetryPresentationStore(tmp_path / "telemetry.json")
    state = _state_with_sensors(store, 1)
    item = state.sensors[0]
    assert state.schema_version == 1 and state.selected == ()
    assert item.visible and not item.enabled
    assert item.font_color == DEFAULT_FONT_COLOR == "#FFFFFF"
    assert item.font_family is None and item.font_size is None and item.position is None


def test_zero_one_two_selected_and_third_rejected_without_replacement(tmp_path: Path) -> None:
    store = TelemetryPresentationStore(tmp_path / "telemetry.json")
    state = _state_with_sensors(store)
    store.set_selected(state, "sensor-0", True)
    store.set_selected(state, "sensor-1", True)
    assert [item.sensor_id for item in state.selected] == ["sensor-0", "sensor-1"]
    with pytest.raises(ValueError):
        store.set_selected(state, "sensor-2", True)
    assert [item.sensor_id for item in state.selected] == ["sensor-0", "sensor-1"]
    assert not state.sensor("sensor-2").enabled
    store.set_selected(state, "sensor-0", False)
    store.set_selected(state, "sensor-2", True)
    assert [item.sensor_id for item in state.selected] == ["sensor-1", "sensor-2"]


def test_save_enforces_two_selection_limit_for_programmatic_mutation(tmp_path: Path) -> None:
    store = TelemetryPresentationStore(tmp_path / "telemetry.json")
    state = _state_with_sensors(store)
    for item in state.sensors:
        item.enabled = True
    store.save(state)
    document = json.loads(store.path.read_text(encoding="utf-8"))
    assert [item["enabled"] for item in document["sensors"]] == [True, True, False, False]
    assert len(store.load().selected) == MAX_SELECTED_SENSORS


def test_malformed_excess_selection_recovers_first_two_deterministically() -> None:
    document = {
        "schema_version": 1,
        "sensors": [
            {"sensor_id": f"sensor-{index}", "enabled": True, "display_label": str(index)}
            for index in range(4)
        ],
    }
    state = presentation_state_from_dict(document)
    assert [item.sensor_id for item in state.selected] == ["sensor-0", "sensor-1"]
    assert [item.enabled for item in state.sensors] == [True, True, False, False]


def test_label_and_color_persist_without_changing_sensor_id(tmp_path: Path) -> None:
    store = TelemetryPresentationStore(tmp_path / "telemetry.json")
    state = _state_with_sensors(store, 2)
    store.set_selected(state, "sensor-0", True)
    store.set_label(state, "sensor-0", "  CPU  ")
    store.set_label(state, "sensor-1", "CPU")
    store.set_color(state, "sensor-0", "#a956ff")
    loaded = store.load()
    assert loaded.sensor("sensor-0").sensor_id == "sensor-0"
    assert loaded.sensor("sensor-0").display_label == "CPU"
    assert loaded.sensor("sensor-1").display_label == "CPU"
    assert loaded.sensor("sensor-0").font_color == "#A956FF"


@pytest.mark.parametrize("label", ["", "   ", "x" * (MAX_DISPLAY_LABEL_LENGTH + 1)])
def test_empty_or_excessive_labels_are_rejected(tmp_path: Path, label: str) -> None:
    store = TelemetryPresentationStore(tmp_path / "telemetry.json")
    state = _state_with_sensors(store, 1)
    with pytest.raises(ValueError):
        store.set_label(state, "sensor-0", label)


@pytest.mark.parametrize("color", ["red", "#FFF", "#GG0000", "123456", "#12345678"])
def test_invalid_font_colors_are_rejected(tmp_path: Path, color: str) -> None:
    store = TelemetryPresentationStore(tmp_path / "telemetry.json")
    state = _state_with_sensors(store, 1)
    with pytest.raises(ValueError):
        store.set_color(state, "sensor-0", color)


def test_malformed_config_recovers_and_unknown_fields_survive(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.json"
    path.write_text("not json", encoding="utf-8")
    assert TelemetryPresentationStore(path).load().sensors == []
    document = {
        "schema_version": 1,
        "future_root": 7,
        "sensors": [{
            "sensor_id": "sensor-0", "enabled": "yes", "display_label": "",
            "font_color": "bad", "future_item": {"kept": True},
        }],
    }
    state = presentation_state_from_dict(document)
    serialized = state.to_dict()
    assert not state.sensors[0].enabled
    assert state.sensors[0].display_label == "Temperature"
    assert state.sensors[0].font_color == DEFAULT_FONT_COLOR
    assert serialized["future_root"] == 7
    assert serialized["sensors"][0]["future_item"] == {"kept": True}


def test_disconnected_sensor_configuration_is_retained(tmp_path: Path) -> None:
    store = TelemetryPresentationStore(tmp_path / "telemetry.json")
    state = _state_with_sensors(store, 1)
    store.set_selected(state, "sensor-0", True)
    store.set_label(state, "sensor-0", "CPU")
    reloaded = store.load()
    store.ensure_sensor(reloaded, "new-sensor", "GPU")
    store.save(reloaded)
    assert store.load().sensor("sensor-0").display_label == "CPU"


def test_atomic_private_xdg_persistence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert telemetry_presentation_path() == tmp_path / "nautiboy/telemetry.json"
    store = TelemetryPresentationStore()
    store.save(_state_with_sensors(store, 1))
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert not store.path.with_name(".telemetry.json.tmp").exists()
