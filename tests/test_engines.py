"""The exercise engines and calibration procedures, played through with a fake
clock and fake camera frames - no camera, no window, no real time.

These rules used to live inside the pygame screens, where nothing could test
them. Moving them into plain classes is what makes a whole session checkable in
milliseconds.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from telerehab.api.models import GameMode
from telerehab.config import TRACK_WIDTH, GameConfig, VisionConfig
from telerehab.games import (
    OpenCloseEngine,
    RangeCalibrationTask,
    TimeScoreEngine,
    TwoPointCalibrationTask,
)
from telerehab.vision.calibration import RangeCalibration, TwoPointCalibration


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass(frozen=True)
class Frame:
    """Anything shaped like a camera frame, as far as the engines are concerned."""

    has_hand: bool = True
    spread: float | None = None
    pinch: float | None = None


NO_HAND = Frame(has_hand=False)


# -- Time / Score ------------------------------------------------------------------------


def time_score(clock: FakeClock, **overrides) -> TimeScoreEngine:
    calibration = RangeCalibration()
    calibration.observe(10.0)
    calibration.observe(50.0)  # so spread 10 -> 0 %, 30 -> 50 %, 50 -> 100 %
    config = GameConfig(**{"exercise_seconds": 60, "gain": 1.0, **overrides})
    return TimeScoreEngine(
        calibration,
        patient_id=7,
        game_config=config,
        vision_config=VisionConfig(),
        clock=clock,
        rng=random.Random(1),
    )


class TestTimeScoreEngine:
    def test_the_butterfly_follows_calibrated_openness(self):
        engine = time_score(FakeClock())
        for _ in range(10):  # let the smoothing window fill
            engine.update(Frame(spread=30.0))
        assert engine.openness == pytest.approx(50.0)
        assert engine.butterfly_x == pytest.approx(TRACK_WIDTH / 2)

    def test_gain_scales_travel_and_is_clamped_to_the_track(self):
        engine = time_score(FakeClock(), gain=2.0)
        for _ in range(10):
            engine.update(Frame(spread=30.0))  # 50 % x gain 2 -> the far end
        assert engine.butterfly_x == pytest.approx(TRACK_WIDTH)

        for _ in range(10):
            engine.update(Frame(spread=50.0))  # 100 % x gain 2 must not overshoot
        assert engine.butterfly_x == pytest.approx(TRACK_WIDTH)

    def test_settling_on_the_flower_scores_after_the_dwell(self):
        clock = FakeClock()
        engine = time_score(clock)
        engine.flower.x = TRACK_WIDTH / 2
        frame = Frame(spread=30.0)  # butterfly at the middle, i.e. on the flower

        assert engine.update(frame) is False  # arrives
        clock.advance(0.3)
        assert engine.update(frame) is False  # not held long enough yet
        clock.advance(0.3)
        assert engine.update(frame) is True  # held for >= 0.5 s: a point
        assert engine.score == 1
        # and the flower has moved off, so the same position no longer scores
        assert abs(engine.flower.x - TRACK_WIDTH / 2) >= engine.config.flower_tolerance_px

    def test_sweeping_past_the_flower_does_not_score(self):
        clock = FakeClock()
        engine = time_score(clock)
        engine.flower.x = TRACK_WIDTH / 2
        for spread in (10.0, 30.0, 50.0):  # passes through the middle, never rests
            engine.update(Frame(spread=spread))
            clock.advance(0.1)
        assert engine.score == 0

    def test_open_close_cycles_count_as_movements(self):
        engine = time_score(FakeClock())
        for spread in (50.0, 10.0, 50.0, 10.0):  # open, close, open, close
            engine.update(Frame(spread=spread))
        assert engine.movements.count == 4

    def test_no_hand_leaves_the_butterfly_where_it_was(self):
        engine = time_score(FakeClock())
        for _ in range(10):
            engine.update(Frame(spread=50.0))
        before = engine.butterfly_x

        engine.update(NO_HAND)
        assert engine.hand_visible is False
        assert engine.butterfly_x == before

    def test_pausing_freezes_the_session_and_the_countdown(self):
        clock = FakeClock()
        engine = time_score(clock)
        assert engine.toggle_pause() is True

        clock.advance(500.0)  # a long pause must cost no exercise time
        assert engine.update(Frame(spread=50.0)) is False
        assert not engine.finished

        assert engine.toggle_pause() is False
        assert engine.timer.remaining == pytest.approx(60.0)

    def test_the_session_ends_when_the_time_is_up(self):
        clock = FakeClock()
        engine = time_score(clock, exercise_seconds=30)
        assert not engine.finished
        clock.advance(31.0)
        assert engine.finished

    def test_result_carries_what_was_played(self):
        engine = time_score(FakeClock(), exercise_seconds=45, gain=1.5)
        session = engine.result()
        assert session.patient_id == 7
        assert session.mode is GameMode.TIME_SCORE
        assert session.metrics["exercise_seconds"] == 45
        assert session.metrics["gain"] == 1.5

    def test_restart_clears_progress(self):
        engine = time_score(FakeClock())
        for spread in (50.0, 10.0):
            engine.update(Frame(spread=spread))
        engine.restart()
        assert engine.movements.count == 0
        assert engine.score == 0
        assert engine.butterfly_x == 0.0


# -- Open / Close ----------------------------------------------------------------------------

OPEN = Frame(pinch=0.40)
CLOSED = Frame(pinch=0.20)  # threshold sits midway, at 0.30


def open_close(clock: FakeClock, **overrides) -> OpenCloseEngine:
    config = GameConfig(**{"open_seconds": 2, "close_seconds": 1, "repetitions": 2, **overrides})
    calibration = TwoPointCalibration(open_sample=0.40, closed_sample=0.20)
    return OpenCloseEngine(calibration, patient_id=3, game_config=config, clock=clock)


def hold(engine: OpenCloseEngine, clock: FakeClock, frame: Frame, seconds: float, step=0.25) -> bool:
    """Feed ``frame`` for ``seconds``; returns whether a hold completed meanwhile."""
    completed = False
    for _ in range(round(seconds / step) + 1):
        completed = engine.update(frame) or completed
        clock.advance(step)
    return completed


class TestOpenCloseEngine:
    def test_the_schedule_alternates_open_then_closed(self):
        engine = open_close(FakeClock())
        assert engine.schedule == [(True, 2.0), (False, 1.0), (True, 2.0), (False, 1.0)]
        assert engine.target_open is True

    def test_holding_the_right_posture_completes_the_hold(self):
        clock = FakeClock()
        engine = open_close(clock)
        assert hold(engine, clock, OPEN, 2.0)
        assert engine.target_open is False  # now asked to close
        assert engine.completed_repetitions == 0  # a repetition is open *and* closed

    def test_the_wrong_posture_does_not_advance_the_timer(self):
        clock = FakeClock()
        engine = open_close(clock)
        assert not hold(engine, clock, CLOSED, 10.0)  # asked for open, giving closed
        assert engine.index == 0
        assert engine.timer.progress == 0.0

    def test_a_wobble_pauses_the_hold_instead_of_erasing_it(self):
        clock = FakeClock()
        engine = open_close(clock)
        hold(engine, clock, OPEN, 1.0)
        progress = engine.timer.progress
        assert 0 < progress < 1

        hold(engine, clock, CLOSED, 3.0)  # a long wobble
        assert engine.timer.progress == pytest.approx(progress)

        assert hold(engine, clock, OPEN, 1.5)  # the remaining second completes it

    def test_a_full_session_completes_every_repetition(self):
        clock = FakeClock()
        engine = open_close(clock)
        for frame, seconds in ((OPEN, 2.0), (CLOSED, 1.0), (OPEN, 2.0), (CLOSED, 1.0)):
            hold(engine, clock, frame, seconds)
        assert engine.finished
        assert engine.completed_repetitions == 2
        assert engine.result().metrics["completed_repetitions"] == 2

    def test_stopping_early_records_only_what_was_finished(self):
        clock = FakeClock()
        engine = open_close(clock)
        hold(engine, clock, OPEN, 2.0)
        hold(engine, clock, CLOSED, 1.0)  # repetition 1 done
        hold(engine, clock, OPEN, 1.0)  # repetition 2 only half under way

        assert not engine.finished
        session = engine.result()
        assert session.metrics["completed_repetitions"] == 1
        assert session.metrics["repetitions"] == 2

    def test_no_hand_is_not_a_correct_posture(self):
        clock = FakeClock()
        engine = open_close(clock)
        engine.update(NO_HAND)
        assert engine.hand_open is None
        assert engine.posture_correct is False

    def test_pausing_keeps_what_has_been_held(self):
        clock = FakeClock()
        engine = open_close(clock)
        hold(engine, clock, OPEN, 1.0)
        progress = engine.timer.progress

        assert engine.toggle_pause() is True
        hold(engine, clock, OPEN, 30.0)  # paused: this must not count
        assert engine.timer.progress == pytest.approx(progress)

        engine.toggle_pause()
        hold(engine, clock, OPEN, 1.5)
        assert engine.target_open is False

    def test_repetition_never_reads_past_the_last(self):
        clock = FakeClock()
        engine = open_close(clock, repetitions=1)
        for frame, seconds in ((OPEN, 2.0), (CLOSED, 1.0)):
            hold(engine, clock, frame, seconds)
        assert engine.finished
        assert engine.repetition == 1  # not "2 / 1"
        assert engine.target_open in (True, False)  # still readable once finished


# -- calibration procedures ---------------------------------------------------------------------


class TestRangeCalibrationTask:
    def test_learns_the_range_over_the_requested_time(self):
        task = RangeCalibrationTask(seconds=5)
        for i in range(40):  # 4 s so far
            task.feed(Frame(spread=10.0 + (i % 2) * 40.0), dt=0.1)
        assert not task.done
        for i in range(20):  # 6 s in total: past the 5 s asked for
            task.feed(Frame(spread=10.0 + (i % 2) * 40.0), dt=0.1)

        assert task.done and task.usable
        assert task.calibration.minimum == 10.0 and task.calibration.maximum == 50.0

    def test_time_only_counts_while_a_hand_is_visible(self):
        task = RangeCalibrationTask(seconds=2)
        for _ in range(100):
            task.feed(NO_HAND, dt=0.1)
        assert task.elapsed == 0.0 and not task.done

    def test_a_hand_that_never_moves_is_not_usable(self):
        task = RangeCalibrationTask(seconds=1)
        for _ in range(20):
            task.feed(Frame(spread=30.0), dt=0.1)
        assert task.done
        assert not task.usable

    def test_progress_and_remaining_agree(self):
        task = RangeCalibrationTask(seconds=4)
        task.feed(Frame(spread=10.0), dt=1.0)
        assert task.progress == pytest.approx(0.25)
        assert task.remaining == pytest.approx(3.0)


class TestTwoPointCalibrationTask:
    def test_captures_open_then_closed_then_confirms(self):
        task = TwoPointCalibrationTask()
        assert task.stage == "open"
        assert task.capture(Frame(pinch=0.40))
        assert task.stage == "closed"
        assert task.capture(Frame(pinch=0.20))
        assert task.stage == "confirm"
        assert task.confirm()
        assert task.calibration.threshold == pytest.approx(0.30)

    def test_no_hand_means_no_capture_and_a_warning(self):
        task = TwoPointCalibrationTask()
        assert not task.capture(NO_HAND)
        assert task.stage == "open"
        assert "No hand detected" in task.warning

        assert not task.capture(None)  # no frame has arrived at all

    def test_identical_postures_are_refused(self):
        task = TwoPointCalibrationTask()
        task.capture(Frame(pinch=0.30))
        task.capture(Frame(pinch=0.30))
        assert not task.confirm()
        assert "identical" in task.warning

    def test_redo_starts_over(self):
        task = TwoPointCalibrationTask()
        task.capture(Frame(pinch=0.40))
        task.reset()
        assert task.stage == "open"
        assert task.calibration.open_sample is None

    def test_confirm_is_only_possible_at_the_end(self):
        assert not TwoPointCalibrationTask().confirm()
