"""Non-overlapping background telemetry snapshot polling."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable

from .discovery import discover_telemetry
from .models import (
    Availability,
    TelemetryDevice,
    TelemetryReading,
    TelemetrySensor,
    TelemetrySnapshot,
)
from .providers.base import TelemetryProvider


class TelemetryPoller:
    def __init__(
        self,
        providers: Iterable[TelemetryProvider],
        publish: Callable[[TelemetrySnapshot], None],
        *,
        interval_seconds: float = 1.0,
        rediscovery_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if interval_seconds <= 0 or rediscovery_seconds <= 0:
            raise ValueError("polling intervals must be positive")
        self._providers = tuple(providers)
        self._providers_by_id = {provider.provider_id: provider for provider in self._providers}
        self._publish = publish
        self.interval_seconds = interval_seconds
        self.rediscovery_seconds = rediscovery_seconds
        self._clock = clock
        self._sample_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._rediscovery_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_sensors: dict[str, TelemetrySensor] = {}
        self._known_sensors: dict[str, TelemetrySensor] = {}
        self._known_devices: dict[str, TelemetryDevice] = {}
        self._last_good: dict[str, tuple[float, float]] = {}
        self._last_discovery_at: float | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="nautiboy-telemetry", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None

    def request_rediscovery(self) -> None:
        self._rediscovery_event.set()

    def sample_once(self) -> TelemetrySnapshot | None:
        if not self._sample_lock.acquire(blocking=False):
            return None
        try:
            now = self._clock()
            discovery_due = (
                self._last_discovery_at is None
                or now - self._last_discovery_at >= self.rediscovery_seconds
                or self._rediscovery_event.is_set()
            )
            if discovery_due:
                self._rediscover(now)
            readings = tuple(
                self._reading(sensor, now)
                for sensor in sorted(self._known_sensors.values(), key=lambda item: item.sensor_id)
            )
            snapshot = TelemetrySnapshot(
                observed_at=now,
                devices=tuple(sorted(self._known_devices.values(), key=lambda item: item.device_id)),
                readings=readings,
            )
            self._publish(snapshot)
            return snapshot
        finally:
            self._sample_lock.release()

    def _rediscover(self, now: float) -> None:
        try:
            inventory = discover_telemetry(self._providers)
        except Exception:
            self._last_discovery_at = now
            self._rediscovery_event.clear()
            return
        self._current_sensors = {sensor.sensor_id: sensor for sensor in inventory.sensors}
        self._known_sensors.update(self._current_sensors)
        self._known_devices.update((device.device_id, device) for device in inventory.devices)
        self._last_discovery_at = now
        self._rediscovery_event.clear()

    def _reading(self, sensor: TelemetrySensor, now: float) -> TelemetryReading:
        last = self._last_good.get(sensor.sensor_id)
        if sensor.sensor_id not in self._current_sensors:
            return TelemetryReading(
                sensor, Availability.UNAVAILABLE, last[0] if last else None, now,
                last[0] if last else None, last[1] if last else None,
            )
        provider = self._providers_by_id.get(sensor.provider)
        if provider is None:
            return TelemetryReading(sensor, Availability.ERROR, None, now, error="provider unavailable")
        try:
            value = provider.sample(sensor)
        except Exception as error:
            if last:
                return TelemetryReading(
                    sensor, Availability.STALE, last[0], now, last[0], last[1], str(error)
                )
            return TelemetryReading(sensor, Availability.ERROR, None, now, error=str(error))
        self._last_good[sensor.sensor_id] = (value, now)
        return TelemetryReading(sensor, Availability.AVAILABLE, value, now, value, now)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            started = self._clock()
            try:
                self.sample_once()
            except Exception:
                # A consumer callback cannot terminate sampling.
                pass
            remaining = max(0.0, self.interval_seconds - (self._clock() - started))
            self._stop_event.wait(remaining)
