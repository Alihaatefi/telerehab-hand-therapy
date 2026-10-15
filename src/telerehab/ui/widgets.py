"""Reusable widgets: the vocabulary every page is built from.

Pages assemble these rather than styling raw Qt widgets, so spacing, colour and
behaviour stay consistent. Appearance lives in :mod:`telerehab.ui.theme`; the
widgets only set the *properties* the stylesheet keys on (``variant``, ``role``,
``pill``, ``card`` ...).
"""
from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import QEvent, QLocale, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QDoubleValidator,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .camera import frame_to_image

AlignCenter = Qt.AlignmentFlag.AlignCenter

# MediaPipe's 21-landmark hand topology, as index pairs.
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


# -- small helpers ---------------------------------------------------------------


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def label(
    text: str = "",
    role: str | None = None,
    *,
    wrap: bool = False,
    align: Qt.AlignmentFlag | None = None,
) -> QLabel:
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    if align is not None:
        widget.setAlignment(align)
    return widget


def set_role(widget: QLabel, role: str) -> None:
    widget.setProperty("role", role)
    repolish(widget)


_ICON_ON = {
    "primary": ("#FFFFFF", "#F2FAFA"),
    "onDark": ("#FFFFFF", "#8FA6AB"),
    "danger": (theme.DANGER, "#D9A29C"),
    "ghost": (theme.TEXT_MUTED, "#A9B4C3"),
}


def button(
    text: str = "",
    variant: str | None = None,
    *,
    icon: str | None = None,
    size: str | None = None,
    tooltip: str | None = None,
    checkable: bool = False,
) -> QPushButton:
    widget = QPushButton(text)
    if variant:
        widget.setProperty("variant", variant)
    if size:
        widget.setProperty("size", size)
    if icon:
        colour, disabled = _ICON_ON.get(variant or "", (theme.TEXT, "#A9B4C3"))
        widget.setIcon(icons.icon(icon, colour, 18, disabled=disabled))
        widget.setIconSize(QSize(18, 18))
    if tooltip:
        widget.setToolTip(tooltip)
    widget.setCheckable(checkable)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def rule() -> QFrame:
    line = QFrame()
    line.setProperty("rule", True)
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


def scrollable(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(content)
    return area


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.widget()
        if child is not None:
            child.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


# -- structure ---------------------------------------------------------------------


class Page(QWidget):
    """A full-size page with the canvas background."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    # Lifecycle hooks the main window calls when a page is shown or hidden.
    def on_show(self) -> None:  # pragma: no cover - overridden where needed
        pass

    def on_hide(self) -> None:  # pragma: no cover - overridden where needed
        pass


class Card(QFrame):
    """A white, bordered surface. Add content through :attr:`body`."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        soft: bool = False,
        padding: int = 20,
        spacing: int = 12,
    ):
        super().__init__(parent)
        self.setProperty("card", "soft" if soft else "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)


class PageHeader(QWidget):
    """Title, optional subtitle, and room for actions on the right."""

    def __init__(self, title: str, subtitle: str = "", eyebrow: str = ""):
        super().__init__()
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)

        text = QVBoxLayout()
        text.setSpacing(4)
        if eyebrow:
            text.addWidget(label(eyebrow.upper(), "eyebrow"))
        self.title = label(title, "h1")
        text.addWidget(self.title)
        self.subtitle = label(subtitle, "muted", wrap=True)
        self.subtitle.setVisible(bool(subtitle))
        text.addWidget(self.subtitle)
        outer.addLayout(text, 1)

        # Not "actions": that name belongs to QWidget (a method returning its QActions).
        self.action_row = QHBoxLayout()
        self.action_row.setSpacing(10)
        outer.addLayout(self.action_row)

    def add_action(self, widget: QWidget) -> None:
        self.action_row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)


