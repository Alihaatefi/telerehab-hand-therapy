"""End-to-end vision checks against the project's own reference photographs.

No camera is involved: the two hand photographs shipped in ``resources/reference``
are fed through the real MediaPipe pipeline. That covers the assumption the
whole application rests on — that these metrics separate an open hand from a
closed one — which no amount of synthetic-landmark testing can establish.

Marked ``vision`` so they can be skipped:  ``pytest -m "not vision"``.
"""
from __future__ import annotations

import pytest

from telerehab.config import REFERENCE_DIR, VisionConfig
from telerehab.vision.calibration import RangeCalibration, TwoPointCalibration

cv2 = pytest.importorskip("cv2")
pytest.importorskip("mediapipe")

pytestmark = pytest.mark.vision

OPEN_HAND = REFERENCE_DIR / "hand_open.jpg"
CLOSED_HAND = REFERENCE_DIR / "hand_closed.jpg"


@pytest.fixture(scope="module")
def samples():
    """Landmarks for the open and closed reference photographs."""
    from telerehab.vision.hand_tracker import still_image_tracker

    with still_image_tracker(VisionConfig(min_detection_confidence=0.5)) as tracker:
        return {
            "open": tracker.process(cv2.imread(str(OPEN_HAND))),
            "closed": tracker.process(cv2.imread(str(CLOSED_HAND))),
        }


def test_reference_images_are_present():
    assert OPEN_HAND.exists() and CLOSED_HAND.exists()


def test_a_hand_is_found_in_both_images(samples):
    assert samples["open"].has_hand
    assert samples["closed"].has_hand


def test_twentyone_landmarks(samples):
    assert len(samples["open"].points) == 21


def test_spread_separates_open_from_closed(samples):
    """The premise of Time/Score mode."""
    assert samples["open"].spread > samples["closed"].spread


def test_pinch_separates_open_from_closed(samples):
    """The premise of Open/Close mode."""
    assert samples["open"].pinch > samples["closed"].pinch


def test_the_separation_is_wide_enough_to_calibrate_on(samples):
    """A margin this thin would make the midpoint threshold noise-sensitive."""
    ratio = samples["open"].pinch / samples["closed"].pinch
    assert ratio > 1.25, f"open/closed pinch ratio is only {ratio:.2f}"


def test_calibration_normalises_the_two_photographs_to_the_full_range(samples):
    calibration = RangeCalibration()
    calibration.observe(samples["closed"].spread)
    calibration.observe(samples["open"].spread)

    assert calibration.ready
    assert calibration.normalize(samples["closed"].spread) == pytest.approx(0.0)
    assert calibration.normalize(samples["open"].spread) == pytest.approx(100.0)


def test_two_point_calibration_classifies_the_photographs_correctly(samples):
    calibration = TwoPointCalibration(
        open_sample=samples["open"].pinch,
        closed_sample=samples["closed"].pinch,
    )

    assert calibration.is_open(samples["open"].pinch)
    assert not calibration.is_open(samples["closed"].pinch)


def test_no_hand_in_a_blank_frame():
    import numpy as np

    from telerehab.vision.hand_tracker import still_image_tracker

    with still_image_tracker() as tracker:
        sample = tracker.process(np.zeros((480, 640, 3), dtype=np.uint8))

    assert not sample.has_hand
    assert sample.spread is None
    assert sample.pinch is None
