"""Provider-neutral telemetry discovery."""

from __future__ import annotations

from collections.abc import Iterable

from .models import TelemetryInventory
from .providers.base import TelemetryProvider


def discover_telemetry(providers: Iterable[TelemetryProvider]) -> TelemetryInventory:
    devices = {}
    sensors = {}
    for provider in providers:
        inventory = provider.discover()
        devices.update((device.device_id, device) for device in inventory.devices)
        sensors.update((sensor.sensor_id, sensor) for sensor in inventory.sensors)
    return TelemetryInventory(
        tuple(sorted(devices.values(), key=lambda item: item.device_id)),
        tuple(sorted(sensors.values(), key=lambda item: item.sensor_id)),
    )
