from __future__ import annotations

import json
import zipfile
from pathlib import Path

from nautiboy.support_report import collect_hardware_report, render_human_report, write_support_bundle


def _write(path: Path, value: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value, encoding="utf-8")


def _usb_device(root: Path, name: str, vid: str, pid: str, product: str, *, serial: str) -> tuple[Path, Path]:
    device = root / name
    interface = root / f"{name}:1.0"
    device.mkdir(parents=True)
    interface.mkdir()
    for key, value in {
        "idVendor": vid, "idProduct": pid, "manufacturer": "Test Vendor",
        "product": product, "serial": serial, "bcdDevice": "0102", "busnum": "1",
        "devnum": "7", "devpath": "3.2", "bDeviceClass": "00", "speed": "12",
    }.items():
        _write(device / key, value)
    for key, value in {
        "bInterfaceNumber": "00", "bInterfaceClass": "03",
        "bInterfaceSubClass": "00", "bInterfaceProtocol": "00",
    }.items():
        _write(interface / key, value)
    endpoint = interface / "ep_81"
    for key, value in {
        "bEndpointAddress": "81", "bmAttributes": "03",
        "wMaxPacketSize": "0040", "bInterval": "01",
    }.items():
        _write(endpoint / key, value)
    # Report ID 1, 64-byte input and 1,024-byte output.
    descriptor = bytes.fromhex("85 01 75 08 95 40 81 02 75 08 96 00 04 91 02")
    _write(interface / "0003:test" / "report_descriptor", descriptor)
    (interface / "hidraw" / "hidraw9").mkdir(parents=True)
    return device, interface


def test_report_collects_known_device_and_redacts_serial(tmp_path: Path) -> None:
    usb = tmp_path / "usb"
    dev = tmp_path / "dev"
    dev.mkdir()
    _write(dev / "hidraw9", b"")
    _usb_device(usb, "1-3.2", "1b1c", "0c57", "CORSAIR Nautilus LCD Cap", serial="PRIVATE-SERIAL")
    os_release = tmp_path / "os-release"
    _write(os_release, 'PRETTY_NAME="Test Linux"\nID=test\n')

    report = collect_hardware_report(usb_root=usb, dev_root=dev, os_release=os_release, nonce=b"fixed")
    assert len(report.devices) == 1
    device = report.devices[0]
    assert device["catalog"]["status"] == "supported"
    assert device["catalog"]["confidence"] == "locally_validated"
    assert str(device["serial"]).startswith("sha256-session:")
    assert "PRIVATE-SERIAL" not in json.dumps(report.as_dict())
    assert device["interfaces"][0]["hid_report_descriptor"]["output_reports"] == [
        {"report_id": 1, "size_bytes": 1025, "payload_bits": 8192}
    ]


def test_unknown_hid_device_is_reported_as_unknown(tmp_path: Path) -> None:
    usb = tmp_path / "usb"
    dev = tmp_path / "dev"
    dev.mkdir()
    _usb_device(usb, "2-1", "1234", "5678", "Mystery OLED", serial="UNIQUE")
    report = collect_hardware_report(
        usb_root=usb, dev_root=dev, os_release=tmp_path / "missing", nonce=b"fixed"
    )
    assert report.devices[0]["catalog"] == {
        "status": "unknown", "confidence": "unknown", "matches": []
    }


def test_non_display_non_hid_usb_device_is_omitted(tmp_path: Path) -> None:
    usb = tmp_path / "usb"
    device = usb / "3-1"
    _write(device / "idVendor", "1234")
    _write(device / "idProduct", "9999")
    _write(device / "product", "Mass Storage")
    report = collect_hardware_report(usb_root=usb, dev_root=tmp_path / "dev", os_release=tmp_path / "missing")
    assert report.devices == ()


def test_bundle_contains_human_and_structured_reports_only(tmp_path: Path) -> None:
    usb = tmp_path / "usb"
    _usb_device(usb, "1-4", "1e71", "3012", "NZXT Kraken Elite V2", serial="SECRET")
    report = collect_hardware_report(usb_root=usb, dev_root=tmp_path / "dev", os_release=tmp_path / "missing", nonce=b"fixed")
    target = write_support_bundle(tmp_path / "bundle", report)
    assert target.name == "bundle.zip"
    assert target.stat().st_mode & 0o777 == 0o600
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["hardware-report.txt", "hardware-report.json"]
        human = archive.read("hardware-report.txt").decode()
        structured = archive.read("hardware-report.json").decode()
    assert "protocol_known_unimplemented" in human
    assert "SECRET" not in human + structured
    assert json.loads(structured)["devices"][0]["vid"] == "1e71"


def test_report_generation_does_not_import_or_call_hardware_backend(monkeypatch, tmp_path: Path) -> None:
    import nautiboy.backends.direct_hidraw as backend

    monkeypatch.setattr(backend.DirectNautilusBackend, "__init__", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("backend opened")))
    report = collect_hardware_report(usb_root=tmp_path / "missing", dev_root=tmp_path / "dev", os_release=tmp_path / "missing")
    assert report.devices == ()


def test_human_report_describes_empty_result(tmp_path: Path) -> None:
    report = collect_hardware_report(usb_root=tmp_path / "missing", dev_root=tmp_path / "dev", os_release=tmp_path / "missing")
    assert "No known or HID/display-like USB candidates" in render_human_report(report)
