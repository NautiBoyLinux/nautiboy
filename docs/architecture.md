# Architecture

## Layers

1. `device` reads udev/sysfs identity and reports hotplug changes. It never opens
   a device node.
2. `protocol` constructs and validates byte sequences without filesystem or Qt
   dependencies.
3. `imaging` decodes JPEG/PNG input and returns a bounded 480×480 baseline JPEG.
4. `gif` validates GIFs, renders one composed frame at a time through the same
   image pipeline, and schedules LCD frames without a backlog.
5. `profiles` models four versioned functional modes and persists their UI-only
   state in an atomic per-user XDG JSON document.
6. `telemetry` discovers and samples normalized read-only Linux sensors. It is
   independent of Qt, HID, media, rendering, and profile persistence.
7. `providers` exposes provider-neutral results. The experimental GIPHY adapter
   is optional and resolves its credential from the process environment or
   desktop keyring.
8. `network` performs bounded, cancellable Qt Network requests in a separate
   thread.
9. `backends` owns direct hidraw access and revalidates device identity before
   every open.
10. `application` and `models` define state-dependent control policy.
11. `gui` presents state and uses timers with in-flight guards. The
   timer only queues work; every USB operation runs in `DeviceWorker` on its
   dedicated `QThread`.

The direct backend is intentionally small. A future OpenLinkHub adapter can
implement the same `NautilusBackend` protocol, but version 0.1 does not start,
configure, or depend on an OpenLinkHub service.

## State model

- `disconnected`: no supported device
- `ready`: supported device configured and idle
- `sending`: one finite report sequence in progress
- `displaying`: this session successfully sent volatile content
- `restoring`: hardware-mode reports in progress
- `error`: the last operation failed

Send and restore are explicit. After the initial send succeeds, `displaying`
maintains the same in-memory JPEG using bounded one-second refreshes. At most one
refresh may be queued or executing. Any transfer failure stops scheduling and
enters `error` without retry. Manual restore, disconnect, and normal close stop
the refresh timer first. A restore failure leaves the window open for a clear,
manual retry rather than hiding the error.

GIF scheduling uses monotonic source-frame deadlines. Only one HID operation may
be in flight. If decoding or transfer takes longer than the requested timing,
obsolete deadlines are coalesced to the current frame instead of queued. A
long-held frame is retransmitted at the existing 1,000 ms keepalive interval.
The selected preview and active LCD media are separate snapshots: selecting new
media never changes the LCD until Send is pressed.

The four fixed profile modes are Thermals, Image, GIF, and Creative. Profile
selection and Image/GIF resize strategies persist in
`$XDG_CONFIG_HOME/nautiboy/profiles.json`. Switching modes changes UI state
only: it does not emit a device operation, stop active playback, or alter the
LCD. Thermals now uses the read-only Linux telemetry subsystem and the
programmatic Orbit renderer. Creative contains four stable, independently stored
sub-presets; their active selection and renameable display names persist while
their background, Orbit, and telemetry-overlay settings remain independent.

Telemetry hardware identity is separate from future user presentation state.
Versioned presentation settings live in a separate atomic per-user
`telemetry.json` file keyed by deterministic sensor ID. A strict maximum of two
enabled items is enforced independently of the UI.
Creative compositing has a fixed visual order: JPEG/PNG/GIF media background,
optional animated Orbit perimeter overlay, then telemetry foreground. The
background remains visually dominant, while telemetry always stays above it.
Orbit is a framing effect confined to the perimeter and must never cover text.
It reuses the existing programmatic Orbit geometry/timing and introduces no new
HID behavior.

The pure compositor is separate from media decoding and device I/O. Its output
is a bounded 480×480 RGB image. The worker uses the already validated static
JPEG transport, while a bounded scheduler combines independent GIF deadlines,
Orbit phase, and approximately 1 Hz telemetry snapshots without queuing stale
frames or allowing concurrent transfers. Merely previewing or browsing profiles
and presets performs no HID operation.

Online search is not a prerequisite for local media. GIPHY downloads live only
for the current session because standard GIPHY integrations may not persistently
cache media without approval. The generic XDG cache implementation is reserved
for providers whose terms allow persistent caching.

The optional GIPHY credential is resolved from the process environment first,
then from the desktop keyring through Python keyring and Freedesktop Secret
Service. NautiBoy settings contain no credential. Provider and Preferences code
depend on a narrow credential-store boundary so tests use only fake secrets.

Normal window close is a visibility operation when the tray controller is
attached: it hides the existing window without touching either scheduler or the
device session. Tray Restore stops scheduling before queuing the existing
hardware-mode restore. Tray Quit is the only application shutdown path; it
blocks new scheduling, closes optional network work, serializes restore behind
any in-flight device operation, stops the device thread, removes the tray icon,
and exits.

Before a `MainWindow` or backend exists, the entry point acquires a per-user Qt
local socket named from the application ID and UID. A second process sends an
activation message and exits. The primary raises its existing window. No PID
searching or process termination is used.

Desktop shortcut commands are handled before constructing `QApplication` or any
hardware-owning object. They resolve Qt's XDG Desktop location and operate only
on a NautiBoy-marked copy of the installed desktop entry.
