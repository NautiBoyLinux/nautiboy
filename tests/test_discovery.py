from __future__ import annotations

from pathlib import Path

from nautiboy.device.discovery import identity_from_sysfs


def write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def test_identity_from_hidraw_sysfs(tmp_path: Path) -> None:
    usb = tmp_path / "devices" / "1-9"
    interface = usb / "1-9:1.0"
    hid = interface / "0003:1B1C:0C57.0001"
    hid.mkdir(parents=True)
    write(usb / "idVendor", "1b1c\n")
    write(usb / "idProduct", "0c57\n")
    write(usb / "manufacturer", "CORSAIR\n")
    write(usb / "product", "CORSAIR Nautilus LCD Cap\n")
    write(usb / "serial", "EXAMPLE\n")
    write(interface / "bInterfaceNumber", "00\n")
    class_path = tmp_path / "class" / "hidraw0"
    class_path.mkdir(parents=True)
    (class_path / "device").symlink_to(hid, target_is_directory=True)
    found = identity_from_sysfs(class_path)
    assert found.vid == 0x1B1C
    assert found.pid == 0x0C57
    assert found.interface == 0
    assert found.serial == "EXAMPLE"
    assert found.device_node == Path("/dev/hidraw0")
