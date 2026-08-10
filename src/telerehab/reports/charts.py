"""Progress charts for clinicians.

Three things the original did are corrected here:

* Charts were rendered from labels re-typed by hand at each call site, and the
  two modes' label lists were **swapped** in one of the two report paths — so
  every chart reached through "Report by ID" mislabelled its axes. Labels now
  come from :data:`telerehab.api.models.FIELD_MAP` alongside the values they
  describe, so the two cannot disagree.
* Plots were written as PNG files into the current working directory, displayed
  by reading them back, then deleted — leaving stray ``plot_*.png`` behind on
  any error path. They are now rendered straight into an in-memory buffer.
* A patient with several sessions produced several files but only the last was
  ever shown. All of them are returned.
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

    This is the view the thesis argues for but never built: a single session
    says little, whereas the trend across sessions is the actual clinical
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
