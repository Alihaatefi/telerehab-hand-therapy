"""Calibration procedures, with no rendering.

Both modes calibrate, but they ask different questions, so there are two
procedures over the two calibrators in :mod:`telerehab.vision.calibration`:

* :class:`RangeCalibrationTask` (Time/Score) — sweep the hand for N seconds to
  learn its range.
* :class:`TwoPointCalibrationTask` (Open/Close) — capture one open sample and
  one closed sample.

Each is a small state machine the interface drives and draws; neither knows
about windows or cameras.
"""
from __future__ import annotations

from ..vision.calibration import RangeCalibration, TwoPointCalibration
from .protocols import SampleLike


class RangeCalibrationTask:
    """Learns a patient's openness range over a fixed number of seconds."""

    def __init__(self, seconds: int):
        self.seconds = max(1, seconds)
        self.calibration = RangeCalibration()
        self.elapsed = 0.0

    def feed(self, sample: SampleLike, dt: float) -> None:
        """Fold in one frame that lasted ``dt`` seconds.

        Only time with a hand actually visible counts, so a patient who takes a
        moment to get into frame is not silently short-changed.
        """
        spread = sample.spread
        if sample.has_hand and spread is not None:
            self.elapsed += dt
            self.calibration.observe(spread)

    @property
    def remaining(self) -> float:
        return max(0.0, self.seconds - self.elapsed)

    @property
    def progress(self) -> float:
        return max(0.0, min(1.0, self.elapsed / self.seconds))

    @property
    def done(self) -> bool:
        return self.elapsed >= self.seconds

    @property
    def usable(self) -> bool:
        """True if the hand was seen and moved enough to normalise against."""
        return self.calibration.ready


class TwoPointCalibrationTask:
    """Captures an open and a closed sample, then asks for confirmation."""

    OPEN, CLOSED, CONFIRM = "open", "closed", "confirm"
    STAGES = (OPEN, CLOSED, CONFIRM)

    PROMPTS = {
        OPEN: "Open your hand fully",
        CLOSED: "Close your hand into a fist",
        CONFIRM: "Both postures captured",
    }

    def __init__(self) -> None:
        self.calibration = TwoPointCalibration()
        self.step = 0
        self.warning: str | None = None

    @property
    def stage(self) -> str:
        return self.STAGES[self.step]

    @property
    def prompt(self) -> str:
        return self.PROMPTS[self.stage]

    def capture(self, sample: SampleLike | None) -> bool:
        """Record the current posture. Returns False (with a warning) on failure."""
        if self.stage == self.CONFIRM:
            return False

        if sample is None or not sample.has_hand:
            self.warning = "No hand detected - hold your hand in view and try again"
            return False

        value = sample.pinch
        if self.stage == self.OPEN:
            self.calibration.open_sample = value
        else:
            self.calibration.closed_sample = value

        self.warning = None
        self.step += 1
        return True

    def confirm(self) -> bool:
        """Accept the two samples. Returns False (with a warning) if they are unusable."""
        opened, closed = self.calibration.open_sample, self.calibration.closed_sample
        if self.stage != self.CONFIRM or opened is None or closed is None:
            return False

        # A hand that reads the same open and closed means the samples were
        # taken in the wrong posture; starting anyway gives nonsense.
        if abs(opened - closed) < 1e-3:
            self.warning = "Open and closed look identical - redo the capture"
            return False
        return True

    def reset(self) -> None:
        self.calibration.reset()
        self.step = 0
        self.warning = None
