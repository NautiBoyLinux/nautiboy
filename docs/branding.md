# Branding assets

The application name is **NautiBoy** and the provisional application ID is
`io.github.nautiboy.NautiBoy`. The ID must be reviewed against the final public
GitHub namespace before release.

`src/nautiboy/assets/logo-reference-original.png` is an unchanged copy of the
supplied 345×358 raster concept. `packaging/generate_icons.py` center-crops it to
the square 345×345 development source used by Qt and generates hicolor PNGs at
16, 32, 48, 64, 128, and 256 pixels.

These are intentionally development assets. Before public packaging, supply a
square vector master (preferably SVG) or at least a transparent 1024×1024 PNG.
The ideal master should preserve the cat/nautilus silhouette and restrained
purple glow while remaining legible at 16 and 32 pixels.
