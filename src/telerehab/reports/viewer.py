"""On-screen report browsing."""
from __future__ import annotations

from typing import Sequence

import pygame

from ..ui import theme
from ..ui.screens import Context, Screen
from ..ui.widgets import Button, draw_panel_text
from .charts import to_surface


class ChartViewer(Screen[None]):
    """Pages through a list of rendered charts with the arrow keys.

    Charts arrive as PNG bytes and are decoded in memory, so browsing a
    patient's history touches the filesystem not at all.
    """

    def __init__(self, ctx: Context, charts: Sequence[bytes], *, caption: str = ""):
        super().__init__(ctx)
        if not charts:
            raise ValueError("nothing to display")

        self.caption = caption
        self.surfaces = [
            pygame.transform.smoothscale(
                to_surface(png),
                self._fit(to_surface(png).get_size(), (ctx.width, ctx.height - 90)),
            )
            for png in charts
        ]
        self.index = 0

        self.prev_button = Button(
            pygame.Rect(24, ctx.height - 66, 130, 46), "< Prev",
            theme.PRIMARY, theme.PRIMARY_HOVER,
        )
        self.next_button = Button(
            pygame.Rect(170, ctx.height - 66, 130, 46), "Next >",
            theme.PRIMARY, theme.PRIMARY_HOVER,
        )
        self.close_button = Button(
            pygame.Rect(ctx.width - 154, ctx.height - 66, 130, 46), "Close",
            theme.DANGER, theme.DANGER_HOVER,
        )

    @staticmethod
    def _fit(size: tuple[int, int], bounds: tuple[int, int]) -> tuple[int, int]:
        scale = min(bounds[0] / size[0], bounds[1] / size[1], 1.0)
        return (max(1, int(size[0] * scale)), max(1, int(size[1] * scale)))

    def _step(self, delta: int) -> None:
        self.index = (self.index + delta) % len(self.surfaces)

    def handle(self, event: pygame.event.Event) -> None:
        if self.close_button.handle(event):
            self.finish(None)
        elif self.prev_button.handle(event):
            self._step(-1)
        elif self.next_button.handle(event):
            self._step(1)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_PAGEUP):
                self._step(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_PAGEDOWN, pygame.K_SPACE):
                self._step(1)

    def on_escape(self) -> None:
        self.finish(None)

    def draw(self) -> None:
        screen = self.ctx.screen
        screen.fill(theme.BACKDROP)

        chart = self.surfaces[self.index]
        screen.blit(chart, chart.get_rect(center=(self.ctx.width // 2, (self.ctx.height - 80) // 2)))

        label = f"{self.index + 1} / {len(self.surfaces)}"
        if self.caption:
            label = f"{self.caption}   -   {label}"
        draw_panel_text(
            screen, label, self.ctx.fonts.small,
            (self.ctx.width // 2, self.ctx.height - 43), center=True,
        )

        multiple = len(self.surfaces) > 1
        self.prev_button.enabled = multiple
        self.next_button.enabled = multiple
        for button in (self.prev_button, self.next_button, self.close_button):
            button.draw(screen, self.ctx.fonts.small)
