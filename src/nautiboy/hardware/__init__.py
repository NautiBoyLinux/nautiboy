"""Shared, write-neutral hardware knowledge layer."""

from .catalog import HARDWARE_CATALOG, identities_for_usb, identify_usb
from .models import Confidence, ControlSupport, Evidence, HardwareIdentity

__all__ = [
    "Confidence", "ControlSupport", "Evidence", "HARDWARE_CATALOG",
    "HardwareIdentity", "identities_for_usb", "identify_usb",
]
