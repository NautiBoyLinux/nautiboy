from __future__ import annotations

from pathlib import Path

import pytest

from nautiboy.backends.direct_hidraw import (
    DeviceDisconnectedError,
    DirectNautilusBackend,
    ShortWriteError,
    hidiocgfeature,
    hidiocsfeature,
)
from nautiboy.device.identity import DeviceIdentity


class FakeFile:
    def __init__(self, fd: int = 42) -> None:
        self.fd = fd

    def __enter__(self) -> "FakeFile":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def fileno(self) -> int:
        return self.fd


def identity() -> DeviceIdentity:
    return DeviceIdentity(
        Path("/dev/hidraw9"), Path("/sys/fake"), 0x1B1C, 0x0C57, 0,
        "CORSAIR", "CORSAIR Nautilus LCD Cap", "EXAMPLE",
    )


def jpeg(size: int = 1200) -> bytes:
    return b"\xff\xd8" + bytes(size - 4) + b"\xff\xd9"


def backend(**kwargs: object) -> DirectNautilusBackend:
    current = identity()
    defaults = {
        "identity_loader": lambda _path: current,
        "open_function": lambda _path, _mode, _buffering: FakeFile(),
    }
    defaults.update(kwargs)
    return DirectNautilusBackend(current, **defaults)  # type: ignore[arg-type]


def test_disconnect_before_open_fails_without_opening() -> None:
    opened = []

    def missing(_path: Path) -> DeviceIdentity:
        raise FileNotFoundError("gone")

    target = DirectNautilusBackend(
        identity(), identity_loader=missing,
        open_function=lambda *_args: opened.append(True) or FakeFile(),
    )
    with pytest.raises(DeviceDisconnectedError):
        target.send_static_image(jpeg())
    assert opened == []


def test_identity_change_before_open_is_rejected() -> None:
    changed = DeviceIdentity(
        identity().device_node, identity().sysfs_path, 0x1B1C, 0x0C57, 0,
        "CORSAIR", "CORSAIR Nautilus LCD Cap", "DIFFERENT",
    )
    target = DirectNautilusBackend(identity(), identity_loader=lambda _path: changed)
    with pytest.raises(DeviceDisconnectedError):
        target.send_static_image(jpeg())


def test_short_write_stops_immediately() -> None:
    calls = []

    def short_write(_fd: int, report: bytes) -> int:
        calls.append(report)
        return 100

    with pytest.raises(ShortWriteError):
        backend(write_function=short_write).send_static_image(jpeg())
    assert len(calls) == 1


def test_disconnect_during_write_has_no_retry() -> None:
    calls = 0

    def disconnected(_fd: int, _report: bytes) -> int:
        nonlocal calls
        calls += 1
        raise OSError("device removed")

    with pytest.raises(DeviceDisconnectedError):
        backend(write_function=disconnected).send_static_image(jpeg())
    assert calls == 1


def test_complete_send_returns_report_count() -> None:
    reports = []

    def write(_fd: int, report: bytes) -> int:
        reports.append(report)
        return len(report)

    count = backend(write_function=write).send_static_image(jpeg())
    assert count == len(reports) == 2


def test_firmware_read_uses_only_get_feature() -> None:
    calls = []
    response = bytes.fromhex(
        "050c469550f5302e332e302e350000000000000000000000000000000000000000"
    )

    def ioctl(fd: int, request: int, buffer: bytearray, mutate: bool) -> int:
        calls.append((fd, request, bytes(buffer), mutate))
        buffer[:] = response
        return 0

    assert backend(ioctl_function=ioctl).read_firmware() == "0.3.0.5"
    assert calls == [(42, hidiocgfeature(33), bytes([5]) + bytes(32), True)]


def test_restore_sends_only_known_feature_reports() -> None:
    calls = []

    def ioctl(fd: int, request: int, buffer: bytearray, mutate: bool) -> int:
        calls.append((fd, request, bytes(buffer), mutate))
        return 0

    backend(ioctl_function=ioctl).restore_hardware_mode()
    assert calls == [
        (42, hidiocsfeature(4), bytes.fromhex("03 1e 01 01"), True),
        (42, hidiocsfeature(4), bytes.fromhex("03 1d 00 01"), True),
    ]


def test_linux_feature_ioctl_numbers() -> None:
    assert hidiocgfeature(33) == 0xC0214807
    assert hidiocsfeature(4) == 0xC0044806
