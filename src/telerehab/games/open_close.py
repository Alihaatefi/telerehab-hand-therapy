"""Open/Close mode — timed posture holds — the rules, with no rendering.

The patient alternates holding the hand open and closed for a prescribed number
of seconds, for a prescribed number of repetitions.

Unlike Time/Score this is a *hold* exercise: what matters is sustaining a
posture, not reaching a position, so the timer only advances while the posture
is correct (see :class:`telerehab.games.scoring.HoldTimer`).

This module is the logic that used to live inside the pygame screen, moved
across unchanged.
"""
from __future__ import annotations

import time

from ..api.models import Session
from ..config import GameConfig
from ..vision.calibration import TwoPointCalibration
from .protocols import SampleLike
from .scoring import Clock, HoldTimer


class OpenCloseEngine:
    """One Open/Close session. Feed it a frame at a time with :meth:`update`."""

    def __init__(
        self,
        calibration: TwoPointCalibration,
        *,
        patient_id: int,
        game_config: GameConfig,
        clock: Clock = time.monotonic,
    ):
        self.calibration = calibration
        self.patient_id = patient_id
        self.config = game_config
        self.clock = clock

        # A flat schedule of (posture, seconds) so "which hold am I on" is a
        # single index rather than nested loops with a break in the middle.
        self.schedule: list[tuple[bool, float]] = []
        for _ in range(max(1, game_config.repetitions)):
            self.schedule.append((True, float(game_config.open_seconds)))
            self.schedule.append((False, float(game_config.close_seconds)))

        self.index = 0
        self.timer = HoldTimer(self.schedule[0][1], clock)
        self.paused = False
        self.hand_open: bool | None = None

    # -- state -------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self.index >= len(self.schedule)

    @property
    def target_open(self) -> bool:
        """The posture currently being asked for."""
        return self.schedule[min(self.index, len(self.schedule) - 1)][0]

    @property
    def repetition(self) -> int:
        """1-based repetition number (one open hold plus one closed hold)."""
        return min(self.index // 2 + 1, self.config.repetitions)

    @property
    def completed_repetitions(self) -> int:
        return self.index // 2

    @property
    def posture_correct(self) -> bool:
        return self.hand_open is not None and self.hand_open == self.target_open

    def result(self) -> Session:
        return Session.open_close(
            self.patient_id,
            open_seconds=self.config.open_seconds,
            close_seconds=self.config.close_seconds,
            repetitions=self.config.repetitions,
            completed_repetitions=self.completed_repetitions,
        )

    # -- control -----------------------------------------------------------

    def toggle_pause(self) -> bool:
        """Pause or resume. Returns True when now paused."""
        self.paused = not self.paused
        return self.paused

    # -- simulation --------------------------------------------------------

    def update(self, sample: SampleLike) -> bool:
        """Advance by one frame. Returns True when a hold has just completed."""
        if self.paused:
            # Feed the timer a "wrong posture" tick so it stops accumulating
            # without discarding what the patient has already held.
            self.timer.update(False)
            return False

        pinch = sample.pinch
        self.hand_open = (
            self.calibration.is_open(pinch) if sample.has_hand and pinch is not None else None
        )
        self.timer.update(self.posture_correct)

        if self.timer.done:
            self._advance()
            return True
        return False

    def _advance(self) -> None:
        self.index += 1
        if self.index >= len(self.schedule):
            self.index = len(self.schedule)  # all repetitions completed
            return
        self.timer = HoldTimer(self.schedule[self.index][1], self.clock)
