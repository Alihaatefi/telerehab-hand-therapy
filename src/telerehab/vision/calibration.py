"""Per-patient calibration of hand-openness.

Raw openness is not comparable between patients or even between sessions: it
scales with hand size, camera distance and lens. A stroke patient with limited
range may span 12-30 raw units where a healthy hand spans 10-60. Feeding raw
values into the game would make the exercise trivially easy for some patients
and physically impossible for others.

Both calibrators therefore map raw openness onto a patient-relative scale, so
game difficulty follows the patient's *own* achievable range rather than an
absolute threshold.
"""
from __future__ import annotations

from dataclasses import dataclass


class CalibrationError(RuntimeError):
    """Raised when a calibrator is used before it has usable samples."""


@dataclass
class RangeCalibration:
    """Tracks the min and max openness a patient reaches during calibration.

    Used by Time/Score mode, which needs a continuous 0-100 signal to position
    the butterfly.
    """

    minimum: float = float("inf")
    maximum: float = float("-inf")

    #: Guards against a degenerate range. If a patient barely moves — or the
    #: hand was never detected — min and max collapse together and normalising
    #: would divide by ~0, sending the butterfly to infinity.
    min_span: float = 1e-3

    def observe(self, openness: float) -> None:
        """Fold one raw sample into the observed range."""
        self.minimum = min(self.minimum, openness)
        self.maximum = max(self.maximum, openness)

    @property
    def span(self) -> float:
        if not self.ready:
            return 0.0
        return self.maximum - self.minimum

    @property
    def ready(self) -> bool:
        """True once at least one sample was seen and the range is non-degenerate."""
        if self.minimum == float("inf") or self.maximum == float("-inf"):
            return False
        return (self.maximum - self.minimum) >= self.min_span

    def reset(self) -> None:
        self.minimum = float("inf")
        self.maximum = float("-inf")

    def normalize(self, openness: float) -> float:
        """Map a raw sample onto 0-100 within the calibrated range.

        Values outside the calibrated range are clamped rather than
        extrapolated: a patient who briefly exceeds their calibration should
        peg the meter, not overshoot the screen.
        """
        if not self.ready:
            raise CalibrationError(
                "calibration incomplete - the hand was not detected, or it did "
                "not move enough during the calibration window"
            )

        scaled = (openness - self.minimum) / (self.maximum - self.minimum) * 100.0
        return max(0.0, min(100.0, scaled))


@dataclass
class TwoPointCalibration:
    """Records one open sample and one closed sample, then classifies.

    Used by Open/Close mode, which only needs a binary decision. The decision
    boundary sits midway between the two calibration samples.
    """

    open_sample: float | None = None
    closed_sample: float | None = None

    @property
    def ready(self) -> bool:
        return self.open_sample is not None and self.closed_sample is not None

    @property
    def threshold(self) -> float:
        if self.open_sample is None or self.closed_sample is None:
            raise CalibrationError("both an open and a closed sample are required")
        return (self.open_sample + self.closed_sample) / 2.0

    def reset(self) -> None:
        self.open_sample = None
        self.closed_sample = None

    def is_open(self, openness: float) -> bool:
        """Classify a raw sample as open (True) or closed (False)."""
        return openness > self.threshold


class MovementCounter:
    """Counts open/close transitions with hysteresis.

    A single threshold would count a hand resting near the boundary as dozens
    of movements as the signal jitters across it. Two thresholds with a dead
    band between them mean the hand must genuinely travel to register.

    The count increments on *every* transition in either direction, so one full
    open-and-close cycle counts as two movements.
    """

    def __init__(self, open_threshold: float = 70.0, close_threshold: float = 30.0):
        if close_threshold >= open_threshold:
            raise ValueError("close_threshold must be below open_threshold")

        self.open_threshold = open_threshold
        self.close_threshold = close_threshold
        self.count = 0
        self.hand_open = False

    def update(self, openness_pct: float) -> int:
        """Feed one normalised (0-100) sample; returns the running count."""
        if openness_pct > self.open_threshold and not self.hand_open:
            self.hand_open = True
            self.count += 1
        elif openness_pct < self.close_threshold and self.hand_open:
            self.hand_open = False
            self.count += 1
        return self.count

    def reset(self) -> None:
        self.count = 0
        self.hand_open = False
