# Changelog

## v0.1.0 — first hardware-validated release

- Added strict discovery for CORSAIR Nautilus LCD Cap `1b1c:0c57`, interface 0.
- Added firmware feature-report reading and display.
- Added safe JPEG/PNG decoding, EXIF orientation, Fit, and Center Crop.
- Added 480×480 baseline-JPEG preview and bounded HID packetization.
- Added one-second volatile static-image refresh with an in-flight guard.
- Added manual and automatic hardware-mode restoration.
- Added normal-user access through a narrowly scoped udev `uaccess` rule.
- Added the NautiBoy Qt Widgets interface, branding, desktop metadata, and
  development icons.
- Added offline tests for protocol boundaries, images, discovery, backend
  failures, refresh scheduling, restoration, and UI branding.
- Hardware validated on Fedora KDE Plasma 44 with firmware 0.3.0.5.

No persistent storage, firmware update, rotation, brightness, RGB, pump, fan,
GIF, telemetry, profile, tray, or autostart functionality is included.
