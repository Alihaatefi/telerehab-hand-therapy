"""Report data, prepared for display — with no rendering and no I/O.

Labels, units and values always travel together, taken from the single
:data:`telerehab.api.models.FIELD_MAP` table. A mislabelled chart renders
exactly as convincingly as a correct one, so nothing downstream would catch a
label that had drifted from its value: this module is where that is prevented.

Metrics of different kinds (a score, a duration, a repetition count) are never
put on one axis. Each metric is its own series.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..api.models import FIELD_MAP, GameMode, MetricField, Session


@dataclass(frozen=True)
class Series:
    """One metric across a patient's sessions in one mode, oldest first."""

    mode: GameMode
    metric: MetricField
    labels: tuple[str, ...]
    values: tuple[float, ...]
    sessions: tuple[Session, ...]

    @property
    def latest(self) -> float:
        return self.values[-1]

    @property
    def best(self) -> float:
        return max(self.values)

    @property
    def change(self) -> float | None:
        """Latest minus first, or ``None`` with fewer than two sessions."""
        return self.values[-1] - self.values[0] if len(self.values) > 1 else None

    @property
    def title(self) -> str:
        return self.metric.axis_label


def metric_series(sessions: Sequence[Session], metric: str) -> Series:
    """One metric plotted across sessions from a single mode.

    A single session says little; the trend across sessions is the clinical
    signal. Requires every session to be from the same mode.
    """
    if not sessions:
        raise ValueError("no sessions to plot")

    modes = {session.mode for session in sessions}
    if len(modes) > 1:
        raise ValueError("cannot plot a trend across different exercise modes")

    mode = modes.pop()
    field = next((f for f in FIELD_MAP[mode] if f.name == metric), None)
    if field is None:
        known = ", ".join(f.name for f in FIELD_MAP[mode])
        raise ValueError(f"{mode.title} has no metric {metric!r}; expected one of {known}")

    return Series(
        mode=mode,
        metric=field,
        labels=tuple(session.date or f"#{session.report_id}" for session in sessions),
        values=tuple(session.metrics[metric] for session in sessions),
        sessions=tuple(sessions),
    )


def sessions_in_mode(sessions: Sequence[Session], mode: GameMode) -> list[Session]:
    return [s for s in sessions if s.mode is mode]


def format_value(field: MetricField, value: float) -> str:
    """A metric value as shown to a person: whole numbers without a decimal."""
    text = f"{value:g}"
    return f"{text} {field.unit}" if field.unit else text


@dataclass(frozen=True)
class Summary:
    """Headline numbers for a patient's history."""

    total_sessions: int
    by_mode: dict[GameMode, int]
    first_date: str
    last_date: str


def summarize(sessions: Sequence[Session]) -> Summary:
    dates = sorted(s.date for s in sessions if s.date)
    return Summary(
        total_sessions=len(sessions),
        by_mode={mode: len(sessions_in_mode(sessions, mode)) for mode in GameMode},
        first_date=dates[0] if dates else "",
        last_date=dates[-1] if dates else "",
    )