class Pill(QLabel):
    """A compact status label: ``neutral``, ``success``, ``warning``, ``danger``, ``info``, ``brand``."""

    def __init__(self, text: str = "", kind: str = "neutral"):
        super().__init__()
        self.setAlignment(AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set(text, kind)

    def set(self, text: str, kind: str) -> None:
        self.setText(text)
        self.setProperty("pill", kind)
        repolish(self)


_BANNER = {
    "info": ("info", theme.ACCENT),
    "success": ("check-circle", theme.SUCCESS),
    "warning": ("alert", theme.WARNING),
    "danger": ("alert", theme.DANGER),
}


class Banner(QFrame):
    """An inline message with an icon, for results and errors."""

    def __init__(self, text: str = "", kind: str = "info"):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(12)

        self._icon = QLabel()
        self._icon.setFixedSize(22, 22)
        row.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)

        self._text = label("", wrap=True)
        row.addWidget(self._text, 1)

        self.action_row = QHBoxLayout()
        row.addLayout(self.action_row)
        self.set(text, kind)

    def set(self, text: str, kind: str = "info") -> None:
        name, colour = _BANNER[kind]
        self._icon.setPixmap(icons.pixmap(name, colour, 20))
        self._text.setText(text)
        self.setProperty("banner", kind)
        repolish(self)

    def add_action(self, widget: QWidget) -> None:
        self.action_row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)


class StatTile(Card):
    """A caption, one large number and a line of context."""

    def __init__(self, caption: str, value: str = "-", hint: str = ""):
        super().__init__(padding=18, spacing=4)
        self.caption = label(caption, "caption")
        self.value = label(value, "stat")
        self.hint = label(hint, "muted")
        self.hint.setVisible(bool(hint))
        for widget in (self.caption, self.value, self.hint):
            self.body.addWidget(widget)

    def set(self, value: str, hint: str = "") -> None:
        self.value.setText(value)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))


class EmptyState(QWidget):
    """What to show when there is nothing to show yet."""

    def __init__(self, icon: str, title: str, text: str = ""):
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(24, 32, 24, 32)
        column.setSpacing(10)
        column.setAlignment(AlignCenter)

        disc = QLabel()
        disc.setFixedSize(56, 56)
        disc.setAlignment(AlignCenter)
        disc.setPixmap(icons.pixmap(icon, theme.PRIMARY, 26))
        disc.setStyleSheet(f"background: {theme.PRIMARY_SOFT}; border-radius: 28px;")
        column.addWidget(disc, 0, AlignCenter)

        column.addWidget(label(title, "h2", align=AlignCenter))
        self.text = label(text, "muted", wrap=True, align=AlignCenter)
        self.text.setMaximumWidth(380)
        column.addWidget(self.text, 0, AlignCenter)
        self._column = column

    def add_action(self, widget: QWidget) -> None:
        self._column.addWidget(widget, 0, AlignCenter)


# -- inputs -------------------------------------------------------------------------


class TextField(QWidget):
    """A labelled text input with a hint and an inline error."""

    returnPressed = Signal()
    textChanged = Signal(str)

    def __init__(
        self,
        caption: str,
        *,
        placeholder: str = "",
        hint: str = "",
        digits_only: bool = False,
        max_length: int = 40,
    ):
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        column.addWidget(label(caption, "h3"))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMaxLength(max_length)
        self.edit.setMinimumHeight(42)
        if digits_only:
            from PySide6.QtCore import QRegularExpression
            from PySide6.QtGui import QRegularExpressionValidator

            self.edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,9}")))
        self.edit.returnPressed.connect(self.returnPressed)
        self.edit.textChanged.connect(self._changed)
        column.addWidget(self.edit)

        self._hint = label(hint, "caption", wrap=True)
        self._hint.setVisible(bool(hint))
        column.addWidget(self._hint)

        self._error = label("", wrap=True)
        self._error.setStyleSheet(f"color: {theme.DANGER}; font-size: 12px;")
        self._error.setVisible(False)
        column.addWidget(self._error)

    def _changed(self, text: str) -> None:
        # isHidden(), not isVisible(): the latter also depends on every ancestor
        # being shown, so an error raised while the page was off-screen would stick.
        if not self._error.isHidden():
            self.set_error(None)
        self.textChanged.emit(text)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, text: str) -> None:
        self.edit.setText(text)

    def set_error(self, message: str | None) -> None:
        self._error.setText(message or "")
        self._error.setVisible(bool(message))
        self.edit.setProperty("invalid", bool(message))
        repolish(self.edit)

    def focus(self) -> None:
        """Put the cursor in the input. (Not ``setFocus``: that would change QWidget's signature.)"""
        self.edit.setFocus()


