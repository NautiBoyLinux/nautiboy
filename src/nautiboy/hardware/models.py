"""Immutable hardware-identification and display-capability models.

Identification is deliberately separate from control authorization.  A catalog
match can provide a friendly name without allowing the matching USB node to be
opened or written.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Confidence(StrEnum):
    LOCALLY_VALIDATED = "locally_validated"
    CONFIRMED_UPSTREAM = "confirmed_upstream"
    PROVISIONAL = "provisional"


class ControlSupport(StrEnum):
    SUPPORTED = "supported"
    EXPERIMENTAL = "experimental"
    PROTOCOL_KNOWN_UNIMPLEMENTED = "protocol_known_unimplemented"
    IDENTIFICATION_ONLY = "identification_only"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class Evidence:
    project: str
    revision: str
    source: str
    detail: str


@dataclass(frozen=True, slots=True)
class HardwareIdentity:
    vendor: str
    family: str
    model: str
    vid: int
    pid: int
    product_strings: tuple[str, ...] = ()
    interface_number: int | None = None
    interface_class: int | None = None
    hid_usage: str | None = None
    report_descriptor_fingerprint: str | None = None
    input_report_sizes: tuple[int, ...] = ()
    output_report_sizes: tuple[int, ...] = ()
    feature_report_sizes: tuple[int, ...] = ()
    panel_width: int | None = None
    panel_height: int | None = None
    media_transport: str | None = None
    protocol_family: str | None = None
    companion_devices: tuple[str, ...] = ()
    capabilities: frozenset[str] = frozenset()
    control_support: ControlSupport = ControlSupport.IDENTIFICATION_ONLY
    confidence: Confidence = Confidence.PROVISIONAL
    evidence: tuple[Evidence, ...] = ()
    notes: str | None = None

    @property
    def key(self) -> tuple[int, int]:
        return self.vid, self.pid

    @property
    def display_name(self) -> str:
        return f"{self.vendor} {self.model}"

    def identifies(self, *, vid: int, pid: int, interface_number: int | None = None) -> bool:
        if (vid, pid) != self.key:
            return False
        return self.interface_number is None or interface_number == self.interface_number

    def authorizes_control(self, *, vid: int, pid: int, interface_number: int | None) -> bool:
        """Return true only for an implemented adapter and its complete identity.

        No VID:PID-only record can authorize a write.  Additional descriptor
        matching can be introduced per adapter without changing catalog data.
        """
        return (
            self.control_support is ControlSupport.SUPPORTED
            and self.interface_number is not None
            and self.identifies(vid=vid, pid=pid, interface_number=interface_number)
        )
