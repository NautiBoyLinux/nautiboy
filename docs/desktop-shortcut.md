# Optional per-user Desktop shortcut

NautiBoy never creates a Desktop shortcut during package installation. An
installed user may explicitly create one with:

```bash
nautiboy --create-desktop-shortcut
```

The command uses Qt's XDG-aware `QStandardPaths.DesktopLocation`; it does not
assume `~/Desktop`, create a missing Desktop directory, or require sudo. It
copies the installed NautiBoy desktop entry, adds an application-specific
ownership marker, and sets execute bits so desktop shells that require an
executable launcher can open it. Some shells may still require a one-time
interactive trust confirmation according to their own security model.

Remove it with:

```bash
nautiboy --remove-desktop-shortcut
```

Removal targets only `io.github.nautiboylinux.nautiboy.desktop` in the resolved XDG
Desktop directory and refuses to delete a same-named file without NautiBoy's
ownership marker.

Creating or removing the shortcut also cleans up the provisional development
filename `io.github.nautiboy.nautiboy.desktop`, but only when that file carries
the same NautiBoy ownership marker.
