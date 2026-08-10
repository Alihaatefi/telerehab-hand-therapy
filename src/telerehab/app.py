"""Application shell: window setup and navigation between screens.

Navigation is a flat loop over a small set of states. The original expressed
the same flow as pages calling each other — ``mode_selection_screen`` ran at
import time, then each page invoked the next one from inside its own event
loop, so "back" recursed instead of returning and the call stack grew for the
whole session. Here every screen returns a value and this module decides what
happens next.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Sequence

import pygame

from .api import BackendError, GameMode, Session, TeleRehabClient
from .config import GameConfig, Settings, load_settings
from .ui import theme
from .ui.screens import (
    BACK,
    QUIT,
    Context,
    MenuScreen,
    MessageScreen,
    Quit,
    FormScreen,
)
from .ui.widgets import TextField

logger = logging.getLogger(__name__)

MENU_TIME_SCORE = "time_score"
MENU_OPEN_CLOSE = "open_close"
MENU_REPORTS = "reports"
MENU_QUIT = "quit"

REPORT_BY_PATIENT = "by_patient"
REPORT_BY_SESSION = "by_session"
REPORT_TREND = "trend"


class Application:
    """Owns the pygame window, the backend client, and the navigation loop."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.client = TeleRehabClient(self.settings.backend)
        self.ctx: Context | None = None
        self._tracker = None

    # -- setup -------------------------------------------------------------

    def _init_pygame(self) -> Context:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            logger.info("no audio device; running without sound")

        size = self.settings.game.window_size
        screen = pygame.display.set_mode(size)
        pygame.display.set_caption("TeleRehab - Hand Therapy")
        return Context(
            screen=screen,
            clock=pygame.time.Clock(),
            fonts=theme.Fonts.build(),
            fps=self.settings.game.fps,
        )

    def _tracker_for_session(self):
        """Open the camera lazily, and only once per process."""
        from .vision.hand_tracker import HandTracker

        if self._tracker is None:
            self._tracker = HandTracker(self.settings.vision).open()
        return self._tracker

    def _release_tracker(self) -> None:
        if self._tracker is not None:
            self._tracker.close()
            self._tracker = None

    # -- helpers -----------------------------------------------------------

    def _notify(self, title: str, lines: Sequence[str] = ()) -> None:
        assert self.ctx is not None
        MessageScreen(self.ctx, title, lines).run()

    def _backend_banner(self) -> str:
        return (
            f"Backend: {self.settings.backend.base_url}"
            if self.client.ping()
            else "Backend unreachable - start mock_server/server.py"
        )

    # -- entry point -------------------------------------------------------

    def run(self) -> int:
        self.ctx = self._init_pygame()
        try:
            self._main_loop()
        finally:
            self._release_tracker()
            self.client.close()
            pygame.quit()
        return 0

    def _main_loop(self) -> None:
        assert self.ctx is not None

        while True:
            choice = MenuScreen(
                self.ctx,
                "Select an exercise",
                [
                    ("Time / Score Mode", MENU_TIME_SCORE, theme.PRIMARY),
                    ("Open / Close Mode", MENU_OPEN_CLOSE, theme.DANGER),
                    ("Reports", MENU_REPORTS, theme.SUCCESS),
                    ("Quit", MENU_QUIT, (90, 90, 90)),
                ],
            ).run()

            if isinstance(choice, Quit) or choice == MENU_QUIT:
                return

            if choice == MENU_REPORTS:
                if self._reports_flow() is QUIT:
                    return
                continue

            mode = (
                GameMode.TIME_SCORE
                if choice == MENU_TIME_SCORE
                else GameMode.OPEN_CLOSE
            )
            if self._exercise_flow(mode) is QUIT:
                return

    # -- authentication ----------------------------------------------------

    def _authenticate(self) -> int | Quit | str | None:
        """Returns a patient id, ``BACK``, or ``QUIT``."""
        assert self.ctx is not None

        while True:
            choice = MenuScreen(
                self.ctx,
                "Patient",
                [
                    ("Log in with patient ID", "login", theme.PRIMARY),
                    ("Register a new patient", "signup", theme.DANGER),
                ],
                back_label="Back",
            ).run()

            if isinstance(choice, Quit):
                return QUIT
            if choice == BACK:
                return BACK

            result = self._login() if choice == "login" else self._register()
            if isinstance(result, Quit):
                return QUIT
            if result != BACK:
                return result

    def _login(self) -> int | Quit | str:
        assert self.ctx is not None
        field = TextField(
            pygame.Rect(40, 180, 320, 44), label="Patient ID", kind="int"
        )

        def submit(group) -> int | str:
            patient_id = group.fields[0].as_int(default=-1)
            if patient_id < 0:
                return "Enter a numeric patient ID"
            try:
                patient = self.client.get_patient(patient_id)
            except BackendError as exc:
                return str(exc)
            if patient is None:
                return f"No patient with ID {patient_id}"
            return patient.id

        return FormScreen(
            self.ctx,
            title="Log in",
            fields=[field],
            submit_label="Log in",
            on_submit=submit,
        ).run()

    def _register(self) -> int | Quit | str:
        assert self.ctx is not None
        fields = [
            TextField(pygame.Rect(40, 180, 320, 44), label="First name"),
            TextField(pygame.Rect(40, 280, 320, 44), label="Last name"),
        ]

        def submit(group) -> int | str:
            first = group.fields[0].value.strip()
            last = group.fields[1].value.strip()
            if not first:
                return "First name is required"
            try:
                patient = self.client.create_patient(first, last or first)
            except BackendError as exc:
                return str(exc)
            self._notify(
                "Registration complete",
                [f"{patient.display_name}", f"Your patient ID is {patient.id}",
                 "Write it down - you will need it to log in."],
            )
            return patient.id

        return FormScreen(
            self.ctx,
            title="Register",
            fields=fields,
            submit_label="Register",
            on_submit=submit,
        ).run()

    # -- exercise flow -----------------------------------------------------

    def _exercise_flow(self, mode: GameMode) -> Quit | None:
        assert self.ctx is not None

        patient_id = self._authenticate()
        if isinstance(patient_id, Quit):
            return QUIT
        if patient_id == BACK or not isinstance(patient_id, int):
            return None

        config = self._configure(mode)
        if isinstance(config, Quit):
            return QUIT
        if config is None:
            return None

        try:
            tracker = self._tracker_for_session()
        except Exception as exc:  # camera unavailable
            self._notify("Camera unavailable", [str(exc)])
            return None

        if mode is GameMode.TIME_SCORE:
            return self._run_time_score(tracker, patient_id, config)
        return self._run_open_close(tracker, patient_id, config)

    def _configure(self, mode: GameMode) -> GameConfig | Quit | None:
        """Ask for the mode's exercise parameters."""
        assert self.ctx is not None
        base = self.settings.game

        if mode is GameMode.TIME_SCORE:
            fields = [
                TextField(pygame.Rect(40, 170, 320, 44), label="Exercise time (s)",
                          value=str(base.exercise_seconds), kind="int"),
                TextField(pygame.Rect(40, 270, 320, 44), label="Gain",
                          value=str(base.gain), kind="decimal"),
                TextField(pygame.Rect(40, 370, 320, 44), label="Calibration time (s)",
                          value=str(base.calibration_seconds), kind="int"),
            ]

            def submit(group) -> GameConfig | str:
                seconds = group.fields[0].as_int(default=0)
                gain = group.fields[1].as_float(default=0.0)
                calibration = group.fields[2].as_int(default=0)
                if seconds < 5:
                    return "Exercise time must be at least 5 seconds"
                if not 0.1 <= gain <= 5.0:
                    return "Gain must be between 0.1 and 5.0"
                if calibration < 3:
                    return "Calibration needs at least 3 seconds"
                return replace(
                    base, exercise_seconds=seconds, gain=gain,
                    calibration_seconds=calibration,
                )

            title = "Time / Score settings"
        else:
            fields = [
                TextField(pygame.Rect(40, 170, 320, 44), label="Open hold (s)",
                          value=str(base.open_seconds), kind="int"),
                TextField(pygame.Rect(40, 270, 320, 44), label="Closed hold (s)",
                          value=str(base.close_seconds), kind="int"),
                TextField(pygame.Rect(40, 370, 320, 44), label="Repetitions",
                          value=str(base.repetitions), kind="int"),
            ]

            def submit(group) -> GameConfig | str:
                open_s = group.fields[0].as_int(default=0)
                close_s = group.fields[1].as_int(default=0)
                reps = group.fields[2].as_int(default=0)
                if open_s < 1 or close_s < 1:
                    return "Each hold must be at least 1 second"
                if not 1 <= reps <= 50:
                    return "Repetitions must be between 1 and 50"
                return replace(
                    base, open_seconds=open_s, close_seconds=close_s, repetitions=reps
                )

            title = "Open / Close settings"

        result = FormScreen(
            self.ctx, title=title, fields=fields,
            submit_label="Continue", on_submit=submit,
        ).run()

        if isinstance(result, Quit):
            return QUIT
        return None if result == BACK else result

    def _run_time_score(self, tracker, patient_id: int, config: GameConfig):
        from .games.calibrating import RangeCalibrationScreen
        from .games.time_score import TimeScoreGame

        assert self.ctx is not None

        while True:
            calibration = RangeCalibrationScreen(
                self.ctx, tracker, config.calibration_seconds
            ).run()
            if isinstance(calibration, Quit):
                return QUIT
            if not calibration.ready:
                self._notify(
                    "Calibration failed",
                    ["Your hand was not detected, or it did not move enough.",
                     "Check the lighting and try again."],
                )
                continue

            game = TimeScoreGame(
                self.ctx, tracker, calibration,
                patient_id=patient_id,
                game_config=config,
                vision_config=self.settings.vision,
            )
            session = game.run()

            if isinstance(session, Quit):
                return QUIT
            if session is None:
                if game.restart_requested:
                    continue
                return None
            if game.error:
                self._notify("Camera error", [game.error])

            self._finish_session(session, [
                f"Score: {int(session.metrics['score'])}",
                f"Movements: {int(session.metrics['movements'])}",
            ])
            return None

    def _run_open_close(self, tracker, patient_id: int, config: GameConfig):
        from .games.calibrating import TwoPointCalibrationScreen
        from .games.open_close import OpenCloseGame

        assert self.ctx is not None

        calibration = TwoPointCalibrationScreen(self.ctx, tracker).run()
        if isinstance(calibration, Quit):
            return QUIT
        if not calibration.ready:
            return None

        game = OpenCloseGame(
            self.ctx, tracker, calibration,
            patient_id=patient_id, game_config=config,
        )
        session = game.run()

        if isinstance(session, Quit):
            return QUIT
        if session is None:
            return None
        if game.error:
            self._notify("Camera error", [game.error])

        completed = int(session.metrics["completed_repetitions"])
        self._finish_session(session, [
            f"Completed {completed} of {config.repetitions} repetitions",
        ])
        return None

    def _finish_session(self, session: Session, summary: Sequence[str]) -> None:
        """Persist a finished session and show the result, then its chart."""
        assert self.ctx is not None

        try:
            stored = self.client.save_session(session)
        except BackendError as exc:
            self._notify(
                "Session not saved",
                [*summary, "", "The results could not be sent to the backend:",
                 str(exc)],
            )
            return

        self._notify(
            "Session complete",
            [*summary, "", f"Saved as report #{stored.report_id}"],
        )
        self._show_charts([stored], caption=f"Report #{stored.report_id}")

    # -- reports -----------------------------------------------------------

    def _show_charts(self, sessions: Sequence[Session], *, caption: str = "") -> None:
        from .reports import ChartViewer, session_chart

        assert self.ctx is not None
        if not sessions:
            self._notify("Nothing to show", ["No sessions matched."])
            return

        ChartViewer(
            self.ctx, [session_chart(s) for s in sessions], caption=caption
        ).run()

    def _reports_flow(self) -> Quit | None:
        assert self.ctx is not None

        while True:
            choice = MenuScreen(
                self.ctx,
                "Reports",
                [
                    ("All sessions for a patient", REPORT_BY_PATIENT, theme.PRIMARY),
                    ("A single report by number", REPORT_BY_SESSION, theme.DANGER),
                    ("Progress over time", REPORT_TREND, theme.ACCENT),
                ],
                back_label="Back",
            ).run()

            if isinstance(choice, Quit):
                return QUIT
            if choice == BACK:
                return None

            outcome = {
                REPORT_BY_PATIENT: self._report_by_patient,
                REPORT_BY_SESSION: self._report_by_session,
                REPORT_TREND: self._report_trend,
            }[choice]()

            if outcome is QUIT:
                return QUIT

    def _ask_id(self, title: str, label: str):
        assert self.ctx is not None

        def submit(group) -> int | str:
            value = group.fields[0].as_int(default=-1)
            return value if value >= 0 else f"Enter a numeric {label.lower()}"

        return FormScreen(
            self.ctx,
            title=title,
            fields=[TextField(pygame.Rect(40, 180, 320, 44), label=label, kind="int")],
            submit_label="Show",
            on_submit=submit,
        ).run()

    def _report_by_patient(self) -> Quit | None:
        patient_id = self._ask_id("Report by patient", "Patient ID")
        if isinstance(patient_id, Quit):
            return QUIT
        if patient_id == BACK:
            return None

        try:
            sessions = self.client.sessions_for_patient(int(patient_id))
        except BackendError as exc:
            self._notify("Backend error", [str(exc)])
            return None

        if not sessions:
            self._notify("No data", [f"No sessions stored for patient {patient_id}."])
            return None

        self._show_charts(sessions, caption=f"Patient {patient_id}")
        return None

    def _report_by_session(self) -> Quit | None:
        report_id = self._ask_id("Report by number", "Report number")
        if isinstance(report_id, Quit):
            return QUIT
        if report_id == BACK:
            return None

        try:
            session = self.client.session_by_report_id(int(report_id))
        except BackendError as exc:
            self._notify("Backend error", [str(exc)])
            return None

        if session is None:
            self._notify("No data", [f"No report numbered {report_id}."])
            return None

        self._show_charts([session], caption=f"Report #{report_id}")
        return None

    def _report_trend(self) -> Quit | None:
        from .reports import ChartViewer, progress_chart

        assert self.ctx is not None
        patient_id = self._ask_id("Progress over time", "Patient ID")
        if isinstance(patient_id, Quit):
            return QUIT
        if patient_id == BACK:
            return None

        try:
            sessions = self.client.sessions_for_patient(int(patient_id))
        except BackendError as exc:
            self._notify("Backend error", [str(exc)])
            return None

        charts: list[bytes] = []
        for mode, metric in (
            (GameMode.TIME_SCORE, "score"),
            (GameMode.OPEN_CLOSE, "completed_repetitions"),
        ):
            subset = [s for s in sessions if s.mode is mode]
            if len(subset) >= 2:
                charts.append(progress_chart(subset, metric))

        if not charts:
            self._notify(
                "Not enough history",
                [f"Patient {patient_id} needs at least two sessions",
                 "in the same mode before a trend can be plotted."],
            )
            return None

        ChartViewer(self.ctx, charts, caption=f"Patient {patient_id}").run()
        return None


def run(settings: Settings | None = None) -> int:
    return Application(settings).run()
