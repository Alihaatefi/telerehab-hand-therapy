"""The simulated camera.

It feeds the *real* MediaPipe pipeline with the two reference photographs and
morphs between the measured landmarks. These tests check that what it produces
is a valid camera for everything downstream: a continuous signal between the two
measured extremes, with the same shape a physical camera would give.
"""
from __future__ import annotations

import pytest

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")

import itertools

from telerehab.config import VisionConfig
from telerehab.vision.calibration import RangeCalibration, TwoPointCalibration
from telerehab.vision.demo import FRAME_HEIGHT, FRAME_WIDTH, DemoTracker

pytestmark = pytest.mark.vision


@pytest.fixture(scope="module")
def tracker():
    with DemoTracker(VisionConfig(), realtime=False) as demo:
        yield demo


def test_a_sample_looks_like_a_camera_frame(tracker):
    tracker.set_openness(0.5)
    sample = tracker.read()

    assert sample.frame.shape == (FRAME_HEIGHT, FRAME_WIDTH, 3)
    assert sample.has_hand
    assert len(sample.points) == 21
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in sample.points)


def test_openness_moves_both_metrics_monotonically(tracker):
    spreads, pinches = [], []
    for openness in (0.0, 0.25, 0.5, 0.75, 1.0):
        tracker.set_openness(openness)
        sample = tracker.read()
        spreads.append(sample.spread)
        pinches.append(sample.pinch)

    assert spreads == sorted(spreads) and spreads[0] < spreads[-1]
    assert pinches == sorted(pinches) and pinches[0] < pinches[-1]


def test_the_thumb_index_distance_never_dips_below_the_closed_pose(tracker):
    """Open/Close mode classifies on this distance.

    Blending the two photographs naively carries the thumb tip across the index
    tip, so the distance dips below *both* ends - and a patient who calibrated
    "closed" in the dip would later see a genuinely closed hand read as open.
    """
    tracker.set_openness(0.0)
    closed = tracker.read().pinch
    tracker.set_openness(1.0)
    opened = tracker.read().pinch

    steps = []
    for i in range(41):
        tracker.set_openness(i / 40)
        steps.append(tracker.read().pinch)

    assert min(steps) >= closed - 1e-9
    assert max(steps) <= opened + 1e-9
    # and it moves smoothly: no jumps between neighbouring poses
    assert max(abs(b - a) for a, b in itertools.pairwise(steps)) < 0.02


def test_the_extremes_are_the_two_measured_photographs(tracker):
    tracker.set_openness(0.0)
    closed = tracker.read()
    tracker.set_openness(1.0)
    opened = tracker.read()

    assert opened.pinch / closed.pinch > 1.25  # the premise the whole app rests on


def test_it_can_drive_the_real_calibrators(tracker):
    """Calibrate on the two extremes; the middle pose must land in between."""
    tracker.set_openness(0.0)
    closed = tracker.read()
    tracker.set_openness(1.0)
    opened = tracker.read()

    range_cal = RangeCalibration()
    range_cal.observe(closed.spread)
    range_cal.observe(opened.spread)
    tracker.set_openness(0.5)
    assert 25.0 < range_cal.normalize(tracker.read().spread) < 75.0

    two_point = TwoPointCalibration(open_sample=opened.pinch, closed_sample=closed.pinch)
    tracker.set_openness(0.95)
    assert two_point.is_open(tracker.read().pinch)
    tracker.set_openness(0.05)
    assert not two_point.is_open(tracker.read().pinch)


def test_hiding_the_hand_gives_a_frame_with_no_landmarks(tracker):
    tracker.hide_hand(True)
    try:
        sample = tracker.read()
    finally:
        tracker.hide_hand(False)

    assert not sample.has_hand
    assert sample.spread is None and sample.pinch is None
    assert sample.frame.shape == (FRAME_HEIGHT, FRAME_WIDTH, 3)


def test_left_alone_it_cycles_and_pauses_at_both_extremes():
    now = [0.0]
    demo = DemoTracker(VisionConfig(), realtime=False, clock=lambda: now[0], period=6.0).open()
    try:
        seen = []
        for _ in range(120):
            seen.append(demo.openness)
            now[0] += 0.05
    finally:
        demo.close()

    assert min(seen) == 0.0 and max(seen) == 1.0
    # Flat spells at each extreme: holds and dwell times must be achievable.
    assert sum(1 for v in seen if v == 1.0) >= 5
    assert sum(1 for v in seen if v == 0.0) >= 5


def test_openness_is_clamped():
    demo = DemoTracker(VisionConfig(), realtime=False)
    demo.set_openness(7.0)
    assert demo.openness == 1.0
    demo.set_openness(-3.0)
    assert demo.openness == 0.0
    demo.set_openness(None)  # back to animating
    assert 0.0 <= demo.openness <= 1.0
