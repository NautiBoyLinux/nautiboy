from __future__ import annotations

import pytest

from nautiboy.protocol import packetizer
from nautiboy.protocol.constants import MAX_JPEG_BYTES, OUTPUT_REPORT_SIZE, PAYLOAD_SIZE
from nautiboy.protocol.packetizer import PacketizationError, packetize_jpeg


def fake_jpeg(size: int) -> bytes:
    assert size >= 4
    return b"\xff\xd8" + bytes((index % 251 for index in range(size - 4))) + b"\xff\xd9"


def test_known_good_first_middle_and_final_packets() -> None:
    jpeg = fake_jpeg(PAYLOAD_SIZE * 2 + 77)
    reports = packetize_jpeg(jpeg)
    assert len(reports) == 3
    assert all(len(report) == OUTPUT_REPORT_SIZE for report in reports)
    assert reports[0][:8] == bytes.fromhex("02 05 00 00 00 00 f8 03")
    assert reports[1][:8] == bytes.fromhex("02 05 00 00 01 00 f8 03")
    assert reports[2][:8] == bytes.fromhex("02 05 00 01 02 00 4d 00")
    rebuilt = b"".join(report[8 : 8 + int.from_bytes(report[6:8], "little")] for report in reports)
    assert rebuilt == jpeg


def test_exact_1016_byte_boundary_marks_full_packet_final() -> None:
    reports = packetize_jpeg(fake_jpeg(PAYLOAD_SIZE))
    assert len(reports) == 1
    assert reports[0][3] == 1
    assert int.from_bytes(reports[0][6:8], "little") == PAYLOAD_SIZE
    assert reports[0][:8] == bytes.fromhex("02 05 00 01 00 00 f8 03")


@pytest.mark.parametrize("value", [b"", b"not a jpeg", b"\xff\xd8truncated"])
def test_empty_or_invalid_input_rejected(value: bytes) -> None:
    with pytest.raises(PacketizationError):
        packetize_jpeg(value)


def test_non_bytes_rejected() -> None:
    with pytest.raises(TypeError):
        packetize_jpeg(bytearray(b"\xff\xd8\xff\xd9"))  # type: ignore[arg-type]


def test_oversized_jpeg_rejected() -> None:
    with pytest.raises(PacketizationError, match="maximum"):
        packetize_jpeg(fake_jpeg(MAX_JPEG_BYTES + 1))


def test_packet_index_overflow_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(packetizer, "MAX_JPEG_BYTES", PAYLOAD_SIZE * 258)
    with pytest.raises(PacketizationError, match="packet index"):
        packetize_jpeg(fake_jpeg(PAYLOAD_SIZE * 257))
