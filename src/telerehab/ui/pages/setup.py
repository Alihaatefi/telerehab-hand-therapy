"""Exercise settings: the prescription for this session."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...api import GameMode
from ...config import GameConfig
from .. import theme
from ..state import AppState
from ..widgets import (
    Avatar,
    Banner,
    Card,
    Page,
    SpinField,
    button,
    clear_layout,
    label,
    rule,
    scrollable,
)

# (config field, title, explanation, minimum, maximum, step, decimals, unit)
FieldSpec = tuple[str, str, str, float, float, float, int, str]

FIELDS: dict[GameMode, list[FieldSpec]] = {
    GameMode.TIME_SCORE: [
        ("exercise_seconds", "Exercise time", "How long the session lasts.", 5, 600, 5, 0, "s"),
        (
            "gain", "Gain",
            "How far the butterfly travels for a given hand movement. Raise it when "
            "your range of movement is limited.",
            0.1, 5.0, 0.1, 1, "",
        ),
        (
            "calibration_seconds", "Calibration time",
            "How long you sweep your hand open and closed so the exercise can learn your range.",
            3, 60, 1, 0, "s",
        ),
    ],
    GameMode.OPEN_CLOSE: [
        ("open_seconds", "Open hold", "How long to keep the hand open in each repetition.", 1, 120, 1, 0, "s"),
        ("close_seconds", "Closed hold", "How long to keep the hand closed in each repetition.", 1, 120, 1, 0, "s"),
        (
            "repetitions", "Repetitions",
            "One repetition is one open hold followed by one closed hold.",
            1, 50, 1, 0, "",
        ),
    ],
}

STEPS = {
    GameMode.TIME_SCORE: [
        ("Calibrate", "Slowly open and close your hand as far as is comfortable, so the exercise learns your range."),
        ("Steer", "Opening your hand moves the butterfly across the garden; closing it moves it back."),
        ("Settle", "Hold the butterfly on the flower for half a second to score. The flower then moves."),
    ],
    GameMode.OPEN_CLOSE: [
        ("Calibrate", "Capture one fully open hand and one closed fist. The exercise places its threshold between them."),
        ("Hold", "Match the flower: in bloom means open hand, a bud means closed. The butterfly advances as you hold."),
        ("Repeat", "The timer only runs while your posture is correct, so a brief wobble costs you nothing."),
    ],
}

TITLES = {
    GameMode.TIME_SCORE: ("Time / Score", "Butterfly Garden settings"),
    GameMode.OPEN_CLOSE: ("Open / Close", "Posture Holds settings"),
}


def format_duration(seconds: float) -> str:
    seconds = round(seconds)
    minutes, rest = divmod(seconds, 60)
    if minutes and rest:
        return f"{minutes} min {rest} s"
    return f"{minutes} min" if minutes else f"{rest} s"


class SetupPage(Page):
    accepted = Signal(object)  # GameConfig
    back = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.mode = GameMode.TIME_SCORE
        self._base = state.settings.game
        self._fields: dict[str, SpinField] = {}

        content = QWidget()
        content.setObjectName("Page")
        column = QVBoxLayout(content)
        column.setContentsMargins(36, 8, 36, 28)
        column.setSpacing(18)

        self.patient_row = QHBoxLayout()
        column.addLayout(self.patient_row)

        body = QHBoxLayout()
        body.setSpacing(20)

        self.form_card = Card(padding=26, spacing=16)
        body.addWidget(self.form_card, 3)

        side = QVBoxLayout()
        side.setSpacing(16)
        self.how_card = Card(padding=24, spacing=14)
        side.addWidget(self.how_card)
        side.addWidget(Banner(
            "Sit where the camera can see your whole hand, in good light, with a plain background if possible.",
            "info",
        ))
        side.addStretch(1)
        body.addLayout(side, 2)
        column.addLayout(body)

        actions = QHBoxLayout()
        back = button("Back", "ghost", icon="arrow-left", size="lg")
        back.clicked.connect(self.back)
        self.go = button("Continue to calibration", "primary", icon="arrow-right", size="lg")
        self.go.clicked.connect(lambda: self.accepted.emit(self.config()))
        actions.addWidget(back)
        actions.addStretch(1)
        actions.addWidget(self.go)
        column.addLayout(actions)
        column.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))

    # -- configuration ------------------------------------------------------------------

    def configure(self, mode: GameMode, base: GameConfig) -> None:
        self.mode = mode
        self._base = base
        self._render_patient()
        self._render_form()
        self._render_steps()

    def config(self) -> GameConfig:
        values: dict[str, Any] = {name: field.value() for name, field in self._fields.items()}
        return replace(self._base, **values)

    # -- rendering --------------------------------------------------------------------------

    def _render_patient(self) -> None:
        clear_layout(self.patient_row)
        patient = self.state.patient
        if patient is None:
            return
        self.patient_row.addWidget(Avatar(patient.display_name, 30))
        self.patient_row.addWidget(label(f"Exercising as {patient.display_name}", "muted"))
        self.patient_row.addWidget(label(f"ID {patient.id}", "caption"))
        self.patient_row.addStretch(1)

    def _render_form(self) -> None:
        clear_layout(self.form_card.body)
        self._fields.clear()
        body = self.form_card.body

        eyebrow, title = TITLES[self.mode]
        body.addWidget(label(eyebrow.upper(), "eyebrow"))
        body.addWidget(label(title, "h1"))

        for name, caption, explanation, low, high, step, decimals, unit in FIELDS[self.mode]:
            body.addWidget(rule())
            row = QHBoxLayout()
            row.setSpacing(24)

            text = QVBoxLayout()
            text.setSpacing(3)
            text.addWidget(label(caption, "h3"))
            text.addWidget(label(explanation, "muted", wrap=True))
            row.addLayout(text, 1)

            field = SpinField(
                minimum=low, maximum=high, step=step, decimals=decimals, suffix=unit,
                value=getattr(self._base, name),
            )
            field.setFixedWidth(190)
            field.valueChanged.connect(lambda _v: self._update_summary())
            row.addWidget(field, 0, Qt.AlignmentFlag.AlignTop)
            body.addLayout(row)
            self._fields[name] = field

        body.addWidget(rule())
        self.summary = label("", "muted")
        body.addWidget(self.summary)
        self._update_summary()

    def _update_summary(self) -> None:
        cfg = self.config()
        if self.mode is GameMode.TIME_SCORE:
            text = (
                f"Session length {format_duration(cfg.exercise_seconds)}, "
                f"after {format_duration(cfg.calibration_seconds)} of calibration."
            )
        else:
            per_rep = cfg.open_seconds + cfg.close_seconds
            text = (
                f"{cfg.repetitions} repetitions of {per_rep} s each - "
                f"{format_duration(per_rep * cfg.repetitions)} of holding in total."
            )
        self.summary.setText(text)

    def _render_steps(self) -> None:
        clear_layout(self.how_card.body)
        self.how_card.body.addWidget(label("How it works", "h2"))

        for number, (heading, text) in enumerate(STEPS[self.mode], start=1):
            row = QHBoxLayout()
            row.setSpacing(14)

            badge = QLabel(str(number))
            badge.setFixedSize(30, 30)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {theme.PRIMARY_SOFT}; color: {theme.PRIMARY_TEXT};"
                "font-weight: 700; border-radius: 15px;"
            )
            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

            words = QVBoxLayout()
            words.setSpacing(2)
            words.addWidget(label(heading, "h3"))
            words.addWidget(label(text, "muted", wrap=True))
            row.addLayout(words, 1)
            self.how_card.body.addLayout(row)
