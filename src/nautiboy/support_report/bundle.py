"""Human-readable rendering and deterministic local support-bundle writing."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from .models import ReportSnapshot


def render_human_report(snapshot: ReportSnapshot) -> str:
    lines = [
        "NautiBoy Hardware Report", "========================", "",
        f"Generated (UTC): {snapshot.generated_utc}",
        f"Kernel: {snapshot.host['kernel']}",
        f"Architecture: {snapshot.host['architecture']}",
        f"Distribution: {snapshot.host['distribution'].get('pretty_name', 'unknown')}",
        "Privacy: serial numbers are replaced by per-report hashes.",
        "Collection: sysfs/procfs metadata reads only; no hardware commands.", "",
    ]
    if not snapshot.devices:
        lines.append("No known or HID/display-like USB candidates were found.")
    for index, device in enumerate(snapshot.devices, 1):
        lines.extend([
            f"Device {index}: {device.get('manufacturer') or 'Unknown vendor'} {device.get('product') or 'Unknown product'}",
            "-" * 72,
            f"USB ID: {device['vid']}:{device['pid']}",
            f"USB path/topology: {device['usb_path']} (bus {device.get('bus_number')}, device {device.get('device_number')}, port {device.get('port_path')})",
            f"Device release: {device.get('bcd_device') or 'unknown'}",
            f"Serial: {device.get('serial') or 'not reported'}",
            f"Catalog status: {device['catalog']['status']}",
            f"Catalog confidence: {device['catalog']['confidence']}",
        ])
        for interface in device["interfaces"]:
            lines.append(
                f"Interface {interface['number']}: class={interface['class']} subclass={interface['subclass']} "
                f"protocol={interface['protocol']} driver={interface['driver'] or 'none'}"
            )
            for endpoint in interface["endpoints"]:
                lines.append(f"  Endpoint {endpoint['address']}: attributes={endpoint['attributes']} max-packet={endpoint['max_packet_size']} interval={endpoint['interval']}")
            descriptor = interface["hid_report_descriptor"]
            if descriptor:
                lines.append(f"  HID descriptor: {descriptor.get('size_bytes')} bytes, SHA-256 {descriptor.get('sha256', 'unavailable')}")
                lines.append(f"  HID report IDs: {descriptor.get('report_ids', [])}")
                for kind in ("input_reports", "output_reports", "feature_reports"):
                    lines.append(f"  {kind.replace('_', ' ')}: {descriptor.get(kind, [])}")
            for permission in interface["hidraw_permissions"]:
                lines.append(
                    f"  {permission['path']}: {permission.get('mode', 'unavailable')}; "
                    f"read={permission.get('current_user_readable', False)} write={permission.get('current_user_writable', False)}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_support_bundle(path: Path, snapshot: ReportSnapshot) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".zip":
        target = target.with_suffix(".zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    payload = json.dumps(snapshot.as_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("hardware-report.txt", render_human_report(snapshot))
            archive.writestr("hardware-report.json", payload)
        os.chmod(temporary, 0o600)
        temporary.replace(target)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return target
