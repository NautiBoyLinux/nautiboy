from __future__ import annotations

import dataclasses
import os
import threading
from pathlib import Path

import pytest

from nautiboy.telemetry import (
    Availability,
    SemanticRole,
    TelemetryDevice,
    TelemetryInventory,
    TelemetryPoller,
    TelemetrySensor,
)
from nautiboy.telemetry.providers.linux_hwmon import HwmonReadError, LinuxHwmonProvider


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="ascii")


def _hwmon(
    sysroot: Path,
    number: int,
    *,
    driver: str,
    device_path: str,
    temperatures: list[tuple[int, str | None, str]],
    pci_id: str | None = None,
    boot_vga: str | None = None,
) -> Path:
    device = sysroot / device_path
    device.mkdir(parents=True, exist_ok=True)
    uevent = [f"DRIVER={driver}"]
    if pci_id:
        uevent.extend((f"PCI_ID={pci_id}", f"PCI_SLOT_NAME={device.name}"))
        vendor, product = pci_id.split(":")
        _write(device / "vendor", f"0x{vendor.lower()}\n")
        _write(device / "device", f"0x{product.lower()}\n")
    if boot_vga is not None:
        _write(device / "boot_vga", f"{boot_vga}\n")
    _write(device / "uevent", "\n".join(uevent) + "\n")
    node = sysroot / "class/hwmon" / f"hwmon{number}"
    node.mkdir(parents=True, exist_ok=True)
    _write(node / "name", f"{driver}\n")
    (node / "device").symlink_to(os.path.relpath(device, node))
    for channel, label, value in temperatures:
        _write(node / f"temp{channel}_input", value)
        if label is not None:
            _write(node / f"temp{channel}_label", f"{label}\n")
    return node


@pytest.fixture
def amd_sysfs(tmp_path: Path) -> Path:
    sysroot = tmp_path / "sys"
    _hwmon(
        sysroot, 4, driver="k10temp", device_path="devices/pci0000:00/0000:00:18.3",
        pci_id="1022:14E3", temperatures=[(1, "Tctl", "50125\n"), (3, "Tccd1", "41250\n")],
    )
    _hwmon(
        sysroot, 1, driver="amdgpu", device_path="devices/pci0000:00/0000:03:00.0",
        pci_id="1002:7550", boot_vga="1",
        temperatures=[(1, "edge", "40000\n"), (2, "junction", "43000\n"), (3, "mem", "62000\n")],
    )
    _hwmon(
        sysroot, 2, driver="amdgpu", device_path="devices/pci0000:00/0000:76:00.0",
        pci_id="1002:164E", boot_vga="0", temperatures=[(1, "edge", "38000\n")],
    )
    return sysroot


def _provider(sysroot: Path) -> LinuxHwmonProvider:
    return LinuxHwmonProvider(sysroot / "class/hwmon", sys_root=sysroot)


def test_hwmon_enumeration_channels_labels_conversion_and_grouping(amd_sysfs: Path) -> None:
    provider = _provider(amd_sysfs)
    inventory = provider.discover()
    assert len(inventory.devices) == 3
    assert len(inventory.sensors) == 6
    discrete = next(device for device in inventory.devices if device.metadata.get("boot_vga") == "1")
    grouped = [sensor for sensor in inventory.sensors if sensor.device_id == discrete.device_id]
    assert [sensor.raw_label for sensor in grouped] == ["edge", "junction", "mem"]
    assert [provider.sample(sensor) for sensor in grouped] == [40.0, 43.0, 62.0]


