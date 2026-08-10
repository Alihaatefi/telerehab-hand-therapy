"""Exercise rules, driven by a fake clock so the tests run instantly."""
from __future__ import annotations

import random

import pytest

from telerehab.games.scoring import (
    ButterflySmoother,
    CountdownTimer,
    FlowerTarget,
    HoldTimer,
    butterfly_position,
)


class FakeClock:
    """A clock the test advances by hand."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestButterflyPosition:
    def test_maps_openness_across_the_track(self):
        assert butterfly_position(0.0, 1.0, 700) == pytest.approx(0.0)
        assert butterfly_position(50.0, 1.0, 700) == pytest.approx(350.0)
        assert butterfly_position(100.0, 1.0, 700) == pytest.approx(700.0)

    def test_gain_amplifies_limited_range(self):
        """A patient reaching only 50% openness still crosses the whole track."""
        assert butterfly_position(50.0, 2.0, 700) == pytest.approx(700.0)

    def test_high_gain_cannot_push_off_screen(self):
        assert butterfly_position(100.0, 4.0, 700) == 700.0

    def test_never_negative(self):
        assert butterfly_position(-10.0, 1.0, 700) == 0.0


class TestButterflySmoother:
    def test_averages_over_the_window(self):
        smoother = ButterflySmoother(window=3)
        smoother.push(0.0)
        smoother.push(30.0)
        assert smoother.push(60.0) == pytest.approx(30.0)

    def test_window_slides(self):
        smoother = ButterflySmoother(window=2)
        smoother.push(0.0)
        smoother.push(100.0)
        assert smoother.push(100.0) == pytest.approx(100.0)

    def test_damps_a_single_frame_spike(self):
        smoother = ButterflySmoother(window=5)
        for _ in range(5):
            smoother.push(100.0)
        # One dropped frame reads as 0 openness; the butterfly must barely move.
        assert smoother.push(0.0) == pytest.approx(80.0)

    def test_empty_smoother_is_zero(self):
        assert ButterflySmoother().value == 0.0

    def test_window_must_be_positive(self):
        with pytest.raises(ValueError):
            ButterflySmoother(window=0)


class TestFlowerTarget:
    def make(self, clock, **kwargs):
        params = dict(
            min_x=50, max_x=750, tolerance_px=50,
            dwell_seconds=0.5, clock=clock, rng=random.Random(1),
        )
        params.update(kwargs)
        return FlowerTarget(**params)

    def test_no_score_for_sweeping_past(self):
        """Passing over the flower must not score - the position must be held."""
        clock = FakeClock()
        flower = self.make(clock)

        assert not flower.update(flower.x)
        clock.advance(0.2)
        assert not flower.update(flower.x)
        clock.advance(0.2)
        assert not flower.update(flower.x + 500)  # swept away
        assert flower.score == 0

    def test_scores_after_the_dwell_time(self):
        clock = FakeClock()
        flower = self.make(clock)
        target = flower.x

        assert not flower.update(target)
        clock.advance(0.6)
        assert flower.update(target)
        assert flower.score == 1

    def test_leaving_resets_the_dwell_timer(self):
        clock = FakeClock()
        flower = self.make(clock)
        target = flower.x

        flower.update(target)
        clock.advance(0.4)
        flower.update(target + 400)   # left the flower
        clock.advance(0.4)
        assert not flower.update(target)  # timer restarted, only 0.0s held
        assert flower.score == 0

    def test_flower_moves_after_scoring(self):
        clock = FakeClock()
        flower = self.make(clock)
        first = flower.x

        flower.update(first)
        clock.advance(0.6)
        flower.update(first)

        assert abs(flower.x - first) >= flower.tolerance_px

    def test_hold_progress_tracks_the_dwell(self):
        clock = FakeClock()
        flower = self.make(clock)

        assert flower.hold_progress() == 0.0
        flower.update(flower.x)
        clock.advance(0.25)
        assert flower.hold_progress() == pytest.approx(0.5)

    def test_tolerance_defines_the_target_width(self):
        clock = FakeClock()
        flower = self.make(clock, tolerance_px=50)

        flower.update(flower.x + 49)
        clock.advance(0.6)
        assert flower.update(flower.x + 49)

    def test_rejects_an_inverted_range(self):
        with pytest.raises(ValueError):
            FlowerTarget(min_x=700, max_x=100, tolerance_px=50,
                         dwell_seconds=0.5, clock=FakeClock())


class TestHoldTimer:
    def test_accumulates_only_correct_posture(self):
        clock = FakeClock()
        timer = HoldTimer(duration=5.0, clock=clock)

        timer.update(True)
        clock.advance(2.0)
        timer.update(True)
        assert timer.elapsed == pytest.approx(2.0)

        clock.advance(3.0)
        timer.update(False)          # wrong posture: this span does not count
        assert timer.elapsed == pytest.approx(2.0)

    def test_a_brief_slip_pauses_rather_than_erases_progress(self):
        """A momentary wobble must not erase an accumulated hold."""
        clock = FakeClock()
        timer = HoldTimer(duration=5.0, clock=clock)

        timer.update(True)
        clock.advance(4.0)
        timer.update(True)
        assert timer.elapsed == pytest.approx(4.0)

        timer.update(False)          # wobble
        clock.advance(1.0)
        timer.update(True)           # recovered
        clock.advance(1.0)
        timer.update(True)

        assert timer.elapsed == pytest.approx(5.0)
        assert timer.done

    def test_progress_and_remaining(self):
        clock = FakeClock()
        timer = HoldTimer(duration=4.0, clock=clock)

        timer.update(True)
        clock.advance(1.0)
        timer.update(True)

        assert timer.progress == pytest.approx(0.25)
        assert timer.remaining == pytest.approx(3.0)

    def test_elapsed_never_exceeds_duration(self):
        clock = FakeClock()
        timer = HoldTimer(duration=2.0, clock=clock)

        timer.update(True)
        clock.advance(10.0)
        timer.update(True)

        assert timer.elapsed == pytest.approx(2.0)
        assert timer.remaining == 0.0

    def test_duration_must_be_positive(self):
        with pytest.raises(ValueError):
            HoldTimer(duration=0.0, clock=FakeClock())


class TestCountdownTimer:
    def test_counts_down(self):
        clock = FakeClock()
        timer = CountdownTimer(duration=60.0, clock=clock)

        clock.advance(20.0)
        assert timer.remaining == pytest.approx(40.0)
        assert timer.progress == pytest.approx(40 / 60)

    def test_pause_freezes_the_clock(self):
        clock = FakeClock()
        timer = CountdownTimer(duration=60.0, clock=clock)

        clock.advance(10.0)
        timer.pause()
        clock.advance(30.0)          # 30s spent in the settings dialog
        assert timer.remaining == pytest.approx(50.0)

        timer.resume()
        clock.advance(10.0)
        assert timer.remaining == pytest.approx(40.0)

    def test_survives_repeated_pauses(self):
        """Repeated pauses must not quietly consume exercise time."""
        clock = FakeClock()
        timer = CountdownTimer(duration=60.0, clock=clock)

        for _ in range(3):
            clock.advance(5.0)
            timer.pause()
            clock.advance(100.0)
            timer.resume()

        assert timer.remaining == pytest.approx(45.0)

    def test_double_pause_is_idempotent(self):
        clock = FakeClock()
        timer = CountdownTimer(duration=60.0, clock=clock)

        timer.pause()
        clock.advance(5.0)
        timer.pause()
        clock.advance(5.0)
        timer.resume()

        assert timer.remaining == pytest.approx(60.0)

    def test_expires_and_clamps_at_zero(self):
        clock = FakeClock()
        timer = CountdownTimer(duration=5.0, clock=clock)

        clock.advance(30.0)
        assert timer.expired
        assert timer.remaining == 0.0
        assert timer.progress == 0.0

    def test_restart(self):
        clock = FakeClock()
        timer = CountdownTimer(duration=5.0, clock=clock)

        clock.advance(30.0)
        timer.restart(duration=10.0)
        assert timer.remaining == pytest.approx(10.0)
        assert not timer.expired
