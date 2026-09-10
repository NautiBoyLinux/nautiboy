from __future__ import annotations

from pathlib import Path

from nautiboy.hardware.catalog import HARDWARE_CATALOG, identities_for_usb, identify_usb
from nautiboy.hardware.compatibility import render_hardware_compatibility
from nautiboy.hardware.models import Confidence, ControlSupport


def test_catalog_keys_are_unique() -> None:
    keys = [record.key for record in HARDWARE_CATALOG]
    assert len(keys) == len(set(keys))


def test_every_record_has_pinned_evidence() -> None:
    for record in HARDWARE_CATALOG:
        assert record.evidence
        for evidence in record.evidence:
            assert evidence.revision
            assert evidence.source.startswith("https://")
            assert evidence.detail


def test_nautilus_remains_only_write_authorized_identity() -> None:
    authorized = [record for record in HARDWARE_CATALOG if record.control_support is ControlSupport.SUPPORTED]
    assert [(record.vid, record.pid, record.interface_number) for record in authorized] == [(0x1B1C, 0x0C57, 0)]
    nautilus = authorized[0]
    assert nautilus.confidence is Confidence.LOCALLY_VALIDATED
    assert nautilus.authorizes_control(vid=0x1B1C, pid=0x0C57, interface_number=0)
    assert not nautilus.authorizes_control(vid=0x1B1C, pid=0x0C57, interface_number=None)
    assert not nautilus.authorizes_control(vid=0x1B1C, pid=0x0C57, interface_number=1)


def test_vid_pid_match_never_authorizes_unimplemented_devices() -> None:
    for record in HARDWARE_CATALOG:
        if record.key != (0x1B1C, 0x0C57):
            assert not record.authorizes_control(vid=record.vid, pid=record.pid, interface_number=record.interface_number)


def test_recognition_lookup_is_write_neutral() -> None:
    matches = identities_for_usb(0x1E71, 0x3012)
    assert len(matches) == 1
    assert matches[0].model == "Kraken Elite RGB 2024"
    assert matches[0].control_support is ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED


def test_interface_constraint_prevents_ambiguous_identity() -> None:
    assert identify_usb(0x1B1C, 0x0C57, 0) is not None
    assert identify_usb(0x1B1C, 0x0C57, 1) is None


def test_unknown_device_remains_unknown() -> None:
    assert identify_usb(0xFFFF, 0xFFFF, 0) is None


def test_panel_dimensions_are_never_partially_known() -> None:
    for record in HARDWARE_CATALOG:
        assert (record.panel_width is None) == (record.panel_height is None)


def test_requested_seed_identities_are_present() -> None:
    expected = {
        (0x1B1C, 0x0C57), (0x1B1C, 0x0C33), (0x1B1C, 0x0C39), (0x1B1C, 0x0C4E),
        (0x1E71, 0x3008), (0x1E71, 0x300E), (0x1E71, 0x300C), (0x1E71, 0x3012), (0x1E71, 0x3014),
        (0x0416, 0x7395), (0x0B05, 0x1988), (0x0B05, 0x1AA2), (0x0B05, 0x1ADA),
        (0x0B05, 0x1ADE), (0x0B05, 0x1BCB), (0x0B05, 0x1936), (0x0B05, 0x1887),
        (0x0DB0, 0xB130), (0x391A, 0x1021), (0x18D1, 0x2D03),
    }
    assert expected <= {record.key for record in HARDWARE_CATALOG}


def test_public_compatibility_document_is_generated_from_catalog() -> None:
    root = Path(__file__).resolve().parents[1]
    document = root / "docs/hardware-compatibility.md"
    assert document.read_text(encoding="utf-8") == render_hardware_compatibility()
    rendered = render_hardware_compatibility()
    assert "Identification does not imply control" in rendered
    assert "hardware@nautiboy.dev" in rendered
    for record in HARDWARE_CATALOG:
        assert f"`{record.vid:04x}:{record.pid:04x}`" in rendered
