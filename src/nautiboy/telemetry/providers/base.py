"""Provider boundary for read-only telemetry sources."""

from __future__ import annotations

from typing import Protocol

from ..models import TelemetryInventory, TelemetrySensor


class TelemetryProvider(Protocol):
    provider_id: str

    def discover(self) -> TelemetryInventory: ...

    def sample(self, sensor: TelemetrySensor) -> float: ...
