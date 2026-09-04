from __future__ import annotations

from pathlib import Path

import pytest

from nautiboy.device.identity import DeviceIdentity, UnsupportedDeviceError, validate_supported_identity


def identity(*, vid: int = 0x1B1C, pid: int = 0x0C57, interface: int = 0) -> DeviceIdentity:
    return DeviceIdentity(Path("/dev/hidraw6"), Path("/sys/fake"), vid, pid, interface, "CORSAIR", "Nautilus", None)


def test_supported_identity() -> None:
    validate_supported_identity(identity())


def test_wrong_vid_rejected() -> None:
    with pytest.raises(UnsupportedDeviceError):
        validate_supported_identity(identity(vid=0xFFFF))


def test_wrong_pid_rejected() -> None:
    with pytest.raises(UnsupportedDeviceError):
        validate_supported_identity(identity(pid=0x0C55))


def test_wrong_interface_rejected() -> None:
    with pytest.raises(UnsupportedDeviceError):
        validate_supported_identity(identity(interface=1))