def test_pci_ids_roles_and_integrated_discrete_distinction(amd_sysfs: Path) -> None:
    inventory = _provider(amd_sysfs).discover()
    by_label = {(sensor.device_id, sensor.raw_label): sensor for sensor in inventory.sensors}
    discrete = next(device for device in inventory.devices if device.metadata.get("boot_vga") == "1")
    integrated = next(device for device in inventory.devices if device.metadata.get("boot_vga") == "0")
    cpu = next(device for device in inventory.devices if device.driver == "k10temp")
    assert discrete.bus_address == "0000:03:00.0" and "1002:7550" in discrete.display_name
    assert integrated.bus_address == "0000:76:00.0" and "Integrated" in integrated.display_name
    assert by_label[(discrete.device_id, "edge")].semantic_role is SemanticRole.GPU_EDGE
    assert by_label[(discrete.device_id, "junction")].semantic_role is SemanticRole.GPU_HOTSPOT
    assert by_label[(discrete.device_id, "mem")].semantic_role is SemanticRole.GPU_MEMORY
    assert by_label[(integrated.device_id, "edge")].default_label == "Integrated GPU"
    assert by_label[(cpu.device_id, "Tctl")].semantic_role is SemanticRole.CPU_PACKAGE
    assert by_label[(cpu.device_id, "Tccd1")].semantic_role is SemanticRole.CPU_CCD


def test_sensor_ids_ignore_volatile_hwmon_number(amd_sysfs: Path) -> None:
    provider = _provider(amd_sysfs)
    before = {sensor.sensor_id for sensor in provider.discover().sensors}
    (amd_sysfs / "class/hwmon/hwmon1").rename(amd_sysfs / "class/hwmon/hwmon91")
    after = {sensor.sensor_id for sensor in provider.discover().sensors}
    assert before == after
    assert not any("hwmon" in sensor_id.removeprefix("linux-hwmon") for sensor_id in before)
    assert "linux-hwmon:pci-0000_03_00_0:amdgpu:temp1" in before


def test_non_pci_identity_fallback_is_deterministic_and_unlabeled_is_safe(tmp_path: Path) -> None:
    sysroot = tmp_path / "sys"
    _hwmon(
        sysroot, 0, driver="boardtemp", device_path="devices/platform/example-board",
        temperatures=[(1, None, "32500\n")],
    )
    provider = _provider(sysroot)
    first = provider.discover()
    (sysroot / "class/hwmon/hwmon0").rename(sysroot / "class/hwmon/hwmon8")
    second = provider.discover()
    assert first.devices[0].device_id == second.devices[0].device_id
    assert first.devices[0].bus_type == "sysfs"
    assert first.sensors[0].sensor_id == second.sensors[0].sensor_id
    assert first.sensors[0].raw_label is None
    assert first.sensors[0].default_label == "Temperature"


def test_non_pci_children_of_same_pci_controller_do_not_collide(tmp_path: Path) -> None:
    sysroot = tmp_path / "sys"
    for number, address in ((0, "17-0051"), (1, "17-0053")):
        _hwmon(
            sysroot, number, driver="spd5118",
            device_path=f"devices/pci0000:00/0000:00:14.0/i2c-17/{address}",
            temperatures=[(1, None, "35000\n")],
        )
    inventory = _provider(sysroot).discover()
    assert len(inventory.devices) == 2
    assert len({device.device_id for device in inventory.devices}) == 2
    assert len({sensor.sensor_id for sensor in inventory.sensors}) == 2


@pytest.mark.parametrize("value", ["not-a-number\n", "301000\n", "-274000\n", "1" * 40])
def test_invalid_or_unbounded_temperature_values_raise(tmp_path: Path, value: str) -> None:
    sysroot = tmp_path / "sys"
    node = _hwmon(
        sysroot, 0, driver="test", device_path="devices/platform/test",
        temperatures=[(1, "Broken", value)],
    )
    provider = _provider(sysroot)
    sensor = provider.discover().sensors[0]
    with pytest.raises(HwmonReadError):
        provider.sample(sensor)
    (node / "temp1_input").unlink()
    with pytest.raises(HwmonReadError):
        provider.sample(sensor)


def test_provider_opens_sysfs_read_only(monkeypatch, amd_sysfs: Path) -> None:
    original = Path.open
    modes: list[str] = []

    def observing_open(path, mode="r", *args, **kwargs):
        modes.append(mode)
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", observing_open)
    provider = _provider(amd_sysfs)
    sensor = provider.discover().sensors[0]
    provider.sample(sensor)
    assert modes and all("w" not in mode and "a" not in mode and "+" not in mode for mode in modes)