class SpinField(QFrame):
    """A number with minus and plus buttons, for exercise parameters.

    Built on a plain line edit rather than ``QSpinBox``: a style-sheeted
    ``QSpinBox`` collapses its editor to a one-pixel sliver, and the style sheet
    is what makes this look right.

    Bounded by construction: only digits can be typed, and the value is clamped
    into range as soon as editing finishes, so an out-of-range value never
    reaches the exercise.
    """

    valueChanged = Signal(float)

    def __init__(
        self,
        *,
        minimum: float,
        maximum: float,
        value: float,
        step: float = 1,
        decimals: int = 0,
        suffix: str = "",
    ):
        super().__init__()
        self.setProperty("field", True)
        self.setMinimumHeight(46)
        self._min, self._max = minimum, maximum
        self._step = step
        self._decimals = decimals
        self._value = self._clamp(value)

        row = QHBoxLayout(self)
        row.setContentsMargins(5, 4, 5, 4)
        row.setSpacing(2)

        self._minus = self._step_button("minus")
        self._plus = self._step_button("plus")

        self._edit = QLineEdit()
        self._edit.setProperty("bare", True)
        self._edit.setAlignment(AlignCenter)
        self._edit.setMinimumWidth(60)
        validator = QDoubleValidator(minimum, maximum, decimals, self._edit)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        validator.setLocale(QLocale.c())  # digits and '.', whatever the system locale
        self._edit.setValidator(validator)
        self._edit.setText(self._format(self._value))
        self._edit.installEventFilter(self)
        self._edit.editingFinished.connect(self._commit)

        self._suffix = label(suffix, "muted")
        self._suffix.setVisible(bool(suffix))

        self._minus.clicked.connect(lambda: self._nudge(-1))
        self._plus.clicked.connect(lambda: self._nudge(1))

        row.addWidget(self._minus)
        row.addWidget(self._edit, 1)
        row.addWidget(self._suffix)
        row.addSpacing(4)
        row.addWidget(self._plus)

    @staticmethod
    def _step_button(name: str) -> QPushButton:
        widget = QPushButton()
        widget.setIcon(icons.icon(name, theme.TEXT_MUTED, 18))
        widget.setIconSize(QSize(18, 18))
        widget.setFixedSize(34, 34)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setAutoRepeat(True)
        widget.setAutoRepeatInterval(90)
        return widget

    # -- value ---------------------------------------------------------------------------

    def _clamp(self, value: float) -> float:
        return round(max(self._min, min(self._max, value)), self._decimals)

    def _format(self, value: float) -> str:
        return f"{value:.{self._decimals}f}" if self._decimals else str(round(value))

    def _set(self, value: float) -> None:
        value = self._clamp(value)
        changed = value != self._value
        self._value = value
        self._edit.setText(self._format(value))
        if changed:
            self.valueChanged.emit(float(value))

    def _commit(self) -> None:
        """Adopt what was typed, clamped; keep the old value if it is not a number."""
        try:
            typed = float(self._edit.text().strip().replace(",", "."))
        except ValueError:
            typed = self._value
        self._set(typed)

    def _nudge(self, direction: int) -> None:
        self._commit()
        self._set(self._value + direction * self._step)

    def value(self) -> float:
        return float(self._value) if self._decimals else int(self._value)

    def setValue(self, value: float) -> None:
        self._set(value)

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.setProperty("focused", event.type() == QEvent.Type.FocusIn)
            repolish(self)
        return super().eventFilter(obj, event)


