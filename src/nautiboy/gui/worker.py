"""All hidraw operations execute in this QObject's dedicated thread."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal, Slot

from nautiboy.backends.direct_hidraw import DirectNautilusBackend
from nautiboy.device.identity import DeviceIdentity


class DeviceWorker(QObject):
    configured = Signal()
    firmware_ready = Signal(str)
    image_sent = Signal(int)
    image_refreshed = Signal(int)
    gif_frame_sent = Signal(int, int, float)
    restored = Signal()
    failed = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._backend: DirectNautilusBackend | None = None

    @Slot(object)
    def configure(self, identity: DeviceIdentity | None) -> None:
        self._backend = DirectNautilusBackend(identity) if identity is not None else None
        self.configured.emit()

    def _required_backend(self) -> DirectNautilusBackend:
        if self._backend is None:
            raise RuntimeError("device is not configured")
        return self._backend

    @Slot()
    def read_firmware(self) -> None:
        try:
            self.firmware_ready.emit(self._required_backend().read_firmware())
        except Exception as error:  # boundary: convert worker failures into UI state
            self.failed.emit("firmware", str(error))

    @Slot(bytes)
    def send_image(self, jpeg: bytes) -> None:
        try:
            self.image_sent.emit(self._required_backend().send_static_image(jpeg))
        except Exception as error:  # boundary: convert worker failures into UI state
            self.failed.emit("send", str(error))

    @Slot(bytes)
    def refresh_image(self, jpeg: bytes) -> None:
        try:
            self.image_refreshed.emit(self._required_backend().send_static_image(jpeg))
        except Exception as error:  # boundary: one failure stops scheduling in the UI
            self.failed.emit("refresh", str(error))

    @Slot(object, int, str)
    def send_gif_frame(self, document: object, index: int, strategy: str) -> None:
        try:
            started = time.monotonic()
            _rendered, jpeg = document.render_frame(index, strategy)
            reports = self._required_backend().send_static_image(jpeg)
            self.gif_frame_sent.emit(index, reports, time.monotonic() - started)
        except Exception as error:  # boundary: decode/HID failure stops scheduling
            self.failed.emit("animation", str(error))

    @Slot()
    def restore(self) -> None:
        try:
            self._required_backend().restore_hardware_mode()
            self.restored.emit()
        except Exception as error:  # boundary: convert worker failures into UI state
            self.failed.emit("restore", str(error))
