# NautiBoy v0.4.0-beta.1 release notes

This is the first public beta of NautiBoy, an unofficial Linux controller for
the Corsair Nautilus LCD Cap.

## Hardware and platform

Physical validation is limited to CORSAIR Nautilus LCD Cap `1b1c:0c57`, USB
interface 0, firmware `0.3.0.5`, on Fedora KDE Plasma 44. Other distributions,
firmware revisions, and Corsair devices are unverified.

## Highlights

- Thermals mode with up to two read-only Linux hwmon temperature sensors
- Animated Orbit thermals display
- Local JPEG, PNG, and animated GIF support
- Image and GIF modes with independent Fit/Center Crop settings
- Four persistent Creative presets combining media, optional Orbit, and telemetry
- KDE/Linux tray background operation and single-instance activation
- Optional per-user autostart and opt-in last-display resume
- Safe manual and quit-time return to stored hardware/iCUE content
- Optional experimental GIPHY search with user-provided desktop-keyring credentials

## Installation expectations

The Fedora RPM installs the `nautiboy` executable, desktop and AppStream
metadata, icons, documentation, and a narrow `uaccess` rule for `1b1c:0c57`.
Reconnect the LCD USB connection, log out/in, or reboot after first installation
so the desktop session receives normal-user access. NautiBoy must not be run as
root.

Development packages named `0.2.0~dev0-*` upgrade to `0.4.0~beta.1-1` normally.
User profiles and selected media are retained. The final application ID is
`io.github.nautiboylinux.nautiboy`.

## Known limitations

- GIPHY is optional, unconfigured by default, and experimental. Public credential
  distribution, licensing, attribution, analytics, and external-display policy
  remain unresolved; users must supply their own key.
- Only temperature telemetry is currently exposed; missing hwmon sensors cannot
  be synthesized by the application.
- Fast GIF/Creative deadlines may be coalesced to preserve bounded operation.
- NautiBoy does not access persistent LCD storage or control firmware, brightness,
  rotation, RGB, pumps, or fans.
- Current Thermals and Preferences screenshots are included. Media-profile
  screenshots await redistribution-safe demonstration media.

NautiBoy is not affiliated with, endorsed by, or supported by Corsair.
