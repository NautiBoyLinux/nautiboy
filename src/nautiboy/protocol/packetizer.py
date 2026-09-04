"""Build bounded 1024-byte volatile LCD reports from a complete JPEG."""

from __future__ import annotations

from .constants import (
    LCD_DATA_OPERATION,
    MAX_JPEG_BYTES,
    MAX_PACKET_INDEX,
    OUTPUT_REPORT_ID,
    OUTPUT_REPORT_SIZE,
    PAYLOAD_SIZE,
)


class PacketizationError(ValueError):
    """Input cannot be represented safely by the validated protocol."""


def _validate_jpeg(jpeg: bytes) -> None:
    if not isinstance(jpeg, bytes):
        raise TypeError("JPEG data must be bytes")
    if not jpeg:
        raise PacketizationError("JPEG data is empty")
    if len(jpeg) > MAX_JPEG_BYTES:
        raise PacketizationError(
            f"JPEG is {len(jpeg)} bytes; maximum is {MAX_JPEG_BYTES}"
        )
    if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
        raise PacketizationError("input is not a complete JPEG")


def packetize_jpeg(jpeg: bytes) -> tuple[bytes, ...]:
    """Return finite, ordered output reports for one volatile JPEG frame."""
    _validate_jpeg(jpeg)
    chunks = [jpeg[start : start + PAYLOAD_SIZE] for start in range(0, len(jpeg), PAYLOAD_SIZE)]
    if len(chunks) > MAX_PACKET_INDEX + 1:
        raise PacketizationError("packet index would exceed 255")

    reports: list[bytes] = []
    for index, chunk in enumerate(chunks):
        report = bytearray(OUTPUT_REPORT_SIZE)
        report[0] = OUTPUT_REPORT_ID
        report[1] = LCD_DATA_OPERATION
        if index == len(chunks) - 1:
            report[3] = 0x01
        report[4] = index
        report[6:8] = len(chunk).to_bytes(2, "little")
        report[8 : 8 + len(chunk)] = chunk
        reports.append(bytes(report))
    return tuple(reports)
