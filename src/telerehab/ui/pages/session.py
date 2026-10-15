"""The exercise itself: the garden scene, the heads-up display and the live camera.

The page owns no rules. It feeds each camera frame to the engine
(:class:`~telerehab.games.TimeScoreEngine` or
:class:`~telerehab.games.OpenCloseEngine`), reads the engine's state back, and
draws it.
"""
from __future__ import annotations

import contextlib
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...api import GameMode, Patient
from ...config import TRACK_WIDTH, GameConfig
from ...games import OpenCloseEngine, TimeScoreEngine
from ...vision.calibration import CalibrationError
from .. import art, icons, theme
from ..camera import CameraController
from ..state import AppState
from ..widgets import CameraView, Page, Pill, ProgressRing, button, label

#: Where the Open/Close butterfly's journey ends, in track units.
OPEN_CLOSE_GOAL = 750.0

COUNTDOWN = ("3", "2", "1", "Go")


def clock_text(seconds: float) -> str:
    seconds = max(0, math.ceil(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class GameStage(QWidget):
    """Paints the scene and animates the butterfly towards where the engine says it is."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(640, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.target_x = 0.0
        self.flower_x = TRACK_WIDTH / 2
        self.dwell = 0.0
        self.bloom = 1.0
        self.alert = False
        self.paused = False
        self.banner: str | None = None  # big centred text, e.g. the countdown

        self._x = 0.0
        self._phase = 0.0
        self._background: QPixmap | None = None
        self._background_key: tuple | None = None
        self._last = time.monotonic()

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._last = time.monotonic()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self.target_x = self._x = 0.0
        self.dwell = 0.0
        self.alert = False
        self.paused = False
        self.banner = None
        self.update()

    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(0.1, now - self._last)
        self._last = now

        # The engine already smooths the signal; this only keeps motion fluid
        # between camera frames, which arrive at a lower rate than the display.
        self._x += (self.target_x - self._x) * min(1.0, dt * 9.0)
        speed = abs(self.target_x - self._x)
        rate = (3.0 if self.alert else 8.0) + min(9.0, speed * 0.04)
        self._phase += dt * rate
        self.update()

    # -- painting -----------------------------------------------------------------------

    def _scene(self) -> QPixmap:
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio)
        if self._background is None or key != self._background_key:
            pixmap = QPixmap(int(self.width() * ratio), int(self.height() * ratio))
            pixmap.setDevicePixelRatio(ratio)
            painter = QPainter(pixmap)
            art.draw_scene(painter, QRectF(0, 0, self.width(), self.height()))
            painter.end()
            self._background, self._background_key = pixmap, key
        return self._background

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self._scene())

        w, h = self.width(), self.height()
        margin = w * 0.09

        def sx(x: float) -> float:
            return margin + (x / TRACK_WIDTH) * (w - 2 * margin)

        ground = h * art.GROUND
        fly_y = h * art.FLIGHT_LINE

        flower_size = max(56.0, min(120.0, h * 0.15))
        flower = QPointF(sx(self.flower_x), fly_y)
        art.draw_flower(
            painter, flower, flower_size,
            bloom=self.bloom, glow=min(1.0, self.dwell * 1.2), stem_to=ground + h * 0.03,
        )
        if self.dwell > 0:
            ring = QPen(theme.qcolor("#FFFFFF", 0.95), 6)
            ring.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(ring)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            radius = flower_size * 0.78
            painter.drawArc(
                QRectF(flower.x() - radius, flower.y() - radius, radius * 2, radius * 2),
                90 * 16, -int(self.dwell * 360 * 16),
            )

        size = max(80.0, min(170.0, h * 0.22))
        bx = sx(self._x)
        by = fly_y + math.sin(self._phase * 0.35) * h * 0.012

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor("#0B3D2B", 0.14))
        painter.drawEllipse(QPointF(bx, ground + h * 0.05), size * 0.30, size * 0.045)

        tilt = max(-14.0, min(14.0, (self.target_x - self._x) * 0.05))
        art.draw_butterfly(painter, QPointF(bx, by), size, self._phase, tilt, alert=self.alert)

        if self.paused or self.banner:
            painter.fillRect(self.rect(), theme.qcolor("#0A1F26", 0.55 if self.paused else 0.28))
            painter.setPen(theme.qcolor("#FFFFFF"))
            if self.paused:
                painter.setFont(theme.app_font(44, QFont.Weight.Bold))
                painter.drawText(self.rect().adjusted(0, -20, 0, -20), int(Qt.AlignmentFlag.AlignCenter), "Paused")
                painter.setFont(theme.app_font(16))
                painter.setPen(theme.qcolor("#D6E4E8"))
                painter.drawText(self.rect().adjusted(0, 70, 0, 70), int(Qt.AlignmentFlag.AlignCenter), "Press Space or Resume to continue")
            else:
                painter.setFont(theme.app_font(96, QFont.Weight.Bold))
                painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.banner or "")


class HudCard(QFrame):
    """A translucent panel floating over the scene."""

    def __init__(self, padding: int = 14, spacing: int = 8, *, horizontal: bool = False):
        super().__init__()
        self.setProperty("hud", True)
        self.body = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)


class StatColumn(QWidget):
    def __init__(self, caption: str):
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.caption = label(caption, "caption")
        self.value = label("-", "h1")
        column.addWidget(self.caption)
        column.addWidget(self.value)

    def set(self, text: str) -> None:
        self.value.setText(text)


class SessionPage(Page):
    done = Signal(object, object)  # (Session | None, error message | None)
    restart = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.mode = GameMode.TIME_SCORE
        self.engine: TimeScoreEngine | OpenCloseEngine | None = None
        self._camera: CameraController | None = None
        self._calibration = None
        self._config: GameConfig | None = None
        self._patient: Patient | None = None
        self._count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 8, 36, 28)

        self.stage = GameStage()
        overlay = QVBoxLayout(self.stage)
        overlay.setContentsMargins(18, 18, 18, 18)
        root.addWidget(self.stage)

        # -- top row: stats, posture prompt, camera ------------------------------------
        top = QHBoxLayout()
        top.setSpacing(14)

        self.stats = HudCard(16, horizontal=True)
        self.stats.body.setSpacing(26)
        self.stat_columns = [StatColumn("Score"), StatColumn("Time left"), StatColumn("Movements")]
        for column in self.stat_columns:
            self.stats.body.addWidget(column)
        top.addWidget(self.stats, 0, Qt.AlignmentFlag.AlignTop)

        top.addStretch(1)
        self.prompt = HudCard(14, 10, horizontal=True)
        self.prompt_label = label("", "h1")
        self.hold_ring = ProgressRing(64, 7)
        self.prompt.body.addWidget(self.prompt_label)
        self.prompt.body.addWidget(self.hold_ring)
        top.addWidget(self.prompt, 0, Qt.AlignmentFlag.AlignTop)
        top.addStretch(1)

        pip = QFrame()
        pip.setFixedSize(236, 178)
        pip.setStyleSheet(f"background: {theme.STAGE_DARK}; border-radius: 16px;")
        pip_layout = QVBoxLayout(pip)
        pip_layout.setContentsMargins(0, 0, 0, 0)
        self.pip = CameraView(compact=True, radius=16)
        pip_layout.addWidget(self.pip)
        top.addWidget(pip, 0, Qt.AlignmentFlag.AlignTop)
        overlay.addLayout(top)
        overlay.addStretch(1)

        # -- bottom row: status and controls -----------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        self.status_card = HudCard(10, horizontal=True)
        self.status = Pill("", "neutral")
        self.status_card.body.addWidget(self.status)
        bottom.addWidget(self.status_card, 0, Qt.AlignmentFlag.AlignBottom)
        bottom.addStretch(1)

        controls = HudCard(10, 8, horizontal=True)
        self.pause_button = button("Pause", icon="pause")
        self.restart_button = button("Restart", icon="rotate-ccw")
        self.finish_button = button("Finish", "danger", icon="square")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.restart_button.clicked.connect(self._ask_restart)
        self.finish_button.clicked.connect(self._ask_finish)
        for widget in (self.pause_button, self.restart_button, self.finish_button):
            controls.body.addWidget(widget)
        bottom.addWidget(controls, 0, Qt.AlignmentFlag.AlignBottom)
        overlay.addLayout(bottom)

        for key, handler in (
            (Qt.Key.Key_Space, self.toggle_pause),
            (Qt.Key.Key_P, self.toggle_pause),
            (Qt.Key.Key_Escape, self._ask_finish),
        ):
            QShortcut(QKeySequence(key), self).activated.connect(handler)

        self._countdown = QTimer(self)
        self._countdown.setInterval(800)
        self._countdown.timeout.connect(self._count_down)

        self._hud_timer = QTimer(self)
        self._hud_timer.setInterval(100)
        self._hud_timer.timeout.connect(self._tick)

    # -- lifecycle -------------------------------------------------------------------------------

    def begin(
        self,
        mode: GameMode,
        calibration,
        config: GameConfig,
        patient: Patient,
        camera: CameraController,
    ) -> None:
        self.end()
        self.mode = mode
        self._calibration = calibration
        self._config = config
        self._patient = patient
        self._camera = camera
        self.engine = None

        time_score = mode is GameMode.TIME_SCORE
        self.restart_button.setVisible(time_score)
        self.prompt.setVisible(not time_score)
        if time_score:
            captions = ("Score", "Time left", "Movements")
        else:
            captions = ("Repetition", "Hold left", "Completed")
        for column, caption in zip(self.stat_columns, captions, strict=False):
            column.caption.setText(caption)
            column.set("-")

        self.stage.reset()
        self.stage.flower_x = TRACK_WIDTH / 2 if time_score else OPEN_CLOSE_GOAL
        self.stage.bloom = 1.0
        self.stage.start()
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(False)
        self.pip.clear()
        self._set_status("Get ready", "info")

        camera.sample.connect(self._on_sample)
        camera.failed.connect(self._on_camera_failed)
        camera.start()

        self._count = 0
        self.stage.banner = COUNTDOWN[0]
        self._countdown.start()
        self._hud_timer.start()

    def end(self) -> None:
        self._countdown.stop()
        self._hud_timer.stop()
        self.stage.stop()
        camera = self._camera
        if camera is not None:
            for signal, slot in ((camera.sample, self._on_sample), (camera.failed, self._on_camera_failed)):
                with contextlib.suppress(RuntimeError, TypeError):
                    signal.disconnect(slot)
        self._camera = None
        self.engine = None

    def _count_down(self) -> None:
        self._count += 1
        if self._count < len(COUNTDOWN):
            self.stage.banner = COUNTDOWN[self._count]
            return
        self._countdown.stop()
        self.stage.banner = None
        self._start_engine()

    def _start_engine(self) -> None:
        assert self._config is not None and self._patient is not None
        assert self._calibration is not None
        # The engine is created only now: its timers start when it is built, so
        # the patient gets the full prescribed time after the countdown.
        if self.mode is GameMode.TIME_SCORE:
            self.engine = TimeScoreEngine(
                self._calibration,
                patient_id=self._patient.id,
                game_config=self._config,
                vision_config=self.state.settings.vision,
            )
        else:
            self.engine = OpenCloseEngine(
                self._calibration,
                patient_id=self._patient.id,
                game_config=self._config,
            )
        self.pause_button.setEnabled(True)
        self._sync()

    # -- camera -------------------------------------------------------------------------------------

    def _on_sample(self, sample) -> None:
        self.pip.set_sample(sample)
        engine = self.engine
        if engine is None:
            return

        try:
            event = engine.update(sample)
        except CalibrationError as exc:  # a calibrator that is not ready: stop cleanly
            self._finish(str(exc))
            return

        if event:
            self.state.play_chime()
        self._sync()
        if engine.finished:
            self._finish()

    def _on_camera_failed(self, message: str) -> None:
        self._finish(f"The camera stopped working: {message}")

    # -- display ---------------------------------------------------------------------------------------

    def _set_status(self, text: str, kind: str) -> None:
        self.status.set(text, kind)

    def _tick(self) -> None:
        engine = self.engine
        if engine is None:
            return
        self._sync()
        if engine.finished:
            self._finish()

    def _sync(self) -> None:
        engine = self.engine
        stage = self.stage
        if engine is None:
            return

        if isinstance(engine, TimeScoreEngine):
            stage.target_x = engine.butterfly_x
            stage.flower_x = engine.flower.x
            stage.dwell = engine.flower.hold_progress() if engine.flower.is_settling else 0.0
            stage.alert = not engine.hand_visible
            stage.paused = engine.paused

            self.stat_columns[0].set(str(engine.score))
            self.stat_columns[1].set(clock_text(engine.timer.remaining))
            self.stat_columns[2].set(str(engine.movements.count))
            if engine.paused:
                self._set_status("Paused", "neutral")
            elif engine.hand_visible:
                self._set_status("Hand detected - the butterfly follows you", "success")
            else:
                self._set_status("No hand detected - move into view", "warning")
            return

        stage.target_x = engine.timer.progress * OPEN_CLOSE_GOAL
        stage.flower_x = OPEN_CLOSE_GOAL
        stage.bloom = 1.0 if engine.target_open else 0.08
        stage.dwell = 0.0
        stage.alert = not engine.posture_correct
        stage.paused = engine.paused

        posture = "OPEN" if engine.target_open else "CLOSED"
        self.prompt_label.setText(f"Keep your hand {posture.lower()}")
        self.hold_ring.set_value(engine.timer.progress)
        self.hold_ring.set_text(f"{engine.timer.remaining:.0f}")
        self.stat_columns[0].set(f"{engine.repetition} / {engine.config.repetitions}")
        self.stat_columns[1].set(f"{engine.timer.remaining:.1f} s")
        self.stat_columns[2].set(str(engine.completed_repetitions))

        if engine.paused:
            self._set_status("Paused", "neutral")
        elif engine.hand_open is None:
            self._set_status("No hand detected - move into view", "warning")
        elif engine.posture_correct:
            self._set_status("Posture correct - keep holding", "success")
        else:
            self._set_status(f"Adjust your hand - it should be {posture.lower()}", "danger")

    # -- controls ----------------------------------------------------------------------------------------

    def toggle_pause(self) -> None:
        engine = self.engine
        if engine is None or not self.isVisible():
            return
        paused = engine.toggle_pause()
        self.pause_button.setText("Resume" if paused else "Pause")
        self.pause_button.setIcon(icons.icon("play" if paused else "pause", theme.TEXT, 18))
        self._sync()

    def _confirm(self, title: str, text: str, detail: str, accept: str) -> bool:
        """Ask a yes/no question with the exercise paused underneath."""
        engine = self.engine
        was_paused = engine.paused if engine is not None else True
        if engine is not None and not was_paused:
            engine.toggle_pause()

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(text)
        box.setInformativeText(detail)
        yes = box.addButton(accept, QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Keep going", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        confirmed = box.clickedButton() is yes

        if engine is not None and not was_paused and not confirmed and self.engine is engine:
            engine.toggle_pause()
        return confirmed

    def _ask_finish(self) -> None:
        if self.engine is None or not self.isVisible():
            return
        if self._confirm(
            "End session?", "End this session now?",
            "Your progress so far will be saved.", "End session",
        ):
            self._finish()

    def _ask_restart(self) -> None:
        if self.engine is None or not self.isVisible():
            return
        if self._confirm(
            "Restart?", "Restart from calibration?",
            "This session's progress will be discarded.", "Restart",
        ):
            self.end()
            self.restart.emit()

    def _finish(self, error: str | None = None) -> None:
        engine = self.engine
        # With no engine yet (the camera failed during the countdown) there is
        # nothing to save, but the failure still has to reach the user.
        session = engine.result() if engine is not None else None
        if session is None and error is None:
            return
        self.end()
        self.done.emit(session, error)
