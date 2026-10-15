"""Calibration: learn this patient's own range before the exercise starts."""
from __future__ import annotations

import contextlib
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from ...api import GameMode
from ...config import GameConfig
from ...games import RangeCalibrationTask, TwoPointCalibrationTask
from .. import icons, theme
from ..camera import CameraController
from ..widgets import (
    Banner,
    CameraView,
    Card,
    Page,
    Pill,
    ProgressRing,
    button,
    clear_layout,
    label,
)


class CalibrationPage(Page):
    done = Signal(object)  # RangeCalibration | TwoPointCalibration
    back = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.mode = GameMode.TIME_SCORE
        self._camera: CameraController | None = None
        self._config: GameConfig | None = None
        self._range: RangeCalibrationTask | None = None
        self._two: TwoPointCalibrationTask | None = None
        self._last = None
        self._clock = time.monotonic
        self._last_time = 0.0

        row = QHBoxLayout(self)
        row.setContentsMargins(36, 8, 36, 28)
        row.setSpacing(20)

        self.view = CameraView()
        row.addWidget(self.view, 3)

        panel = Card(padding=26, spacing=14)
        panel.setMinimumWidth(360)
        panel.setMaximumWidth(440)
        self.panel = panel
        row.addWidget(panel, 2)

        self.eyebrow = label("", "eyebrow")
        self.title = label("", "h1", wrap=True)
        self.text = label("", "muted", wrap=True)
        for widget in (self.eyebrow, self.title, self.text):
            panel.body.addWidget(widget)

        self.modes = QStackedWidget()
        self.modes.addWidget(self._build_range())
        self.modes.addWidget(self._build_two_point())
        panel.body.addWidget(self.modes, 1)

        self.banner = Banner("", "warning")
        self.banner.setVisible(False)
        panel.body.addWidget(self.banner)

        footer = QHBoxLayout()
        self.back_button = button("Back", "ghost", icon="arrow-left")
        self.back_button.clicked.connect(self.back)
        footer.addWidget(self.back_button)
        footer.addStretch(1)
        self.retry_button = button("Try again", icon="refresh")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self._retry)
        footer.addWidget(self.retry_button)
        panel.body.addLayout(footer)

        # O and C only act in their own step, as the on-screen prompts say.
        for key, handler in (
            ("O", lambda: self._capture(TwoPointCalibrationTask.OPEN)),
            ("C", lambda: self._capture(TwoPointCalibrationTask.CLOSED)),
            ("S", self._confirm),
            ("R", self._redo),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(handler)

    # -- panels ----------------------------------------------------------------------------

    def _build_range(self) -> QWidget:
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 8, 0, 0)
        column.setSpacing(14)
        column.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.ring = ProgressRing(170, 12)
        column.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self.range_pill = Pill("Waiting for your hand", "warning")
        column.addWidget(self.range_pill, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addStretch(1)
        return page

    def _build_two_point(self) -> QWidget:
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 8, 0, 0)
        column.setSpacing(12)
        column.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.steps_box = QVBoxLayout()
        self.steps_box.setSpacing(10)
        column.addLayout(self.steps_box)

        self.action = button("", "primary", size="lg")
        self.action.clicked.connect(self._action)
        column.addWidget(self.action)
        self.redo_button = button("Redo", "ghost", icon="rotate-ccw")
        self.redo_button.clicked.connect(self._redo)
        column.addWidget(self.redo_button, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)
        return page

    # -- lifecycle ----------------------------------------------------------------------------

    def begin(self, mode: GameMode, config: GameConfig, camera: CameraController) -> None:
        self.end()
        self.mode = mode
        self._config = config
        self._camera = camera
        self._last = None
        self._last_time = self._clock()

        self.view.clear()
        self.view.set_message(None)
        self.banner.setVisible(False)
        self.retry_button.setVisible(False)

        if mode is GameMode.TIME_SCORE:
            self.eyebrow.setText("TIME / SCORE CALIBRATION")
            self.title.setText("Calibrate your range")
            self.text.setText(
                "Slowly open and close your hand as far as is comfortable. "
                "Time only counts while your hand is in view."
            )
            self.modes.setCurrentIndex(0)
            self._start_range()
        else:
            self.eyebrow.setText("OPEN / CLOSE CALIBRATION")
            self.title.setText("Capture two postures")
            self.text.setText("Hold each posture steadily in view, then capture it.")
            self.modes.setCurrentIndex(1)
            self._two = TwoPointCalibrationTask()
            self._render_two_point()

        camera.sample.connect(self._on_sample)
        camera.failed.connect(self._on_camera_failed)
        camera.start()

    def end(self) -> None:
        camera = self._camera
        if camera is not None:
            for signal, slot in ((camera.sample, self._on_sample), (camera.failed, self._on_camera_failed)):
                with contextlib.suppress(RuntimeError, TypeError):
                    signal.disconnect(slot)
        self._camera = None

    # -- Time / Score ---------------------------------------------------------------------------

    def _start_range(self) -> None:
        assert self._config is not None
        self._range = RangeCalibrationTask(self._config.calibration_seconds)
        self.ring.set_value(0.0)
        self.ring.set_text(f"{self._config.calibration_seconds}", "seconds left")
        self.range_pill.set("Waiting for your hand", "warning")
        self.banner.setVisible(False)
        self.retry_button.setVisible(False)

    # -- samples ---------------------------------------------------------------------------------

    def _on_sample(self, sample) -> None:
        now = self._clock()
        dt = min(0.25, max(0.0, now - self._last_time))
        self._last_time = now

        self._last = sample
        self.view.set_sample(sample)

        task = self._range
        if self.mode is GameMode.TIME_SCORE and task is not None and not task.done:
            task.feed(sample, dt)
            self.ring.set_value(task.progress)
            self.ring.set_text(f"{task.remaining:.0f}", "seconds left")
            if sample.has_hand:
                self.range_pill.set("Calibrating - keep moving", "success")
            else:
                self.range_pill.set("Waiting for your hand", "warning")

            if task.done:
                self._finish_range(task)

    def _finish_range(self, task: RangeCalibrationTask) -> None:
        if task.usable:
            self.done.emit(task.calibration)
            return
        self.banner.set(
            "Your hand was not detected, or it did not move enough. "
            "Check the lighting and try again.",
            "danger",
        )
        self.banner.setVisible(True)
        self.retry_button.setVisible(True)

    def _retry(self) -> None:
        camera = self._camera
        if camera is not None and not camera.running:
            self.view.set_message(None)
            self.banner.setVisible(False)
            self.retry_button.setVisible(False)
            camera.start()
            return
        if self.mode is GameMode.TIME_SCORE:
            self._start_range()

    def _on_camera_failed(self, message: str) -> None:
        self.view.set_message(f"Camera unavailable\n{message}")
        self.banner.set(
            f"The camera could not be used: {message}. Check that no other application "
            "is using it, or switch to the demo camera in Settings.",
            "danger",
        )
        self.banner.setVisible(True)
        self.retry_button.setVisible(True)

    # -- Open / Close -----------------------------------------------------------------------------

    def _render_two_point(self) -> None:
        task = self._two
        if task is None:
            return
        clear_layout(self.steps_box)

        specs = [
            (TwoPointCalibrationTask.OPEN, "Open your hand fully", task.calibration.open_sample),
            (TwoPointCalibrationTask.CLOSED, "Close your hand into a fist", task.calibration.closed_sample),
            (TwoPointCalibrationTask.CONFIRM, "Check and start", None),
        ]
        current = task.step
        for index, (_stage, caption, value) in enumerate(specs):
            done = index < current
            active = index == current

            row = QHBoxLayout()
            row.setSpacing(12)
            badge = QLabel()
            badge.setFixedSize(28, 28)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if done:
                badge.setPixmap(icons.pixmap("check", "#FFFFFF", 16, stroke=2.4))
                badge.setStyleSheet(f"background: {theme.PRIMARY}; border-radius: 14px;")
            else:
                badge.setText(str(index + 1))
                colour = theme.PRIMARY_TEXT if active else theme.TEXT_SUBTLE
                background = theme.PRIMARY_SOFT if active else "#EEF2F6"
                badge.setStyleSheet(
                    f"background: {background}; color: {colour}; font-weight: 700; border-radius: 14px;"
                )
            row.addWidget(badge)

            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(label(caption, "h3" if active or done else "muted"))
            if value is not None:
                text.addWidget(label(f"captured: {value:.3f}", "mono"))
            row.addLayout(text, 1)
            self.steps_box.addLayout(row)

        stage = task.stage
        if stage == TwoPointCalibrationTask.OPEN:
            self.action.setText("Capture open hand   (O)")
        elif stage == TwoPointCalibrationTask.CLOSED:
            self.action.setText("Capture closed hand   (C)")
        else:
            self.action.setText("Start exercise   (S)")
        self.action.setIcon(icons.icon("check" if stage == TwoPointCalibrationTask.CONFIRM else "camera", "#FFFFFF", 18))
        self.redo_button.setVisible(current > 0)

        if task.warning:
            self.banner.set(task.warning, "warning")
            self.banner.setVisible(True)
        elif not self.retry_button.isVisible():
            self.banner.setVisible(False)

    def _action(self) -> None:
        task = self._two
        if self.mode is not GameMode.OPEN_CLOSE or task is None:
            return
        if task.stage == TwoPointCalibrationTask.CONFIRM:
            self._confirm()
        else:
            self._capture()

    def _capture(self, only_stage: str | None = None) -> None:
        task = self._two
        if self.mode is not GameMode.OPEN_CLOSE or task is None or not self.isVisible():
            return
        if task.stage == TwoPointCalibrationTask.CONFIRM:
            return
        if only_stage is not None and task.stage != only_stage:
            return
        task.capture(self._last)
        self._render_two_point()

    def _confirm(self) -> None:
        task = self._two
        if self.mode is not GameMode.OPEN_CLOSE or task is None or not self.isVisible():
            return
        if task.confirm():
            self.done.emit(task.calibration)
        else:
            self._render_two_point()

    def _redo(self) -> None:
        task = self._two
        if self.mode is not GameMode.OPEN_CLOSE or task is None or not self.isVisible():
            return
        task.reset()
        self._render_two_point()
