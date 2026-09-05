# Fedora RPM packaging

The public-beta spec is `packaging/fedora/nautiboy.spec`. It builds the pure
Python application with Fedora's PEP 517/`pyproject-rpm-macros` workflow and
uses Fedora packages for Python, PySide6, Pillow, and pyudev. It does not bundle
the development virtual environment.

For `v0.4.0-beta.1`, RPM version `0.4.0~beta.1` and release `1%{?dist}` order
correctly after the earlier `0.2.0~dev0-*` packages and before final `0.4.0`.
`Source0` is the immutable GitHub tag archive named
`nautiboy-v0.4.0-beta.1.tar.gz`; it expands to `nautiboy-0.4.0-beta.1`.
The tag must exist before a clean Fedora or COPR build can fetch that source.

`python3-keyring` supplies the standard desktop credential abstraction for the
optional experimental GIPHY key. Fedora's package depends on SecretStorage for
Freedesktop Secret Service integration with compatible desktop wallets.

The binary RPM owns the `nautiboy` executable, Python package, desktop entry,
AppStream metadata, hicolor icons, documentation, code and artwork license
notices, and the narrow rule:

```udev
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1b1c", ATTRS{idProduct}=="0c57", TAG+="uaccess"
```

The rule is installed in `/usr/lib/udev/rules.d`. The package contains no
service, API key, user-home file, autostart entry, Desktop shortcut, test GIF,
or persistent-device operation. Package installation does not broadly trigger
HID devices. Reconnecting the LCD USB device after installation is the default
way to apply the rule to an already-existing node.

RPM removal deletes only package-owned system files. It intentionally leaves
user-owned configuration, cache, autostart, and optional Desktop shortcut data.
After quitting NautiBoy normally, a user may remove those explicitly with:

```bash
nautiboy --remove-desktop-shortcut
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/io.github.nautiboylinux.nautiboy.desktop"
rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/nautiboy"
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/nautiboy"
rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/io.github.nautiboylinux.nautiboy"
```

The recursive commands target only NautiBoy's exact per-user directories
and must be run as the desktop user, never with sudo. They are documentation,
not RPM uninstall scriptlets.

The application ID is `io.github.nautiboylinux.nautiboy`, derived from the
project-owned `NautiBoyLinux/nautiboy` GitHub namespace.

The RPM license expression is `GPL-3.0-or-later AND CC-BY-SA-4.0`: GPL covers
the source code, while CC BY-SA covers the bundled NautiBoy branding artwork.
The scopes and attribution are recorded in `LICENSE` and
`ARTWORK-LICENSE.txt` respectively.

All package-owned system files are declared as `root:root` with the standard
RPM `%defattr(-,root,root,-)` file-list directive. This is harmless explicit
ownership hardening. Both the RPM payload and the normal Fedora host
installation were validated as `root:root`.

During development, Codex's constrained user namespace made those same host
files appear to be owned by `nobody:nobody`. Host UID/GID 0 is unmapped in that
namespace and is displayed there as the overflow identity `65534:65534`. This
was a namespace visibility artifact, not an RPM payload or host-install
ownership failure. Inspect the RPM header with `rpm -qplv`, and perform
privileged DNF/RPM transactions and final host ownership checks from a normal
host terminal rather than relying on ownership information reported through
the constrained development namespace.

The Fedora development RPM was installed, exercised, removed, audited for
residual package files, reinstalled, and hardware-regression tested on Fedora
KDE Plasma 44. RPM verification was clean after installation and reinstallation.
Uninstall removed all 182 recorded package-owned paths while intentionally
retaining user-owned NautiBoy settings/state.

Public builds should be produced from a clean checkout of the release tag in a
clean Fedora/COPR environment. Distributed RPMs should be signed and accompanied
by a published SHA-256 checksum; local developer build-host metadata must not be
treated as a release artifact.