class Switch(QAbstractButton):
    """An on/off toggle."""

    def __init__(self, checked: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)

    def sizeHint(self) -> QSize:
        return QSize(46, 26)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        track = theme.qcolor(theme.PRIMARY if on else theme.BORDER_STRONG)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, 46, 26), 13, 13)
        painter.setBrush(theme.qcolor("#FFFFFF"))
        painter.drawEllipse(QRectF(24 if on else 3, 3, 20, 20))


class Chip(QPushButton):
    """A selectable filter chip."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setProperty("chip", True)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Tab(QPushButton):
    """An underlined tab button."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setProperty("tab", True)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# -- navigation -----------------------------------------------------------------------


class NavButton(QPushButton):
    """A sidebar entry with an icon that lightens when selected or hovered."""

    def __init__(self, text: str, icon: str):
        super().__init__(text)
        self.setProperty("nav", True)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(20, 20))

        from PySide6.QtGui import QIcon

        glyph = QIcon()
        muted = icons.pixmap(icon, theme.SIDEBAR_TEXT, 20)
        bright = icons.pixmap(icon, "#FFFFFF", 20)
        faded = icons.pixmap(icon, theme.SIDEBAR_MUTED, 20)
        glyph.addPixmap(muted, QIcon.Mode.Normal, QIcon.State.Off)
        glyph.addPixmap(bright, QIcon.Mode.Normal, QIcon.State.On)
        glyph.addPixmap(bright, QIcon.Mode.Active, QIcon.State.Off)
        glyph.addPixmap(bright, QIcon.Mode.Active, QIcon.State.On)
        glyph.addPixmap(faded, QIcon.Mode.Disabled)
        self.setIcon(glyph)


class StatusDot(QWidget):
    """A small coloured circle for connection status."""

    def __init__(self, colour: str = theme.TEXT_SUBTLE):
        super().__init__()
        self._colour = colour
        self.setFixedSize(10, 10)

    def set_colour(self, colour: str) -> None:
        self._colour = colour
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(self._colour))
        painter.drawEllipse(QRectF(1, 1, 8, 8))


class Stepper(QWidget):
    """A horizontal progress indicator for the exercise steps."""

    def __init__(self, steps: Sequence[str]):
        super().__init__()
        self._steps = list(steps)
        self._current = 0
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_current(self, index: int) -> None:
        self._current = index
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        count = len(self._steps)
        slot = self.width() / count
        radius = 12.0
        cy = self.height() / 2

        font = theme.app_font(13, QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        # Connectors first, so the circles sit on top of them.
        for i in range(count - 1):
            x1 = slot * i + slot / 2 + radius + metrics.horizontalAdvance(self._steps[i]) / 2 + 16
            x2 = slot * (i + 1) + slot / 2 - radius - metrics.horizontalAdvance(self._steps[i + 1]) / 2 - 16
            done = i < self._current
            painter.setPen(QPen(theme.qcolor(theme.PRIMARY if done else theme.BORDER_STRONG), 2))
            if x2 > x1:
                painter.drawLine(QPointF(x1, cy), QPointF(x2, cy))

        for i, name in enumerate(self._steps):
            text_w = metrics.horizontalAdvance(name)
            total = radius * 2 + 8 + text_w
            x0 = slot * i + (slot - total) / 2
            centre = QPointF(x0 + radius, cy)

            done, current = i < self._current, i == self._current
            if done or current:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.qcolor(theme.PRIMARY))
            else:
                painter.setPen(QPen(theme.qcolor(theme.BORDER_STRONG), 2))
                painter.setBrush(theme.qcolor(theme.SURFACE))
            painter.drawEllipse(centre, radius, radius)

            if done:
                painter.drawPixmap(
                    QPointF(centre.x() - 8, centre.y() - 8),
                    icons.pixmap("check", "#FFFFFF", 16, stroke=2.4),
                )
            else:
                painter.setPen(theme.qcolor("#FFFFFF" if current else theme.TEXT_SUBTLE))
                painter.drawText(
                    QRectF(centre.x() - radius, centre.y() - radius, radius * 2, radius * 2),
                    int(AlignCenter),
                    str(i + 1),
                )

            painter.setPen(theme.qcolor(theme.TEXT if current else theme.TEXT_MUTED))
            painter.drawText(
                QRectF(x0 + radius * 2 + 8, 0, text_w + 4, self.height()),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                name,
            )


