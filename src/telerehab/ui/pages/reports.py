"""Reports: a patient's history, trends per metric, and export."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...api import FIELD_MAP, GameMode, Patient, Session
from ...reports import (
    default_filename,
    format_value,
    metric_series,
    sessions_in_mode,
    sessions_to_csv,
    sessions_to_pdf,
    summarize,
)
from .. import theme
from ..charts import LineChart
from ..state import AppState
from ..tasks import run_async
from ..widgets import (
    Avatar,
    Banner,
    Card,
    Chip,
    EmptyState,
    Page,
    PageHeader,
    Pill,
    StatTile,
    Tab,
    TextField,
    button,
    clear_layout,
    label,
    scrollable,
)

#: The metric charted first for each mode.
DEFAULT_METRIC = {GameMode.TIME_SCORE: "score", GameMode.OPEN_CLOSE: "completed_repetitions"}


class SessionDetail(QDialog):
    """One session, in full."""

    def __init__(self, session: Session, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Report #{session.report_id}" if session.report_id else "Report")
        self.setMinimumWidth(560)

        column = QVBoxLayout(self)
        column.setContentsMargins(28, 26, 28, 24)
        column.setSpacing(14)

        head = QHBoxLayout()
        head.addWidget(label(session.mode.title, "h1"))
        head.addStretch(1)
        head.addWidget(Pill(session.date or "undated", "brand"))
        column.addLayout(head)

        facts = [f"Patient ID {session.patient_id}"]
        if session.report_id is not None:
            facts.append(f"Report #{session.report_id}")
        column.addWidget(label("   -   ".join(facts), "muted"))

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        for field in session.fields:
            tiles.addWidget(StatTile(field.label, format_value(field, session.metrics[field.name])))
        column.addLayout(tiles)

        close = button("Close", "primary")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        column.addLayout(row)


class ReportsPage(Page):
    startExercise = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._patient: Patient | None = None
        self._patient_id: int | None = None
        self._sessions: list[Session] = []
        self._mode = GameMode.TIME_SCORE
        self._metric = DEFAULT_METRIC[self._mode]
        self._stale = True

        content = QWidget()
        content.setObjectName("Page")
        column = QVBoxLayout(content)
        column.setContentsMargins(36, 30, 36, 36)
        column.setSpacing(18)

        self.header = PageHeader(
            "Reports", "Progress over time, one metric at a time.", eyebrow="Clinician view"
        )
        self.csv_button = button("Export CSV", icon="download")
        self.pdf_button = button("Export PDF", "primary", icon="file-text")
        self.csv_button.clicked.connect(self._export_csv)
        self.pdf_button.clicked.connect(self._export_pdf)
        self.header.add_action(self.csv_button)
        self.header.add_action(self.pdf_button)
        column.addWidget(self.header)

        column.addWidget(self._build_lookup())

        self.notice = Banner("", "info")
        self.notice.setVisible(False)
        column.addWidget(self.notice)

        self.body = QVBoxLayout()
        self.body.setSpacing(18)
        column.addLayout(self.body)
        column.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))

        state.patientChanged.connect(self._patient_changed)
        self._set_export_enabled(False)
        self._render_empty("Choose a patient", "Enter a patient ID above to see their sessions.")

    # -- lookup bar -----------------------------------------------------------------------

    def _build_lookup(self) -> Card:
        card = Card(padding=18, spacing=0)
        row = QHBoxLayout()
        row.setSpacing(14)

        self.id_field = TextField("Patient ID", placeholder="e.g. 1", digits_only=True, max_length=9)
        self.id_field.setMaximumWidth(220)
        self.id_field.returnPressed.connect(self._load_clicked)
        row.addWidget(self.id_field)
        load = button("Load patient", "primary", icon="search")
        load.clicked.connect(self._load_clicked)
        row.addWidget(load, 0, Qt.AlignmentFlag.AlignBottom)

        row.addSpacing(30)
        self.report_field = TextField("Report number", placeholder="e.g. 37", digits_only=True, max_length=9)
        self.report_field.setMaximumWidth(220)
        self.report_field.returnPressed.connect(self._open_report)
        row.addWidget(self.report_field)
        open_report = button("Open report", icon="file-text")
        open_report.clicked.connect(self._open_report)
        row.addWidget(open_report, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        card.body.addLayout(row)
        return card

    # -- loading ----------------------------------------------------------------------------

    def on_show(self) -> None:
        patient = self.state.patient
        if self._stale and patient is not None and self._patient_id is None:
            self.load_patient(patient.id)
        elif self._stale and self._patient_id is not None:
            self.load_patient(self._patient_id)

    def _patient_changed(self, patient: Patient | None) -> None:
        self._stale = True
        if patient is not None and self.isVisible():
            self.load_patient(patient.id)

    def _load_clicked(self) -> None:
        text = self.id_field.text()
        if not text:
            self.id_field.set_error("Enter a numeric patient ID")
            return
        self.load_patient(int(text))

    def load_patient(self, patient_id: int) -> None:
        self._stale = False
        self._patient_id = patient_id
        self.id_field.setText(str(patient_id))
        self.notice.setVisible(False)
        self._set_export_enabled(False)
        clear_layout(self.body)
        self.body.addWidget(label("Loading...", "muted"))

        client = self.state.client

        def fetch():
            return client.get_patient(patient_id), client.sessions_for_patient(patient_id)

        run_async(fetch, self._loaded, self._load_failed, owner=self)

    def _loaded(self, result) -> None:
        patient, sessions = result
        self._patient = patient
        self._sessions = list(sessions)

        if patient is None and not self._sessions:
            self._render_empty("Patient not found", f"No patient or sessions were found for ID {self._patient_id}.")
            return
        if not self._sessions:
            self._render_empty(
                "No sessions yet",
                "This patient has not completed an exercise. Their sessions will appear here.",
                action=True,
            )
            return

        modes = [m for m in GameMode if sessions_in_mode(self._sessions, m)]
        if self._mode not in modes:
            self._mode = modes[0]
            self._metric = DEFAULT_METRIC[self._mode]
        self._render()

    def _load_failed(self, exc: Exception) -> None:
        clear_layout(self.body)
        self.notice.set(str(exc), "danger")
        self.notice.setVisible(True)
        self._set_export_enabled(False)

    # -- rendering ---------------------------------------------------------------------------

    def _set_export_enabled(self, enabled: bool) -> None:
        self.csv_button.setEnabled(enabled)
        self.pdf_button.setEnabled(enabled)

    def _render_empty(self, title: str, text: str, *, action: bool = False) -> None:
        clear_layout(self.body)
        card = Card(padding=10)
        empty = EmptyState("bar-chart", title, text)
        if action:
            start = button("Start an exercise", "primary", icon="play")
            start.clicked.connect(self.startExercise)
            empty.add_action(start)
        card.body.addWidget(empty)
        self.body.addWidget(card)
        self._set_export_enabled(False)

    def _patient_name(self) -> str:
        if self._patient is not None:
            return self._patient.display_name
        return f"Patient {self._patient_id}"

    def _render(self) -> None:
        clear_layout(self.body)
        self._set_export_enabled(True)
        summary = summarize(self._sessions)

        # Who and how much.
        who = Card(padding=18, spacing=0)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(Avatar(self._patient_name(), 48))
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(label(self._patient_name(), "h2"))
        span = f"{summary.first_date} to {summary.last_date}" if summary.first_date else "undated sessions"
        names.addWidget(label(f"Patient ID {self._patient_id}   -   {span}", "muted"))
        row.addLayout(names, 1)
        who.body.addLayout(row)
        self.body.addWidget(who)

        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        tiles.addWidget(StatTile("Sessions", str(summary.total_sessions)), 1)
        tiles.addWidget(StatTile("Time / Score", str(summary.by_mode[GameMode.TIME_SCORE]), "sessions"), 1)
        tiles.addWidget(StatTile("Open / Close", str(summary.by_mode[GameMode.OPEN_CLOSE]), "sessions"), 1)
        tiles.addWidget(StatTile("Last session", summary.last_date or "-"), 1)
        self.body.addLayout(tiles)

        self.body.addWidget(self._build_trend())
        self.body.addWidget(self._build_table())

    def _build_trend(self) -> Card:
        card = Card(padding=22, spacing=14)

        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        for mode in GameMode:
            if not sessions_in_mode(self._sessions, mode):
                continue
            tab = Tab(mode.title)
            tab.setChecked(mode is self._mode)
            tab.clicked.connect(lambda _c=False, m=mode: self._select_mode(m))
            tabs.addWidget(tab)
        tabs.addStretch(1)
        card.body.addLayout(tabs)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        for field in FIELD_MAP[self._mode]:
            chip = Chip(field.label)
            chip.setChecked(field.name == self._metric)
            chip.clicked.connect(lambda _c=False, n=field.name: self._select_metric(n))
            chips.addWidget(chip)
        chips.addStretch(1)
        card.body.addLayout(chips)

        subset = sessions_in_mode(self._sessions, self._mode)
        series = metric_series(subset, self._metric)
        index = [f.name for f in FIELD_MAP[self._mode]].index(self._metric)

        stats = QHBoxLayout()
        stats.setSpacing(30)
        for caption, value in (
            ("Latest", format_value(series.metric, series.latest)),
            ("Best", format_value(series.metric, series.best)),
            ("Change since first", "-" if series.change is None else f"{series.change:+g}"),
        ):
            column = QVBoxLayout()
            column.setSpacing(0)
            column.addWidget(label(caption, "caption"))
            column.addWidget(label(value, "h1"))
            stats.addLayout(column)
        stats.addStretch(1)
        card.body.addLayout(stats)

        chart = LineChart()
        chart.set_series(series, theme.SERIES[index % len(theme.SERIES)])
        card.body.addWidget(chart)
        if len(subset) == 1:
            card.body.addWidget(label("Only one session so far - a trend appears after the second.", "caption"))
        return card

    def _build_table(self) -> Card:
        card = Card(padding=22, spacing=12)
        card.body.addWidget(label(f"{self._mode.title} sessions", "h2"))

        subset = list(reversed(sessions_in_mode(self._sessions, self._mode)))
        fields = FIELD_MAP[self._mode]
        headers = ["Date", "Report", *[f.axis_label for f in fields]]

        table = QTableWidget(len(subset), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        for r, session in enumerate(subset):
            cells = [
                session.date or "-",
                "-" if session.report_id is None else f"#{session.report_id}",
                *[f"{session.metrics[f.name]:g}" for f in fields],
            ]
            for c, text in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(text))

        height = 46 + 44 * len(subset) + 4
        table.setFixedHeight(height)
        table.cellDoubleClicked.connect(lambda row, _col, rows=subset: SessionDetail(rows[row], self).exec())
        card.body.addWidget(table)
        card.body.addWidget(label("Double-click a row for the full report.", "caption"))
        return card

    # -- interaction ----------------------------------------------------------------------------

    def _select_mode(self, mode: GameMode) -> None:
        self._mode = mode
        self._metric = DEFAULT_METRIC[mode]
        self._render()

    def _select_metric(self, name: str) -> None:
        self._metric = name
        self._render()

    def _open_report(self) -> None:
        text = self.report_field.text()
        if not text:
            self.report_field.set_error("Enter a numeric report number")
            return
        number = int(text)
        client = self.state.client

        def done(session: Session | None) -> None:
            if session is None:
                self.report_field.set_error(f"No report numbered {number}")
                return
            SessionDetail(session, self).exec()

        def failed(exc: Exception) -> None:
            self.notice.set(str(exc), "danger")
            self.notice.setVisible(True)

        run_async(lambda: client.session_by_report_id(number), done, failed, owner=self)

    # -- export -----------------------------------------------------------------------------------

    def _export(self, suffix: str, caption: str, pattern: str, write) -> None:
        if not self._sessions or self._patient_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, caption, default_filename(self._patient_id, suffix), pattern
        )
        if not path:
            return
        try:
            written = write(path)
        except OSError as exc:
            self.notice.set(f"Could not write the file: {exc}", "danger")
        else:
            self.notice.set(f"Saved {written}", "success")
        self.notice.setVisible(True)

    def _export_csv(self) -> None:
        self._export("csv", "Export sessions as CSV", "CSV files (*.csv)",
                     lambda p: sessions_to_csv(self._sessions, p))

    def _export_pdf(self) -> None:
        self._export("pdf", "Export progress report", "PDF files (*.pdf)",
                     lambda p: sessions_to_pdf(self._sessions, p, patient_name=self._patient_name()))
