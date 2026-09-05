# Per-user graphical-session autostart

NautiBoy can create one user-owned XDG desktop autostart entry:

`$XDG_CONFIG_HOME/autostart/io.github.nautiboylinux.nautiboy.desktop`

When `XDG_CONFIG_HOME` is unset, the location is
`~/.config/autostart/io.github.nautiboylinux.nautiboy.desktop`. No system directory,
root service, or boot-time unit is involved.

The Settings dialog exposes **Launch NautiBoy at login** and **Start minimized
to system tray**. The latter defaults on. A minimized entry runs
`nautiboy --background`; a non-minimized entry runs `nautiboy`. Background mode
creates normal discovery, worker, single-instance, and tray infrastructure but
does not select media, send an LCD frame, or leave hardware mode by default.
If the independent opt-in **Resume last display on launch** preference is
enabled, NautiBoy may restore the last successfully active display once the
supported LCD and saved state validate. Resume defaults off and never enables
autostart itself.

The checkbox is derived from the actual desktop entry rather than a cached
boolean. If the entry is deleted or malformed outside NautiBoy, the next dialog
open reports autostart disabled. Only the minimized preference is stored in
`$XDG_CONFIG_HOME/nautiboy/settings.ini`.

Opening Preferences migrates an owned development entry named
`io.github.nautiboy.nautiboy.desktop` to the current filename. Enabling or
disabling autostart also removes that legacy entry only when it contains
NautiBoy's ownership marker; unrelated files are never removed.

Disabling the option removes only NautiBoy's named user entry. To remove it
manually during uninstall:

```bash
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/io.github.nautiboylinux.nautiboy.desktop"
```

The command should be run as the desktop user, never with `sudo`. Development
checkouts must ensure `nautiboy` is installed somewhere in the graphical
session's `PATH` before enabling autostart.
