"""Immutable USB/HID identity and allowlist checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nautiboy.protocol.constants import SUPPORTED_DEVICES


class UnsupportedDeviceError(ValueError):
    """A hidraw node does not match the strict supported-device allowlist."""


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_node: Path
    sysfs_path: Path
    vid: int
    pid: int
    interface: int
    manufacturer: str
    product: str
    serial: str | None

    @property
    def supported(self) -> bool:
        return (self.vid, self.pid, self.interface) in SUPPORTED_DEVICES

    @property
    def display_name(self) -> str:
        return self.product or "CORSAIR Nautilus LCD Cap"


def validate_supported_identity(identity: DeviceIdentity) -> None:
    key = (identity.vid, identity.pid, identity.interface)
    if key not in SUPPORTED_DEVICES:
        raise UnsupportedDeviceError(
            f"unsupported HID identity {identity.vid:04x}:{identity.pid:04x} interface {identity.interface}"
        )


def identities_match(expected: DeviceIdentity, current: DeviceIdentity) -> bool:
    return (
        expected.device_node == current.device_node
        and expected.vid == current.vid
        and expected.pid == current.pid
        and expected.interface == current.interface
        and (expected.serial is None or current.serial == expected.serial)
    )
