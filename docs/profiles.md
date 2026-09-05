# Functional profiles

NautiBoy provides four fixed modes: Thermals, Image, GIF,
and Creative. Image exposes the existing JPEG/PNG workflow; GIF exposes the
existing local GIF and experimental GIPHY workflow. Thermals exposes read-only
Linux temperature selection and the Orbit theme. Creative provides layered
media, Orbit, and telemetry compositing.

Profile state is stored per user at
`$XDG_CONFIG_HOME/nautiboy/profiles.json`, falling back to
`~/.config/nautiboy/profiles.json`. Writes use atomic replacement and mode
`0600`. The RPM contains no user profile file, and profiles never use the LCD's
persistent storage.

Schema version 1 keeps stable IDs and types (`thermals`, `image`, `gif`, and
`creative`), a single active ID, fixed display names, and independent settings.
Image and GIF each retain their own Fit or Center Crop choice. Creative owns
four ordered sub-presets with stable IDs (`preset_1` through `preset_4`) and a
persistent active-preset ID. Each preset has a renameable display name and its
own nested background, Orbit, and telemetry-overlay settings.
Names are trimmed, cannot be empty, and are limited to 20 characters; duplicate
display names are safe because identity always comes from the stable ID.
Unknown fields are retained where safe. Missing or malformed data recovers to
defaults. The earlier pre-preset Creative development shape is conservatively
loaded into Preset 1. A document from a newer schema is not overwritten.

Changing modes or selecting/renaming Creative presets never sends to the device,
enters software mode, stops an active LCD scheduler, restores hardware mode, or
changes the current LCD content.
Creative presets persist only app-owned media references and safe display
settings; media bytes are never stored in `profiles.json`. Explicitly selected
GIPHY media is stored in deterministic per-preset XDG data slots, while browsing
results and thumbnails remain session-only.

## Creative compositor milestone

Each Creative preset can place the approved moving Orbit ring effect around its
JPEG, PNG, or GIF background and optionally draw the globally selected telemetry
items above it. The preview and device worker use the same compositor.
Local media and the existing experimental GIPHY search are available directly
from the Background section. GIPHY selections are never written into the profile
file. Explicit choices are copied to the selected-media store so previews survive
restart; generic search results are never cached.

The fixed rendering order is:

1. user-selected JPEG/GIF background
2. optional animated Orbit perimeter overlay
3. telemetry foreground

The overlay defaults to **off**. Per-preset settings include enabled,
primary color, secondary color, whether colors follow selected telemetry, and
whether animation is enabled. Rings remain confined to the outer perimeter and
frame rather than obscure the background. Telemetry stays above both layers.
The compositor reuses the validated Orbit timing and geometry and knows nothing
about HID. Dynamic playback is latest-state-wins with one transfer in flight and
a 10 FPS ceiling; telemetry-only compositions update at 1 Hz. Static-only
compositions use the existing 1,000 ms keepalive refresher.
