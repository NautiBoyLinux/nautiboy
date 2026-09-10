#!/usr/bin/env python3
"""Regenerate the public hardware compatibility page from the catalog."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nautiboy.hardware.compatibility import render_hardware_compatibility  # noqa: E402


def main() -> None:
    (ROOT / "docs/hardware-compatibility.md").write_text(
        render_hardware_compatibility(), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
