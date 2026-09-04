"""Public application identity and bundled asset locations."""

from pathlib import Path

APP_NAME = "NautiBoy"
APP_ID = "io.github.nautiboy.NautiBoy"
APP_DESCRIPTION = "NautiBoy is an open-source Linux controller for Corsair NAUTILUS RS LCD displays."
DISCLAIMER = (
    "NautiBoy is an unofficial community project and is not affiliated with, "
    "endorsed by, or supported by Corsair."
)


def asset_path(name: str) -> Path:
    return Path(__file__).with_name("assets") / name
