"""Hand-openness metrics.

These are plain functions over ``(x, y)`` points in MediaPipe's normalised
image space, deliberately kept free of any MediaPipe or OpenCV import. That is
what makes the clinically meaningful part of the vision pipeline unit-testable
without a camera — see ``tests/test_geometry.py``.

Two different metrics are used, because the two exercises ask different
questions of the hand:

``spread_openness``
    How far the fingertips are from the wrist. Continuous and monotonic, so it
    can drive a position. Used by Time/Score mode.

``pinch_openness``
    Thumb-tip to index-tip distance. Cheap and robust for a binary
    open/closed decision. Used by Open/Close mode.
"""
from __future__ import annotations

from math import hypot
from typing import Iterable, Sequence

Point = tuple[float, float]

#: MediaPipe Hands landmark indices.
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_TIP = 12
RING_TIP = 16
PINKY_TIP = 20

FINGERTIPS: tuple[int, ...] = (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)


def distance(a: Point, b: Point) -> float:
    """Euclidean distance between two normalised landmark positions."""
    return hypot(a[0] - b[0], a[1] - b[1])


def spread_openness(points: Sequence[Point]) -> float:
    """Mean wrist-to-fingertip distance, scaled to a convenient 0-100-ish range.

    ``points`` must be the full 21-landmark hand. The result is *not* a
    percentage: its absolute value depends on how far the hand is from the
    camera, which is exactly why every session starts with a calibration pass
    (see :class:`telerehab.vision.calibration.RangeCalibration`).
    """
    if len(points) <= max(FINGERTIPS):
        raise ValueError(f"expected a full hand of landmarks, got {len(points)}")

    wrist = points[WRIST]
    total = sum(distance(points[tip], wrist) for tip in FINGERTIPS)
    return (total / len(FINGERTIPS)) * 100.0


def pinch_openness(points: Sequence[Point]) -> float:
    """Thumb-tip to index-tip distance, in normalised image units."""
    if len(points) <= INDEX_TIP:
        raise ValueError(f"expected a full hand of landmarks, got {len(points)}")

    return distance(points[THUMB_TIP], points[INDEX_TIP])


def moving_average(samples: Iterable[float]) -> float:
    """Mean of ``samples``; 0.0 for an empty sequence."""
    values = list(samples)
    return sum(values) / len(values) if values else 0.0
