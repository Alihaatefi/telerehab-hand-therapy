"""Runtime configuration.

Everything that used to be a hard-coded literal scattered across the game files
lives here. The backend URL is read from the environment so the same build can
talk to the real service or to the bundled mock server.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"

IMAGES_DIR = ASSETS_DIR / "images"
SOUNDS_DIR = ASSETS_DIR / "sounds"

DEFAULT_BASE_URL = "http://localhost:3000"


@dataclass(frozen=True)
class BackendConfig:
    """How to reach the tele-rehabilitation REST backend.

    The backend itself is a third-party service and is not part of this
    repository; `mock_server/` implements just enough of it to run the game.
    """

    base_url: str = DEFAULT_BASE_URL
    token: str | None = None
    timeout: float = 5.0
    doctor_id: int = 1

    @classmethod
    def from_env(cls) -> "BackendConfig":
        return cls(
            base_url=os.environ.get("TELEREHAB_API_URL", DEFAULT_BASE_URL).rstrip("/"),
            token=os.environ.get("TELEREHAB_API_TOKEN") or None,
            timeout=float(os.environ.get("TELEREHAB_API_TIMEOUT", "5.0")),
            doctor_id=int(os.environ.get("TELEREHAB_DOCTOR_ID", "1")),
        )


@dataclass(frozen=True)
class VisionConfig:
    """Camera and MediaPipe Hands parameters."""

    camera_index: int = 0
    max_num_hands: int = 1
    min_detection_confidence: float = 0.7
    min_tracking_confidence: float = 0.7

    #: Openness percentages at which a hand flips between open and closed.
    #: The gap between them is deliberate hysteresis, so a hand hovering near
    #: the midpoint does not rack up dozens of phantom movements.
    open_threshold: float = 70.0
    close_threshold: float = 30.0


@dataclass(frozen=True)
class GameConfig:
    """Defaults for both exercise modes. All of these are editable in-game."""

    window_size: tuple[int, int] = (900, 700)
    fps: int = 30

    # Time/Score mode
    exercise_seconds: int = 60
    gain: float = 1.0
    calibration_seconds: int = 5
    #: How close (px) the butterfly must be to the flower, and for how long (s),
    #: before a point is scored.
    flower_tolerance_px: int = 50
    flower_dwell_seconds: float = 0.5
    #: Number of samples in the moving average that smooths butterfly motion.
    #: Raw MediaPipe openness is jittery enough to be unpleasant without it.
    smoothing_window: int = 5

    # Open/Close mode
    open_seconds: int = 5
    close_seconds: int = 5
    repetitions: int = 3


@dataclass(frozen=True)
class Settings:
    backend: BackendConfig = field(default_factory=BackendConfig.from_env)
    vision: VisionConfig = field(default_factory=VisionConfig)
    game: GameConfig = field(default_factory=GameConfig)


def load_settings() -> Settings:
    return Settings()
