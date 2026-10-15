"""The application window: a navigation sidebar and the pages it switches between."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..api import GameMode, Patient
from . import icons, theme
from .pages.flow import ExerciseFlowPage
from .pages.home import HomePage
from .pages.patients import PatientsPage
from .pages.reports import ReportsPage
from .pages.settings import SettingsPage
from .state import AppState
from .widgets import Avatar, NavButton, StatusDot, label


class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    NAV = (
        ("home", "Home", "home"),
        ("patients", "Patient", "user"),
        ("reports", "Reports", "bar-chart"),
        ("settings", "Settings", "sliders"),
    )

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._pending_mode: GameMode | None = None

        self.setWindowTitle("TeleRehab - Hand Therapy")
        self.setWindowIcon(QIcon(icons.logo(128)))
        self.resize(1320, 840)
        self.setMinimumSize(1100, 720)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.home = HomePage(state)
        self.patients = PatientsPage(state)
        self.reports = ReportsPage(state)
        self.settings_page = SettingsPage(state)
        self.flow = ExerciseFlowPage(state)
        self.pages = {
            "home": self.home,
            "patients": self.patients,
            "reports": self.reports,
            "settings": self.settings_page,
            "flow": self.flow,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.home.startExercise.connect(self.start_exercise)
        self.home.openPatients.connect(lambda: self.show_page("patients"))
        self.home.openReports.connect(lambda: self.show_page("reports"))
        self.patients.signedIn.connect(self._signed_in)
        self.reports.startExercise.connect(lambda: self.show_page("home"))
        self.flow.exited.connect(lambda: self.show_page("home"))
        self.flow.openReports.connect(self._open_reports_for)

        state.patientChanged.connect(self._refresh_patient)
        state.backendChanged.connect(lambda _ok: self._refresh_status())
        state.settingsChanged.connect(self._refresh_status)

        self._refresh_patient(state.patient)
        self._refresh_status()
        self._current = ""
        self.show_page("home")

    # -- sidebar -----------------------------------------------------------------------

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(248)
        column = QVBoxLayout(side)
        column.setContentsMargins(16, 22, 16, 16)
        column.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        mark = QLabel()
        mark.setPixmap(icons.logo(38))
        brand.addWidget(mark)
        names = QVBoxLayout()
        names.setSpacing(0)
        app_name = label("TeleRehab", "onDark")
        app_name.setStyleSheet("font-size: 16px; font-weight: 700;")
        names.addWidget(app_name)
        names.addWidget(label("Hand Therapy", "onDarkMuted"))
        brand.addLayout(names)
        brand.addStretch(1)
        column.addLayout(brand)
        column.addSpacing(26)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, NavButton] = {}
        for key, text, glyph in self.NAV:
            nav = NavButton(text, glyph)
            nav.clicked.connect(lambda _c=False, k=key: self.show_page(k))
            self.nav_group.addButton(nav)
            self.nav_buttons[key] = nav
            column.addWidget(nav)

        column.addStretch(1)

        self.patient_chip = ClickableFrame()
        self.patient_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.patient_chip.setStyleSheet(
            f"QFrame {{ background: {theme.SIDEBAR_HOVER}; border-radius: 12px; }}"
        )
        self.patient_chip.clicked.connect(lambda: self.show_page("patients"))
        chip = QHBoxLayout(self.patient_chip)
        chip.setContentsMargins(12, 10, 12, 10)
        chip.setSpacing(10)
        self.chip_avatar = Avatar("", 34, on_dark=True)
        chip.addWidget(self.chip_avatar)
        who = QVBoxLayout()
        who.setSpacing(0)
        self.chip_name = label("Not signed in", "onDark")
        self.chip_name.setStyleSheet("font-weight: 600;")
        self.chip_sub = label("Click to sign in", "onDarkMuted")
        self.chip_sub.setStyleSheet(f"color: {theme.SIDEBAR_TEXT}; font-size: 12px;")
        who.addWidget(self.chip_name)
        who.addWidget(self.chip_sub)
        chip.addLayout(who, 1)
        column.addWidget(self.patient_chip)
        column.addSpacing(12)

        self.backend_dot, self.backend_text = self._status_row(column)
        self.camera_dot, self.camera_text = self._status_row(column)
        column.addSpacing(6)
        version = label(f"Version {__version__}", "onDarkMuted")
        version.setStyleSheet(f"color: {theme.SIDEBAR_MUTED}; font-size: 11px;")
        column.addWidget(version)
        return side

    @staticmethod
    def _status_row(column: QVBoxLayout) -> tuple[StatusDot, QLabel]:
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 0, 0)
        row.setSpacing(8)
        dot = StatusDot()
        text = label("", "onDarkMuted")
        text.setStyleSheet(f"color: {theme.SIDEBAR_TEXT}; font-size: 12px;")
        row.addWidget(dot)
        row.addWidget(text, 1)
        column.addLayout(row)
        return dot, text

    def _refresh_patient(self, patient: Patient | None) -> None:
        if patient is None:
            self.chip_avatar.set_name("")
            self.chip_name.setText("Not signed in")
            self.chip_sub.setText("Click to sign in")
        else:
            self.chip_avatar.set_name(patient.display_name)
            self.chip_name.setText(patient.display_name)
            self.chip_sub.setText(f"Patient ID {patient.id}")

    def _refresh_status(self) -> None:
        ok = self.state.backend_ok
        if ok is None:
            self.backend_dot.set_colour(theme.SIDEBAR_MUTED)
            self.backend_text.setText("Checking backend...")
        elif ok:
            self.backend_dot.set_colour(theme.MINT)
            self.backend_text.setText("Backend connected")
        else:
            self.backend_dot.set_colour("#F27C70")
            self.backend_text.setText("Backend unreachable")

        demo = self.state.settings.vision.demo
        self.camera_dot.set_colour("#7FB2FF" if demo else theme.SIDEBAR_TEXT)
        self.camera_text.setText(self.state.camera_label)

    # -- navigation ------------------------------------------------------------------------

    def show_page(self, key: str) -> None:
        previous = self.stack.currentWidget()
        if previous is not None and hasattr(previous, "on_hide"):
            previous.on_hide()

        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self._current = key
        self.sidebar.setVisible(key != "flow")

        if key != "patients":
            # Wandering off the sign-in page abandons the exercise that sent us there.
            self._pending_mode = None
            self.patients.set_notice(None)
        if key in self.nav_buttons:
            self.nav_buttons[key].setChecked(True)
        page.on_show()

    def start_exercise(self, mode: GameMode) -> None:
        if self.state.patient is None:
            self._pending_mode = mode
            self.patients.set_notice(f"Sign in or register to start {mode.title}.")
            self.show_page("patients")
            return
        self.flow.start(mode)
        self.show_page("flow")

    def _signed_in(self, _patient: Patient) -> None:
        mode, self._pending_mode = self._pending_mode, None
        self.patients.set_notice(None)
        if mode is not None:
            self.start_exercise(mode)
        else:
            self.show_page("home")

    def _open_reports_for(self, patient_id: int) -> None:
        self.reports.load_patient(patient_id)
        self.show_page("reports")

    # -- lifecycle ---------------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self.flow.stop()
        self.state.close()
        super().closeEvent(event)
