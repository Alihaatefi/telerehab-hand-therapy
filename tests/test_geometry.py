"""Openness metrics over synthetic hands."""
from __future__ import annotations

import math

import pytest

from telerehab.vision.geometry import (
    FINGERTIPS,
    INDEX_TIP,
    THUMB_TIP,
    WRIST,
    distance,
    moving_average,
    pinch_openness,
    spread_openness,
)


def make_hand(fingertip_radius: float, pinch_gap: float = 0.1) -> list[tuple[float, float]]:
    """A 21-landmark hand with fingertips a fixed distance from the wrist."""
    points = [(0.5, 0.5)] * 21
    for tip in FINGERTIPS:
        points[tip] = (0.5, 0.5 - fingertip_radius)
    points[THUMB_TIP] = (0.5 - pinch_gap / 2, 0.5 - fingertip_radius)
    points[INDEX_TIP] = (0.5 + pinch_gap / 2, 0.5 - fingertip_radius)
    return points


def test_distance_is_euclidean():
    assert distance((0.0, 0.0), (3.0, 4.0)) == pytest.approx(5.0)


def test_spread_openness_grows_with_extension():
    closed = spread_openness(make_hand(0.05))
    open_ = spread_openness(make_hand(0.30))
    assert open_ > closed


def test_spread_openness_matches_mean_fingertip_distance():
    # Thumb and index are offset sideways by pinch_gap/2, the other three are
    # directly above the wrist, so the mean is not simply the radius.
    hand = make_hand(0.2, pinch_gap=0.0)
    assert spread_openness(hand) == pytest.approx(0.2 * 100.0)


def test_spread_openness_is_scale_dependent():
    """The metric scales with apparent hand size - which is why we calibrate.

    The same gesture at half the distance from the camera reads as twice the
    openness, so a fixed threshold could never work across patients or setups.
    """
    near = spread_openness(make_hand(0.4, pinch_gap=0.2))
    far = spread_openness(make_hand(0.2, pinch_gap=0.1))
    assert near == pytest.approx(2 * far, rel=1e-6)


def test_pinch_openness_measures_thumb_to_index():
    hand = make_hand(0.2, pinch_gap=0.15)
    assert pinch_openness(hand) == pytest.approx(0.15)


def test_pinch_openness_ignores_other_fingers():
    a = make_hand(0.1, pinch_gap=0.2)
    b = make_hand(0.4, pinch_gap=0.2)
    assert pinch_openness(a) == pytest.approx(pinch_openness(b))


@pytest.mark.parametrize("metric", [spread_openness, pinch_openness])
def test_incomplete_hand_is_rejected(metric):
    with pytest.raises(ValueError, match="full hand"):
        metric([(0.0, 0.0)] * 3)


def test_moving_average_of_empty_is_zero():
    assert moving_average([]) == 0.0


def test_moving_average():
    assert moving_average([1.0, 2.0, 6.0]) == pytest.approx(3.0)


def test_landmark_indices_match_mediapipe():
    """Guards the constants against a silent renumbering upstream."""
    assert (WRIST, THUMB_TIP, INDEX_TIP) == (0, 4, 8)
    assert FINGERTIPS == (4, 8, 12, 16, 20)
