"""The one thing the exercise rules need to know about a camera frame.

The engines never import the vision stack: they are handed anything shaped like
this, which is what makes them testable with a few lines of fake data and no
camera, no MediaPipe and no display.
"""
from __future__ import annotations

from typing import Protocol


class SampleLike(Protocol):
    """A processed video frame, reduced to what the exercises read."""

    @property
    def has_hand(self) -> bool: ...

    @property
    def spread(self) -> float | None: ...

    @property
    def pinch(self) -> float | None: ...
