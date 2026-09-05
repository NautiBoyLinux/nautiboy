# NautiBoy branding assets

This package contains the permanent NautiBoy brand artwork. None of the assets include version or beta text.

## Which asset to use

- **Application icon:** use `masters/nautiboy-icon-1024.png`, `masters/nautiboy-icon.svg`, or the matching file under `icons/png/`. The icon-only cat/neon-square mark is designed for KDE, desktop entries, RPM packaging, AppStream/Discover, and Flathub.
- **README, GitHub, releases, and promotional branding:** use `masters/nautiboy-logo-1024.png` or `masters/nautiboy-logo.svg`. This version includes the NautiBoy wordmark and descriptor and should not be squeezed into small icon slots.
- **Tiny sizes:** use the supplied 16–64 px PNGs rather than scaling the full wordmark. They have been downsampled from the icon master and sharpened for legibility.

## Contents

- `masters/nautiboy-icon-1024.png` — transparent 1024×1024 raster icon master
- `masters/nautiboy-icon.svg` — clean, editable vector interpretation of the approved icon
- `masters/nautiboy-logo-1024.png` — transparent 1024×1024 full logo master
- `masters/nautiboy-logo.svg` — editable full-logo SVG
- `icons/png/` — 16, 32, 48, 64, 128, 256, 512, and 1024 px application icons
- `/ARTWORK-LICENSE.txt` — repository-root copyright, artwork license,
  code-license distinction, and disclaimer
- `reference/approved-logo-reference.png` — original approved low-resolution reference retained for provenance

## Naming/integration

The desktop icon name should remain the application ID/name expected by the repository. Copy the needed derivative into the repository's normal icon hierarchy and rename it only as packaging requires. Preserve this package as the source-of-truth artwork bundle.

## License and disclaimer

Artwork is copyright Andrew Tyler and licensed under CC BY-SA 4.0. NautiBoy
source code remains under GPL-3.0-or-later. See the repository-root
`ARTWORK-LICENSE.txt` for the full statement and required non-affiliation
disclaimer.
