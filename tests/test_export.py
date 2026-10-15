"""CSV export: every session, every metric, correctly labelled.

The two modes record different metrics, so they cannot share columns without one
of them being mislabelled. Each gets its own header row.
"""
from __future__ import annotations

import csv

from telerehab.api.models import FIELD_MAP, GameMode, Session
from telerehab.reports import default_filename, sessions_to_csv


def ts(score: int, day: int, report_id: int) -> Session:
    return Session(
        patient_id=4,
        mode=GameMode.TIME_SCORE,
        metrics={"score": float(score), "gain": 1.5, "exercise_seconds": 60.0, "movements": 22.0},
        report_id=report_id,
        timestamp=f"2026-09-{day:02d}T10:00:00.000Z",
    )


def oc(done: int, day: int, report_id: int) -> Session:
    return Session(
        patient_id=4,
        mode=GameMode.OPEN_CLOSE,
        metrics={
            "open_seconds": 5.0, "close_seconds": 5.0,
            "repetitions": 10.0, "completed_repetitions": float(done),
        },
        report_id=report_id,
        timestamp=f"2026-09-{day:02d}T10:00:00.000Z",
    )


def read(path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def test_each_mode_gets_its_own_header_with_the_shared_labels(tmp_path):
    path = sessions_to_csv([ts(5, 1, 10), oc(7, 2, 11), ts(9, 3, 12)], tmp_path / "out.csv")
    rows = read(path)

    ts_header = ["report_id", "date", "mode", *[f.axis_label for f in FIELD_MAP[GameMode.TIME_SCORE]]]
    oc_header = ["report_id", "date", "mode", *[f.axis_label for f in FIELD_MAP[GameMode.OPEN_CLOSE]]]
    assert rows[0] == ts_header
    assert oc_header in rows
    assert ts_header != oc_header


def test_values_travel_with_their_own_column(tmp_path):
    rows = read(sessions_to_csv([ts(5, 1, 10)], tmp_path / "out.csv"))
    header, row = rows[0], rows[1]
    cells = dict(zip(header, row, strict=False))

    assert cells["Score"] == "5"
    assert cells["Gain"] == "1.5"
    assert cells["Exercise Time (s)"] == "60"
    assert cells["report_id"] == "10"
    assert cells["date"] == "2026-09-01"
    assert cells["mode"] == "Time / Score"


def test_sessions_keep_the_order_they_were_given(tmp_path):
    rows = read(sessions_to_csv([ts(1, 1, 1), ts(2, 2, 2), ts(3, 3, 3)], tmp_path / "out.csv"))
    assert [r[0] for r in rows[1:]] == ["1", "2", "3"]


def test_a_blank_row_separates_the_two_modes(tmp_path):
    rows = read(sessions_to_csv([ts(1, 1, 1), oc(2, 2, 2)], tmp_path / "out.csv"))
    assert [] in rows


def test_a_single_mode_has_no_stray_blank_rows(tmp_path):
    rows = read(sessions_to_csv([ts(1, 1, 1), ts(2, 2, 2)], tmp_path / "out.csv"))
    assert [] not in rows
    assert len(rows) == 3


def test_a_session_without_a_report_id_exports_an_empty_cell(tmp_path):
    unsaved = Session.time_score(4, score=3, gain=1.0, exercise_seconds=30, movements=2)
    rows = read(sessions_to_csv([unsaved], tmp_path / "out.csv"))
    assert rows[1][0] == ""


def test_default_filename_names_the_patient_and_the_format():
    name = default_filename(12, "pdf")
    assert name.startswith("telerehab_patient12_") and name.endswith(".pdf")
    assert default_filename(12, ".csv").endswith(".csv")
