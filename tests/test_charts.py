"""Chart rendering.

The charts are the clinician-facing output, so what is asserted here is mostly
that a label always travels with the value it describes. A mislabelled chart
renders perfectly and reads as authoritative, so nothing downstream would catch
the mistake.
"""
from __future__ import annotations

import pytest

from telerehab.api.models import GameMode, Session
from telerehab.reports.charts import progress_chart, session_chart

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


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


class TestSessionChart:
    def test_renders_a_png(self):
        png = session_chart(time_score(12))
        assert png.startswith(PNG_MAGIC)
        assert len(png) > 5_000

    def test_writes_nothing_to_disk(self, tmp_path, monkeypatch):
        """Rendering must not touch the filesystem, on any path."""
        monkeypatch.chdir(tmp_path)
        session_chart(time_score(12))
        assert list(tmp_path.iterdir()) == []

    def test_both_modes_render(self):
        open_close = Session.open_close(
            1, open_seconds=5, close_seconds=5,
            repetitions=10, completed_repetitions=7,
        )
        assert session_chart(open_close).startswith(PNG_MAGIC)

    def test_labels_come_from_the_shared_field_map(self):
        labels, values = time_score(12).chart_series()
        assert labels[0] == "Score" and values[0] == 12.0

        open_close = Session.open_close(
            1, open_seconds=4, close_seconds=6,
            repetitions=3, completed_repetitions=2,
        )
        oc_labels, oc_values = open_close.chart_series()
        assert oc_labels[0] == "Open Time (s)" and oc_values[0] == 4.0


class TestProgressChart:
    def test_plots_a_metric_across_sessions(self):
        sessions = [time_score(s, day=i + 1) for i, s in enumerate([4, 7, 9, 14])]
        assert progress_chart(sessions, "score").startswith(PNG_MAGIC)

    def test_rejects_an_empty_series(self):
        with pytest.raises(ValueError, match="no sessions"):
            progress_chart([], "score")

    def test_refuses_to_mix_modes(self):
        """Plotting a score and a repetition count on one axis is meaningless."""
        mixed = [
            time_score(5),
            Session.open_close(1, open_seconds=5, close_seconds=5,
                               repetitions=3, completed_repetitions=3),
        ]
        with pytest.raises(ValueError, match="different exercise modes"):
            progress_chart(mixed, "score")

    def test_unknown_metric_names_the_valid_ones(self):
        with pytest.raises(ValueError, match="expected one of"):
            progress_chart([time_score(5)], "heart_rate")
