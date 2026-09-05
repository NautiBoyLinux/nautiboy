# Changelog

## v0.2.0 — in development

- Added bounded local animated GIF decoding, preview, and LCD scheduling.
- Added an optional provider-neutral online GIF browser with an experimental
  GIPHY development adapter.
- Kept online search independent from local JPEG, PNG, and GIF operation.
- Preserved the hardware-validated v0.1 HID protocol and restoration behavior.
- Added background playback, a system-tray menu, explicit safe Quit, and
  per-user single-instance activation.
- Added optional per-user XDG graphical-session autostart with background mode.
- Standardized window, launcher, tray, and notification branding on one bundled
  multi-resolution NautiBoy icon loader.
- Migrated the reverse-DNS application ID to
  `io.github.nautiboylinux.nautiboy` after securing the public GitHub namespace.
- Added explicit XDG Desktop shortcut create/remove commands and Fedora RPM
  packaging infrastructure.
- Validated Fedora RPM installation, normal-user udev access, uninstall,
  reinstall, and a post-reinstall hardware regression on Fedora KDE Plasma 44.
- Completed the 142-test software suite and RPM `%check` validation.

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
