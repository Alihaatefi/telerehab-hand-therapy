"""The two exercise modes and the rules behind them.

``scoring`` is dependency-free and unit-tested; the other modules need pygame,
so they are imported lazily.
"""
from .scoring import (
    ButterflySmoother,
    CountdownTimer,
    FlowerTarget,
    HoldTimer,
    butterfly_position,
)

__all__ = [
    "ButterflySmoother",
    "CountdownTimer",
    "FlowerTarget",
    "HoldTimer",
    "butterfly_position",
    "OpenCloseGame",
    "TimeScoreGame",
    "RangeCalibrationScreen",
    "TwoPointCalibrationScreen",
]

_LAZY = {
    "TimeScoreGame": ".time_score",
    "OpenCloseGame": ".open_close",
    "RangeCalibrationScreen": ".calibrating",
    "TwoPointCalibrationScreen": ".calibrating",
}


def __getattr__(name: str):  # pragma: no cover - thin lazy-import shim
    if name in _LAZY:
        from importlib import import_module

        return getattr(import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
