"""Small helpers for state-dependent UI policy."""

from __future__ import annotations

from dataclasses import dataclass

from .models import AppState


@dataclass(frozen=True, slots=True)
class ControlPolicy:
    select_image: bool
    send: bool
    restore: bool


def control_policy(
    state: AppState, *, has_device: bool, has_image: bool, session_touched_display: bool
) -> ControlPolicy:
    interactive = state in {AppState.READY, AppState.DISPLAYING}
    return ControlPolicy(
        select_image=interactive,
        send=interactive and has_device and has_image,
        restore=(state in {AppState.DISPLAYING, AppState.ERROR})
        and has_device
        and session_touched_display,
    )


def state_after_image_error(*, has_device: bool) -> AppState:
    """Image input errors are recoverable and must not lock the selector."""
    return AppState.READY if has_device else AppState.DISCONNECTED
