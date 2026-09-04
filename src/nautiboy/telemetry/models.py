"""Immutable normalized telemetry models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class Metric(str, Enum):
    TEMPERATURE = "temperature"


class Unit(str, Enum):
    CELSIUS = "celsius"


class SemanticRole(str, Enum):
    TEMPERATURE = "temperature"
    CPU_PACKAGE = "cpu_package"
    CPU_CCD = "cpu_ccd"
    GPU_EDGE = "gpu_edge"
    GPU_HOTSPOT = "gpu_hotspot"
    GPU_MEMORY = "gpu_memory"


class Availability(str, Enum):
    AVAILABLE = "available"
    STALE = "stale"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


def frozen_metadata(values: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True, slots=True)
class TelemetryDevice:
    device_id: str
    provider: str
    identity_key: str
    raw_name: str
    driver: str
    bus_type: str
    bus_address: str | None
    display_name: str
    metadata: Mapping[str, str] = field(default_factory=frozen_metadata)


@dataclass(frozen=True, slots=True)
class TelemetrySensor:
    sensor_id: str
    device_id: str
    provider: str
    channel: str
    raw_label: str | None
    metric: Metric
    semantic_role: SemanticRole
    unit: Unit
    default_label: str
    metadata: Mapping[str, str] = field(default_factory=frozen_metadata)


@dataclass(frozen=True, slots=True)
class TelemetryReading:
    sensor: TelemetrySensor
    availability: Availability
    value: float | None
    observed_at: float
    last_good_value: float | None = None
    last_good_at: float | None = None
    error: str | None = None

    @property
    def age_seconds(self) -> float | None:
        if self.last_good_at is None:
            return None
        return max(0.0, self.observed_at - self.last_good_at)


@dataclass(frozen=True, slots=True)
class TelemetryInventory:
    devices: tuple[TelemetryDevice, ...]
    sensors: tuple[TelemetrySensor, ...]


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    observed_at: float
    devices: tuple[TelemetryDevice, ...]
    readings: tuple[TelemetryReading, ...]

    def reading(self, sensor_id: str) -> TelemetryReading:
        return next(reading for reading in self.readings if reading.sensor.sensor_id == sensor_id)
