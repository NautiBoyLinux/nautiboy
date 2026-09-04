# Functional profiles

NautiBoy v0.3 development introduces four fixed modes: Thermals, Image, GIF,
and Creative. Image exposes the existing JPEG/PNG workflow; GIF exposes the
existing local GIF and experimental GIPHY workflow. Thermals and Creative are
placeholders for later telemetry and compositing work.

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
own nested background and telemetry-overlay namespaces for future additions.
Names are trimmed, cannot be empty, and are limited to 20 characters; duplicate
display names are safe because identity always comes from the stable ID.
Unknown fields are retained where safe. Missing or malformed data recovers to
defaults. The earlier pre-preset Creative development shape is conservatively
loaded into Preset 1. A document from a newer schema is not overwritten.

Changing modes or selecting/renaming Creative presets never sends to the device,
enters software mode, stops an active LCD scheduler, restores hardware mode, or
changes the current LCD content.
Selected media paths, GIPHY URLs, and downloaded media are not persisted.
