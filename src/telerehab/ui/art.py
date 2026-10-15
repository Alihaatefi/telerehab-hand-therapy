"""The exercise scene, drawn in code.

The garden, the butterfly and the flower are vector shapes painted with
:class:`QPainter`, not bitmaps. They are therefore sharp at any window size or
display scaling, carry no third-party artwork licence, and can respond to the
exercise — the butterfly's wings beat, the flower opens and closes to show the
posture being asked for.

Colours are soft and low in contrast on purpose: this screen is looked at for
minutes at a time by people who are concentrating on their hand.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)


def _c(value: str, alpha: float = 1.0) -> QColor:
    colour = QColor(value)
    colour.setAlphaF(alpha)
    return colour


# Where the meadow starts, as a fraction of the scene height. The butterfly
# flies above this line; flower stems are planted below it.
GROUND = 0.86
FLIGHT_LINE = 0.50


# -- scene --------------------------------------------------------------------------


def _cloud(p: QPainter, x: float, y: float, scale: float) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c("#FFFFFF", 0.9))
    for dx, dy, rx, ry in (
        (0.0, 0.0, 64, 24), (-38, 8, 40, 18), (40, 9, 44, 17), (6, -14, 36, 22),
    ):
        p.drawEllipse(QPointF(x + dx * scale, y + dy * scale), rx * scale, ry * scale)


def _hills(
    p: QPainter, w: float, h: float, base: float, amp: float, freq: float,
    phase: float, colour: str,
) -> None:
    path = QPainterPath()
    path.moveTo(0, h)
    x = 0.0
    while x <= w + 6:
        t = x / w
        y = h * (
            base
            + amp * math.sin(t * freq * 2 * math.pi + phase)
            + amp * 0.45 * math.sin(t * freq * 5.1 * math.pi + phase * 1.7)
        )
        path.lineTo(x, y)
        x += 6
    path.lineTo(w, h)
    path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c(colour))
    p.drawPath(path)


def draw_scene(p: QPainter, rect: QRectF) -> None:
    """The calm garden backdrop: sky, sun, clouds, three hill layers, meadow."""
    w, h = rect.width(), rect.height()
    p.save()
    p.translate(rect.topLeft())
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    sky = QLinearGradient(0, 0, 0, h * 0.75)
    sky.setColorAt(0.0, _c("#7EC8F0"))
    sky.setColorAt(0.7, _c("#D2EDFA"))
    sky.setColorAt(1.0, _c("#F3FAF1"))
    p.fillRect(QRectF(0, 0, w, h), sky)

    # Sun and its glow.
    sun = QPointF(w * 0.84, h * 0.19)
    glow = QRadialGradient(sun, h * 0.36)
    glow.setColorAt(0.0, _c("#FFF7CF", 0.95))
    glow.setColorAt(0.35, _c("#FFF1B8", 0.35))
    glow.setColorAt(1.0, _c("#FFF1B8", 0.0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(glow))
    p.drawEllipse(sun, h * 0.36, h * 0.36)
    p.setBrush(_c("#FFF3A8"))
    p.drawEllipse(sun, h * 0.062, h * 0.062)

    for fx, fy, scale in ((0.13, 0.17, 1.0), (0.47, 0.09, 0.7), (0.70, 0.30, 0.85)):
        _cloud(p, w * fx, h * fy, scale * max(0.6, h / 640))

    _hills(p, w, h, 0.62, 0.050, 1.1, 0.6, "#CDE8DC")
    _hills(p, w, h, 0.69, 0.055, 1.7, 2.1, "#A5D8BD")
    _hills(p, w, h, 0.77, 0.045, 1.3, 4.0, "#7DC5A1")

    meadow = QLinearGradient(0, h * 0.80, 0, h)
    meadow.setColorAt(0.0, _c("#6DBF93"))
    meadow.setColorAt(1.0, _c("#3F9A72"))
    _hills(p, w, h, 0.835, 0.018, 1.6, 1.3, "#6DBF93")
    path = QPainterPath()
    path.moveTo(0, h)
    x = 0.0
    while x <= w + 6:
        path.lineTo(x, h * (0.835 + 0.018 * math.sin(x / w * 1.6 * 2 * math.pi + 1.3)
                            + 0.008 * math.sin(x / w * 8.2 * math.pi)))
        x += 6
    path.lineTo(w, h)
    path.closeSubpath()
    p.setBrush(QBrush(meadow))
    p.drawPath(path)

    # Scattered wildflowers and tufts in the meadow, fixed by a seeded RNG so the
    # scene is identical on every repaint.
    rng = random.Random(11)
    palette = ["#FFFFFF", "#FFD3E4", "#FFE59B", "#E4D6FF", "#FFC4A8"]
    for _ in range(int(40 + w / 14)):
        fx = rng.random() * w
        fy = h * (0.865 + rng.random() * 0.13)
        radius = (2.0 + rng.random() * 2.6) * max(0.7, h / 640)
        p.setBrush(_c(rng.choice(palette), 0.92))
        p.drawEllipse(QPointF(fx, fy), radius, radius)
        p.setBrush(_c("#FFD24D", 0.95))
        p.drawEllipse(QPointF(fx, fy), radius * 0.38, radius * 0.38)

    p.restore()


# -- butterfly -------------------------------------------------------------------------


def _wing_paths() -> tuple[QPainterPath, QPainterPath]:
    upper = QPainterPath()
    upper.moveTo(0.05, 0.08)
    upper.cubicTo(0.25, 1.00, 1.00, 1.05, 1.00, 0.50)
    upper.cubicTo(1.00, 0.20, 0.50, 0.00, 0.05, 0.08)
    upper.closeSubpath()

    lower = QPainterPath()
    lower.moveTo(0.05, 0.00)
    lower.cubicTo(0.60, 0.05, 0.95, -0.30, 0.70, -0.72)
    lower.cubicTo(0.50, -0.95, 0.12, -0.55, 0.05, -0.02)
    lower.closeSubpath()
    return upper, lower


_UPPER, _LOWER = _wing_paths()


def draw_butterfly(
    p: QPainter,
    centre: QPointF,
    size: float,
    flap: float = 0.0,
    tilt: float = 0.0,
    *,
    alert: bool = False,
) -> None:
    """A butterfly of wingspan ``size`` (pixels).

    ``flap`` is the wing-beat phase in radians; ``tilt`` leans the whole
    butterfly, in degrees. ``alert`` turns the wings a muted grey-blue, used to
    show that the current posture is not the one being asked for.
    """
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(centre)
    p.rotate(tilt)
    scale = size / 2.0
    p.scale(scale, -scale)  # unit coordinates, y up

    beat = 0.30 + 0.70 * abs(math.cos(flap))

    upper = QLinearGradient(0, 0, 1, 1)
    lower = QLinearGradient(0, 0, 0.8, -0.8)
    if alert:
        upper.setColorAt(0, _c("#9FB4C7"))
        upper.setColorAt(1, _c("#6F8AA6"))
        lower.setColorAt(0, _c("#C3D2DF"))
        lower.setColorAt(1, _c("#93A9BF"))
    else:
        upper.setColorAt(0, _c("#FF9A4D"))
        upper.setColorAt(1, _c("#EE4F7E"))
        lower.setColorAt(0, _c("#FFCA5A"))
        lower.setColorAt(1, _c("#F59A39"))

    outline = QPen(_c("#4B2A49", 0.55), 0.035)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    for side in (-1, 1):
        p.save()
        p.scale(side * beat, 1.0)
        p.setPen(outline)
        p.setBrush(QBrush(lower))
        p.drawPath(_LOWER)
        p.setBrush(QBrush(upper))
        p.drawPath(_UPPER)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c("#FFFFFF", 0.8))
        p.drawEllipse(QPointF(0.70, 0.62), 0.09, 0.09)
        p.drawEllipse(QPointF(0.42, 0.44), 0.05, 0.05)
        p.drawEllipse(QPointF(0.55, -0.45), 0.055, 0.055)
        p.restore()

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c("#3A2440"))
    p.drawEllipse(QPointF(0, 0), 0.07, 0.50)
    p.drawEllipse(QPointF(0, 0.52), 0.078, 0.078)

    feeler = QPen(_c("#3A2440"), 0.03)
    feeler.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(feeler)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for side in (-1, 1):
        path = QPainterPath()
        path.moveTo(0.02 * side, 0.58)
        path.cubicTo(0.06 * side, 0.78, 0.15 * side, 0.88, 0.24 * side, 0.92)
        p.drawPath(path)

    p.restore()


# -- flower ------------------------------------------------------------------------------


def _draw_bud(p: QPainter, head: QPointF, size: float) -> None:
    """A closed bud: three overlapping petals held in a pair of green sepals.

    This is what the patient is asked to match when the target posture is a fist,
    so it must read as "closed" at a glance, not as a half-open flower.
    """
    p.save()
    p.translate(head)
    p.setPen(QPen(_c("#B5385F", 0.35), max(1.0, size * 0.012)))
    for angle, shade in ((-15, "#F4628A"), (15, "#FF93B4"), (0, "#FF7FA3")):
        p.save()
        p.rotate(angle)
        p.setBrush(_c(shade))
        p.drawEllipse(QPointF(0, -size * 0.04), size * 0.15, size * 0.31)
        p.restore()

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c("#4EA977"))
    for side in (-1, 1):
        sepal = QPainterPath()
        sepal.moveTo(0, size * 0.34)
        sepal.cubicTo(side * size * 0.30, size * 0.24, side * size * 0.30, size * 0.00, side * size * 0.10, -size * 0.06)
        sepal.cubicTo(side * size * 0.15, size * 0.08, side * size * 0.07, size * 0.22, 0, size * 0.34)
        p.drawPath(sepal)
    p.restore()


def draw_flower(
    p: QPainter,
    head: QPointF,
    size: float,
    *,
    bloom: float = 1.0,
    glow: float = 0.0,
    stem_to: float | None = None,
) -> None:
    """A flower whose head is at ``head`` with diameter ``size``.

    ``bloom`` runs from 0 (a closed bud) to 1 (fully open); ``glow`` from 0 to 1
    lights a halo behind it. A stem is planted down to ``stem_to`` when given.
    """
    bloom = max(0.0, min(1.0, bloom))
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    if stem_to is not None and stem_to > head.y():
        stem = QPen(_c("#3C8F64"), max(3.0, size * 0.075))
        stem.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(stem)
        path = QPainterPath()
        path.moveTo(head.x(), head.y() + size * 0.25)
        path.cubicTo(
            head.x() + size * 0.10, head.y() + (stem_to - head.y()) * 0.4,
            head.x() - size * 0.10, head.y() + (stem_to - head.y()) * 0.7,
            head.x(), stem_to,
        )
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c("#4EA977"))
        for side, frac in ((-1, 0.45), (1, 0.62)):
            leaf_y = head.y() + (stem_to - head.y()) * frac
            p.save()
            p.translate(head.x(), leaf_y)
            p.rotate(side * 52)
            p.drawEllipse(QPointF(0, -size * 0.28), size * 0.11, size * 0.30)
            p.restore()

    if glow > 0:
        halo = QRadialGradient(head, size * (0.95 + 0.5 * glow))
        halo.setColorAt(0.0, _c("#FFF0A8", 0.85 * glow))
        halo.setColorAt(1.0, _c("#FFF0A8", 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(head, size * 1.5, size * 1.5)

    if bloom < 0.5:
        _draw_bud(p, head, size)
        p.restore()
        return

    petals = 8
    length = size * 0.50
    spread = 0.22 + 0.78 * bloom
    reach = length * 0.56 * spread
    half_width = size * (0.145 + 0.045 * bloom)
    half_height = length * (0.62 - 0.14 * bloom)

    p.setPen(QPen(_c("#B5385F", 0.35), max(1.0, size * 0.012)))
    for i in range(petals):
        p.save()
        p.translate(head)
        p.rotate(i * 360.0 / petals)
        shade = "#FF93B4" if i % 2 == 0 else "#F4628A"
        p.setBrush(_c(shade))
        p.drawEllipse(QPointF(0, -reach), half_width, half_height)
        p.restore()

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c("#FFD24D"))
    p.drawEllipse(head, size * 0.13 * (0.5 + 0.5 * bloom), size * 0.13 * (0.5 + 0.5 * bloom))
    if bloom > 0.5:
        p.setBrush(_c("#E9A72A"))
        for k in range(6):
            angle = k * math.pi / 3
            p.drawEllipse(
                QPointF(head.x() + math.cos(angle) * size * 0.07,
                        head.y() + math.sin(angle) * size * 0.07),
                size * 0.016, size * 0.016,
            )
    p.restore()


# -- small illustrations for the home page ---------------------------------------------------


def draw_emblem(p: QPainter, rect: QRectF, kind: str) -> None:
    """A miniature of an exercise, for its card: ``"time_score"`` or ``"open_close"``."""
    p.save()
    clip = QPainterPath()
    clip.addRoundedRect(rect, 14, 14)
    p.setClipPath(clip)
    draw_scene(p, rect)

    size = rect.height() * 0.30
    base = rect.top() + rect.height() * 0.88
    if kind == "time_score":
        flower = QPointF(rect.left() + rect.width() * 0.70, rect.top() + rect.height() * 0.50)
        draw_flower(p, flower, size, bloom=1.0, glow=0.5, stem_to=base)
        draw_butterfly(p, QPointF(rect.left() + rect.width() * 0.34, rect.top() + rect.height() * 0.44),
                       size * 1.35, flap=0.5, tilt=-8)
    else:
        bud = QPointF(rect.left() + rect.width() * 0.28, rect.top() + rect.height() * 0.52)
        bloom = QPointF(rect.left() + rect.width() * 0.72, rect.top() + rect.height() * 0.52)
        draw_flower(p, bud, size, bloom=0.1, stem_to=base)
        draw_flower(p, bloom, size, bloom=1.0, glow=0.4, stem_to=base)
        draw_butterfly(p, QPointF(rect.center().x(), rect.top() + rect.height() * 0.30),
                       size * 1.1, flap=0.3, tilt=4)
    p.restore()
