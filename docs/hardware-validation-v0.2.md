# NautiBoy v0.2 hardware validation

## Local GIF test 1 — passed

Date: 2026-09-04
Device: CORSAIR Nautilus LCD Cap, `1b1c:0c57`, interface 0
Host: Fedora KDE Plasma 44
Asset: `test-assets/gif-validation-steady.gif`
SHA-256: `46802ed643cdbbfe952394bb2fa00c63cfdfc650621076795d57f47a8646900b`

The asset is a 480×480 opaque GIF with six visually distinct frames, 750 ms per
frame, and a 4.5-second loop. The GUI preview and metadata were correct before
Send, and no HID frame had been transmitted at that point.

The user observed correct animation on the physical LCD. The saved application
log records 56 completed frame transfers over approximately 41.7 seconds and
1,347 total HID reports. Individual encoded frames required 22–26 reports and
completed in 10.5–14.1 ms. Frame order remained sequential and the scheduler
reported zero coalesced frames. There were no short writes, disconnects,
identity changes, or backend errors, and the controller did not fall back to its
stored animation during playback.

Restore began after the final logged GIF frame. No later frame was written.
The unchanged hardware-mode restore completed approximately 6 ms later, and the
user confirmed that the stored iCUE GIF returned. Persistent storage was not
accessed or modified.

This test predates the v0.2 tray/background change. It used the then-existing
normal-window shutdown path. Tray/background behavior will receive a separate
hardware validation before the variable-duration GIF test proceeds.

## KDE tray, background, and branding — passed

The real KDE desktop validation was performed with normal read-only Nautilus
device discovery and no selected media or LCD transmission. Closing the main
window hid the existing process to the KDE tray rather than terminating it.
Open NautiBoy restored that same window, and closing it again returned it to the
tray. The application remained alive throughout and the LCD did not change.

The application, main-window header, task-switcher/window, tray, and notification
paths all use the canonical bundled `branding.application_icon()` loader. The
tray/background lifecycle and use of the existing NautiBoy artwork are approved.

## Local GIF test 2 — passed

Date: 2026-09-04
Device: CORSAIR Nautilus LCD Cap, `1b1c:0c57`, interface 0
Host: Fedora KDE Plasma 44
Asset: `test-assets/gif-validation-variable.gif`
SHA-256: `8399b86c617aba1b550b9624447d95513ee49dfac497eb69d9cf539399441186`

The asset is a 480×480 opaque GIF with 12 visually distinct frames and a
3.14-second loop. Its normalized frame durations are 20, 20, 40, 500, 30, 900,
60, 350, 20, 700, 50, and 450 ms. The GUI identified it as animated, reported
480×480, 12 frames, and approximately 3.1 seconds, and animated the preview
before Send. No HID image transmission occurred before the user's single manual
Send action.

The user observed the GIF displaying and animating on the physical LCD without
corruption or obviously broken frames. Playback looked intentionally uneven,
matching the GUI preview and the deliberately challenging source timing rather
than exhibiting an LCD-specific fault. The controller did not fall back to its
stored iCUE animation during active playback.

The application log covers playback from approximately 07:26:15.922 through
07:28:23.487. Encoded frames used 146–149 HID reports per transfer and completed
in approximately 40.7–55.1 ms. The scheduler coalesced frames whose deadlines
could not be met, reaching a final cumulative count of 242, rather than building
a backlog. Transfers remained bounded and serialized; no overlapping transfer,
short write, disconnect, device-identity change, or backend error was observed.

Restore Hardware Mode was selected while NautiBoy remained open. Restore began
at 07:28:23.700 and the unchanged restore sequence completed at 07:28:23.706.
The scheduler stopped first and no GIF frame was logged after restoration began.
The user confirmed that the stored iCUE GIF resumed correctly and that NautiBoy
remained running and responsive afterward. Persistent device storage was not
accessed or modified.

