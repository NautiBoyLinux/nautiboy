from __future__ import annotations

from nautiboy.creative.playback import (
    CREATIVE_DYNAMIC_INTERVAL_MS,
    CREATIVE_TELEMETRY_INTERVAL_MS,
    CreativePlaybackController,
)


class Timeout:
    def connect(self, callback): self.callback = callback


class Timer:
    def __init__(self): self.timeout, self.active, self.interval = Timeout(), False, None
    def setInterval(self, value): self.interval = value
    def start(self): self.active = True
    def stop(self): self.active = False


class Gif:
    frame_count = 3
    durations_ms = (100, 200, 300)
    duration_ms = 600


def test_dynamic_latest_state_wins_without_overlap_or_backlog() -> None:
    now = [10.0]
    timer = Timer()
    controller = CreativePlaybackController(clock=lambda: now[0], timer=timer)
    frames = []
    controller.frame_requested.connect(lambda phase, index: frames.append((phase, index)))
    controller.start(Gif(), orbit_animated=False, telemetry_enabled=False)
    assert timer.interval == CREATIVE_DYNAMIC_INTERVAL_MS and len(frames) == 1
    now[0] += .25
    timer.timeout.callback(); timer.timeout.callback()
    assert len(frames) == 1 and controller.dropped_frames == 2
    controller.transfer_completed(); timer.timeout.callback()
    assert len(frames) == 2 and frames[-1][1] == 1


def test_telemetry_only_uses_one_hz_and_stop_blocks_requests() -> None:
    timer = Timer()
    controller = CreativePlaybackController(timer=timer)
    frames = []
    controller.frame_requested.connect(lambda *args: frames.append(args))
    controller.start(None, orbit_animated=False, telemetry_enabled=True)
    assert timer.interval == CREATIVE_TELEMETRY_INTERVAL_MS and len(frames) == 1
    controller.stop(); timer.timeout.callback()
    assert len(frames) == 1 and not controller.active
