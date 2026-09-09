"""Passive Linux USB/HID inventory for tester support bundles.

This module reads metadata files only. It never opens a USB or hidraw device and
contains no ioctl, write, feature-report, control-transfer, or backend calls.
"""

from __future__ import annotations

import hashlib
import os
import platform
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path

from nautiboy.hardware.catalog import identities_for_usb

from .hid import summarize_report_descriptor
from .models import ReportSnapshot

DISPLAY_WORDS = ("lcd", "oled", "amoled", "display", "aio", "cooler", "kraken", "ryujin", "ryuo", "panorama")
MAX_DESCRIPTOR_BYTES = 65536


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip() or None
    except OSError:
        return None


def _hex(path: Path) -> int | None:
    value = _text(path)
    try:
        return int(value, 16) if value is not None else None
    except ValueError:
        return None


def _driver(path: Path) -> str | None:
    try:
        return (path / "driver").resolve(strict=True).name
    except OSError:
        return None


def _hash_unique(value: str | None, nonce: bytes) -> str | None:
    if value is None:
        return None
    digest = hashlib.sha256(nonce + value.encode("utf-8", errors="replace")).hexdigest()
    return f"sha256-session:{digest[:20]}"


def _permission(path: Path) -> dict[str, object]:
    try:
        info = path.stat()
    except OSError as error:
        return {"path": str(path), "exists": False, "error": type(error).__name__}
    return {
        "path": str(path),
        "exists": True,
        "mode": stat.filemode(info.st_mode),
        "uid": info.st_uid,
        "gid": info.st_gid,
        "current_user_readable": os.access(path, os.R_OK),
        "current_user_writable": os.access(path, os.W_OK),
    }


def _hidraw_nodes(interface: Path, dev_root: Path) -> list[dict[str, object]]:
    names: set[str] = set()
    try:
        for candidate in interface.rglob("hidraw*"):
            if candidate.name.startswith("hidraw"):
                names.add(candidate.name)
    except OSError:
        pass
    return [_permission(dev_root / name) for name in sorted(names)]


def _descriptor(interface: Path) -> dict[str, object] | None:
    candidates: list[Path] = []
    try:
        candidates = sorted(interface.rglob("report_descriptor"))
    except OSError:
        pass
    for path in candidates:
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if len(raw) > MAX_DESCRIPTOR_BYTES:
            return {"error": "descriptor_too_large", "size_bytes": len(raw)}
        summary = summarize_report_descriptor(raw)
        return {
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "hex": raw.hex(),
            **summary,
        }
    return None


def _endpoints(interface: Path) -> list[dict[str, object]]:
    endpoints: list[dict[str, object]] = []
    try:
        children = sorted(interface.iterdir())
    except OSError:
        return endpoints
    for child in children:
        address = _hex(child / "bEndpointAddress")
        if address is None:
            continue
        endpoints.append({
            "address": f"0x{address:02x}",
            "attributes": _hex(child / "bmAttributes"),
            "max_packet_size": _hex(child / "wMaxPacketSize"),
            "interval": _hex(child / "bInterval"),
        })
    return endpoints


def _catalog(vid: int, pid: int, interface_numbers: tuple[int, ...]) -> dict[str, object]:
    matches = identities_for_usb(vid, pid)
    if not matches:
        return {"status": "unknown", "confidence": "unknown", "matches": []}
    rows = []
    for match in matches:
        interface_match = match.interface_number is None or match.interface_number in interface_numbers
        rows.append({
            "name": match.display_name,
            "family": match.family,
            "status": match.control_support.value if interface_match else "candidate_interface_mismatch",
            "confidence": match.confidence.value,
            "expected_interface": match.interface_number,
            "interface_match": interface_match,
            "protocol_family": match.protocol_family,
            "capabilities": sorted(match.capabilities),
        })
    valid = [row for row in rows if row["interface_match"]]
    if not valid:
        status = "candidate / insufficient fingerprint"
        confidence = "provisional"
    else:
        status = str(valid[0]["status"])
        confidence = str(valid[0]["confidence"])
    return {"status": status, "confidence": confidence, "matches": rows}


def _interfaces(device: Path, usb_root: Path, dev_root: Path) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    try:
        siblings = sorted(usb_root.glob(f"{device.name}:*"))
    except OSError:
        return found
    for interface in siblings:
        number = _hex(interface / "bInterfaceNumber")
        found.append({
            "number": number,
            "class": _hex(interface / "bInterfaceClass"),
            "subclass": _hex(interface / "bInterfaceSubClass"),
            "protocol": _hex(interface / "bInterfaceProtocol"),
            "driver": _driver(interface),
            "endpoints": _endpoints(interface),
            "hid_report_descriptor": _descriptor(interface),
            "hidraw_permissions": _hidraw_nodes(interface, dev_root),
        })
    return found


def _os_release(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = _text(path)
    if text is None:
        return values
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key in {"NAME", "VERSION", "ID", "VERSION_ID", "PRETTY_NAME"}:
            values[key.lower()] = value.strip().strip('"')
    return values


def collect_hardware_report(
    *,
    usb_root: Path = Path("/sys/bus/usb/devices"),
    dev_root: Path = Path("/dev"),
    os_release: Path = Path("/etc/os-release"),
    nonce: bytes | None = None,
) -> ReportSnapshot:
    nonce = nonce or secrets.token_bytes(32)
    devices: list[dict[str, object]] = []
    try:
        entries = sorted(usb_root.iterdir())
    except OSError:
        entries = []
    for device in entries:
        vid, pid = _hex(device / "idVendor"), _hex(device / "idProduct")
        if vid is None or pid is None:
            continue
        interfaces = _interfaces(device, usb_root, dev_root)
        catalog_matches = identities_for_usb(vid, pid)
        label = " ".join(filter(None, (_text(device / "manufacturer"), _text(device / "product")))).lower()
        has_hid = any(row["class"] == 0x03 or row["hid_report_descriptor"] is not None for row in interfaces)
        if not catalog_matches and not has_hid and not any(word in label for word in DISPLAY_WORDS):
            continue
        interface_numbers = tuple(row["number"] for row in interfaces if isinstance(row["number"], int))
        devices.append({
            "usb_path": device.name,
            "bus_number": _text(device / "busnum"),
            "device_number": _text(device / "devnum"),
            "port_path": _text(device / "devpath"),
            "vid": f"{vid:04x}",
            "pid": f"{pid:04x}",
            "bcd_device": _text(device / "bcdDevice"),
            "firmware_metadata": {
                "usb_device_release": _text(device / "bcdDevice"),
                "sysfs_firmware_version": _text(device / "firmware_version"),
                "note": "No device command is issued; unavailable firmware fields remain null.",
            },
            "manufacturer": _text(device / "manufacturer"),
            "product": _text(device / "product"),
            "serial": _hash_unique(_text(device / "serial"), nonce),
            "usb_class": _hex(device / "bDeviceClass"),
            "speed_mbps": _text(device / "speed"),
            "driver": _driver(device),
            "interfaces": interfaces,
            "catalog": _catalog(vid, pid, interface_numbers),
        })
    return ReportSnapshot(
        schema_version=1,
        generated_utc=datetime.now(timezone.utc).isoformat(),
        privacy={
            "serial_numbers": "replaced by per-report non-reversible hashes",
            "automatic_upload": False,
            "hardware_access": "sysfs/procfs metadata reads only; no USB or HID device opens",
        },
        host={
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "distribution": _os_release(os_release),
        },
        devices=tuple(devices),
    )
