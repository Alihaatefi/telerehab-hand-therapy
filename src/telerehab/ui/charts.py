"""The progress chart, and the PDF report built from it.

One metric per chart, always from the shared :class:`~telerehab.reports.Series`
so its label and unit cannot disagree with its values. Points are spaced by the
*real* time between sessions, not evenly: a fortnight's gap should look like
one.

The same drawing code paints the on-screen widget and the PDF page.
"""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QFont,
    QLinearGradient,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
)
from PySide6.QtWidgets import QWidget

from ..api.models import FIELD_MAP, GameMode, Session
from ..reports.series import Series, format_value, metric_series, sessions_in_mode, summarize
from . import theme


def nice_ticks(top: float, count: int = 4) -> list[float]:
    """Round-numbered axis ticks from 0 up to just above ``top``."""
    if top <= 0:
        return [0.0, 1.0]
    raw = top / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = magnitude
    for factor in (1, 2, 2.5, 5, 10):
        step = factor * magnitude
        if step >= raw:
            break
    ceiling = step * math.ceil(top / step)
    return [round(i * step, 10) for i in range(round(ceiling / step) + 1)]


def _parse(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _short_date(label: str) -> str:
    try:
        day = datetime.strptime(label, "%Y-%m-%d")
    except ValueError:
        return label
    return f"{day:%b} {day.day}"


class LineChart(QWidget):
    """A single-metric trend line with hover read-out."""

    def __init__(self) -> None:
        super().__init__()
        self._series: Series | None = None
        self._colour = theme.PRIMARY
        self._points: list[QPointF] = []
        self._hover: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(280)

    def set_series(self, series: Series | None, colour: str | None = None) -> None:
        self._series = series
        if colour:
            self._colour = colour
        self._hover = None
        self.update()

    # -- interaction ---------------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:
        nearest, best = None, 28.0
        for i, point in enumerate(self._points):
            distance = math.hypot(point.x() - event.position().x(), point.y() - event.position().y())
            if distance < best:
                nearest, best = i, distance
        if nearest != self._hover:
            self._hover = nearest
            self.update()

    def leaveEvent(self, _event) -> None:
        if self._hover is not None:
            self._hover = None
            self.update()

    # -- painting ----------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._points = self.paint_to(painter, QRectF(self.rect()), hover=self._hover)

    def paint_to(
        self,
        painter: QPainter,
        rect: QRectF,
        *,
        scale: float = 1.0,
        hover: int | None = None,
    ) -> list[QPointF]:
        """Draw into ``rect``; returns the pixel position of every data point."""
        series = self._series
        left, right, top, bottom = 52 * scale, 18 * scale, 18 * scale, 40 * scale
        plot = QRectF(
            rect.left() + left, rect.top() + top,
            rect.width() - left - right, rect.height() - top - bottom,
        )

        if series is None or not series.values:
            painter.setPen(theme.qcolor(theme.TEXT_SUBTLE))
            painter.setFont(theme.app_font(round(14 * scale)))
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "No sessions to chart yet")
            return []

        ticks = nice_ticks(max(series.values) * 1.08)
        ceiling = ticks[-1]

        small = theme.app_font(round(12 * scale))
        painter.setFont(small)
        for tick in ticks:
            y = plot.bottom() - plot.height() * (tick / ceiling)
            painter.setPen(QPen(theme.qcolor(theme.BORDER), max(1.0, scale)))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(theme.qcolor(theme.TEXT_SUBTLE))
            painter.drawText(
                QRectF(rect.left(), y - 10 * scale, left - 10 * scale, 20 * scale),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                f"{tick:g}",
            )

        xs = self._x_positions(series, plot)
        ys = [plot.bottom() - plot.height() * (v / ceiling) for v in series.values]
        points = [QPointF(x, y) for x, y in zip(xs, ys, strict=False)]

        # Area under the line.
        if len(points) > 1:
            area = QPainterPath()
            area.moveTo(points[0].x(), plot.bottom())
            for point in points:
                area.lineTo(point)
            area.lineTo(points[-1].x(), plot.bottom())
            area.closeSubpath()
            fill = QLinearGradient(0, plot.top(), 0, plot.bottom())
            fill.setColorAt(0, theme.qcolor(self._colour, 0.20))
            fill.setColorAt(1, theme.qcolor(self._colour, 0.0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill))
            painter.drawPath(area)

            line = QPen(theme.qcolor(self._colour), 2.6 * scale)
            line.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            line.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(line)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            painter.drawPath(path)

        # X labels, thinned so they never collide.
        every = max(1, math.ceil(len(points) / 7))
        painter.setFont(small)
        painter.setPen(theme.qcolor(theme.TEXT_SUBTLE))
        for i, point in enumerate(points):
            if i % every and i != len(points) - 1:
                continue
            painter.drawText(
                QRectF(point.x() - 40 * scale, plot.bottom() + 8 * scale, 80 * scale, 20 * scale),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                _short_date(series.labels[i]),
            )

        # Markers; the latest and the hovered point are emphasised.
        for i, point in enumerate(points):
            emphasised = i == hover or i == len(points) - 1
            radius = (6.0 if emphasised else 4.2) * scale
            painter.setPen(QPen(theme.qcolor(self._colour), 2.4 * scale))
            painter.setBrush(theme.qcolor(self._colour if emphasised else "#FFFFFF"))
            painter.drawEllipse(point, radius, radius)

        if hover is not None and hover < len(points):
            self._paint_tooltip(painter, rect, points[hover], series, hover, scale)
        return points

    @staticmethod
    def _x_positions(series: Series, plot: QRectF) -> list[float]:
        count = len(series.values)
        if count == 1:
            return [plot.center().x()]

        stamps = [m.timestamp() for m in (_parse(s.timestamp) for s in series.sessions) if m]
        inset = 14.0
        usable = plot.width() - 2 * inset
        if len(stamps) == count and len(set(stamps)) > 1:
            start = stamps[0]
            span = stamps[-1] - start
            return [plot.left() + inset + usable * ((stamp - start) / span) for stamp in stamps]
        return [plot.left() + inset + usable * i / (count - 1) for i in range(count)]

    def _paint_tooltip(
        self, painter: QPainter, rect: QRectF, point: QPointF,
        series: Series, index: int, scale: float,
    ) -> None:
        session = series.sessions[index]
        lines = [
            format_value(series.metric, series.values[index]),
            series.labels[index] + (f"  -  report #{session.report_id}" if session.report_id else ""),
        ]
        bold = theme.app_font(round(14 * scale), QFont.Weight.Bold)
        plain = theme.app_font(round(12 * scale))
        painter.setFont(bold)
        width = max(
            painter.fontMetrics().horizontalAdvance(lines[0]),
            QFont_metrics(plain).horizontalAdvance(lines[1]),
        ) + 26 * scale
        height = 50 * scale
        x = min(max(point.x() - width / 2, rect.left() + 4), rect.right() - width - 4)
        y = point.y() - height - 14 * scale
        if y < rect.top() + 2:
            y = point.y() + 14 * scale

        box = QRectF(x, y, width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(theme.TEXT, 0.94))
        painter.drawRoundedRect(box, 8 * scale, 8 * scale)
        painter.setPen(theme.qcolor("#FFFFFF"))
        painter.setFont(bold)
        painter.drawText(box.adjusted(0, 6 * scale, 0, 0), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), lines[0])
        painter.setPen(theme.qcolor("#C9D4E2"))
        painter.setFont(plain)
        painter.drawText(box.adjusted(0, 0, 0, -6 * scale), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom), lines[1])


