#!/usr/bin/env python3
"""Install and validate the approved permanent NautiBoy icon derivatives."""

from pathlib import Path
from shutil import copyfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "io.github.nautiboylinux.nautiboy"
MASTER = ROOT / "artwork/masters/nautiboy-icon-1024.png"
CURATED = ROOT / "artwork/icons/png"
RUNTIME = ROOT / "src/nautiboy/assets"
SIZES = (16, 32, 48, 64, 128, 256, 512)


def _validate_icon(path: Path, size: int) -> None:
    with Image.open(path) as image:
        if image.size != (size, size):
            raise ValueError(f"{path} must be exactly {size}x{size}")
        if image.mode not in {"RGBA", "LA", "P"} or "transparency" not in image.info and image.mode != "RGBA":
            raise ValueError(f"{path} must contain transparency")
        rgba = image.convert("RGBA")
        low, high = rgba.getchannel("A").getextrema()
        if low != 0 or high == 0:
            raise ValueError(f"{path} must contain visible pixels on a transparent background")


def main() -> None:
    _validate_icon(MASTER, 1024)

    for size in SIZES:
        source = CURATED / f"nautiboy-{size}.png"
        _validate_icon(source, size)
        destination = (
            ROOT
            / "packaging/icons/hicolor"
            / f"{size}x{size}"
            / "apps"
            / f"{APP_ID}.png"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source, destination)

    for size in (32, 48, 1024):
        source = CURATED / f"nautiboy-{size}.png"
        _validate_icon(source, size)
        copyfile(source, RUNTIME / f"nautiboy-icon-{size}.png")


if __name__ == "__main__":
    main()
