"""The two exercise modes and the rules behind them.

Everything here is dependency-free and unit-tested: the engines take any object
shaped like a camera frame (see :mod:`telerehab.games.protocols`) and an
injectable clock, so a whole session can be played through in a test.
"""
from .calibrating import RangeCalibrationTask, TwoPointCalibrationTask
from .open_close import OpenCloseEngine
from .scoring import (
    ButterflySmoother,
    CountdownTimer,
    FlowerTarget,
    HoldTimer,
    butterfly_position,
)
from .time_score import TimeScoreEngine

__all__ = [
    "ButterflySmoother",
    "CountdownTimer",
    "FlowerTarget",
    "HoldTimer",
    "OpenCloseEngine",
    "RangeCalibrationTask",
    "TimeScoreEngine",
    "TwoPointCalibrationTask",
    "butterfly_position",
]
