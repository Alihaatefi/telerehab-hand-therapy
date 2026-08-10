"""Colours, fonts and asset loading.

Every colour, font and asset lookup is named here, so a visual change is made in
one place rather than hunted for across the screens that use it.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

from ..config import IMAGES_DIR, SOUNDS_DIR

Color = tuple[int, int, int]

# -- palette ---------------------------------------------------------------

BACKDROP: Color = (30, 30, 30)
TEXT: Color = (255, 255, 255)
TEXT_DARK: Color = (0, 0, 0)
PANEL: Color = (255, 255, 255)
PANEL_SHADOW: Color = (100, 100, 100)

PRIMARY: Color = (0, 128, 255)
PRIMARY_HOVER: Color = (0, 150, 255)
DANGER: Color = (200, 0, 0)
DANGER_HOVER: Color = (255, 0, 0)
SUCCESS: Color = (0, 160, 60)
SUCCESS_HOVER: Color = (0, 200, 80)
ACCENT: Color = (128, 0, 255)
ACCENT_HOVER: Color = (150, 0, 255)

FIELD_ACTIVE: Color = (0, 128, 255)
FIELD_IDLE: Color = (120, 120, 120)

GOOD: Color = (0, 170, 0)
BAD: Color = (200, 0, 0)


@dataclass(frozen=True)
class Fonts:
    title: pygame.font.Font
    body: pygame.font.Font
    small: pygame.font.Font

    @classmethod
    def build(cls) -> "Fonts":
        return cls(
            title=pygame.font.Font(None, 44),
            body=pygame.font.Font(None, 36),
            small=pygame.font.Font(None, 28),
        )


# -- assets ----------------------------------------------------------------


class AssetError(RuntimeError):
    """An image or sound file is missing or unreadable."""


@lru_cache(maxsize=None)
def _load_surface(path: Path) -> pygame.Surface:
    if not path.exists():
        raise AssetError(f"missing asset: {path}")
    try:
        return pygame.image.load(str(path))
    except pygame.error as exc:  # pragma: no cover - depends on file contents
        raise AssetError(f"could not read {path}: {exc}") from exc


def image(name: str, size: tuple[int, int] | None = None) -> pygame.Surface:
    """Load an image from ``assets/images``, optionally scaled.

    Results are cached, so drawing the same sprite on every frame does not hit
    the disk thirty times a second.
    """
    surface = _load_surface(IMAGES_DIR / name)
    surface = surface.convert_alpha() if pygame.display.get_init() else surface
    return pygame.transform.smoothscale(surface, size) if size else surface


@lru_cache(maxsize=None)
def sound(name: str) -> pygame.mixer.Sound | None:
    """Load a sound, or return ``None`` if audio is unavailable.

    A machine with no working audio device is a bad reason to refuse a
    rehabilitation session, so this degrades to silence instead of raising.
    """
    path = SOUNDS_DIR / name
    if not path.exists() or not pygame.mixer.get_init():
        return None
    try:
        return pygame.mixer.Sound(str(path))
    except pygame.error:  # pragma: no cover - depends on the audio backend
        return None


def background(name: str, size: tuple[int, int]) -> pygame.Surface:
    return image(name, size)
