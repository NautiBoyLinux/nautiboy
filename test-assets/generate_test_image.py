#!/usr/bin/env python3
"""Generate the deterministic static image used for hardware validation."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).with_name("test-image-480.jpg")


def centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((480 - (right - left)) // 2, y), text, font=font, fill=fill)


def main() -> None:
    image = Image.new("RGB", (480, 480), "#080c12")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, 461, 461), radius=32, outline="#42d9ff", width=8)
    draw.ellipse((181, 72, 299, 190), outline="#42d9ff", width=10)
    draw.line((216, 131, 236, 151, 272, 108), fill="#7dff91", width=12, joint="curve")
    regular = ImageFont.truetype("/usr/share/fonts/open-sans/OpenSans-Regular.ttf", 36)
    bold = ImageFont.truetype("/usr/share/fonts/open-sans/OpenSans-Bold.ttf", 42)
    small = ImageFont.truetype("/usr/share/fonts/open-sans/OpenSans-Regular.ttf", 24)
    centered(draw, 225, "NAUTILUS", bold, "#f4f8ff")
    centered(draw, 282, "LINUX LCD TEST", regular, "#42d9ff")
    centered(draw, 351, "1 SECOND REFRESH", small, "#aab6c5")
    image.save(
        OUTPUT,
        format="JPEG",
        quality=90,
        subsampling=0,
        optimize=False,
        progressive=False,
    )


if __name__ == "__main__":
    main()
