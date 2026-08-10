"""Computer-vision layer: camera capture, hand landmarks, calibration.

``geometry`` and ``calibration`` are dependency-free and safe to import
anywhere. ``hand_tracker`` pulls in OpenCV and MediaPipe, so it is imported
lazily to keep test collection and ``--help`` fast.
"""
from .calibration import (
    CalibrationError,
    MovementCounter,
    RangeCalibration,
    TwoPointCalibration,
)
from .geometry import (
    FINGERTIPS,
    INDEX_TIP,
    THUMB_TIP,
    WRIST,
    distance,
    moving_average,
    pinch_openness,
    spread_openness,
)

__all__ = [
    "CalibrationError",
    "MovementCounter",
    "RangeCalibration",
    "TwoPointCalibration",
    "FINGERTIPS",
    "INDEX_TIP",
    "THUMB_TIP",
    "WRIST",
    "distance",
    "moving_average",
    "pinch_openness",
    "spread_openness",
    "HandSample",
    "HandTracker",
    "CameraError",
    "still_image_tracker",
]


def __getattr__(name: str):  # pragma: no cover - thin lazy-import shim
    if name in {"HandSample", "HandTracker", "CameraError", "still_image_tracker"}:
        from . import hand_tracker

        return getattr(hand_tracker, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
