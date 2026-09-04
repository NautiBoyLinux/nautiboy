# v0.1 hardware validation

Status: **passed** on 2026-09-03.

## Validated system and device

- Host: Fedora KDE 44
- User: `Dad` (application ran without `sudo`)
- Device: CORSAIR Nautilus LCD Cap
- USB identity: `1b1c:0c57`, interface 0
- Firmware: `0.3.0.5`
- Device node during validation: `/dev/hidraw6`
- Application: the direct-hidraw v0.1 core now branded as NautiBoy

## Static test asset

- Path: `test-assets/test-image-480.jpg`
- Format: baseline RGB JPEG, 480×480
- Source SHA-256: `7f642cee162ec182b8f0a7f9003f7d2ac4de0f0397928d796634eef572a63222`
- Source size: 47,724 bytes
- Application-processed size: 47,752 bytes
- Application-processed packet count: 47

## Procedure and result

Exactly one application instance was launched as the normal desktop user. The
GUI detected the expected device, read firmware 0.3.0.5, and entered `ready`.
The test JPEG was selected with Fit and displayed correctly in the preview.

Send to LCD was clicked exactly once. The initial bounded transfer completed as
47 reports and the physical display showed the expected image. The application
then refreshed the identical in-memory JPEG every 1,000 ms, with at most one
transfer in flight. The display was observed for more than 15 seconds and did
not return to hardware-mode content at the earlier approximately five-second
timeout. The GUI remained usable throughout.

The application was closed normally. It stopped refresh scheduling before
sending the two documented hardware-mode reports. The previously stored iCUE
GIF resumed immediately and correctly. The persistent content was not modified.

## Application log

```text
2026-09-03 23:41:58,100 INFO nautilus_lcd.gui.main_window: Connected to CORSAIR Nautilus LCD Cap
2026-09-03 23:42:55,913 INFO nautilus_lcd.gui.main_window: Prepared test-image-480.jpg using fit
2026-09-03 23:43:06,691 INFO nautilus_lcd.gui.main_window: Sending one volatile image…
2026-09-03 23:43:06,704 INFO nautilus_lcd.gui.main_window: Image displayed successfully (47 reports)
2026-09-03 23:43:43,229 INFO nautilus_lcd.gui.main_window: Restoring hardware mode…
2026-09-03 23:43:43,235 INFO nautilus_lcd.gui.main_window: Hardware mode restored
```

The log namespace shown above predates the NautiBoy package rename and is retained
verbatim as validation evidence. The process exited with status 0. No application errors or warnings occurred.
The elapsed displayed interval recorded by the log was approximately 36.5
seconds, exceeding the required 15 seconds.

## Permissions after validation

The installed rule exactly matches `packaging/70-nautilus-lcd.rules`:

```udev
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1b1c", ATTRS{idProduct}=="0c57", TAG+="uaccess"
```

The node remained `root:root` mode `0660`; systemd-logind supplied user `Dad`
an `rw-` ACL. Read and write access both succeeded without sudo. The device
retained `uaccess` and `seat` tags. No application instance remained afterward.

## Scope confirmed

This validation exercised only firmware report 0x05, volatile `0x02/0x05` JPEG
transfers, and the documented hardware-mode restore pair. It did not access
persistent storage or perform rotation, brightness, frame-rate, firmware,
cooling, pump, fan, or RGB operations.

Offline verification before hardware validation completed with 51 passing
tests, successful Python compilation, successful wheel/source builds, and clean
Git whitespace checks.
