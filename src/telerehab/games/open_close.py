"""Open/Close mode — timed posture holds.

The patient alternates holding the hand open and closed for a prescribed number
of seconds, for a prescribed number of repetitions. The butterfly crosses the
screen as the current hold progresses, so progress is visible without reading a
number.

Unlike Time/Score this is a *hold* exercise: what matters is sustaining a
posture, not reaching a position, so the timer only advances while the posture
is correct (see :class:`telerehab.games.scoring.HoldTimer`).
"""
from __future__ import annotations

import time

import pygame

from ..api.models import Session
from ..config import GameConfig
from ..ui import theme
from ..ui.screens import Context, Screen
from ..ui.widgets import Button, draw_panel_text, draw_progress_ring
from ..vision.calibration import TwoPointCalibration
from ..vision.hand_tracker import CameraError, HandTracker
from .scoring import HoldTimer

BUTTERFLY_SIZE = (100, 100)
FLOWER_SIZE = (70, 70)


class OpenCloseGame(Screen):
    """Runs one Open/Close session and returns a :class:`Session`, or ``None``."""

    def __init__(
        self,
        ctx: Context,
        tracker: HandTracker,
        calibration: TwoPointCalibration,
        *,
        patient_id: int,
        game_config: GameConfig,
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

        self.baseline_y = int(ctx.height * 0.5)
        self.track_start = 20
        self.track_end = ctx.width - BUTTERFLY_SIZE[0] - 20

        # A flat schedule of (posture, seconds) so "which hold am I on" is a
        # single index rather than nested loops with a break in the middle.
        self.schedule: list[tuple[bool, float]] = []
        for _ in range(max(1, game_config.repetitions)):
            self.schedule.append((True, float(game_config.open_seconds)))
            self.schedule.append((False, float(game_config.close_seconds)))

        self.index = 0
        self.timer = HoldTimer(self.schedule[0][1], clock)
        self.paused = False
        self.hand_open: bool | None = None
        self.error: str | None = None

        self.pause_button = Button(
            pygame.Rect(ctx.width - 170, 24, 146, 48), "Pause",
            theme.PRIMARY, theme.PRIMARY_HOVER,
        )
        self.finish_button = Button(
            pygame.Rect(ctx.width - 170, 84, 146, 48), "Finish",
            theme.ACCENT, theme.ACCENT_HOVER,
        )

    # -- state -------------------------------------------------------------

    @property
    def target_open(self) -> bool:
        return self.schedule[self.index][0]

    @property
    def repetition(self) -> int:
        """1-based repetition number (one open hold plus one closed hold)."""
        return self.index // 2 + 1

    @property
    def completed_repetitions(self) -> int:
        return self.index // 2

    @property
    def posture_correct(self) -> bool:
        return self.hand_open is not None and self.hand_open == self.target_open

    def result(self) -> Session:
        return Session.open_close(
            self.patient_id,
            open_seconds=self.config.open_seconds,
            close_seconds=self.config.close_seconds,
            repetitions=self.config.repetitions,
            completed_repetitions=self.completed_repetitions,
        )

    # -- input -------------------------------------------------------------

    def handle(self, event: pygame.event.Event) -> None:
        if self.pause_button.handle(event):
            self._toggle_pause()
        elif self.finish_button.handle(event):
            self.finish(self.result())
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            self._toggle_pause()

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_button.label = "Resume" if self.paused else "Pause"

    def on_escape(self) -> None:
        self.finish(self.result())

    # -- simulation --------------------------------------------------------

    def update(self, dt: float) -> None:
        if self.paused:
            # Feed the timer a "wrong posture" tick so it stops accumulating
            # without discarding what the patient has already held.
            self.timer.update(False)
            return

        try:
            sample = self.tracker.read()
        except CameraError as exc:
            self.error = str(exc)
            self.finish(self.result())
            return

        self.hand_open = (
            self.calibration.is_open(sample.pinch) if sample.has_hand else None
        )
        self.timer.update(self.posture_correct)

        if self.timer.done:
            self._advance()

    def _advance(self) -> None:
        if self.chime:
            self.chime.play()

        self.index += 1
        if self.index >= len(self.schedule):
            self.index = len(self.schedule)  # all repetitions completed
            self.finish(self.result())
            return

        self.timer = HoldTimer(self.schedule[self.index][1], self.clock_fn)

    # -- rendering ---------------------------------------------------------

    def draw(self) -> None:
        screen, fonts = self.ctx.screen, self.ctx.fonts
        screen.blit(self.background, (0, 0))

        travel = self.track_start + self.timer.progress * (
            self.track_end - self.track_start
        )
        screen.blit(
            self.flower_sprite,
            (self.track_end + (BUTTERFLY_SIZE[0] - FLOWER_SIZE[0]) // 2,
             self.baseline_y + (BUTTERFLY_SIZE[1] - FLOWER_SIZE[1]) // 2),
        )
        screen.blit(self.butterfly, (int(travel), self.baseline_y))

        posture = "open" if self.target_open else "closed"
        draw_panel_text(
            screen,
            f"Repetition {self.repetition}/{self.config.repetitions}",
            fonts.small, (20, 20),
        )
        draw_panel_text(
            screen, f"Keep your hand {posture}", fonts.body,
            (self.ctx.width // 2, 40), center=True,
        )
        draw_panel_text(
            screen, f"{self.timer.remaining:.1f}s left", fonts.small,
            (20, 76),
        )
        draw_progress_ring(
            screen, (self.ctx.width // 2, self.ctx.height - 90), 30,
            self.timer.progress, color=theme.GOOD,
        )

        if self.hand_open is None:
            state, colour = "No hand detected", theme.BAD
        elif self.hand_open:
            state = "Hand open"
            colour = theme.GOOD if self.target_open else theme.BAD
        else:
            state = "Hand closed"
            colour = theme.BAD if self.target_open else theme.GOOD
        draw_panel_text(
            screen, state, fonts.small, (self.ctx.width - 200, self.ctx.height - 60),
            color=colour, center=True,
        )

        if not self.posture_correct and not self.paused:
            draw_panel_text(
                screen, f"Adjust your hand - it should be {posture}", fonts.small,
                (self.ctx.width // 2, self.ctx.height - 40),
                color=theme.BAD, center=True,
            )

        if self.paused:
            draw_panel_text(
                screen, "PAUSED", fonts.title,
                (self.ctx.width // 2, self.ctx.height // 2),
                color=theme.BAD, center=True,
            )

        for button in (self.pause_button, self.finish_button):
            button.draw(screen, fonts.small)
