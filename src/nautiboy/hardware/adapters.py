"""Device-independent display contract for future native NautiBoy adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from PIL import Image

from .models import HardwareIdentity


class DisplayState(StrEnum):
    READY = "ready"
    DISPLAYING = "displaying"
    HARDWARE_MODE = "hardware_mode"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RenderedFrame:
    """Device-neutral RGB frame produced by Image/GIF/Thermals/Creative."""

    image: Image.Image
    duration_ms: int | None = None

    def __post_init__(self) -> None:
        if self.image.mode != "RGB":
            raise ValueError("display frames must be RGB")
        if self.image.width <= 0 or self.image.height <= 0:
            raise ValueError("display frames must be non-empty")
        if self.duration_ms is not None and self.duration_ms <= 0:
            raise ValueError("frame duration must be positive")


@dataclass(frozen=True, slots=True)
class DisplayCapabilities:
    width: int
    height: int
    static_images: bool = False
    animation: bool = False
    video: bool = False
    brightness: bool = False
    orientation: bool = False
    hardware_mode_restore: bool = False


class NativeDisplayAdapter(Protocol):
    """Lifecycle boundary implemented natively for each proven device family.

    Adapters own initialization, encoding, packetization, transport, bounded
    scheduling, readback and restoration. Renderers never access USB/HID.
    """

    identity: HardwareIdentity
    capabilities: DisplayCapabilities

    def initialize(self) -> None: ...
    def state(self) -> DisplayState: ...
    def send_frame(self, frame: RenderedFrame) -> None: ...
    def set_brightness(self, percent: int) -> None: ...
    def set_orientation(self, degrees: int) -> None: ...
    def restore(self) -> None: ...
    def close(self) -> None: ...
