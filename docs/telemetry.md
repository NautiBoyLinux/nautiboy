# Read-only Linux telemetry

The telemetry subsystem discovers Linux hwmon temperature channels without root
and never writes sysfs. Volatile `hwmonN` names are excluded from identity.
Deterministic sensor IDs combine the provider, normalized physical-device
identity, driver, and channel attribute. Best-effort semantic roles and display
labels are metadata, not identity.

Sensors share a normalized device record, allowing GPU edge, hotspot, and memory
channels to appear under one physical GPU. PCI devices use their domain/bus/slot
address; non-PCI devices use a deterministic digest of canonical sysfs ancestry.
Raw driver, label, bus, PCI, subsystem, and topology metadata remain available.

Temperatures are bounded ASCII integer reads expressed by hwmon in
millidegrees Celsius and normalized to Celsius floats. Missing or invalid data
never becomes zero. Readings are `available`, `stale`, `error`, or `unavailable`.
A stale or unavailable reading may retain its last good value and timestamp.

`TelemetryPoller` runs independently of Qt and HID, permits only one sample pass
at a time, publishes immutable complete snapshots, samples approximately once
per second, and performs slow bounded rediscovery. Rediscovery can also be
requested explicitly for future device-change integration. Removed sensors stay
visible as unavailable; a returning deterministic ID is recognized as the same
sensor.

Presentation settings are stored separately and keyed by sensor ID. The model
reserves a custom label, visibility, font color/family/size, and layout position.
Creative rendering order is strictly:

1. JPEG or GIF background
2. optional Orbit perimeter overlay
3. telemetry foreground

Presentation identity remains independent of rendering and raw discovery.

## Presentation configuration

User presentation state is stored separately at
`$XDG_CONFIG_HOME/nautiboy/telemetry.json`, falling back to
`~/.config/nautiboy/telemetry.json`. Writes use atomic replacement and mode
`0600`. The versioned document is keyed by deterministic sensor ID and retains
entries when sensors disconnect.

At most two temperature items may be enabled. The limit is enforced when files
are loaded or saved and by the selection API; excess malformed selections are
disabled deterministically after the first two. No selection is silently
replaced. Each entry reserves visibility, font family, font size, and position,
and currently exposes a custom display label and normalized `#RRGGBB` font
color. These values never alter raw sensor identity or hardware metadata.

The Thermals panel groups every discovered sensor by normalized physical device.
Selected sensors remain editable, while unselected checkboxes are disabled at
the two-item limit without hiding their sensor rows. This panel configures
presentation state and never emits HID operations by itself.

## Orbit theme

The programmatic 480×480 Orbit theme uses a nearly black static base, subtle
stationary rings and ticks, and thin segmented perimeter arcs. Arc phase is
derived from monotonic time over a twelve-second rotation, so dropped frames do
not change animation speed. One selected item is centered; two are placed in
separate upper and lower safe regions. Labels come from presentation settings,
values use their configured colors, and unavailable/stale state is explicit.

The GUI preview and LCD worker call the same renderer. Preview runs at 10 FPS
without device access. The refined renderer caches its static black/ring/tick
layer and redraws only animated arcs and telemetry text. Orbit uses a dedicated
bounded baseline-JPEG encoder at quality 86; representative offline frames are
about 30 KiB without visible loss in the preview.

The LCD scheduler has a conservative 10 FPS candidate interval for controlled
hardware validation, permits exactly one transfer in flight, and drops timer
events rather than queuing them. Phase remains monotonic, so every completed
transfer is followed by the newest position instead of stale animation work.
Instrumentation records render time, JPEG encode time and size, HID report count,
HID transfer time, total time, achieved FPS, and coalesced timer events. This
does not poll telemetry faster: sensor snapshots remain near 1 Hz. Restore and
Quit stop Orbit before invoking the existing hardware-mode path.

## Refined Orbit hardware validation

The refined design was visually approved on the hardware-tested CORSAIR
Nautilus LCD Cap (`1b1c:0c57`, interface 0, firmware `0.3.0.5`) on Fedora KDE
Plasma 44. Live CPU/GPU values, selected colors, the layered animated perimeter,
large typography, and mascot divider rendered correctly. Restore returned the
controller to its existing stored iCUE GIF; persistent LCD storage was not used.

The controlled run sustained 10.0 FPS without backlog or coalescing. Forty-one
logged ten-frame measurement windows reported the following rounded values:

| Measurement | Minimum | Average | Maximum |
| --- | ---: | ---: | ---: |
| Achieved FPS | 10.0 | 10.03 | 10.4 |
| Frame render | 25.5 ms | 26.2 ms | 27.8 ms |
| JPEG encode | 0.7 ms | 0.7 ms | 0.8 ms |
| JPEG size | 39.8 KiB | 40.48 KiB | 41.1 KiB |
| HID transfer | 10.5 ms | 10.7 ms | 11.4 ms |

Encoded frames required 41 HID reports in the observed run. The first measured
frame took 38.5 ms generation-to-send; subsequent component averages total
about 37.6 ms, leaving ample headroom inside the 100 ms scheduler interval.
No short write, disconnect, device mismatch, fallback, or backend error was
observed.

## Creative physical validation

The full Creative stack was physically validated on the same hardware-tested
CORSAIR Nautilus LCD Cap (`1b1c:0c57`, interface 0, firmware `0.3.0.5`) on
Fedora KDE Plasma 44. The controlled workload combined an animated GIPHY
background, animated Orbit perimeter, two live temperature readings, and Orbit
colors derived from those telemetry selections. The first completed composite
frame was 103 HID reports and took 56.9 ms generation-to-send.

The background GIF and Orbit both animated correctly while the two live values
remained readable above both lower layers. The perimeter stayed within its
intended circular boundary. No visible flicker, corruption, fallback,
disconnect, short write, or rendering defect was observed. Restore stopped the
Creative scheduler first and the existing stored iCUE GIF resumed through the
unchanged hardware-mode restoration path. Persistent LCD storage was not read
or modified.

Only the first-frame timing was retained in the UI details copied from this
run, so aggregate min/average/max performance values are intentionally not
claimed here. The application now retains bounded per-session measurements and
emits their aggregate summary when a subsequent Creative run is restored.
