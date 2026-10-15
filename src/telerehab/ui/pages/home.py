"""Home: pick an exercise, see who is signed in, glance at recent activity."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ...api import GameMode, Session
from .. import art
from ..state import AppState
from ..tasks import run_async
from ..widgets import (
    Avatar,
    Banner,
    Card,
    EmptyState,
    Page,
    PageHeader,
    Pill,
    StatTile,
    button,
    clear_layout,
    label,
    rule,
    scrollable,
)

EXERCISES = {
    GameMode.TIME_SCORE: dict(
        kind="time_score",
        title="Butterfly Garden",
        mode_label="Time / Score",
        text=(
            "Open and close your hand to steer the butterfly onto the flower, then "
            "hold it there to score. Trains smooth, continuous control."
        ),
        meta=["Continuous control", "Scores points", "Adjustable gain"],
    ),
    GameMode.OPEN_CLOSE: dict(
        kind="open_close",
        title="Posture Holds",
        mode_label="Open / Close",
        text=(
            "Hold your hand open, then closed, for a set time. The timer only runs "
            "while your posture is correct. Trains sustained, steady holds."
        ),
        meta=["Timed holds", "Repetitions"],
    ),
}


class EmblemView(QWidget):
    """A miniature illustration of an exercise."""

    def __init__(self, kind: str):
        super().__init__()
        self._kind = kind
        self.setFixedHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        art.draw_emblem(painter, QRectF(self.rect()), self._kind)


def headline(session: Session) -> str:
    """The one number that best summarises a session."""
    if session.mode is GameMode.TIME_SCORE:
        return f"Score {int(session.metrics['score'])}"
    done = int(session.metrics["completed_repetitions"])
    total = int(session.metrics["repetitions"])
    return f"{done} of {total} repetitions"


class HomePage(Page):
    startExercise = Signal(object)  # GameMode
    openPatients = Signal()
    openReports = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._sessions: list[Session] | None = None

        content = QWidget()
        content.setObjectName("Page")
        column = QVBoxLayout(content)
        column.setContentsMargins(36, 30, 36, 36)
        column.setSpacing(22)

        self.header = PageHeader(
            "Hand therapy exercises",
            "Camera-guided exercises that adapt to your own range of motion.",
            eyebrow="Welcome",
        )
        self.backend_pill = Pill()
        self.camera_pill = Pill()
        self.retry = button("", "ghost", icon="refresh", tooltip="Check the backend again", size="sm")
        self.retry.clicked.connect(state.check_backend)
        for widget in (self.backend_pill, self.retry, self.camera_pill):
            self.header.add_action(widget)
        column.addWidget(self.header)

        self.patient_box = QVBoxLayout()
        column.addLayout(self.patient_box)

        self.cards = QHBoxLayout()
        self.cards.setSpacing(20)
        for mode, spec in EXERCISES.items():
            self.cards.addWidget(self._exercise_card(mode, spec), 1)
        column.addLayout(self.cards)

        column.addWidget(label("Recent activity", "h2"))
        self.activity = Card(padding=22, spacing=16)
        column.addWidget(self.activity)
        column.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))

        state.patientChanged.connect(self._patient_changed)
        state.backendChanged.connect(lambda _ok: self._refresh_status())
        state.settingsChanged.connect(self._refresh_status)

        self._refresh_status()
        self._render_patient()
        self._render_activity()

    # -- exercise cards --------------------------------------------------------------

    def _exercise_card(self, mode: GameMode, spec: dict) -> Card:
        card = Card(padding=0, spacing=0)
        card.body.addWidget(EmblemView(spec["kind"]))

        inner = QVBoxLayout()
        inner.setContentsMargins(22, 18, 22, 22)
        inner.setSpacing(10)
        inner.addWidget(label(spec["mode_label"].upper(), "eyebrow"))
        inner.addWidget(label(spec["title"], "h1"))
        inner.addWidget(label(spec["text"], "muted", wrap=True))

        pills = QHBoxLayout()
        pills.setSpacing(8)
        for text in spec["meta"]:
            pills.addWidget(Pill(text, "neutral"))
        pills.addStretch(1)
        inner.addLayout(pills)
        inner.addSpacing(6)

        start = button("Start exercise", "primary", icon="play", size="lg")
        start.clicked.connect(lambda: self.startExercise.emit(mode))
        inner.addWidget(start)
        card.body.addLayout(inner)
        return card

    # -- status -----------------------------------------------------------------------

    def _refresh_status(self) -> None:
        ok = self.state.backend_ok
        if ok is None:
            self.backend_pill.set("Checking backend...", "neutral")
        elif ok:
            self.backend_pill.set("Backend connected", "success")
        else:
            self.backend_pill.set("Backend unreachable", "danger")
        demo = self.state.settings.vision.demo
        self.camera_pill.set(self.state.camera_label, "info" if demo else "neutral")

    # -- patient ----------------------------------------------------------------------

    def _patient_changed(self, _patient) -> None:
        self._sessions = None
        self._render_patient()
        self.refresh()

    def _render_patient(self) -> None:
        clear_layout(self.patient_box)
        patient = self.state.patient

        if patient is None:
            self.header.title.setText("Hand therapy exercises")
            banner = Banner("Sign in or register a patient so sessions can be recorded.", "info")
            sign_in = button("Sign in", "primary", icon="log-in", size="sm")
            sign_in.clicked.connect(self.openPatients)
            banner.add_action(sign_in)
            self.patient_box.addWidget(banner)
            return

        first = patient.first_name or patient.display_name
        self.header.title.setText(f"Welcome back, {first}")

        card = Card(padding=18, spacing=0)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(Avatar(patient.display_name, 48))

        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(label(patient.display_name, "h2"))
        names.addWidget(label(f"Patient ID {patient.id}", "muted"))
        row.addLayout(names, 1)

        reports = button("View reports", icon="bar-chart")
        reports.clicked.connect(self.openReports)
        switch = button("Switch patient", "ghost")
        switch.clicked.connect(self.openPatients)
        row.addWidget(reports)
        row.addWidget(switch)
        card.body.addLayout(row)
        self.patient_box.addWidget(card)

    # -- activity -----------------------------------------------------------------------

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        patient = self.state.patient
        if patient is None:
            self._sessions = None
            self._render_activity()
            return

        client = self.state.client
        run_async(
            lambda: client.sessions_for_patient(patient.id),
            self._loaded,
            self._load_failed,
            owner=self,
        )

    def _loaded(self, sessions) -> None:
        self._sessions = list(sessions)
        self._render_activity()

    def _load_failed(self, _error) -> None:
        self._sessions = None
        self._render_activity(error=True)

    def _render_activity(self, *, error: bool = False) -> None:
        clear_layout(self.activity.body)
        body = self.activity.body

        if self.state.patient is None:
            empty = EmptyState("user", "No patient signed in", "Sign in to see recent sessions and progress.")
            body.addWidget(empty)
            return
        if error:
            body.addWidget(Banner("Recent sessions could not be loaded from the backend.", "warning"))
            return
        if self._sessions is None:
            body.addWidget(label("Loading...", "muted"))
            return
        if not self._sessions:
            body.addWidget(EmptyState("activity", "No sessions yet", "Your first exercise will appear here."))
            return

        sessions = self._sessions
        tiles = QHBoxLayout()
        tiles.setSpacing(14)

        scores = [s.metrics["score"] for s in sessions if s.mode is GameMode.TIME_SCORE]
        holds = [s.metrics["completed_repetitions"] for s in sessions if s.mode is GameMode.OPEN_CLOSE]
        last = max((s.date for s in sessions if s.date), default="-")

        tile_specs = [
            ("Sessions", str(len(sessions)), ""),
            ("Last session", last, ""),
            ("Best score", f"{max(scores):g}" if scores else "-", "Time / Score"),
            ("Most repetitions", f"{max(holds):g}" if holds else "-", "Open / Close"),
        ]
        for caption, value, hint in tile_specs:
            tile = StatTile(caption, value, hint)
            tile.setProperty("card", "soft")
            tiles.addWidget(tile, 1)
        body.addLayout(tiles)
        body.addWidget(rule())

        for session in reversed(sessions[-5:]):
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addWidget(Pill(session.mode.title, "brand"))
            row.addWidget(label(session.date or "-", "muted"))
            row.addStretch(1)
            row.addWidget(label(headline(session), "h3"))
            if session.report_id is not None:
                row.addWidget(label(f"#{session.report_id}", "caption"))
            body.addLayout(row)

        more = button("Open reports", "ghost", icon="arrow-right")
        more.clicked.connect(self.openReports)
        body.addWidget(more, 0, Qt.AlignmentFlag.AlignLeft)
