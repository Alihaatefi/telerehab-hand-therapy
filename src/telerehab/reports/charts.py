"""Progress charts for clinicians.

Three properties worth stating, since charts are the clinician-facing output:

* Axis labels come from :data:`telerehab.api.models.FIELD_MAP` alongside the
  values they describe, so a label cannot disagree with its bar. A mislabelled
  chart is indistinguishable from a correct one at a glance, which makes this
  the most consequential thing in the module.
* Rendering goes straight to an in-memory buffer. Nothing is written to disk, so
  no error path can leave stray files behind.
* Functions return every chart they produce, not just the last one; a patient's
  history is the point of the report.
"""
from __future__ import annotations

import io
from typing import Sequence

import matplotlib

# Must precede pyplot: there is no interactive display to attach to, and on
# Windows the default backend opens its own window and blocks the game loop.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from ..api.models import FIELD_MAP, Session  # noqa: E402

BAR_COLOR = "#3b7dd8"
TREND_COLOR = "#d83b52"


def _finish(figure) -> bytes:
    buffer = io.BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=100)
    plt.close(figure)
    return buffer.getvalue()


def session_chart(session: Session, size: tuple[float, float] = (8, 6)) -> bytes:
    """A bar chart of one session's metrics, as PNG bytes."""
    labels, values = session.chart_series()

    figure, axes = plt.subplots(figsize=size)
    bars = axes.bar(labels, values, color=BAR_COLOR)
    axes.set_title(session.chart_title())
    axes.set_ylabel("Value")
    axes.spines[["top", "right"]].set_visible(False)

    for bar, value in zip(bars, values):
        axes.annotate(
            f"{value:g}",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            ha="center", va="bottom", fontsize=9,
        )

    return _finish(figure)


def progress_chart(
    sessions: Sequence[Session],
    metric: str,
    size: tuple[float, float] = (8, 6),
) -> bytes:
    """One metric plotted across a patient's sessions over time.

    A single session says little; the trend across sessions is the clinical
    signal. Requires all ``sessions`` to be from the same mode.
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

    values = [session.metrics[metric] for session in sessions]
    labels = [session.date or f"#{session.report_id}" for session in sessions]

    figure, axes = plt.subplots(figsize=size)
    axes.plot(labels, values, marker="o", color=TREND_COLOR)
    axes.set_title(f"Patient {sessions[0].patient_id} - {field.label} over time")
    axes.set_ylabel(field.axis_label)
    axes.grid(True, alpha=0.3)
    axes.spines[["top", "right"]].set_visible(False)
    figure.autofmt_xdate(rotation=30)

    return _finish(figure)


def to_surface(png_bytes: bytes):
    """Load rendered PNG bytes as a pygame surface, with no file on disk."""
    import pygame

    return pygame.image.load(io.BytesIO(png_bytes), "chart.png")
