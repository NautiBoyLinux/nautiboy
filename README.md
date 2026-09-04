# NautiBoy

NautiBoy is an open-source Linux controller for Corsair NAUTILUS RS LCD displays.

![NautiBoy interface](docs/nautiboy-v0.1-ui.png)

Version 0.1 provides a deliberately small, hardware-validated desktop interface
for displaying a static JPEG or PNG on a supported Nautilus LCD cap. It keeps the
selected image active using bounded one-second volatile refreshes and restores
the controller's existing hardware-mode content when the application exits.

NautiBoy is an unofficial community project and is not affiliated with, endorsed
by, or supported by Corsair.

## Features

- Automatic supported-device discovery through udev and sysfs
- Firmware version display
- JPEG and PNG input with EXIF orientation support
- Fit and Center Crop processing to 480×480
- Static-image preview
- Bounded 1,000 ms volatile refresh with no overlapping transfers
- Manual and automatic hardware-mode restoration
- Normal-user operation through a narrowly scoped `uaccess` rule

## Hardware support

Confirmed hardware-tested configuration:

| Device | VID:PID | Interface | Firmware | Operating system |
|---|---|---:|---|---|
| CORSAIR Nautilus LCD Cap | `1b1c:0c57` | 0 | `0.3.0.5` | Fedora KDE Plasma 44 |

Other Linux distributions, other Nautilus LCD firmware versions, and other
Corsair LCD products are currently unverified. Device acceptance is intentionally
restricted to the tested VID, PID, and interface.

See [the hardware-validation record](docs/HARDWARE-VALIDATION.md) for the test
procedure and results.

## Source installation

Requirements:

- Linux with hidraw, udev, and systemd-logind `uaccess` support
- Python 3.11 or newer
- PySide6, Pillow, and pyudev

From an extracted source release or local checkout:

```bash
python3 -m venv .venv
.venv/bin/pip install .
```

Install the narrowly scoped device-access rule:

```bash
sudo install -m 0644 packaging/70-nautilus-lcd.rules /etc/udev/rules.d/70-nautilus-lcd.rules
sudo udevadm control --reload-rules
```

Reconnect the LCD USB device or reboot so udev and logind apply the rule. Then
run NautiBoy as the normal desktop user:

```bash
.venv/bin/nautiboy
```

Do not run the GUI with `sudo`. Detailed rule verification and removal guidance
is in [docs/permissions.md](docs/permissions.md).

## Removal

1. Close NautiBoy normally so hardware mode is restored.
2. Remove the source checkout or virtual environment when no longer needed.
3. If no longer using NautiBoy, remove its udev rule:

   ```bash
   sudo rm /etc/udev/rules.d/70-nautilus-lcd.rules
   sudo udevadm control --reload-rules
   ```

4. Reconnect the LCD USB device or reboot.

NautiBoy v0.1 does not install a service, write controller profiles, or place
content in the LCD's persistent storage.

## Known limitations

- Static JPEG/PNG display only; no GIF playback
- No CPU/GPU monitoring screens
- NautiBoy must remain running to maintain volatile software display
- No profiles, tray integration, autostart, or background service
- No persistent controller storage access
- No brightness, rotation, or frame-rate controls
- No pump, fan, RGB, or firmware operations
- Only the hardware configuration listed above has been physically validated
- The application ID is provisional and the current icon is a development raster

A final square SVG or transparent 1024×1024 icon master is desired before a
polished public release.

## Safety and architecture

The direct backend revalidates the USB identity immediately before every device
open. Each image transfer is finite and bounded; short writes, disconnects, and
identity changes stop refresh without automatic retry. The GUI delegates all HID
operations to a dedicated worker thread.

See:

- [Safety model](docs/safety.md)
- [Protocol subset](docs/protocol.md)
- [Architecture](docs/architecture.md)
- [Development and tests](docs/development.md)

## License and attribution

NautiBoy is licensed under GPL-3.0-or-later. The LCD framing implementation was
informed by the GPLv3 OpenLinkHub project and independently validated on physical
hardware. See [ATTRIBUTION.md](ATTRIBUTION.md).