def QFont_metrics(font: QFont):
    from PySide6.QtGui import QFontMetrics

    return QFontMetrics(font)


# -- PDF -----------------------------------------------------------------------------------


def write_report_pdf(sessions: Sequence[Session], path: Path, *, patient_name: str) -> Path:
    """A printable progress report: headline numbers, one chart per metric, a table."""
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(144)
    writer.setTitle(f"TeleRehab progress report - {patient_name}")

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = 144 / 96  # the on-screen design is drawn for 96 dpi

    page_w, page_h = writer.width(), writer.height()
    margin = 70.0
    width = page_w - 2 * margin
    y = margin

    def new_page() -> None:
        nonlocal y
        writer.newPage()
        y = margin

    def need(height: float) -> None:
        if y + height > page_h - margin:
            new_page()

    # Header.
    painter.setPen(theme.qcolor(theme.PRIMARY))
    painter.setFont(theme.app_font(round(13 * scale), QFont.Weight.Bold))
    painter.drawText(QRectF(margin, y, width, 30 * scale), int(Qt.AlignmentFlag.AlignLeft), "TELEREHAB - HAND THERAPY")
    y += 30 * scale
    painter.setPen(theme.qcolor(theme.TEXT))
    painter.setFont(theme.app_font(round(26 * scale), QFont.Weight.Bold))
    painter.drawText(QRectF(margin, y, width, 44 * scale), int(Qt.AlignmentFlag.AlignLeft), "Progress report")
    y += 46 * scale
    painter.setPen(theme.qcolor(theme.TEXT_MUTED))
    painter.setFont(theme.app_font(round(14 * scale)))
    summary = summarize(sessions)
    when = f"{summary.first_date} to {summary.last_date}" if summary.first_date else "no dated sessions"
    painter.drawText(
        QRectF(margin, y, width, 26 * scale), int(Qt.AlignmentFlag.AlignLeft),
        f"{patient_name}   -   {summary.total_sessions} sessions   -   {when}",
    )
    y += 40 * scale

    chart = LineChart()
    for mode in GameMode:
        subset = sessions_in_mode(sessions, mode)
        if not subset:
            continue

        need(80 * scale)
        painter.setPen(theme.qcolor(theme.TEXT))
        painter.setFont(theme.app_font(round(18 * scale), QFont.Weight.Bold))
        painter.drawText(QRectF(margin, y, width, 30 * scale), int(Qt.AlignmentFlag.AlignLeft), mode.title)
        y += 38 * scale

        for index, field in enumerate(FIELD_MAP[mode]):
            height = 190 * scale
            need(height + 34 * scale)
            painter.setPen(theme.qcolor(theme.TEXT_MUTED))
            painter.setFont(theme.app_font(round(13 * scale), QFont.Weight.DemiBold))
            painter.drawText(QRectF(margin, y, width, 22 * scale), int(Qt.AlignmentFlag.AlignLeft), field.axis_label)
            y += 24 * scale
            chart.set_series(metric_series(subset, field.name), theme.SERIES[index % len(theme.SERIES)])
            chart.paint_to(painter, QRectF(margin, y, width, height), scale=scale)
            y += height + 16 * scale

        # Table of sessions.
        columns = ["Date", "Report", *[f.axis_label for f in FIELD_MAP[mode]]]
        col_w = width / len(columns)
        row_h = 26 * scale
        need(row_h * 2)
        painter.setFont(theme.app_font(round(12 * scale), QFont.Weight.Bold))
        painter.setPen(theme.qcolor(theme.TEXT_MUTED))
        for c, name in enumerate(columns):
            painter.drawText(QRectF(margin + c * col_w, y, col_w, row_h), int(Qt.AlignmentFlag.AlignVCenter), name)
        y += row_h
        painter.setFont(theme.app_font(round(12 * scale)))
        for session in subset:
            need(row_h)
            painter.setPen(QPen(theme.qcolor(theme.BORDER), 1))
            painter.drawLine(QPointF(margin, y), QPointF(margin + width, y))
            painter.setPen(theme.qcolor(theme.TEXT))
            cells = [
                session.date,
                "" if session.report_id is None else f"#{session.report_id}",
                *[f"{session.metrics[f.name]:g}" for f in FIELD_MAP[mode]],
            ]
            for c, cell in enumerate(cells):
                painter.drawText(QRectF(margin + c * col_w, y, col_w, row_h), int(Qt.AlignmentFlag.AlignVCenter), cell)
            y += row_h
        y += 36 * scale

    painter.end()
    return path
