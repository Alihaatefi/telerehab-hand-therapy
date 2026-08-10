"""Exercise rules, with no rendering and no I/O.

The scoring and hold-timing rules are the part of the game a clinician would
actually want to argue about, so they live here as small classes driven by an
injected clock rather than being spelled out inline in the pygame loop. That
makes them testable in milliseconds instead of real seconds.
"""
from __future__ import annotations

import random
from collections import deque
from typing import Callable, Deque

Clock = Callable[[], float]


class ButterflySmoother:
    """Moving average over recent butterfly positions.

    Raw MediaPipe openness jitters by several percent frame to frame. Mapped
    straight onto position that reads as a butterfly with a tremor, which is an
    unfortunate thing to show a patient with a movement disorder.
    """

    def __init__(self, window: int = 5):
        if window < 1:
            raise ValueError("window must be at least 1")
        self._samples: Deque[float] = deque(maxlen=window)

    def push(self, position: float) -> float:
        self._samples.append(position)
        return sum(self._samples) / len(self._samples)

    @property
    def value(self) -> float:
        return sum(self._samples) / len(self._samples) if self._samples else 0.0

    def clear(self) -> None:
        self._samples.clear()


def butterfly_position(openness_pct: float, gain: float, track_width: int) -> float:
    """Map normalised openness onto a horizontal position.

    ``gain`` is the therapeutic dial: above 1.0 a patient with reduced range
    still reaches the far end of the track, below 1.0 the exercise demands more
    movement for the same distance. The result is clamped so a high gain cannot
    push the butterfly off-screen.
    """
    position = (openness_pct / 100.0) * track_width * gain
    return max(0.0, min(float(track_width), position))


class FlowerTarget:
    """The flower the butterfly must settle on to score.

    A point requires the butterfly to *stay* within tolerance for
    ``dwell_seconds`` — a patient must hold the position, not sweep past it.
    """

    def __init__(
        self,
        *,
        min_x: int,
        max_x: int,
        tolerance_px: int,
        dwell_seconds: float,
        clock: Clock,
        rng: random.Random | None = None,
    ):
        if min_x >= max_x:
            raise ValueError("min_x must be below max_x")

        self.min_x = min_x
        self.max_x = max_x
        self.tolerance_px = tolerance_px
        self.dwell_seconds = dwell_seconds
        self._clock = clock
        self._rng = rng or random.Random()

        self.x = self._rng.randint(min_x, max_x)
        self.score = 0
        self._settled_at: float | None = None

    @property
    def is_settling(self) -> bool:
        """True while the butterfly is on the flower but has not scored yet."""
        return self._settled_at is not None

    def hold_progress(self) -> float:
        """0.0-1.0 progress towards the next point, for the dwell indicator."""
        if self._settled_at is None:
            return 0.0
        elapsed = self._clock() - self._settled_at
        return max(0.0, min(1.0, elapsed / self.dwell_seconds))

    def update(self, butterfly_x: float) -> bool:
        """Advance the dwell timer. Returns True on the frame a point is scored."""
        on_target = abs(butterfly_x - self.x) < self.tolerance_px

        if not on_target:
            self._settled_at = None
            return False

        now = self._clock()
        if self._settled_at is None:
            self._settled_at = now
            return False

        if now - self._settled_at >= self.dwell_seconds:
            self.score += 1
            self._settled_at = None
            self.respawn()
            return True

        return False

    def respawn(self) -> None:
        """Move the flower somewhere new, never on top of where it just was."""
        for _ in range(10):
            candidate = self._rng.randint(self.min_x, self.max_x)
            if abs(candidate - self.x) >= self.tolerance_px:
                self.x = candidate
                return
        self.x = self._rng.randint(self.min_x, self.max_x)

    def reset(self) -> None:
        self.score = 0
        self._settled_at = None
        self.x = self._rng.randint(self.min_x, self.max_x)


class HoldTimer:
    """Accumulates time spent in the *correct* hand posture.

    Open/Close mode asks the patient to hold a posture for N seconds. The
    original implementation reset its start time on every wrong-posture frame,
    which means a patient who wobbles once loses all accumulated credit and
    starts the hold from zero. This version pauses instead of resetting, so
    progress is preserved across a brief slip.
    """

    def __init__(self, duration: float, clock: Clock):
        if duration <= 0:
            raise ValueError("duration must be positive")

        self.duration = duration
        self._clock = clock
        self._accumulated = 0.0
        self._since: float | None = None

    def update(self, posture_correct: bool) -> None:
        now = self._clock()

        if posture_correct:
            if self._since is None:
                self._since = now
            else:
                self._accumulated += now - self._since
                self._since = now
        else:
            self._since = None

    @property
    def elapsed(self) -> float:
        return min(self._accumulated, self.duration)

    @property
    def remaining(self) -> float:
        return max(0.0, self.duration - self._accumulated)

    @property
    def progress(self) -> float:
        return max(0.0, min(1.0, self._accumulated / self.duration))

    @property
    def done(self) -> bool:
        return self._accumulated >= self.duration

    def reset(self) -> None:
        self._accumulated = 0.0
        self._since = None


class CountdownTimer:
    """A wall-clock countdown that can be paused without losing time.

    The original added the paused duration back onto ``start_time`` on resume,
    which works until the game is paused twice, or paused while a dialog is
    open — both of which drop time on the floor.
    """

    def __init__(self, duration: float, clock: Clock):
        self.duration = duration
        self._clock = clock
        self._start = clock()
        self._paused_at: float | None = None

    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    def pause(self) -> None:
        if self._paused_at is None:
            self._paused_at = self._clock()

    def resume(self) -> None:
        if self._paused_at is not None:
            self._start += self._clock() - self._paused_at
            self._paused_at = None

    def toggle(self) -> bool:
        self.resume() if self.paused else self.pause()
        return self.paused

    @property
    def elapsed(self) -> float:
        now = self._paused_at if self._paused_at is not None else self._clock()
        return now - self._start

    @property
    def remaining(self) -> float:
        return max(0.0, self.duration - self.elapsed)

    @property
    def progress(self) -> float:
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.remaining / self.duration))

    @property
    def expired(self) -> bool:
        return self.remaining <= 0

    def restart(self, duration: float | None = None) -> None:
        if duration is not None:
            self.duration = duration
        self._start = self._clock()
        self._paused_at = None
