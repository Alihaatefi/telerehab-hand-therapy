"""Calibration screens.

Both modes calibrate, but they ask different questions, so there are two
screens over the two calibrators in :mod:`telerehab.vision.calibration`.

The original ran calibration inside a bare ``while`` loop that showed the
camera in a separate OpenCV window (``cv2.imshow``) while drawing the countdown
into the pygame window — two windows, one of which ignored the close button.
Both screens here render the camera feed inside the game window.
"""
from __future__ import annotations

import pygame

from ..vision import RangeCalibration, TwoPointCalibration
from ..vision.hand_tracker import CameraError, HandTracker
from ..ui import theme
from ..ui.screens import QUIT, Context, Screen
from ..ui.widgets import draw_panel_text, draw_progress_ring, frame_to_surface


class _CameraScreen(Screen):
    """Shared plumbing: pull a frame each tick and blit it behind the overlay."""

    def __init__(self, ctx: Context, tracker: HandTracker):
        super().__init__(ctx)
        self.tracker = tracker
        self.sample = None
        self.error: str | None = None

    def update(self, dt: float) -> None:
        try:
            self.sample = self.tracker.read()
        except CameraError as exc:
            self.error = str(exc)
            self.finish(QUIT)

    def draw_camera(self) -> None:
        self.ctx.screen.fill(theme.BACKDROP)
        if self.sample is None:
            return
        surface = frame_to_surface(self.sample.frame)
        self.ctx.screen.blit(
            pygame.transform.smoothscale(surface, self.ctx.size), (0, 0)
        )

    def draw_hand_hint(self) -> None:
        if self.sample is not None and not self.sample.has_hand:
            draw_panel_text(
                self.ctx.screen, "No hand detected - move into frame",
                self.ctx.fonts.small, (self.ctx.width // 2, 60),
                color=theme.BAD, center=True,
            )


class RangeCalibrationScreen(_CameraScreen):
    """Time/Score: sweep the hand for N seconds to learn its range.

    Returns the populated :class:`RangeCalibration`, or ``QUIT``.
    """

    def __init__(self, ctx: Context, tracker: HandTracker, seconds: int):
        super().__init__(ctx, tracker)
        self.seconds = max(1, seconds)
        self.calibration = RangeCalibration()
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.sample is None:
            return

        # Only count time while a hand is actually visible, so a patient who
        # takes a moment to get into frame is not silently short-changed.
        if self.sample.has_hand:
            self.elapsed += dt
            self.calibration.observe(self.sample.spread)

        if self.elapsed >= self.seconds:
            self.finish(self.calibration)

    def draw(self) -> None:
        self.draw_camera()
        remaining = max(0, self.seconds - self.elapsed)

        draw_panel_text(
            self.ctx.screen,
            "Open and close your hand slowly, as far as you comfortably can",
            self.ctx.fonts.small, (self.ctx.width // 2, self.ctx.height - 70),
            center=True,
        )
        draw_panel_text(
            self.ctx.screen, f"Calibrating: {remaining:.0f}s",
            self.ctx.fonts.body, (self.ctx.width // 2, 40), center=True,
        )
        draw_progress_ring(
            self.ctx.screen,
            (self.ctx.width // 2, self.ctx.height // 2),
            60, self.elapsed / self.seconds,
        )
        self.draw_hand_hint()


class TwoPointCalibrationScreen(_CameraScreen):
    """Open/Close: capture one open sample and one closed sample.

    Returns the populated :class:`TwoPointCalibration`, or ``QUIT``.
    """

    STEPS = (
        ("open", "Open your hand fully, then press O"),
        ("closed", "Close your hand into a fist, then press C"),
        ("confirm", "Press S to start the exercise"),
    )

    def __init__(self, ctx: Context, tracker: HandTracker):
        super().__init__(ctx, tracker)
        self.calibration = TwoPointCalibration()
        self.step = 0
        self.warning: str | None = None

    @property
    def stage(self) -> str:
        return self.STEPS[self.step][0]

    def _capture(self, target: str) -> None:
        if self.sample is None or not self.sample.has_hand:
            self.warning = "No hand detected - hold your hand in view and try again"
            return

        value = self.sample.pinch
        if target == "open":
            self.calibration.open_sample = value
        else:
            self.calibration.closed_sample = value

        self.warning = None
        self.step += 1

    def handle(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if self.stage == "open" and event.key == pygame.K_o:
            self._capture("open")
        elif self.stage == "closed" and event.key == pygame.K_c:
            self._capture("closed")
        elif self.stage == "confirm" and event.key == pygame.K_s:
            # A hand that reads the same open and closed means the samples were
            # taken in the wrong posture; starting anyway gives nonsense.
            if abs(self.calibration.open_sample - self.calibration.closed_sample) < 1e-3:
                self.warning = "Open and closed look identical - press R to redo"
                return
            self.finish(self.calibration)
        elif event.key == pygame.K_r:
            self.calibration.reset()
            self.step = 0
            self.warning = None

    def draw(self) -> None:
        self.draw_camera()
        _, prompt = self.STEPS[self.step]
        colour = theme.GOOD if self.stage == "confirm" else theme.TEXT_DARK

        draw_panel_text(
            self.ctx.screen, prompt, self.ctx.fonts.body,
            (self.ctx.width // 2, self.ctx.height - 70), color=colour, center=True,
        )

        captured = []
        if self.calibration.open_sample is not None:
            captured.append(f"open {self.calibration.open_sample:.3f}")
        if self.calibration.closed_sample is not None:
            captured.append(f"closed {self.calibration.closed_sample:.3f}")
        if captured:
            draw_panel_text(
                self.ctx.screen, "  |  ".join(captured), self.ctx.fonts.small,
                (self.ctx.width // 2, 40), center=True,
            )

        if self.warning:
            draw_panel_text(
                self.ctx.screen, self.warning, self.ctx.fonts.small,
                (self.ctx.width // 2, self.ctx.height - 130),
                color=theme.BAD, center=True,
            )
        self.draw_hand_hint()
