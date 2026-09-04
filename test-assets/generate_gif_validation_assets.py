"""Generate deterministic, local-only GIFs for the approved v0.2 hardware test."""

from pathlib import Path
import random

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent


def frame(number: int, total: int, color: tuple[int, int, int], label: str) -> Image.Image:
    image = Image.new("RGB", (480, 480), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((28, 28, 452, 452), outline="white", width=12)
    draw.text((58, 70), "NAUTIBOY v0.2", fill="white", stroke_width=2, stroke_fill="black")
    draw.text((58, 205), label, fill="white", stroke_width=3, stroke_fill="black")
    draw.text((58, 355), f"FRAME {number}/{total}", fill="white", stroke_width=2, stroke_fill="black")
    return image


def save(name: str, colors: list[tuple[int, int, int]], durations: list[int], label: str) -> None:
    frames = [frame(index + 1, len(colors), color, label) for index, color in enumerate(colors)]
    frames[0].save(
        ROOT / name,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )


def complex_frame(number: int, total: int) -> Image.Image:
    """High-entropy but bounded frame that produces a much larger LCD JPEG."""
    noise = Image.frombytes("L", (480, 480), random.Random(9000 + number).randbytes(480 * 480))
    image = Image.merge("RGB", (noise, noise, noise))
    draw = ImageDraw.Draw(image)
    accent = ((number * 53) % 256, (number * 97) % 256, 255)
    draw.rectangle((25, 25, 455, 455), outline=accent, width=14)
    draw.rectangle((35, 180, 445, 300), fill=(10, 8, 20))
    draw.text((55, 195), "VARIABLE / COALESCE", fill="white")
    draw.text((55, 250), f"FRAME {number}/{total}", fill="white")
    return image


save(
    "gif-validation-steady.gif",
    [(128, 0, 255), (0, 120, 255), (0, 190, 90), (240, 150, 0), (225, 35, 80), (100, 30, 180)],
    [750] * 6,
    "STEADY 750 ms",
)

variable_durations = [10, 20, 40, 500, 30, 900, 60, 350, 20, 700, 50, 450]
variable_frames = [complex_frame(index + 1, 12) for index in range(12)]
variable_frames[0].save(
    ROOT / "gif-validation-variable.gif",
    format="GIF",
    save_all=True,
    append_images=variable_frames[1:],
    duration=variable_durations,
    loop=0,
    optimize=False,
)
