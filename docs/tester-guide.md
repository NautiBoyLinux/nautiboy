# External beta tester guide

NautiBoy `v0.4.0-beta.1` is beta/testing software. Hardware control is supported
only for the CORSAIR Nautilus LCD Cap `1b1c:0c57`, interface 0. Recognition of
another device does not mean NautiBoy can control it and does not authorize a
write. Review the [compatibility status](hardware-compatibility.md) before use.

## Install on Fedora 44

1. Download the RPM and `SHA256SUMS` from the
   [v0.4.0-beta.1 release](https://github.com/NautiBoyLinux/nautiboy/releases/tag/v0.4.0-beta.1).
2. From the download directory, verify the exact RPM against `SHA256SUMS`.
3. Install it from a normal terminal:

   ```bash
   sudo dnf install ./nautiboy-0.4.0~beta.1-1.fc44.noarch.rpm
   ```

4. Reconnect only the Nautilus LCD USB connection, or log out and back in, so
   the desktop session applies the packaged normal-user access rule.
5. Launch **NautiBoy** from the application menu. Never run the GUI with `sudo`.

Fedora KDE Plasma 44 is the validated platform. Other distributions may require
distribution-specific packaging and have not been validated for this beta.

## What to test

- Confirm the displayed version is `BETA 0.4.0b1`.
- Confirm the device name, VID:PID, and firmware information are correct.
- Select and preview media before choosing Send. Merely launching NautiBoy or
  switching profiles must not send media.
- Use **Restore Hardware Mode** and confirm the device's stored hardware/iCUE
  display returns.
- Quit through the tray to exercise the safe shutdown and restoration path.

Do not test undocumented commands, persistent LCD storage, firmware, brightness,
pump, fan, or RGB controls. Those operations are not part of this beta.

## Submit a Hardware Report

If hardware is unsupported, unknown, or detected incorrectly:

1. Click **CHECK MY HARDWARE** in the main window. This remains available when
   NautiBoy finds no device or recognizes hardware it cannot control. The same
   workflow is also available under **Settings → Generate Hardware Report**.
2. Review all displayed text and structured JSON before saving.
3. Save the ZIP locally.
4. Email the ZIP yourself to **hardware@nautiboy.dev**, including the marketed
   device model and a short description of the detection problem.

The report collector reads Linux sysfs and operating-system metadata only. It
does not open USB or hidraw nodes, issue hardware commands, upload data, send
email, or perform network reporting. Raw serial numbers are replaced with a new
non-reversible hash for each report.

For general help, use **support@nautiboy.dev**. Bugs can also be reported through
[GitHub Issues](https://github.com/NautiBoyLinux/nautiboy/issues). The official
project site is [nautiboy.dev](https://nautiboy.dev).

## Uninstall

Quit NautiBoy through its tray, confirm hardware mode has returned, then run:

```bash
sudo dnf remove nautiboy
```

Package removal intentionally retains per-user preferences and selected media.
The exact retained locations and optional manual cleanup steps are documented in
the [README](../README.md#uninstall-and-user-data). No service or privileged
background daemon is installed.
