"""Bounded, read-only Linux hwmon discovery and temperature sampling."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..models import (
    Metric,
    SemanticRole,
    TelemetryDevice,
    TelemetryInventory,
    TelemetrySensor,
    Unit,
    frozen_metadata,
)

PROVIDER_ID = "linux-hwmon"
_PCI_COMPONENT = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$")
_TEMP_INPUT = re.compile(r"^(temp[0-9]+)_input$")
_MIN_MILLIDEGREES = -273_150
_MAX_MILLIDEGREES = 300_000


class HwmonReadError(RuntimeError):
    pass


def _bounded_text(path: Path, limit: int) -> str:
    try:
        with path.open("r", encoding="ascii", errors="strict") as stream:
            value = stream.read(limit + 1)
    except (OSError, UnicodeError) as error:
        raise HwmonReadError(f"cannot read {path.name}: {error}") from error
    if len(value) > limit:
        raise HwmonReadError(f"{path.name} exceeds {limit} bytes")
    return value.strip()


def _safe_text(path: Path, limit: int) -> str | None:
    try:
        value = _bounded_text(path, limit)
    except HwmonReadError:
        return None
    return value or None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def _device_location(device_path: Path, sys_root: Path) -> tuple[str, str, str | None]:
    # Only a device that is itself a PCI function may use the PCI address.
    # I2C, NVMe, and other children can share an upstream PCI controller.
    if _PCI_COMPONENT.fullmatch(device_path.name):
        address = device_path.name.lower()
        return f"pci-{_slug(address)}", "pci", address
    try:
        relative = device_path.relative_to(sys_root).as_posix()
    except ValueError:
        relative = device_path.as_posix()
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
    return f"sysfs-{digest}", "sysfs", None


def _semantic_role(driver: str, label: str | None) -> tuple[SemanticRole, str]:
    normalized = (label or "").casefold()
    if driver == "k10temp":
        if normalized.startswith("tccd"):
            return SemanticRole.CPU_CCD, "CPU CCD"
        if normalized == "tctl":
            return SemanticRole.CPU_PACKAGE, "CPU"
    if driver == "amdgpu":
        if normalized == "edge":
            return SemanticRole.GPU_EDGE, "GPU"
        if normalized in {"junction", "hotspot"}:
            return SemanticRole.GPU_HOTSPOT, "GPU Hotspot"
        if normalized in {"mem", "memory"}:
            return SemanticRole.GPU_MEMORY, "GPU Memory"
    return SemanticRole.TEMPERATURE, label or "Temperature"


class LinuxHwmonProvider:
    provider_id = PROVIDER_ID

    def __init__(self, root: Path = Path("/sys/class/hwmon"), *, sys_root: Path | None = None) -> None:
        self.root = root
        self.sys_root = sys_root or (root.parents[1] if len(root.parents) > 1 else Path("/sys"))
        self._inputs: dict[str, Path] = {}

    def discover(self) -> TelemetryInventory:
        devices: dict[str, TelemetryDevice] = {}
        sensors: list[TelemetrySensor] = []
        inputs: dict[str, Path] = {}
        try:
            hwmons = sorted(self.root.glob("hwmon*"), key=lambda path: path.name)
        except OSError:
            hwmons = []
        for hwmon in hwmons:
            driver = _safe_text(hwmon / "name", 64)
            if not driver:
                continue
            device_link = hwmon / "device"
            try:
                device_path = device_link.resolve(strict=True)
            except OSError:
                try:
                    resolved_hwmon = hwmon.resolve(strict=True)
                except OSError:
                    continue
                device_path = resolved_hwmon.parent if resolved_hwmon.name.startswith("hwmon") else resolved_hwmon
            identity_key, bus_type, bus_address = _device_location(device_path, self.sys_root)
            device_id = f"{PROVIDER_ID}:{identity_key}"
            metadata = self._device_metadata(device_path)
            if device_id not in devices:
                devices[device_id] = TelemetryDevice(
                    device_id=device_id,
                    provider=PROVIDER_ID,
                    identity_key=identity_key,
                    raw_name=driver,
                    driver=metadata.get("DRIVER", driver),
                    bus_type=bus_type,
                    bus_address=bus_address,
                    display_name=self._device_display_name(driver, metadata),
                    metadata=frozen_metadata(metadata),
                )
            try:
                entries = sorted(hwmon.iterdir(), key=lambda path: path.name)
            except OSError:
                continue
            for entry in entries:
                match = _TEMP_INPUT.fullmatch(entry.name)
                if not match or not entry.is_file():
                    continue
                channel = match.group(1)
                label = _safe_text(hwmon / f"{channel}_label", 128)
                sensor_id = f"{PROVIDER_ID}:{identity_key}:{_slug(driver)}:{channel}"
                role, default_label = _semantic_role(driver, label)
                if driver == "amdgpu" and role is SemanticRole.GPU_EDGE:
                    default_label = "GPU" if metadata.get("boot_vga") == "1" else "Integrated GPU"
                sensors.append(
                    TelemetrySensor(
                        sensor_id=sensor_id,
                        device_id=device_id,
                        provider=PROVIDER_ID,
                        channel=channel,
                        raw_label=label,
                        metric=Metric.TEMPERATURE,
                        semantic_role=role,
                        unit=Unit.CELSIUS,
                        default_label=default_label,
                        metadata=frozen_metadata({"input_attribute": entry.name}),
                    )
                )
                inputs[sensor_id] = entry
        self._inputs = inputs
        return TelemetryInventory(
            tuple(sorted(devices.values(), key=lambda device: device.device_id)),
            tuple(sorted(sensors, key=lambda sensor: sensor.sensor_id)),
        )

    def sample(self, sensor: TelemetrySensor) -> float:
        path = self._inputs.get(sensor.sensor_id)
        if path is None:
            raise HwmonReadError("sensor is not present in the current discovery set")
        raw = _bounded_text(path, 32)
        try:
            millidegrees = int(raw, 10)
        except ValueError as error:
            raise HwmonReadError(f"invalid millidegree value for {sensor.channel}") from error
        if not _MIN_MILLIDEGREES <= millidegrees <= _MAX_MILLIDEGREES:
            raise HwmonReadError(f"millidegree value out of bounds for {sensor.channel}")
        return millidegrees / 1000.0

    @staticmethod
    def _device_metadata(device_path: Path) -> dict[str, str]:
        metadata: dict[str, str] = {}
        uevent = _safe_text(device_path / "uevent", 4096)
        if uevent:
            for line in uevent.splitlines():
                key, separator, value = line.partition("=")
                if separator and key in {"DRIVER", "PCI_ID", "PCI_SLOT_NAME", "MODALIAS"}:
                    metadata[key] = value
        for name in ("vendor", "device", "subsystem_vendor", "subsystem_device", "class", "boot_vga"):
            value = _safe_text(device_path / name, 64)
            if value is not None:
                metadata[name] = value
        metadata["canonical_path"] = device_path.as_posix()
        return metadata

    @staticmethod
    def _device_display_name(driver: str, metadata: dict[str, str]) -> str:
        if driver == "k10temp":
            return "CPU (k10temp)"
        if driver == "amdgpu":
            kind = "AMD GPU" if metadata.get("boot_vga") == "1" else "Integrated AMD GPU"
            pci_id = metadata.get("PCI_ID")
            return f"{kind} ({pci_id})" if pci_id else kind
        return driver
