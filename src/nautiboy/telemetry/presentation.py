"""Versioned per-user presentation settings keyed by stable sensor ID."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any

PRESENTATION_SCHEMA_VERSION = 1
MAX_SELECTED_SENSORS = 2
MAX_DISPLAY_LABEL_LENGTH = 24
DEFAULT_FONT_COLOR = "#FFFFFF"
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ROOT_FIELDS = frozenset({"schema_version", "sensors"})
_ITEM_FIELDS = frozenset(
    {"sensor_id", "enabled", "visible", "display_label", "font_color", "font_family", "font_size", "position"}
)


class TelemetryPresentationError(RuntimeError):
    pass


def normalize_color(value: str) -> str:
    if not isinstance(value, str) or not _COLOR.fullmatch(value):
        raise ValueError("font color must use #RRGGBB format")
    return value.upper()


def normalize_label(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("display label must be text")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("display label cannot be empty")
    if len(cleaned) > MAX_DISPLAY_LABEL_LENGTH:
        raise ValueError(f"display label cannot exceed {MAX_DISPLAY_LABEL_LENGTH} characters")
    return cleaned


@dataclass(slots=True)
class SensorPresentation:
    sensor_id: str
    enabled: bool = False
    visible: bool = True
    display_label: str = "Temperature"
    font_color: str = DEFAULT_FONT_COLOR
    font_family: str | None = None
    font_size: int | None = None
    position: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **deepcopy(self.extra),
            "sensor_id": self.sensor_id,
            "enabled": self.enabled,
            "visible": self.visible,
            "display_label": self.display_label,
            "font_color": self.font_color,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "position": deepcopy(self.position),
        }


@dataclass(slots=True)
class TelemetryPresentationState:
    schema_version: int = PRESENTATION_SCHEMA_VERSION
    sensors: list[SensorPresentation] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    writable: bool = True

    @property
    def selected(self) -> tuple[SensorPresentation, ...]:
        return tuple(item for item in self.sensors if item.enabled)

    def sensor(self, sensor_id: str) -> SensorPresentation:
        return next(item for item in self.sensors if item.sensor_id == sensor_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            **deepcopy(self.extra),
            "schema_version": self.schema_version,
            "sensors": [item.to_dict() for item in self.sensors],
        }


def _item_from_dict(raw: object) -> SensorPresentation | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("sensor_id"), str) or not raw["sensor_id"]:
        return None
    try:
        label = normalize_label(raw.get("display_label", "Temperature"))
    except ValueError:
        label = "Temperature"
    try:
        color = normalize_color(raw.get("font_color", DEFAULT_FONT_COLOR))
    except ValueError:
        color = DEFAULT_FONT_COLOR
    font_family = raw.get("font_family") if isinstance(raw.get("font_family"), str) else None
    font_size = raw.get("font_size")
    if not isinstance(font_size, int) or isinstance(font_size, bool) or not 1 <= font_size <= 512:
        font_size = None
    position = deepcopy(raw.get("position")) if isinstance(raw.get("position"), dict) else None
    return SensorPresentation(
        sensor_id=raw["sensor_id"],
        enabled=raw.get("enabled") is True,
        visible=raw.get("visible") is not False,
        display_label=label,
        font_color=color,
        font_family=font_family,
        font_size=font_size,
        position=position,
        extra={key: deepcopy(value) for key, value in raw.items() if key not in _ITEM_FIELDS},
    )


def presentation_state_from_dict(document: object) -> TelemetryPresentationState:
    if isinstance(document, dict) and isinstance(document.get("schema_version"), int):
        if document["schema_version"] > PRESENTATION_SCHEMA_VERSION:
            return TelemetryPresentationState(writable=False)
    if not isinstance(document, dict) or document.get("schema_version") != PRESENTATION_SCHEMA_VERSION:
        return TelemetryPresentationState()
    raw_items = document.get("sensors")
    if not isinstance(raw_items, list):
        return TelemetryPresentationState()
    items: list[SensorPresentation] = []
    seen: set[str] = set()
    selected = 0
    for raw in raw_items:
        item = _item_from_dict(raw)
        if item is None or item.sensor_id in seen:
            continue
        seen.add(item.sensor_id)
        if item.enabled:
            selected += 1
            if selected > MAX_SELECTED_SENSORS:
                item.enabled = False
        items.append(item)
    return TelemetryPresentationState(
        sensors=items,
        extra={key: deepcopy(value) for key, value in document.items() if key not in _ROOT_FIELDS},
    )


def config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured else Path.home() / ".config"


def telemetry_presentation_path() -> Path:
    return config_home() / "nautiboy" / "telemetry.json"


class TelemetryPresentationStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or telemetry_presentation_path()

    def load(self) -> TelemetryPresentationState:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return TelemetryPresentationState()
        return presentation_state_from_dict(document)

    def save(self, state: TelemetryPresentationState) -> None:
        if not state.writable:
            raise TelemetryPresentationError(
                "telemetry settings were created by a newer NautiBoy version and will not be overwritten"
            )
        selected = 0
        for item in state.sensors:
            if item.enabled:
                selected += 1
                if selected > MAX_SELECTED_SENSORS:
                    item.enabled = False
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            temporary.chmod(0o600)
            temporary.replace(self.path)
        except OSError as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise TelemetryPresentationError(f"cannot save telemetry settings: {error}") from error

    def ensure_sensor(
        self, state: TelemetryPresentationState, sensor_id: str, default_label: str
    ) -> SensorPresentation:
        try:
            return state.sensor(sensor_id)
        except StopIteration:
            item = SensorPresentation(sensor_id=sensor_id, display_label=normalize_label(default_label))
            state.sensors.append(item)
            return item

    def set_selected(self, state: TelemetryPresentationState, sensor_id: str, selected: bool) -> None:
        item = state.sensor(sensor_id)
        if selected and not item.enabled and len(state.selected) >= MAX_SELECTED_SENSORS:
            raise ValueError(f"select up to {MAX_SELECTED_SENSORS} temperatures")
        item.enabled = selected
        self.save(state)

    def set_label(self, state: TelemetryPresentationState, sensor_id: str, label: str) -> None:
        state.sensor(sensor_id).display_label = normalize_label(label)
        self.save(state)

    def set_color(self, state: TelemetryPresentationState, sensor_id: str, color: str) -> None:
        state.sensor(sensor_id).font_color = normalize_color(color)
        self.save(state)
