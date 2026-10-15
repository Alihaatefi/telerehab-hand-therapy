"""Time/Score mode — "Butterfly Garden" — the rules, with no rendering.

Hand openness drives the butterfly's horizontal position. Settling on the
flower for half a second scores a point and moves the flower. The session runs
for a fixed time, then reports score and movement count.

The therapeutic dial is ``gain``: it decouples the patient's achievable range
from the distance the butterfly must cover, so the same exercise works for a
hand that opens 20 degrees and one that opens 90.

This module is the logic that used to live inside the pygame screen, moved
across unchanged. It owns no window and no camera, so a session can be played
through in a unit test with a fake clock.
"""
from __future__ import annotations

import random
import time

from ..api.models import Session
from ..config import TRACK_WIDTH, GameConfig, VisionConfig
from ..vision.calibration import MovementCounter, RangeCalibration
from .protocols import SampleLike
from .scoring import (
    ButterflySmoother,
    Clock,
    CountdownTimer,
    FlowerTarget,
    butterfly_position,
)


class TimeScoreEngine:
    """One Time/Score session. Feed it a frame at a time with :meth:`update`."""

    def __init__(
        self,
        calibration: RangeCalibration,
        *,
        patient_id: int,
        game_config: GameConfig,
        vision_config: VisionConfig,
        track_width: int = TRACK_WIDTH,
        clock: Clock = time.monotonic,
        rng: random.Random | None = None,
    ):
        self.calibration = calibration
        self.patient_id = patient_id
        self.config = game_config
        self.track_width = track_width
        self.clock = clock

        self.smoother = ButterflySmoother(game_config.smoothing_window)
        self.movements = MovementCounter(
            vision_config.open_threshold, vision_config.close_threshold
        )
        self.timer = CountdownTimer(game_config.exercise_seconds, clock)
        self.flower = FlowerTarget(
            min_x=50,
            max_x=max(51, track_width - 50),
            tolerance_px=game_config.flower_tolerance_px,
            dwell_seconds=game_config.flower_dwell_seconds,
            clock=clock,
            rng=rng,
        )

        self.butterfly_x = 0.0
        self.openness = 0.0
        self.gain = game_config.gain
        self.hand_visible = False

    # -- state -------------------------------------------------------------

    @property
    def score(self) -> int:
        return self.flower.score

    @property
    def paused(self) -> bool:
        return self.timer.paused

    @property
    def finished(self) -> bool:
        return self.timer.expired

    def result(self) -> Session:
        """The session record for what has been played so far."""
        return Session.time_score(
            self.patient_id,
            score=self.flower.score,
            gain=self.gain,
            exercise_seconds=self.config.exercise_seconds,
            movements=self.movements.count,
        )

    # -- control -----------------------------------------------------------

    def toggle_pause(self) -> bool:
        """Pause or resume. Returns True when now paused."""
        return self.timer.toggle()

    def restart(self) -> None:
        self.smoother.clear()
        self.movements.reset()
        self.flower.reset()
        self.timer.restart()
        self.butterfly_x = 0.0
        self.openness = 0.0

    # -- simulation --------------------------------------------------------

    def update(self, sample: SampleLike) -> bool:
        """Advance by one frame. Returns True on the frame a point is scored."""
        if self.timer.paused:
            return False

        self.hand_visible = sample.has_hand
        spread = sample.spread
        if sample.has_hand and spread is not None:
            self.openness = self.calibration.normalize(spread)
            self.movements.update(self.openness)
            self.butterfly_x = self.smoother.push(
                butterfly_position(self.openness, self.gain, self.track_width)
            )

        return self.flower.update(self.butterfly_x)
