"""Reusable pygame widgets.

The original defined ``draw_text``, ``draw_input_box`` and two incompatible
button helpers separately in each game file, then decided what a click meant by
polling ``pygame.mouse.get_pressed()`` *while drawing*. That has two
consequences worth naming, because both are fixed here:

* A held mouse button re-fires the action on every frame — roughly thirty times
  a second — so holding "Reset" over a dialog could trigger it repeatedly.
* Button rectangles were created after the event loop that already referenced
  them, so a click landing on the very first frame raised ``NameError``.

Widgets here are ordinary objects: constructed once, fed events, then drawn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import pygame

from . import theme


@dataclass
class Button:
    """A clickable rectangle.

    A click is a press *and* release inside the same button, matching what
    users expect: pressing down then dragging away cancels the action.
    """

    rect: pygame.Rect
    label: str
    color: theme.Color = theme.PRIMARY
    hover_color: theme.Color = theme.PRIMARY_HOVER
    text_color: theme.Color = theme.TEXT
    radius: int = 15
    enabled: bool = True

    _pressed: bool = field(default=False, init=False, repr=False)

    def handle(self, event: pygame.event.Event) -> bool:
        """Feed one event. Returns True exactly once per completed click."""
        if not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._pressed = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            clicked = self._pressed and self.rect.collidepoint(event.pos)
            self._pressed = False
            return clicked
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        hovered = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        color = self.hover_color if hovered else self.color
        if not self.enabled:
            color = tuple(c // 2 for c in self.color)  # type: ignore[assignment]

        pygame.draw.rect(surface, color, self.rect, border_radius=self.radius)
        label = font.render(self.label, True, self.text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))


class TextField:
    """A single-line text input with per-field validation.

    ``kind`` controls what keystrokes are accepted:

    ``"text"``     anything printable
    ``"int"``      digits only
    ``"decimal"``  digits and a single decimal point
    """

    def __init__(
        self,
        rect: pygame.Rect,
        *,
        label: str,
        value: str = "",
        kind: str = "text",
        max_length: int = 32,
    ):
        if kind not in {"text", "int", "decimal"}:
            raise ValueError(f"unknown field kind: {kind}")

        self.rect = rect
        self.label = label
        self.value = value
        self.kind = kind
        self.max_length = max_length
        self.active = False

    def _accepts(self, char: str) -> bool:
        if not char or not char.isprintable():
            return False
        if self.kind == "int":
            return char.isdigit()
        if self.kind == "decimal":
            return char.isdigit() or (char == "." and "." not in self.value)
        return True

    def handle(self, event: pygame.event.Event) -> str | None:
        """Feed one event. Returns ``"submit"`` when Enter is pressed."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
            return None

        if event.type != pygame.KEYDOWN or not self.active:
            return None

        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return "submit"
        if event.key == pygame.K_TAB:
            return "next"
        if event.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]
        elif len(self.value) < self.max_length and self._accepts(event.unicode):
            self.value += event.unicode
        return None

    def draw(self, surface: pygame.Surface, fonts: theme.Fonts) -> None:
        caption = fonts.small.render(self.label, True, theme.TEXT_DARK)
        surface.blit(caption, (self.rect.x, self.rect.y - 30))

        border = theme.FIELD_ACTIVE if self.active else theme.FIELD_IDLE
        pygame.draw.rect(surface, theme.PANEL, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=6)

        text = fonts.small.render(self.value, True, theme.TEXT_DARK)
        surface.blit(text, (self.rect.x + 8, self.rect.y + 8))

        if self.active and pygame.time.get_ticks() % 1000 < 500:
            caret_x = self.rect.x + 10 + text.get_width()
            pygame.draw.line(
                surface, theme.TEXT_DARK,
                (caret_x, self.rect.y + 8), (caret_x, self.rect.bottom - 8), 2,
            )

    # -- typed access ------------------------------------------------------

    def as_int(self, default: int = 0, minimum: int | None = None) -> int:
        try:
            parsed = int(self.value)
        except ValueError:
            return default
        return max(minimum, parsed) if minimum is not None else parsed

    def as_float(self, default: float = 0.0, minimum: float | None = None) -> float:
        try:
            parsed = float(self.value)
        except ValueError:
            return default
        return max(minimum, parsed) if minimum is not None else parsed


class FieldGroup:
    """A set of text fields with Tab/Enter moving focus between them."""

    def __init__(self, fields: Sequence[TextField]):
        self.fields = list(fields)
        if self.fields:
            self.fields[0].active = True

    def focus(self, index: int) -> None:
        for i, field_ in enumerate(self.fields):
            field_.active = i == index % len(self.fields)

    def advance(self) -> None:
        current = next(
            (i for i, f in enumerate(self.fields) if f.active), -1
        )
        self.focus(current + 1)

    def handle(self, event: pygame.event.Event) -> None:
        for field_ in self.fields:
            if field_.handle(event) in {"submit", "next"}:
                self.advance()
                return

    def draw(self, surface: pygame.Surface, fonts: theme.Fonts) -> None:
        for field_ in self.fields:
            field_.draw(surface, fonts)


# -- drawing helpers -------------------------------------------------------


def draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: theme.Color,
    position: tuple[int, int],
    *,
    center: bool = False,
) -> pygame.Rect:
    rendered = font.render(str(text), True, color)
    rect = (
        rendered.get_rect(center=position)
        if center
        else rendered.get_rect(topleft=position)
    )
    surface.blit(rendered, rect)
    return rect


def draw_panel_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    position: tuple[int, int],
    *,
    color: theme.Color = theme.TEXT_DARK,
    panel: theme.Color = theme.PANEL,
    shadow: theme.Color = theme.PANEL_SHADOW,
    center: bool = False,
) -> pygame.Rect:
    """Text on a drop-shadowed plate, for legibility over the busy background."""
    rendered = font.render(str(text), True, color)
    rect = (
        rendered.get_rect(center=position)
        if center
        else rendered.get_rect(topleft=position)
    )
    plate = rect.inflate(20, 12)
    pygame.draw.rect(surface, shadow, plate.move(2, 2), border_radius=6)
    pygame.draw.rect(surface, panel, plate, border_radius=6)
    surface.blit(rendered, rect)
    return plate


def draw_progress_ring(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    progress: float,
    *,
    color: theme.Color = theme.DANGER,
    width: int = 8,
) -> None:
    """A circular progress indicator, filling clockwise from twelve o'clock."""
    import math

    progress = max(0.0, min(1.0, progress))
    pygame.draw.circle(surface, (200, 200, 200), center, radius, 2)
    if progress <= 0:
        return

    box = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
    start = math.pi / 2
    pygame.draw.arc(surface, color, box, start - progress * 2 * math.pi, start, width)


def frame_to_surface(frame) -> pygame.Surface:
    """Convert an OpenCV BGR frame into a pygame surface."""
    import cv2
    import numpy as np

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return pygame.surfarray.make_surface(np.rot90(np.fliplr(rgb)))


def fit_camera_surface(
    frame, size: tuple[int, int]
) -> pygame.Surface:  # pragma: no cover - needs a real frame
    return pygame.transform.smoothscale(frame_to_surface(frame), size)
