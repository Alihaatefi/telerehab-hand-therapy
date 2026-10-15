"""Exporting a patient's history for a clinician.

CSV is the lossless one: every session, every metric, one row each, readable by
any spreadsheet. The PDF is the one that gets printed or attached to a record;
it needs Qt, so it is imported only when asked for.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ..api.models import FIELD_MAP, GameMode, Session
from .series import format_value, metric_series, sessions_in_mode


def csv_header(mode: GameMode) -> list[str]:
    return ["report_id", "date", "mode", *[f.axis_label for f in FIELD_MAP[mode]]]


def csv_row(session: Session) -> list[str]:
    return [
        "" if session.report_id is None else str(session.report_id),
        session.date,
        session.mode.title,
        *[f"{session.metrics[f.name]:g}" for f in session.fields],
    ]


def sessions_to_csv(sessions: Sequence[Session], path: str | Path) -> Path:
    """Write one CSV, with a separate header block per exercise mode.

    The two modes record different metrics, so they cannot share columns without
    one of them being mislabelled; each gets its own header row.
    """
    target = Path(path)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        first = True
        for mode in GameMode:
            subset = sessions_in_mode(sessions, mode)
            if not subset:
                continue
            if not first:
                writer.writerow([])
            first = False
            writer.writerow(csv_header(mode))
            for session in subset:
                writer.writerow(csv_row(session))
    return target


def sessions_to_pdf(
    sessions: Sequence[Session], path: str | Path, *, patient_name: str
) -> Path:  # pragma: no cover - exercised through the UI smoke test
    """Render a one-patient progress report as a PDF."""
    from ..ui.charts import write_report_pdf

    return write_report_pdf(sessions, Path(path), patient_name=patient_name)


def default_filename(patient_id: int, suffix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    return f"telerehab_patient{patient_id}_{stamp}.{suffix.lstrip('.')}"


__all__ = [
    "csv_header",
    "csv_row",
    "default_filename",
    "format_value",
    "metric_series",
    "sessions_to_csv",
    "sessions_to_pdf",
]
