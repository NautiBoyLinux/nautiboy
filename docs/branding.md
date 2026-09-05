# Branding assets

The application name is **NautiBoy**, release target `v0.4.0-beta.1`, and the final application ID is
`io.github.nautiboylinux.nautiboy`. The normalized ID is used consistently for the
desktop entry, AppStream component, icons, autostart entry, and per-user
single-instance identity. It is derived from the project-owned
`NautiBoyLinux/nautiboy` GitHub namespace.

Permanent source artwork lives under `artwork/`. The icon-only masters are
`artwork/masters/nautiboy-icon.svg` and the transparent 1024×1024
`artwork/masters/nautiboy-icon-1024.png`. The full wordmark/logo masters are
`artwork/masters/nautiboy-logo.svg` and the transparent 1024×1024
`artwork/masters/nautiboy-logo-1024.png`. The icon-only mark is used for the
application, desktop entry, AppStream/Discover, tray, and RPM; the full logo is
reserved for README, documentation, release, and promotional presentation.

The original approved 345×358 concept is retained only at
`artwork/reference/approved-logo-reference.png` as historical provenance. It is
not an active runtime or icon-generation input.

`branding.application_icon()` is the single runtime loader for the window,
task switcher, tray icon, tray notifications, and header logo. It always loads
bundled assets and therefore does not depend on an installed desktop entry or
system icon theme. Exact copies of the optimized 32×32 and 48×48 derivatives
are bundled alongside the 1024×1024 icon master so Qt can favor crisp small
artwork.

Curated transparent derivatives at 16, 32, 48, 64, 128, 256, 512, and 1024
pixels live under `artwork/icons/png/`. `packaging/generate_icons.py` validates
their dimensions and transparency, then copies them into the hicolor hierarchy
using the final application ID. The supplied optimized small derivatives are
used directly instead of downscaling the wordmark or regenerating tiny icons.

The NautiBoy icon, mascot, logo, wordmark, and derivatives are copyright Andrew
Tyler and licensed under CC BY-SA 4.0. Source code remains separately licensed
under GPL-3.0-or-later. See `ARTWORK-LICENSE.txt`; neither license statement
grants ownership of Corsair names or marks. NautiBoy remains an unofficial
community project and is not affiliated with, endorsed by, or supported by
Corsair.
