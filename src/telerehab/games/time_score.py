"""Time/Score mode — "Butterfly Garden".

Hand openness drives the butterfly's horizontal position. Settling on the
flower for half a second scores a point and moves the flower. The session runs
for a fixed time, then reports score and movement count.

The therapeutic dial is ``gain``: it decouples the patient's achievable range
from the distance the butterfly must cover, so the same exercise works for a
hand that opens 20 degrees and one that opens 90.
"""
from __future__ import annotations

import time

import pygame

from ..api.models import Session
from ..config import GameConfig, VisionConfig
from ..ui import theme
from ..ui.screens import Context, Screen
from ..ui.widgets import Button, draw_panel_text, draw_progress_ring
from ..vision.calibration import MovementCounter, RangeCalibration
from ..vision.hand_tracker import CameraError, HandTracker
from .scoring import (
    ButterflySmoother,
    CountdownTimer,
    FlowerTarget,
    butterfly_position,
)

BUTTERFLY_SIZE = (100, 100)
FLOWER_SIZE = (70, 70)


class TimeScoreGame(Screen):
    """Runs one Time/Score session and returns a :class:`Session`, or ``None``."""

    def __init__(
        self,
        ctx: Context,
        tracker: HandTracker,
        calibration: RangeCalibration,
        *,
        patient_id: int,
        game_config: GameConfig,
        vision_config: VisionConfig,
        clock: "callable" = time.monotonic,
    ):
        super().__init__(ctx)
        self.tracker = tracker
        self.calibration = calibration
        self.patient_id = patient_id
        self.config = game_config
        self.clock_fn = clock

        self.background = theme.background("background_garden.jpg", ctx.size)
        self.butterfly = theme.image("butterfly.png", BUTTERFLY_SIZE)
        self.flower_sprite = theme.image("flower.png", FLOWER_SIZE)
        self.chime = theme.sound("score.wav")

        self.track_width = ctx.width - BUTTERFLY_SIZE[0]
        self.baseline_y = int(ctx.height * 0.55)

        self.smoother = ButterflySmoother(game_config.smoothing_window)
        self.movements = MovementCounter(
            vision_config.open_threshold, vision_config.close_threshold
        )
        self.timer = CountdownTimer(game_config.exercise_seconds, clock)
        self.flower = FlowerTarget(
            min_x=50,
            max_x=max(51, self.track_width - 50),
            tolerance_px=game_config.flower_tolerance_px,
            dwell_seconds=game_config.flower_dwell_seconds,
            clock=clock,
        )

        self.butterfly_x = 0.0
        self.gain = game_config.gain
        self.hand_visible = False
        self.error: str | None = None
        self.restart_requested = False

        self.pause_button = Button(
            pygame.Rect(ctx.width - 170, 24, 146, 48), "Pause",
            theme.PRIMARY, theme.PRIMARY_HOVER,
        )
        self.restart_button = Button(
            pygame.Rect(ctx.width - 170, 84, 146, 48), "Restart",
            theme.DANGER, theme.DANGER_HOVER,
        )
        self.finish_button = Button(
            pygame.Rect(ctx.width - 170, 144, 146, 48), "Finish",
            theme.ACCENT, theme.ACCENT_HOVER,
        )

    # -- lifecycle ---------------------------------------------------------

    def result(self) -> Session:
        """The session record for what has been played so far."""
        return Session.time_score(
            self.patient_id,
            score=self.flower.score,
            gain=self.gain,
            exercise_seconds=self.config.exercise_seconds,
            movements=self.movements.count,
        )

    def restart(self) -> None:
        self.smoother.clear()
        self.movements.reset()
        self.flower.reset()
        self.timer.restart()
        self.butterfly_x = 0.0

    # -- input -------------------------------------------------------------

    def handle(self, event: pygame.event.Event) -> None:
        if self.pause_button.handle(event):
            self._toggle_pause()
        elif self.restart_button.handle(event):
            self.restart_requested = True
            self.finish(None)
        elif self.finish_button.handle(event):
            self.finish(self.result())
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            self._toggle_pause()

    def _toggle_pause(self) -> None:
        paused = self.timer.toggle()
        self.pause_button.label = "Resume" if paused else "Pause"

    def on_escape(self) -> None:
        self.finish(self.result())

    # -- simulation --------------------------------------------------------

    def update(self, dt: float) -> None:
        if self.timer.paused:
            return

        try:
            sample = self.tracker.read()
        except CameraError as exc:
            self.error = str(exc)
            self.finish(self.result())
            return

        self.hand_visible = sample.has_hand
        if sample.has_hand:
            openness = self.calibration.normalize(sample.spread)
            self.movements.update(openness)
            self.butterfly_x = self.smoother.push(
                butterfly_position(openness, self.gain, self.track_width)
            )

        if self.flower.update(self.butterfly_x) and self.chime:
            self.chime.play()

        if self.timer.expired:
            self.finish(self.result())

    # -- rendering ---------------------------------------------------------

    def draw(self) -> None:
        screen, fonts = self.ctx.screen, self.ctx.fonts
        screen.blit(self.background, (0, 0))

        screen.blit(
            self.flower_sprite,
            (self.flower.x, self.baseline_y + (BUTTERFLY_SIZE[1] - FLOWER_SIZE[1]) // 2),
        )
        screen.blit(self.butterfly, (int(self.butterfly_x), self.baseline_y))

        if self.flower.is_settling:
            draw_progress_ring(
                screen,
                (self.flower.x + FLOWER_SIZE[0] // 2, self.baseline_y - 30),
                20, self.flower.hold_progress(), color=theme.GOOD, width=5,
            )

        draw_panel_text(screen, f"Score: {self.flower.score}", fonts.body, (20, 20))
        draw_panel_text(
            screen, f"Time: {self.timer.remaining:.0f}s", fonts.body, (20, 76)
        )
        draw_panel_text(
            screen, f"Movements: {self.movements.count}", fonts.body, (20, 132)
        )
        draw_progress_ring(screen, (260, 46), 26, self.timer.progress)

        if not self.hand_visible:
            draw_panel_text(
                screen, "No hand detected", fonts.small,
                (self.ctx.width // 2, self.ctx.height - 50),
                color=theme.BAD, center=True,
            )

        if self.timer.paused:
            draw_panel_text(
                screen, "PAUSED", fonts.title,
                (self.ctx.width // 2, self.ctx.height // 2),
                color=theme.BAD, center=True,
            )

        for button in (self.pause_button, self.restart_button, self.finish_button):
            button.draw(screen, fonts.small)
