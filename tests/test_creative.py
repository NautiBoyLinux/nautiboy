from __future__ import annotations

from dataclasses import replace

from PIL import Image, ImageChops
import pytest

from nautiboy.creative import CreativeComposition, compose_creative
from nautiboy.telemetry.orbit import OrbitItem


PURPLE = OrbitItem("CPU", 52.0, "#9B30FF")
CYAN = OrbitItem("GPU", 41.0, "#00D9FF")


def _background(color="navy"):
    return Image.new("RGB", (480, 480), color)


@pytest.mark.parametrize(
    ("orbit", "telemetry"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_static_combinations_render_480_rgb(orbit, telemetry) -> None:
    result = compose_creative(
        CreativeComposition(_background(), (PURPLE, CYAN), telemetry, orbit)
    )
    assert result.mode == "RGB"
    assert result.size == (480, 480)


def test_strict_layer_order_telemetry_is_foreground(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "nautiboy.creative.compositor.apply_orbit_perimeter",
        lambda image, *_args, **_kwargs: (calls.append("orbit"), image)[1],
    )
    monkeypatch.setattr(
        "nautiboy.creative.compositor.apply_telemetry_foreground",
        lambda image, *_args, **_kwargs: (calls.append("telemetry"), image)[1],
    )
    compose_creative(CreativeComposition(_background(), (PURPLE,), True, True))
    assert calls == ["orbit", "telemetry"]


def test_follow_telemetry_colors_and_custom_colors(monkeypatch) -> None:
    colors = []
    monkeypatch.setattr(
        "nautiboy.creative.compositor.apply_orbit_perimeter",
        lambda image, selected, *_args, **_kwargs: (colors.append(selected), image)[1],
    )
    compose_creative(CreativeComposition(_background(), (PURPLE, CYAN), False, True, True))
    compose_creative(
        CreativeComposition(_background(), (PURPLE,), False, True, True, False, "#112233", "#445566")
    )
    assert colors == [("#9B30FF", "#00D9FF"), ("#112233", "#445566")]


def test_unavailable_telemetry_and_max_two_rule() -> None:
    unavailable = replace(PURPLE, value=None, availability="unavailable")
    assert compose_creative(CreativeComposition(_background(), (unavailable,), True)).size == (480, 480)
    with pytest.raises(ValueError, match="at most two"):
        compose_creative(CreativeComposition(_background(), (PURPLE, CYAN, PURPLE), True))


def test_orbit_changes_only_when_enabled() -> None:
    base = _background()
    without = compose_creative(CreativeComposition(base, (PURPLE,), False, False))
    with_orbit = compose_creative(CreativeComposition(base, (PURPLE,), False, True))
    assert ImageChops.difference(without.convert("RGB"), base).getbbox() is None
    assert ImageChops.difference(with_orbit.convert("RGB"), base).getbbox() is not None
