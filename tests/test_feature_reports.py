from __future__ import annotations

import pytest

from nautiboy.protocol.feature_reports import (
    FeatureReportError,
    decode_firmware_report,
    firmware_request_buffer,
    hardware_mode_reports,
)


def test_validated_firmware_response() -> None:
    response = bytes.fromhex(
        "050c469550f5302e332e302e350000000000000000000000000000000000000000"
    )
    assert decode_firmware_report(response) == "0.3.0.5"


def test_firmware_request_is_bounded() -> None:
    request = firmware_request_buffer()
    assert len(request) == 33
    assert request[0] == 5
    assert not any(request[1:])


def test_malformed_firmware_rejected() -> None:
    with pytest.raises(FeatureReportError):
        decode_firmware_report(bytes(33))


def test_restore_command_generation() -> None:
    assert hardware_mode_reports() == (
        bytes.fromhex("03 1e 01 01"),
        bytes.fromhex("03 1d 00 01"),
    )
