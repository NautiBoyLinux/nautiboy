# Changelog

## v0.4.0-beta.1 — release candidate

- Added four persistent modes: Thermals, Image, GIF, and Creative.
- Added read-only Linux hwmon discovery and selection of up to two temperature
  sensors.
- Added the hardware-validated animated Orbit thermals renderer.
- Added four persistent, renameable Creative presets with layered media, Orbit,
  and telemetry compositing.
- Added bounded local animated GIF decoding, preview, deadline scheduling, and
  long-frame keepalive behavior.
- Added optional experimental GIPHY search with user-provided credentials stored
  in the desktop keyring and durable storage only for explicitly selected media.
- Added selected-versus-active display snapshots and opt-in one-shot resume of
  the last successfully sent display.
- Added KDE/Linux tray background operation, safe Quit, single-instance
  activation, per-user autostart, and optional Desktop shortcut commands.
- Added Fedora RPM packaging, final `io.github.nautiboylinux.nautiboy` identity,
  and final project-owned branding with separate CC BY-SA 4.0 licensing.
- Preserved the hardware-validated v0.1 HID framing, device matching, bounded
  transfer behavior, and hardware-mode restoration.

## v0.2 development milestones

- Hardware-validated local steady and variable-duration GIF playback.
- Validated scheduling coalescing without overlapping HID transfers or backlog.
- Validated Fedora RPM installation, normal-user udev access, uninstall,
  reinstall, tray operation, autostart, and a post-reinstall hardware regression.
- Validated secure GIPHY keyring persistence and an incidental GIPHY-to-LCD test.

## v0.1.0 — first hardware-validated release

- Added strict discovery for CORSAIR Nautilus LCD Cap `1b1c:0c57`, interface 0.
- Added firmware feature-report reading and display.
- Added safe JPEG/PNG decoding, EXIF orientation, Fit, and Center Crop.
- Added 480×480 baseline-JPEG preview and bounded HID packetization.
- Added one-second volatile static-image refresh with an in-flight guard.
- Added manual and automatic hardware-mode restoration.
- Added normal-user access through a narrowly scoped udev `uaccess` rule.
- Hardware validated on Fedora KDE Plasma 44 with firmware `0.3.0.5`.

The v0.1.0 release intentionally excluded persistent LCD storage, firmware,
rotation, brightness, RGB, pump, fan, GIF, telemetry, profiles, tray, and
autostart functionality.
