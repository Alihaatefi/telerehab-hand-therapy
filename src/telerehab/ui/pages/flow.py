"""The exercise flow: setup, calibration, the exercise, then results.

This page is the conductor. It owns the single camera that the calibration and
the exercise share, so the camera is opened once per exercise and released as
soon as the exercise is over — never left running behind a menu.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from ...api import GameMode, Session
from ...config import GameConfig
from ..camera import CameraController
from ..state import AppState
from ..widgets import Page, Stepper, button, label
from .calibration import CalibrationPage
from .results import ResultsPage
from .session import SessionPage
from .setup import TITLES, SetupPage

STEP_NAMES = ["Setup", "Calibrate", "Exercise", "Results"]
SETUP, CALIBRATE, EXERCISE, RESULTS = range(4)


class ExerciseFlowPage(Page):
    exited = Signal()
    openReports = Signal(int)  # patient id

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.mode = GameMode.TIME_SCORE
        self._config: GameConfig | None = None
        self._camera: CameraController | None = None
        self._camera_key: tuple | None = None
        self._step = SETUP

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("Page")
        bar = QHBoxLayout(header)
        bar.setContentsMargins(36, 22, 36, 14)
        bar.setSpacing(18)

        self.exit_button = button("Exit", "ghost", icon="x")
        self.exit_button.clicked.connect(self._exit_clicked)
        bar.addWidget(self.exit_button)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.eyebrow = label("", "eyebrow")
        self.title = label("", "h2")
        titles.addWidget(self.eyebrow)
        titles.addWidget(self.title)
        bar.addLayout(titles)
        bar.addStretch(1)

        self.stepper = Stepper(STEP_NAMES)
        self.stepper.setMinimumWidth(560)
        bar.addWidget(self.stepper, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(header)

        self.setup = SetupPage(state)
        self.calibration = CalibrationPage()
        self.session = SessionPage(state)
        self.results = ResultsPage(state)

        self.stack = QStackedWidget()
        for page in (self.setup, self.calibration, self.session, self.results):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        self.setup.back.connect(self.leave)
        self.setup.accepted.connect(self._begin_calibration)
        self.calibration.back.connect(self._back_to_setup)
        self.calibration.done.connect(self._begin_session)
        self.session.restart.connect(self._restart)
        self.session.done.connect(self._show_results)
        self.results.again.connect(lambda: self.start(self.mode))
        self.results.home.connect(self.leave)
        self.results.viewReports.connect(self._view_reports)

    # -- camera -------------------------------------------------------------------------------

    def _camera_controller(self) -> CameraController:
        """One camera per exercise, rebuilt if the camera settings changed."""
        vision = self.state.settings.vision
        key = (vision.demo, vision.camera_index)
        if self._camera is None or key != self._camera_key:
            self._release_camera()
            self._camera = CameraController(self.state.tracker_factory(), self)
            self._camera_key = key
        return self._camera

    def _release_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._camera.deleteLater()
            self._camera = None

    def stop(self) -> None:
        """Stop everything that runs: pages first, then the camera."""
        self.calibration.end()
        self.session.end()
        self._release_camera()

    # -- navigation -------------------------------------------------------------------------------

    def start(self, mode: GameMode) -> None:
        self.stop()
        self.mode = mode
        eyebrow, _ = TITLES[mode]
        self.eyebrow.setText(eyebrow.upper())
        self.title.setText("Butterfly Garden" if mode is GameMode.TIME_SCORE else "Posture Holds")
        self.setup.configure(mode, self.state.settings.game)
        self._go(SETUP)

    def _go(self, step: int) -> None:
        self._step = step
        self.stepper.set_current(step)
        self.stack.setCurrentIndex(step)

    def _back_to_setup(self) -> None:
        self.stop()
        self._go(SETUP)

    def _begin_calibration(self, config: GameConfig) -> None:
        self._config = config
        self._go(CALIBRATE)
        self.calibration.begin(self.mode, config, self._camera_controller())

    def _restart(self) -> None:
        assert self._config is not None
        self._begin_calibration(self._config)

    def _begin_session(self, calibration) -> None:
        patient = self.state.patient
        assert self._config is not None and patient is not None
        self.calibration.end()
        self._go(EXERCISE)
        self.session.begin(self.mode, calibration, self._config, patient, self._camera_controller())

    def _show_results(self, session: Session | None, error: str | None) -> None:
        self._release_camera()
        self._go(RESULTS)
        self.results.show_result(session, error)

    def _view_reports(self, patient_id: int) -> None:
        self.stop()
        self.openReports.emit(patient_id)

    def leave(self) -> None:
        self.stop()
        self.exited.emit()

    def _exit_clicked(self) -> None:
        # Mid-exercise, leaving goes through the same "end the session?" question
        # as the Finish button, so progress is saved rather than silently lost.
        if self._step == EXERCISE and self.session.engine is not None:
            self.session._ask_finish()
            return
        self.leave()

    def on_hide(self) -> None:
        self.stop()
