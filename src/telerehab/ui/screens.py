"""Screen scaffolding and the generic screens shared by both modes.

Navigation in the original worked by calling the next page *from inside* the
current one — ``user_input_page()`` called ``sign_up_page()`` which called
``user_input_page()`` again — so "going back" grew the call stack instead of
unwinding it, and no page could ever return a value to its caller.

Here a screen owns its own loop, returns a result, and exits. Deciding what
comes next is :mod:`telerehab.app`'s job, in a flat loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Sequence, TypeVar

import pygame

from . import theme
from .widgets import Button, FieldGroup, TextField, draw_panel_text, draw_text

T = TypeVar("T")


class Quit:
    """Returned when the user closes the window. Distinct from a Back result."""

    _instance: "Quit | None" = None

    def __new__(cls) -> "Quit":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "QUIT"


QUIT = Quit()
BACK = "__back__"


@dataclass
class Context:
    """Everything a screen needs from the host application."""

    screen: pygame.Surface
    clock: pygame.time.Clock
    fonts: theme.Fonts
    fps: int = 30

    @property
    def size(self) -> tuple[int, int]:
        return self.screen.get_size()

    @property
    def width(self) -> int:
        return self.screen.get_width()

    @property
    def height(self) -> int:
        return self.screen.get_height()


class Screen(Generic[T]):
    """Base class: subclasses implement :meth:`handle` and :meth:`draw`."""

    def __init__(self, ctx: Context):
        self.ctx = ctx
        self._result: T | Quit | None = None
        self._running = False

    # -- to override -------------------------------------------------------

    def handle(self, event: pygame.event.Event) -> None:
        """React to one event; call :meth:`finish` to leave the screen."""

    def update(self, dt: float) -> None:
        """Advance any animation. ``dt`` is seconds since the last frame."""

    def draw(self) -> None:
        raise NotImplementedError

    # -- driving -----------------------------------------------------------

    def finish(self, result: T | Quit) -> None:
        self._result = result
        self._running = False

    def run(self) -> T | Quit:
        self._running = True
        self._result = None

        while self._running:
            dt = self.ctx.clock.tick(self.ctx.fps) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.finish(QUIT)
                    break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.on_escape()
                    if not self._running:
                        break
                self.handle(event)

            if not self._running:
                break

            self.update(dt)
            self.draw()
            pygame.display.flip()

        return self._result  # type: ignore[return-value]

    def on_escape(self) -> None:
        """Escape means Back by default; screens with no Back ignore it."""


class MenuScreen(Screen[Any]):
    """A titled column of buttons, each returning a value."""

    def __init__(
        self,
        ctx: Context,
        title: str,
        options: Sequence[tuple[str, Any, theme.Color]],
        *,
        back_label: str | None = None,
    ):
        super().__init__(ctx)
        self.title = title

        button_width, button_height, gap = 400, 56, 24
        top = 220
        left = (ctx.width - button_width) // 2

        self.buttons: list[tuple[Button, Any]] = []
        for index, (label, value, color) in enumerate(options):
            rect = pygame.Rect(
                left, top + index * (button_height + gap), button_width, button_height
            )
            hover = tuple(min(255, c + 40) for c in color)
            self.buttons.append((Button(rect, label, color, hover), value))  # type: ignore[arg-type]

        self.back_button: Button | None = None
        if back_label:
            rect = pygame.Rect(
                left, top + len(options) * (button_height + gap) + 16,
                button_width, button_height,
            )
            self.back_button = Button(rect, back_label, (90, 90, 90), (120, 120, 120))

    def handle(self, event: pygame.event.Event) -> None:
        for button, value in self.buttons:
            if button.handle(event):
                self.finish(value)
                return
        if self.back_button and self.back_button.handle(event):
            self.finish(BACK)

    def on_escape(self) -> None:
        if self.back_button:
            self.finish(BACK)

    def draw(self) -> None:
        self.ctx.screen.fill(theme.BACKDROP)
        draw_text(
            self.ctx.screen, self.title, self.ctx.fonts.title, theme.TEXT,
            (self.ctx.width // 2, 140), center=True,
        )
        for button, _ in self.buttons:
            button.draw(self.ctx.screen, self.ctx.fonts.body)
        if self.back_button:
            self.back_button.draw(self.ctx.screen, self.ctx.fonts.body)


class FormScreen(Screen[Any]):
    """A background image, a column of fields, and submit/back buttons.

    ``on_submit`` receives the field group and returns either the screen's
    result, or a string to display as an error and stay put.
    """

    def __init__(
        self,
        ctx: Context,
        *,
        title: str,
        fields: Sequence[TextField],
        submit_label: str,
        on_submit: Callable[[FieldGroup], Any],
        background: str = "background_form.jpg",
    ):
        super().__init__(ctx)
        self.title = title
        self.group = FieldGroup(fields)
        self.on_submit = on_submit
        self.message: str | None = None
        self.message_color: theme.Color = theme.BAD
        self.busy = False

        self.background = theme.background(background, ctx.size)
        button_width = 260
        self.submit = Button(
            pygame.Rect(ctx.width - button_width - 30, ctx.height - 80,
                        button_width, 52),
            submit_label, theme.SUCCESS, theme.SUCCESS_HOVER,
        )
        self.back = Button(
            pygame.Rect(30, ctx.height - 80, button_width, 52),
            "Back", (90, 90, 90), (120, 120, 120),
        )

    def _submit(self) -> None:
        self.busy = True
        self.draw()
        pygame.display.flip()
        try:
            outcome = self.on_submit(self.group)
        finally:
            self.busy = False

        if isinstance(outcome, str):
            self.message = outcome
            self.message_color = theme.BAD
        elif outcome is not None:
            self.finish(outcome)

    def handle(self, event: pygame.event.Event) -> None:
        if self.back.handle(event):
            self.finish(BACK)
            return
        if self.submit.handle(event):
            self._submit()
            return
        if event.type == pygame.KEYDOWN and event.key in (
            pygame.K_RETURN, pygame.K_KP_ENTER
        ):
            last = self.group.fields[-1]
            if last.active:
                self._submit()
                return
        self.group.handle(event)

    def on_escape(self) -> None:
        self.finish(BACK)

    def draw(self) -> None:
        self.ctx.screen.blit(self.background, (0, 0))
        draw_text(
            self.ctx.screen, self.title, self.ctx.fonts.title, theme.TEXT_DARK, (30, 24)
        )
        self.group.draw(self.ctx.screen, self.ctx.fonts)

        self.submit.label = "Working..." if self.busy else self.submit.label
        self.submit.enabled = not self.busy
        self.submit.draw(self.ctx.screen, self.ctx.fonts.small)
        self.back.draw(self.ctx.screen, self.ctx.fonts.small)

        if self.message:
            draw_panel_text(
                self.ctx.screen, self.message, self.ctx.fonts.small,
                (self.ctx.width // 2, self.ctx.height - 120),
                color=self.message_color, center=True,
            )


class MessageScreen(Screen[None]):
    """A blocking notice with a single dismiss button."""

    def __init__(
        self,
        ctx: Context,
        title: str,
        lines: Sequence[str] = (),
        *,
        button_label: str = "Continue",
    ):
        super().__init__(ctx)
        self.title = title
        self.lines = list(lines)
        self.button = Button(
            pygame.Rect((ctx.width - 240) // 2, ctx.height - 140, 240, 52),
            button_label, theme.PRIMARY, theme.PRIMARY_HOVER,
        )

    def handle(self, event: pygame.event.Event) -> None:
        if self.button.handle(event):
            self.finish(None)
        elif event.type == pygame.KEYDOWN and event.key in (
            pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE
        ):
            self.finish(None)

    def on_escape(self) -> None:
        self.finish(None)

    def draw(self) -> None:
        self.ctx.screen.fill(theme.BACKDROP)
        draw_text(
            self.ctx.screen, self.title, self.ctx.fonts.title, theme.TEXT,
            (self.ctx.width // 2, 180), center=True,
        )
        for index, line in enumerate(self.lines):
            draw_text(
                self.ctx.screen, line, self.ctx.fonts.body, theme.TEXT,
                (self.ctx.width // 2, 260 + index * 46), center=True,
            )
        self.button.draw(self.ctx.screen, self.ctx.fonts.body)


class ConfirmScreen(Screen[bool]):
    """A yes/no question."""

    def __init__(self, ctx: Context, question: str, *, yes: str = "Yes", no: str = "No"):
        super().__init__(ctx)
        self.question = question
        centre = ctx.width // 2
        self.yes = Button(
            pygame.Rect(centre - 220, 340, 200, 52), yes, theme.PRIMARY, theme.PRIMARY_HOVER
        )
        self.no = Button(
            pygame.Rect(centre + 20, 340, 200, 52), no, theme.DANGER, theme.DANGER_HOVER
        )

    def handle(self, event: pygame.event.Event) -> None:
        if self.yes.handle(event):
            self.finish(True)
        elif self.no.handle(event):
            self.finish(False)

    def on_escape(self) -> None:
        self.finish(False)

    def draw(self) -> None:
        self.ctx.screen.fill(theme.BACKDROP)
        draw_text(
            self.ctx.screen, self.question, self.ctx.fonts.body, theme.TEXT,
            (self.ctx.width // 2, 250), center=True,
        )
        self.yes.draw(self.ctx.screen, self.ctx.fonts.body)
        self.no.draw(self.ctx.screen, self.ctx.fonts.body)
