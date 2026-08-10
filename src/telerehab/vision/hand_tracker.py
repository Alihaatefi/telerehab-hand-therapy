"""Camera capture and MediaPipe hand landmark extraction.

This module is the *only* place in the project that imports MediaPipe or
OpenCV. Everything downstream works with :class:`HandSample`, which is plain
Python data.

That boundary is load-bearing rather than decorative: MediaPipe removed the
``mp.solutions`` API used here in releases after 0.10.14, which is why
``requirements.txt`` pins that version exactly. When the pin has to move to the
newer Tasks API, this file is the only one that changes.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Iterator, Sequence

import cv2
import mediapipe as mp
import numpy as np

from ..config import VisionConfig
from .geometry import Point, pinch_openness, spread_openness

_mp_hands = mp.solutions.hands
_mp_drawing = mp.solutions.drawing_utils


class CameraError(RuntimeError):
    """The webcam could not be opened or stopped delivering frames."""


@dataclass(frozen=True)
class HandSample:
    """One processed video frame.

    Attributes:
        frame: The BGR frame, with the hand skeleton drawn on it when a hand
            was found. Safe to hand to OpenCV or convert for pygame.
        points: 21 normalised ``(x, y)`` landmarks, or ``None`` if no hand was
            detected in this frame.
    """

    frame: np.ndarray
    points: Sequence[Point] | None

    @property
    def has_hand(self) -> bool:
        return self.points is not None

    @property
    def spread(self) -> float | None:
        """Wrist-to-fingertip openness, or ``None`` when no hand is visible."""
        return spread_openness(self.points) if self.points else None

    @property
    def pinch(self) -> float | None:
        """Thumb-to-index distance, or ``None`` when no hand is visible."""
        return pinch_openness(self.points) if self.points else None


class HandTracker:
    """Reads frames from a camera and extracts hand landmarks.

    Use it as a context manager so the camera is released on every exit path,
    including exceptions — a leaked capture device stays locked until the
    process dies, and the next run cannot open it::

        with HandTracker(VisionConfig()) as tracker:
            for sample in tracker.stream():
                ...
    """

    def __init__(self, config: VisionConfig | None = None, *, mirror: bool = True):
        self.config = config or VisionConfig()
        self.mirror = mirror
        self._capture: cv2.VideoCapture | None = None
        self._hands = _mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=self.config.max_num_hands,
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
        )

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> "HandTracker":
        if self._capture is None:
            capture = cv2.VideoCapture(self.config.camera_index)
            if not capture.isOpened():
                capture.release()
                raise CameraError(
                    f"could not open camera {self.config.camera_index}. "
                    "Check that no other application is using it."
                )
            self._capture = capture
        return self

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._hands.close()

    def __enter__(self) -> "HandTracker":
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- reading -----------------------------------------------------------

    def read(self) -> HandSample:
        """Grab one frame from the camera and process it."""
        if self._capture is None:
            self.open()
        assert self._capture is not None

        ok, frame = self._capture.read()
        if not ok:
            raise CameraError("camera stopped delivering frames")

        if self.mirror:
            # Patients steer by watching themselves; an unmirrored feed makes
            # every correction go the wrong way.
            frame = cv2.flip(frame, 1)

        return self.process(frame)

    def process(self, frame: np.ndarray) -> HandSample:
        """Run landmark detection on an already-captured BGR frame.

        Separate from :meth:`read` so the vision pipeline can be exercised from
        a still image with no camera attached, which is how it is tested.
        """
        results = self._hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        hands_found = results.multi_hand_landmarks

        if not hands_found:
            return HandSample(frame=frame, points=None)

        landmarks = hands_found[0]
        _mp_drawing.draw_landmarks(frame, landmarks, _mp_hands.HAND_CONNECTIONS)
        points = [(lm.x, lm.y) for lm in landmarks.landmark]
        return HandSample(frame=frame, points=points)

    def stream(self) -> Iterator[HandSample]:
        """Yield processed frames until the caller stops consuming them."""
        while True:
            yield self.read()


@contextlib.contextmanager
def still_image_tracker(config: VisionConfig | None = None) -> Iterator[HandTracker]:
    """A tracker configured for single images rather than a video stream.

    MediaPipe's tracking mode assumes temporal continuity between calls; for
    isolated images that produces worse landmarks than static mode does.
    """
    config = config or VisionConfig()
    tracker = HandTracker.__new__(HandTracker)
    tracker.config = config
    tracker.mirror = False
    tracker._capture = None
    tracker._hands = _mp_hands.Hands(
        static_image_mode=True,
        max_num_hands=config.max_num_hands,
        min_detection_confidence=config.min_detection_confidence,
    )
    try:
        yield tracker
    finally:
        tracker.close()
