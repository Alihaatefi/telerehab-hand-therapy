"""A simulated camera, for demos, screenshots and machines with no webcam.

The two reference photographs shipped with the project — one open hand, one
closed — are run through the real MediaPipe pipeline once, and the simulated
hand then morphs between the two sets of landmarks. Everything downstream (the
calibration, both exercises, the reports) cannot tell it from a physical
camera: it receives ordinary :class:`~telerehab.vision.hand_tracker.HandSample`
objects.

Landmarks are interpolated linearly and the frame is a cross-fade of the two
photographs, which is crude as imagery but exact as a signal: openness moves
smoothly between the two measured extremes.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Iterator

import cv2
import numpy as np

from ..config import REFERENCE_DIR, VisionConfig
from .geometry import INDEX_TIP, THUMB_TIP, WRIST, Point
from .hand_tracker import HandSample, still_image_tracker

FRAME_WIDTH, FRAME_HEIGHT = 640, 480

#: Backdrop behind the letterboxed photographs (BGR); close to their own white.
_BACKDROP = (250, 250, 250)


def _read_photo(name: str) -> np.ndarray:
    path = REFERENCE_DIR / name
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"reference photograph is missing or unreadable: {path}")
    return image


def _thumb_geometry(points: np.ndarray) -> tuple[float, float]:
    """How far the thumb tip is from the wrist, and from the index tip."""
    reach = float(np.hypot(*(points[THUMB_TIP] - points[WRIST])))
    gap = float(np.hypot(*(points[THUMB_TIP] - points[INDEX_TIP])))
    return reach, gap


def _place_thumb(
    current: np.ndarray, wrist: np.ndarray, index: np.ndarray, reach: float, gap: float
) -> np.ndarray:
    """The thumb-tip position that is ``reach`` from the wrist and ``gap`` from the index tip.

    Two circles meet in (up to) two points; take the one nearest to where plain
    blending put the thumb, so it moves smoothly instead of flipping sides.
    """
    axis = index - wrist
    distance = float(np.hypot(*axis))
    if distance < 1e-9:
        return current
    unit = axis / distance
    normal = np.array([-unit[1], unit[0]])

    along = (distance * distance + reach * reach - gap * gap) / (2.0 * distance)
    height_squared = reach * reach - along * along
    height = math.sqrt(height_squared) if height_squared > 0 else 0.0

    base = wrist + unit * along
    first, second = base + normal * height, base - normal * height
    near_first = float(np.hypot(*(first - current))) <= float(np.hypot(*(second - current)))
    return first if near_first else second


def _letterbox(image: np.ndarray) -> np.ndarray:
    """Fit a photograph into a 4:3 camera-shaped frame without distorting it."""
    height, width = image.shape[:2]
    scale = min(FRAME_WIDTH / width, FRAME_HEIGHT / height)
    resized = cv2.resize(image, (int(width * scale), int(height * scale)))

    canvas = np.empty((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    canvas[:] = _BACKDROP
    top = (FRAME_HEIGHT - resized.shape[0]) // 2
    left = (FRAME_WIDTH - resized.shape[1]) // 2
    canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return canvas


class DemoTracker:
    """Drop-in stand-in for :class:`~telerehab.vision.hand_tracker.HandTracker`.

    By default the hand opens and closes continuously, pausing briefly at each
    extreme so holds and dwell times are achievable. :meth:`set_openness` pins
    it to a fixed pose, and :meth:`hide_hand` removes it, for tests and for
    exercising the "no hand detected" paths.
    """

    def __init__(
        self,
        config: VisionConfig | None = None,
        *,
        period: float = 6.0,
        fps: float = 30.0,
        realtime: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.config = config or VisionConfig()
        self.period = period
        self.fps = fps
        self.realtime = realtime
        self._clock = clock

        self._openness: float | None = None
        self._hand_hidden = False
        self._started = clock()
        self._next_frame = 0.0
        self._opened = False

        with still_image_tracker(
            VisionConfig(min_detection_confidence=0.5)
        ) as tracker:
            self._open_frame = _letterbox(_read_photo("hand_open.jpg"))
            self._closed_frame = _letterbox(_read_photo("hand_closed.jpg"))
            open_sample = tracker.process(self._open_frame.copy())
            closed_sample = tracker.process(self._closed_frame.copy())

        if not (open_sample.has_hand and closed_sample.has_hand):
            raise RuntimeError("no hand found in the bundled reference photographs")

        self._open_points = np.asarray(open_sample.points, dtype=np.float64)
        self._closed_points = np.asarray(closed_sample.points, dtype=np.float64)
        self._open_thumb = _thumb_geometry(self._open_points)
        self._closed_thumb = _thumb_geometry(self._closed_points)
        self._blank = np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), _BACKDROP, np.uint8)

    # -- lifecycle (mirrors HandTracker) -----------------------------------

    def open(self) -> DemoTracker:
        self._opened = True
        self._started = self._clock()
        self._next_frame = 0.0
        return self

    def close(self) -> None:
        self._opened = False

    def __enter__(self) -> DemoTracker:
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- control -----------------------------------------------------------

    def set_openness(self, value: float | None) -> None:
        """Pin the hand at ``value`` (0 closed .. 1 open), or ``None`` to animate."""
        self._openness = None if value is None else max(0.0, min(1.0, value))

    def hide_hand(self, hidden: bool = True) -> None:
        self._hand_hidden = hidden

    @property
    def openness(self) -> float:
        """Current simulated openness, 0 (closed) to 1 (open)."""
        if self._openness is not None:
            return self._openness
        phase = (self._clock() - self._started) / self.period
        # Over-driven sine, clipped: flat spells at both extremes.
        return max(0.0, min(1.0, 0.5 + 0.62 * math.sin(2.0 * math.pi * phase)))

    # -- reading -----------------------------------------------------------

    def read(self) -> HandSample:
        if self.realtime:
            now = self._clock()
            if self._next_frame > now:
                time.sleep(self._next_frame - now)
            self._next_frame = max(now, self._next_frame) + 1.0 / self.fps

        if self._hand_hidden:
            return HandSample(frame=self._blank.copy(), points=None)

        t = self.openness
        points = (1.0 - t) * self._closed_points + t * self._open_points

        # Blending two very different poses carries the thumb tip across the
        # index tip, so the thumb-to-index distance dips below both ends. A real
        # hand does not do that while it closes, and that distance is what
        # Open/Close mode classifies on. Re-place the thumb tip so that distance,
        # and its distance from the wrist (which Time/Score's spread depends on),
        # are each a straight blend of the two measured ones.
        open_reach, open_gap = self._open_thumb
        closed_reach, closed_gap = self._closed_thumb
        points[THUMB_TIP] = _place_thumb(
            points[THUMB_TIP],
            points[WRIST],
            points[INDEX_TIP],
            (1.0 - t) * closed_reach + t * open_reach,
            (1.0 - t) * closed_gap + t * open_gap,
        )

        frame = cv2.addWeighted(self._closed_frame, 1.0 - t, self._open_frame, t, 0.0)
        return HandSample(frame=frame, points=[Point_(x, y) for x, y in points])

    def stream(self) -> Iterator[HandSample]:
        while True:
            yield self.read()


def Point_(x: float, y: float) -> Point:
    return (float(x), float(y))
