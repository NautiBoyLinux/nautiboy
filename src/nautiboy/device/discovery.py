"""Read-only Nautilus discovery through hidraw sysfs and udev monitoring."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pyudev

from .identity import DeviceIdentity, validate_supported_identity


class DiscoveryError(RuntimeError):
    """The sysfs hierarchy was incomplete or changed during discovery."""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise DiscoveryError(f"cannot read {path}: {error}") from error


def identity_from_sysfs(hidraw_class_path: Path) -> DeviceIdentity:
    hidraw_class_path = Path(hidraw_class_path)
    hid_device = (hidraw_class_path / "device").resolve(strict=True)
    interface = hid_device.parent
    usb_device = interface.parent
    identity = DeviceIdentity(
        device_node=Path("/dev") / hidraw_class_path.name,
        sysfs_path=hid_device,
        vid=int(_read(usb_device / "idVendor"), 16),
        pid=int(_read(usb_device / "idProduct"), 16),
        interface=int(_read(interface / "bInterfaceNumber"), 16),
        manufacturer=_read(usb_device / "manufacturer"),
        product=_read(usb_device / "product"),
        serial=_read(usb_device / "serial") if (usb_device / "serial").exists() else None,
    )
    return identity


def identity_from_device_node(device_node: Path) -> DeviceIdentity:
    node = Path(device_node)
    if node.parent != Path("/dev") or not node.name.startswith("hidraw"):
        raise DiscoveryError(f"not a hidraw device node: {node}")
    return identity_from_sysfs(Path("/sys/class/hidraw") / node.name)


def discover_supported_devices(root: Path = Path("/sys/class/hidraw")) -> tuple[DeviceIdentity, ...]:
    devices: list[DeviceIdentity] = []
    for entry in sorted(root.glob("hidraw*")):
        try:
            identity = identity_from_sysfs(entry)
            validate_supported_identity(identity)
        except (DiscoveryError, FileNotFoundError, ValueError):
            continue
        devices.append(identity)
    return tuple(devices)


class DeviceMonitor:
    """Translate udev hidraw changes into a simple rescan notification."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._observer: pyudev.MonitorObserver | None = None

    def start(self) -> None:
        if self._observer is not None:
            return
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem="hidraw")

        def changed(action: str, _device: pyudev.Device) -> None:
            if action in {"add", "remove", "change", "bind", "unbind"}:
                self._callback()

        self._observer = pyudev.MonitorObserver(monitor, callback=changed, name="nautilus-udev")
        self._observer.start()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer = None
