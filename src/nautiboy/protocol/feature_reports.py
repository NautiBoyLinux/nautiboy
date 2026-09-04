"""The only permitted HID feature-report operations in version 0.1."""

from __future__ import annotations

import re

from .constants import FEATURE_REPORT_SIZE, FIRMWARE_REPORT_ID

HARDWARE_MODE_REPORTS = (
    bytes.fromhex("03 1e 01 01"),
    bytes.fromhex("03 1d 00 01"),
)


class FeatureReportError(ValueError):
    """A feature report was missing or malformed."""


def firmware_request_buffer() -> bytearray:
    buffer = bytearray(FEATURE_REPORT_SIZE)
    buffer[0] = FIRMWARE_REPORT_ID
    return buffer


def decode_firmware_report(response: bytes) -> str:
    if len(response) != FEATURE_REPORT_SIZE:
        raise FeatureReportError(f"expected {FEATURE_REPORT_SIZE} bytes, got {len(response)}")
    if response[0] != FIRMWARE_REPORT_ID:
        raise FeatureReportError("unexpected feature report ID")
    version = response[6:].split(b"\x00", 1)[0].decode("ascii", errors="strict")
    if not re.fullmatch(r"\d+(?:\.\d+){1,3}", version):
        raise FeatureReportError("firmware version is malformed")
    return version


def hardware_mode_reports() -> tuple[bytes, bytes]:
    return HARDWARE_MODE_REPORTS