Both planned local GIF hardware validations therefore passed. GIPHY and other
online-provider media had not yet been tested on the LCD at that point.

## Experimental GIPHY development validation — passed with accidental LCD send

Date: 2026-09-04
Device: CORSAIR Nautilus LCD Cap, `1b1c:0c57`, interface 0
Host: Fedora KDE Plasma 44

The development API key was supplied through hidden terminal input and inherited
as a process-only environment variable. Its value was not printed, logged,
embedded in source, or written to the repository. Search for `cat`, result
loading, Load More pagination, result selection, and the animated main-window
preview all worked successfully.

Although the planned validation was intended to stop before HID transmission,
the user accidentally selected Send to LCD. The chosen GIPHY GIF displayed and
animated correctly on the physical LCD through the existing validated playback
pipeline. Restore Hardware Mode then worked correctly and the stored iCUE GIF
resumed. This is recorded as a successful incidental GIPHY-to-LCD development
test; it does not resolve or alter GIPHY production licensing, external-display,
or attribution-policy questions. GIPHY support remains experimental.

## Fedora RPM installation and lifecycle — passed

Date: 2026-09-04
Package: `nautiboy-0.2.0~dev0-2.fc44.noarch`
Device: CORSAIR Nautilus LCD Cap, `1b1c:0c57`, interface 0, firmware `0.3.0.5`
Host: Fedora KDE Plasma 44

The Fedora RPM completed its internal `%check` with all 142 tests passing. The
binary RPM recorded every payload entry as `root:root`; normal host installation
also produced correct `root:root` ownership and a clean `rpm -V nautiboy`.
Codex's constrained user namespace temporarily displayed host root-owned files
as overflow identity `65534:65534` (`nobody:nobody`). Comparison with ordinary
system files proved this was a namespace visibility artifact, not a package or
host-install ownership defect.

The packaged narrow udev rule granted the logged-in user access to only the
matching `1b1c:0c57` interface-0 hidraw device through `TAG+="uaccess"`. The
installed KDE launcher, application/window icon, tray icon, device discovery,
and firmware read all worked without root. Merely launching NautiBoy did not
send media or disturb the stored hardware-mode GIF.

Installed-package runtime validation passed for static JPEG playback, local
animated GIF playback, hardware-mode restoration, close-to-tray playback,
tray reopen/restore, single-instance behavior, and per-user autostart creation
and removal. Autostart used the lowercase
`io.github.nautiboy.nautiboy.desktop` entry with `nautiboy --background` and did
not transmit media.

DNF uninstall removed every one of the 182 recorded package-owned paths and
left user-owned configuration/state intact. Reinstallation restored a clean
package with correct ownership, no automatic autostart entry, Desktop shortcut,
service, timer, or API key. A post-reinstall hardware regression detected
firmware `0.3.0.5`, left hardware mode unchanged at launch, displayed one known
static image, restored the stored iCUE GIF, and quit cleanly.

Persistent LCD/controller storage was never accessed or modified during v0.2
development or lifecycle validation.

## Validated scope and release gates

Hardware claims are limited to the CORSAIR Nautilus LCD Cap, VID:PID
`1b1c:0c57`, interface 0, firmware `0.3.0.5`, on Fedora KDE Plasma 44. Other
distributions, device IDs, interfaces, and firmware versions remain unverified.

The final software suite contains 142 passing tests. Static JPEG/PNG, both local
GIF scenarios (including variable-duration deadline coalescing), KDE
tray/background behavior, single-instance operation, per-user autostart, Fedora
RPM installation, uninstall/reinstall, and hardware-mode restoration are
validated. Persistent controller storage remains out of scope.

The GIPHY adapter remains experimental and requires a process environment key;
no API key is embedded or persisted. Public distribution or enablement remains
unresolved pending clarification of GIPHY licensing, attribution, and
external-display use. Local GIF support is independent of GIPHY.
