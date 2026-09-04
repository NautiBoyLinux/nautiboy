"""Backend contract kept independent of Qt and application state."""

from __future__ import annotations

from typing import Protocol

from nautiboy.device.identity import DeviceIdentity


class NautilusBackend(Protocol):
    identity: DeviceIdentity

    def read_firmware(self) -> str: ...

    def send_static_image(self, jpeg: bytes) -> int: ...

    def restore_hardware_mode(self) -> None: ...