class FakeProvider:
    provider_id = "fake"

    def __init__(self) -> None:
        self.device = TelemetryDevice("fake:device", "fake", "device", "fake", "fake", "test", None, "Fake")
        from nautiboy.telemetry import Metric, Unit
        self.sensor = TelemetrySensor(
            "fake:device:test:temp1", self.device.device_id, "fake", "temp1", "CPU",
            Metric.TEMPERATURE, SemanticRole.CPU_PACKAGE, Unit.CELSIUS, "CPU",
        )
        self.present = True
        self.value: float | Exception = 42.0
        self.discoveries = 0
        self.sample_started: threading.Event | None = None
        self.sample_release: threading.Event | None = None

    def discover(self) -> TelemetryInventory:
        self.discoveries += 1
        return TelemetryInventory((self.device,), (self.sensor,) if self.present else ())

    def sample(self, sensor: TelemetrySensor) -> float:
        if self.sample_started:
            self.sample_started.set()
        if self.sample_release:
            self.sample_release.wait(1)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def test_poller_stale_error_unavailable_and_returning_identity() -> None:
    provider = FakeProvider()
    clock_value = [10.0]
    snapshots = []
    poller = TelemetryPoller([provider], snapshots.append, clock=lambda: clock_value[0])
    good = poller.sample_once()
    assert good and good.readings[0].availability is Availability.AVAILABLE
    provider.value = OSError("temporary")
    clock_value[0] = 11.0
    stale = poller.sample_once()
    assert stale and stale.readings[0].availability is Availability.STALE
    assert stale.readings[0].value == 42.0 and stale.readings[0].last_good_at == 10.0
    assert stale.readings[0].age_seconds == 1.0
    provider.present = False
    clock_value[0] = 41.0
    missing = poller.sample_once()
    assert missing and missing.readings[0].availability is Availability.UNAVAILABLE
    provider.present = True
    provider.value = 43.0
    poller.request_rediscovery()
    returned = poller.sample_once()
    assert returned and returned.readings[0].sensor.sensor_id == provider.sensor.sensor_id
    assert returned.readings[0].availability is Availability.AVAILABLE


def test_first_failed_read_is_error_not_zero() -> None:
    provider = FakeProvider()
    provider.value = OSError("no sample")
    snapshot = TelemetryPoller([provider], lambda _snapshot: None).sample_once()
    assert snapshot
    reading = snapshot.readings[0]
    assert reading.availability is Availability.ERROR
    assert reading.value is None and reading.last_good_value is None


def test_explicit_and_bounded_rediscovery() -> None:
    provider = FakeProvider()
    now = [0.0]
    poller = TelemetryPoller(
        [provider], lambda _snapshot: None, rediscovery_seconds=30, clock=lambda: now[0]
    )
    poller.sample_once()
    now[0] = 1.0
    poller.sample_once()
    assert provider.discoveries == 1
    poller.request_rediscovery()
    poller.sample_once()
    assert provider.discoveries == 2


def test_poller_drops_overlapping_sample_pass() -> None:
    provider = FakeProvider()
    provider.sample_started = threading.Event()
    provider.sample_release = threading.Event()
    poller = TelemetryPoller([provider], lambda _snapshot: None)
    thread = threading.Thread(target=poller.sample_once)
    thread.start()
    assert provider.sample_started.wait(1)
    assert poller.sample_once() is None
    provider.sample_release.set()
    thread.join(1)
    assert not thread.is_alive()


def test_snapshots_and_metadata_are_immutable() -> None:
    provider = FakeProvider()
    snapshot = TelemetryPoller([provider], lambda _snapshot: None).sample_once()
    assert snapshot
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.observed_at = 2.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        snapshot.devices[0].metadata["new"] = "value"  # type: ignore[index]


def test_background_poller_publishes_and_stops_cleanly() -> None:
    provider = FakeProvider()
    published = threading.Event()
    poller = TelemetryPoller([provider], lambda _snapshot: published.set(), interval_seconds=0.01)
    poller.start()
    assert published.wait(1)
    assert poller.running
    poller.stop()
    assert not poller.running
