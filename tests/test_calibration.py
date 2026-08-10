"""Per-patient calibration and movement counting."""
from __future__ import annotations

import pytest

from telerehab.vision.calibration import (
    CalibrationError,
    MovementCounter,
    RangeCalibration,
    TwoPointCalibration,
)


class TestRangeCalibration:
    def test_is_not_ready_before_any_sample(self):
        assert not RangeCalibration().ready

    def test_normalize_before_calibration_is_an_error_not_a_nan(self):
        with pytest.raises(CalibrationError, match="calibration incomplete"):
            RangeCalibration().normalize(42.0)

    def test_maps_calibrated_range_onto_0_100(self):
        calib = RangeCalibration()
        for sample in (20.0, 60.0, 35.0):
            calib.observe(sample)

        assert calib.normalize(20.0) == pytest.approx(0.0)
        assert calib.normalize(60.0) == pytest.approx(100.0)
        assert calib.normalize(40.0) == pytest.approx(50.0)

    def test_clamps_outside_the_calibrated_range(self):
        """A patient exceeding their calibration pegs the meter, not overshoots."""
        calib = RangeCalibration()
        calib.observe(20.0)
        calib.observe(60.0)

        assert calib.normalize(80.0) == 100.0
        assert calib.normalize(0.0) == 0.0

    def test_degenerate_range_is_refused(self):
        """A hand that never moved would otherwise divide by ~zero."""
        calib = RangeCalibration()
        calib.observe(30.0)
        calib.observe(30.0)

        assert not calib.ready
        with pytest.raises(CalibrationError):
            calib.normalize(30.0)

    def test_span_reports_the_patients_usable_range(self):
        calib = RangeCalibration()
        calib.observe(12.0)
        calib.observe(31.0)
        assert calib.span == pytest.approx(19.0)

    def test_reset_clears_history(self):
        calib = RangeCalibration()
        calib.observe(10.0)
        calib.observe(90.0)
        calib.reset()
        assert not calib.ready


class TestTwoPointCalibration:
    def test_threshold_sits_midway(self):
        calib = TwoPointCalibration(open_sample=0.40, closed_sample=0.10)
        assert calib.threshold == pytest.approx(0.25)

    def test_classifies_either_side_of_the_threshold(self):
        calib = TwoPointCalibration(open_sample=0.40, closed_sample=0.10)
        assert calib.is_open(0.35)
        assert not calib.is_open(0.15)

    def test_requires_both_samples(self):
        calib = TwoPointCalibration(open_sample=0.4)
        assert not calib.ready
        with pytest.raises(CalibrationError, match="open and a closed"):
            calib.is_open(0.3)


class TestMovementCounter:
    def test_counts_each_transition_in_both_directions(self):
        counter = MovementCounter()
        counter.update(90.0)  # open
        counter.update(10.0)  # closed
        counter.update(90.0)  # open
        assert counter.count == 3

    def test_hysteresis_ignores_jitter_in_the_dead_band(self):
        """The whole point: a hand hovering mid-range must not rack up movements."""
        counter = MovementCounter(open_threshold=70.0, close_threshold=30.0)
        counter.update(90.0)
        assert counter.count == 1

        for jitter in (65.0, 55.0, 45.0, 60.0, 68.0, 35.0, 50.0):
            counter.update(jitter)

        assert counter.count == 1

    def test_repeated_samples_past_a_threshold_count_once(self):
        counter = MovementCounter()
        for _ in range(20):
            counter.update(95.0)
        assert counter.count == 1

    def test_thresholds_must_not_be_inverted(self):
        with pytest.raises(ValueError, match="below open_threshold"):
            MovementCounter(open_threshold=30.0, close_threshold=70.0)

    def test_reset(self):
        counter = MovementCounter()
        counter.update(90.0)
        counter.reset()
        assert counter.count == 0
        assert not counter.hand_open
