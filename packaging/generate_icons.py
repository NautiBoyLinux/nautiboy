#!/usr/bin/env python3
"""Derive temporary square desktop icons from the supplied raster reference."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "io.github.nautiboy.NautiBoy"
REFERENCE = ROOT / "src/nautiboy/assets/logo-reference-original.png"
SOURCE = ROOT / "src/nautiboy/assets/nautiboy-icon-development-source.png"
SIZES = (16, 32, 48, 64, 128, 256)


def main() -> None:
    original = Image.open(REFERENCE).convert("RGBA")
    side = min(original.size)
    left = (original.width - side) // 2
    top = (original.height - side) // 2
    square = original.crop((left, top, left + side, top + side))
    square.save(SOURCE)

    for size in SIZES:
        destination = (
            ROOT
            / "packaging/icons/hicolor"
            / f"{size}x{size}"
            / "apps"
            / f"{APP_ID}.png"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        square.resize((size, size), Image.Resampling.LANCZOS).save(destination)


if __name__ == "__main__":
    main()
