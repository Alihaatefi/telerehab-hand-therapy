"""Report data, as it reaches a chart or a table.

What is asserted here is mostly that a label always travels with the value it
describes. A mislabelled chart renders perfectly and reads as authoritative, so
nothing downstream would catch the mistake.
"""
from __future__ import annotations

import pytest

from telerehab.api.models import FIELD_MAP, GameMode, Session
from telerehab.reports import (
    format_value,
    metric_series,
    sessions_in_mode,
    summarize,
)


def time_score(score: int, day: int = 1) -> Session:
    return Session(
        patient_id=1,
        mode=GameMode.TIME_SCORE,
        metrics={
            "score": float(score), "gain": 1.0,
            "exercise_seconds": 60.0, "movements": float(score * 2),
        },
        report_id=score,
        timestamp=f"2024-09-{day:02d}T10:00:00.000Z",
    )


def open_close(done: int = 3, day: int = 1) -> Session:
    return Session(
        patient_id=1,
        mode=GameMode.OPEN_CLOSE,
        metrics={
            "open_seconds": 5.0, "close_seconds": 5.0,
            "repetitions": 10.0, "completed_repetitions": float(done),
        },
        report_id=100 + done,
        timestamp=f"2024-09-{day:02d}T10:00:00.000Z",
    )


class TestSessionSeries:
    def test_labels_come_from_the_shared_field_map(self):
        labels, values = time_score(12).chart_series()
        assert labels[0] == "Score" and values[0] == 12.0

        oc_labels, oc_values = Session.open_close(
            1, open_seconds=4, close_seconds=6, repetitions=3, completed_repetitions=2,
        ).chart_series()
        assert oc_labels[0] == "Open Time (s)" and oc_values[0] == 4.0

    def test_every_metric_has_a_unique_label_within_its_mode(self):
        for mode, fields in FIELD_MAP.items():
            labels = [f.axis_label for f in fields]
            assert len(labels) == len(set(labels)), mode


class TestMetricSeries:
    def test_plots_one_metric_across_sessions_oldest_first(self):
        sessions = [time_score(s, day=i + 1) for i, s in enumerate([4, 7, 9, 14])]
        series = metric_series(sessions, "score")

        assert series.values == (4.0, 7.0, 9.0, 14.0)
        assert series.labels == ("2024-09-01", "2024-09-02", "2024-09-03", "2024-09-04")
        assert series.metric.label == "Score"

    def test_headline_numbers(self):
        series = metric_series([time_score(s, day=i + 1) for i, s in enumerate([4, 15, 9])], "score")
        assert series.latest == 9.0
        assert series.best == 15.0
        assert series.change == 5.0  # latest minus first

    def test_a_single_session_has_no_change(self):
        assert metric_series([time_score(5)], "score").change is None

    def test_the_title_carries_the_unit(self):
        series = metric_series([time_score(5)], "exercise_seconds")
        assert series.title == "Exercise Time (s)"

    def test_rejects_an_empty_series(self):
        with pytest.raises(ValueError, match="no sessions"):
            metric_series([], "score")

    def test_refuses_to_mix_modes(self):
        """Plotting a score and a repetition count on one axis is meaningless."""
        with pytest.raises(ValueError, match="different exercise modes"):
            metric_series([time_score(5), open_close()], "score")

    def test_unknown_metric_names_the_valid_ones(self):
        with pytest.raises(ValueError, match="expected one of"):
            metric_series([time_score(5)], "heart_rate")

    def test_a_metric_of_the_other_mode_is_unknown(self):
        with pytest.raises(ValueError, match="no metric"):
            metric_series([time_score(5)], "completed_repetitions")

    def test_undated_sessions_fall_back_to_their_report_number(self):
        undated = Session(
            patient_id=1, mode=GameMode.TIME_SCORE,
            metrics=dict(time_score(3).metrics), report_id=77,
        )
        assert metric_series([undated], "score").labels == ("#77",)


class TestFormatting:
    def test_whole_numbers_have_no_decimal(self):
        score = FIELD_MAP[GameMode.TIME_SCORE][0]
        assert format_value(score, 12.0) == "12"

    def test_units_follow_the_number(self):
        seconds = next(f for f in FIELD_MAP[GameMode.TIME_SCORE] if f.unit == "s")
        assert format_value(seconds, 60.0) == "60 s"

    def test_fractions_are_kept(self):
        gain = next(f for f in FIELD_MAP[GameMode.TIME_SCORE] if f.name == "gain")
        assert format_value(gain, 1.5) == "1.5"


class TestSummary:
    def test_counts_and_date_range(self):
        sessions = [time_score(5, day=3), open_close(4, day=1), time_score(6, day=9)]
        summary = summarize(sessions)

        assert summary.total_sessions == 3
        assert summary.by_mode[GameMode.TIME_SCORE] == 2
        assert summary.by_mode[GameMode.OPEN_CLOSE] == 1
        assert summary.first_date == "2024-09-01"
        assert summary.last_date == "2024-09-09"

    def test_an_empty_history_is_summarised_not_an_error(self):
        summary = summarize([])
        assert summary.total_sessions == 0
        assert summary.first_date == "" and summary.last_date == ""

    def test_filtering_by_mode(self):
        sessions = [time_score(5), open_close(4), time_score(6)]
        assert len(sessions_in_mode(sessions, GameMode.OPEN_CLOSE)) == 1
        assert len(sessions_in_mode(sessions, GameMode.TIME_SCORE)) == 2
