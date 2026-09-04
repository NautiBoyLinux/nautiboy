"""Strict, finite Linux hidraw backend for a supported Nautilus LCD."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from nautiboy.device.discovery import DiscoveryError, identity_from_device_node
from nautiboy.device.identity import (
    DeviceIdentity,
    UnsupportedDeviceError,
    identities_match,
    validate_supported_identity,
)
from nautiboy.protocol.constants import FEATURE_REPORT_SIZE, OUTPUT_REPORT_SIZE
from nautiboy.protocol.feature_reports import (
    decode_firmware_report,
    firmware_request_buffer,
    hardware_mode_reports,
)
from nautiboy.protocol.packetizer import packetize_jpeg


class BackendError(RuntimeError):
    """A finite device operation failed."""


class DeviceDisconnectedError(BackendError):
    """The selected device disappeared or changed identity."""


class ShortWriteError(BackendError):
    """hidraw accepted fewer bytes than a complete report."""


IdentityLoader = Callable[[Path], DeviceIdentity]
OpenFunction = Callable[[Path, str, int], BinaryIO]
WriteFunction = Callable[[int, bytes], int]
IoctlFunction = Callable[[int, int, bytearray, bool], int]


def _hid_ioctl(number: int, length: int) -> int:
    # Linux _IOC(_IOC_READ | _IOC_WRITE, 'H', number, length), from hidraw.h.
    return (3 << 30) | (length << 16) | (ord("H") << 8) | number


def hidiocsfeature(length: int) -> int:
    return _hid_ioctl(0x06, length)


def hidiocgfeature(length: int) -> int:
    return _hid_ioctl(0x07, length)


def _open_path(path: Path, mode: str, buffering: int) -> BinaryIO:
    return path.open(mode, buffering=buffering)


class DirectNautilusBackend:
    def __init__(
        self,
        identity: DeviceIdentity,
        *,
        identity_loader: IdentityLoader = identity_from_device_node,
        open_function: OpenFunction = _open_path,
        write_function: WriteFunction = os.write,
        ioctl_function: IoctlFunction = fcntl.ioctl,
    ) -> None:
        validate_supported_identity(identity)
        self.identity = identity
        self._identity_loader = identity_loader
        self._open = open_function
        self._write = write_function
        self._ioctl = ioctl_function

    def _validate_immediately(self) -> None:
        try:
            current = self._identity_loader(self.identity.device_node)
            validate_supported_identity(current)
        except (OSError, ValueError, DiscoveryError, UnsupportedDeviceError) as error:
            raise DeviceDisconnectedError(f"device validation failed: {error}") from error
        if not identities_match(self.identity, current):
            raise DeviceDisconnectedError("hidraw node identity changed")

    def read_firmware(self) -> str:
        self._validate_immediately()
        buffer = firmware_request_buffer()
        try:
            with self._open(self.identity.device_node, "r+b", 0) as device:
                self._ioctl(device.fileno(), hidiocgfeature(FEATURE_REPORT_SIZE), buffer, True)
        except OSError as error:
            raise BackendError(f"firmware read failed: {error}") from error
        return decode_firmware_report(bytes(buffer))

    def send_static_image(self, jpeg: bytes) -> int:
        reports = packetize_jpeg(jpeg)
        self._validate_immediately()
        try:
            with self._open(self.identity.device_node, "wb", 0) as device:
                for index, report in enumerate(reports):
                    written = self._write(device.fileno(), report)
                    if written != OUTPUT_REPORT_SIZE:
                        raise ShortWriteError(
                            f"report {index} wrote {written} of {OUTPUT_REPORT_SIZE} bytes"
                        )
        except ShortWriteError:
            raise
        except OSError as error:
            raise DeviceDisconnectedError(f"image transfer failed: {error}") from error
        return len(reports)

    def restore_hardware_mode(self) -> None:
        self._validate_immediately()
        try:
            with self._open(self.identity.device_node, "r+b", 0) as device:
                for report in hardware_mode_reports():
                    buffer = bytearray(report)
                    self._ioctl(device.fileno(), hidiocsfeature(len(buffer)), buffer, True)
        except OSError as error:
            raise DeviceDisconnectedError(f"hardware-mode restore failed: {error}") from error
