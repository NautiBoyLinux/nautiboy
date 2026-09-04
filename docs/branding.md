# Branding assets

The application name is **NautiBoy** and the provisional application ID is
`io.github.nautiboy.nautiboy`. The normalized ID is used consistently for the
desktop entry, AppStream component, icons, autostart entry, and per-user
single-instance identity. The `io.github` namespace remains provisional and
must be reviewed against the final public
GitHub namespace before release.

`src/nautiboy/assets/logo-reference-original.png` is an unchanged copy of the
supplied 345×358 raster concept. `packaging/generate_icons.py` center-crops it to
the square 345×345 development source used by Qt and generates hicolor PNGs at
16, 32, 48, 64, 128, and 256 pixels.

`branding.application_icon()` is the single runtime loader for the window,
task switcher, tray icon, tray notifications, and header logo. It always loads
bundled assets and therefore does not depend on an installed desktop entry or
system icon theme. Exact copies of the existing 32×32 and 48×48 derivatives are
bundled alongside the 345×345 source so Qt can favor crisp small artwork.

The existing 32×32 and 48×48 derivatives retain the recognizable purple cat
silhouette. The existing 16×16 derivative loses much of that silhouette, so it
is not included in the runtime icon set; Qt scales the clearer 32×32 artwork for
16–24 pixel tray slots. No logo artwork was redesigned.

These are intentionally development assets. Before public packaging, supply a
square vector master (preferably SVG) or at least a transparent 1024×1024 PNG.
The ideal master should preserve the cat/nautilus silhouette and restrained
purple glow while remaining legible at 16 and 32 pixels.