# -- feedback ---------------------------------------------------------------------------


class ProgressRing(QWidget):
    """A circular progress indicator with centred text."""

    def __init__(
        self,
        diameter: int = 140,
        thickness: int = 11,
        colour: str = theme.PRIMARY,
        track: str = "#E2E8EF",
    ):
        super().__init__()
        self._value = 0.0
        self._thickness = thickness
        self._colour = colour
        self._track = track
        self._main = ""
        self._sub = ""
        self._on_dark = False
        self.setFixedSize(diameter, diameter)

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(1.0, value))
        self.update()

    def set_text(self, main: str, sub: str = "") -> None:
        self._main, self._sub = main, sub
        self.update()

    def set_colour(self, colour: str) -> None:
        self._colour = colour
        self.update()

    def set_on_dark(self, on_dark: bool) -> None:
        self._on_dark = on_dark
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        inset = self._thickness / 2 + 1
        box = QRectF(inset, inset, self.width() - 2 * inset, self.height() - 2 * inset)

        track = QPen(theme.qcolor("#FFFFFF", 0.14) if self._on_dark else theme.qcolor(self._track), self._thickness)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.drawEllipse(box)

        if self._value > 0:
            arc = QPen(theme.qcolor(self._colour), self._thickness)
            arc.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc)
            painter.drawArc(box, 90 * 16, -int(self._value * 360 * 16))

        text_colour = "#FFFFFF" if self._on_dark else theme.TEXT
        sub_colour = theme.SIDEBAR_TEXT if self._on_dark else theme.TEXT_MUTED
        size = max(16, self.width() // 4)
        if self._main:
            painter.setPen(theme.qcolor(text_colour))
            painter.setFont(theme.app_font(size, QFont.Weight.Bold))
            lift = int(size * 0.28) if self._sub else 0
            painter.drawText(self.rect().translated(0, -lift), int(AlignCenter), self._main)
        if self._sub:
            painter.setPen(theme.qcolor(sub_colour))
            painter.setFont(theme.app_font(12))
            top = self.height() / 2 + size * 0.32
            painter.drawText(
                QRectF(0, top, self.width(), 20),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                self._sub,
            )


class Avatar(QLabel):
    """A round badge with a person's initials."""

    def __init__(self, name: str = "", diameter: int = 44, *, on_dark: bool = False):
        super().__init__()
        self._diameter = diameter
        self._on_dark = on_dark
        self.setFixedSize(diameter, diameter)
        self.setAlignment(AlignCenter)
        self.set_name(name)

    def set_name(self, name: str) -> None:
        parts = [p for p in name.split() if p]
        initials = "".join(p[0] for p in parts[:2]).upper() or "?"
        background = "rgba(45,212,191,0.18)" if self._on_dark else theme.PRIMARY_SOFT
        colour = theme.MINT if self._on_dark else theme.PRIMARY_TEXT
        self.setText(initials)
        self.setStyleSheet(
            f"background: {background}; color: {colour}; font-weight: 700;"
            f"font-size: {max(12, self._diameter // 3)}px; border-radius: {self._diameter // 2}px;"
        )


class CameraView(QWidget):
    """The live video frame, with the detected hand drawn over it.

    The overlay is drawn here, in the interface, from the 21 normalised
    landmarks — the video frame itself stays clean, and the skeleton stays sharp
    at any window size.
    """

    def __init__(
        self,
        *,
        placeholder: str = "Starting camera...",
        badge: bool = True,
        radius: int = 16,
        compact: bool = False,
    ):
        super().__init__()
        self._image: QImage | None = None
        self._points: Sequence[tuple[float, float]] | None = None
        self._has_hand = False
        self._placeholder = placeholder
        self._message: str | None = None
        self._badge = badge
        self._radius = radius
        self._compact = compact
        self.setMinimumSize(160, 120) if compact else self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_sample(self, sample) -> None:
        self._image = frame_to_image(sample.frame)
        self._points = sample.points
        self._has_hand = sample.has_hand
        self._message = None
        self.update()

    def set_message(self, text: str | None) -> None:
        """Replace the video with a message (e.g. a camera error)."""
        self._message = text
        if text:
            self._image = None
        self.update()

    def clear(self) -> None:
        self._image = None
        self._points = None
        self._has_hand = False
        self.update()

    def _frame_rect(self) -> QRectF:
        bounds = QRectF(self.rect())
        if self._image is None:
            return bounds
        scale = min(bounds.width() / self._image.width(), bounds.height() / self._image.height())
        width, height = self._image.width() * scale, self._image.height() * scale
        return QRectF(
            bounds.x() + (bounds.width() - width) / 2,
            bounds.y() + (bounds.height() - height) / 2,
            width,
            height,
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        outer = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(outer, self._radius, self._radius)
        painter.setClipPath(clip)
        painter.fillRect(outer, theme.qcolor(theme.STAGE_DARK))

        if self._image is None:
            self._paint_status(painter, outer)
            return

        target = self._frame_rect()
        painter.drawImage(target, self._image)

        if self._points:
            self._paint_hand(painter, target)
        if self._badge:
            self._paint_badge(painter, outer)

    def _paint_status(self, painter: QPainter, bounds: QRectF) -> None:
        text = self._message or self._placeholder
        colour = theme.WARNING_SOFT if self._message else theme.SIDEBAR_TEXT
        painter.setPen(theme.qcolor(colour))
        painter.setFont(theme.app_font(13 if self._compact else 14, QFont.Weight.DemiBold))
        icon = "camera-off" if self._message else "camera"
        pixmap = icons.pixmap(icon, colour, 28 if not self._compact else 20)
        top = bounds.center().y() - (26 if not self._compact else 18)
        painter.drawPixmap(
            QPointF(bounds.center().x() - pixmap.width() / pixmap.devicePixelRatio() / 2, top),
            pixmap,
        )
        painter.drawText(
            bounds.adjusted(16, top - bounds.top() + 36, -16, 0),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            text,
        )

    def _paint_hand(self, painter: QPainter, target: QRectF) -> None:
        points = self._points
        if not points:
            return

        def at(index: int) -> QPointF:
            x, y = points[index]
            return QPointF(target.x() + x * target.width(), target.y() + y * target.height())

        bones = QPen(theme.qcolor("#FFFFFF", 0.85), 2.4 if not self._compact else 1.6)
        bones.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bones)
        for a, b in HAND_CONNECTIONS:
            painter.drawLine(at(a), at(b))

        radius = 4.6 if not self._compact else 3.2
        painter.setPen(QPen(theme.qcolor("#FFFFFF"), 1.6))
        painter.setBrush(theme.qcolor(theme.MINT))
        for i in range(len(points)):
            painter.drawEllipse(at(i), radius, radius)

    def _paint_badge(self, painter: QPainter, bounds: QRectF) -> None:
        text = "Hand detected" if self._has_hand else "No hand detected"
        colour = theme.MINT if self._has_hand else "#F5B84C"

        painter.setFont(theme.app_font(12 if not self._compact else 11, QFont.Weight.DemiBold))
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + 34
        height = 26 if not self._compact else 22
        box = QRectF(bounds.x() + 12, bounds.y() + 12, width, height)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor("#06141A", 0.72))
        painter.drawRoundedRect(box, height / 2, height / 2)
        painter.setBrush(theme.qcolor(colour))
        painter.drawEllipse(QPointF(box.x() + 13, box.center().y()), 4.5, 4.5)
        painter.setPen(theme.qcolor("#FFFFFF"))
        painter.drawText(
            box.adjusted(24, 0, 0, 0),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )
