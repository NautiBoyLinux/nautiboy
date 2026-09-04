from __future__ import annotations

from nautiboy.application import control_policy, state_after_image_error
from nautiboy.models import AppState


def test_controls_disabled_when_disconnected() -> None:
    policy = control_policy(AppState.DISCONNECTED, has_device=False, has_image=True, session_touched_display=False)
    assert not policy.select_image and not policy.send and not policy.restore


def test_ready_with_image_enables_send() -> None:
    policy = control_policy(AppState.READY, has_device=True, has_image=True, session_touched_display=False)
    assert policy.select_image and policy.send and not policy.restore


def test_busy_states_disable_controls() -> None:
    for state in (AppState.SENDING, AppState.RESTORING):
        policy = control_policy(state, has_device=True, has_image=True, session_touched_display=True)
        assert not policy.select_image and not policy.send and not policy.restore


def test_error_after_touched_display_allows_restore_only() -> None:
    policy = control_policy(AppState.ERROR, has_device=True, has_image=True, session_touched_display=True)
    assert not policy.select_image and not policy.send and policy.restore


def test_failed_image_selection_returns_to_ready_and_allows_reselection() -> None:
    state = state_after_image_error(has_device=True)
    policy = control_policy(
        state, has_device=True, has_image=False, session_touched_display=False
    )

    assert state is AppState.READY
    assert policy.select_image
    assert not policy.send
