"""Application-wide state: who is signed in, how to reach the backend and camera.

Pages never build a client or a tracker themselves; they ask this object, so
changing the backend URL or switching to the demo camera in Settings takes
effect everywhere at once.

Preferences set in the Settings page persist between runs through
:class:`QSettings`. Anything given explicitly on the command line wins over a
stored preference for that run (see ``pinned``).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Iterable

from PySide6.QtCore import QObject, QSettings, QUrl, Signal

from ..api import Patient, TeleRehabClient
from ..config import SOUNDS_DIR, Settings, VisionConfig
from .tasks import run_async

SETTINGS_ORG = "TeleRehab"
SETTINGS_APP = "HandTherapy"


class AppState(QObject):
    patientChanged = Signal(object)  # Patient | None
    settingsChanged = Signal()
    backendChanged = Signal(object)  # True / False / None (unknown)

    def __init__(
        self,
        settings: Settings,
        *,
        store: QSettings | None = None,
        pinned: Iterable[str] = (),
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.store = store
        self._pinned = set(pinned)
        self.settings = self._with_stored(settings)
        self.client = TeleRehabClient(self.settings.backend)

        self.patient: Patient | None = None
        self.backend_ok: bool | None = None
        self.sound_enabled = self._stored("app/sound", True, bool)
        self._chime: Any = None

    # -- stored preferences ----------------------------------------------------

    def _stored(self, key: str, default: Any, kind: type) -> Any:
        if self.store is None:
            return default
        value = self.store.value(key, default)
        if kind is bool:
            return value if isinstance(value, bool) else str(value).lower() == "true"
        try:
            return kind(value)
        except (TypeError, ValueError):
            return default

    def _with_stored(self, settings: Settings) -> Settings:
        if self.store is None:
            return settings

        backend, vision = settings.backend, settings.vision
        if "api_url" not in self._pinned:
            url = self._stored("backend/url", backend.base_url, str)
            backend = replace(backend, base_url=url.rstrip("/"))
        if "camera" not in self._pinned:
            vision = replace(
                vision,
                camera_index=self._stored("vision/camera_index", vision.camera_index, int),
            )
        if "demo" not in self._pinned:
            vision = replace(vision, demo=self._stored("vision/demo", vision.demo, bool))
        return replace(settings, backend=backend, vision=vision)

    def apply(
        self,
        *,
        base_url: str | None = None,
        camera_index: int | None = None,
        demo: bool | None = None,
        sound: bool | None = None,
    ) -> None:
        """Change settings, persist them, and rebuild whatever depends on them."""
        backend, vision = self.settings.backend, self.settings.vision

        if base_url is not None:
            backend = replace(backend, base_url=base_url.strip().rstrip("/"))
        if camera_index is not None:
            vision = replace(vision, camera_index=camera_index)
        if demo is not None:
            vision = replace(vision, demo=demo)
        if sound is not None:
            self.sound_enabled = sound

        if backend != self.settings.backend:
            self.client.close()
            self.client = TeleRehabClient(backend)
            self.backend_ok = None

        self.settings = replace(self.settings, backend=backend, vision=vision)

        if self.store is not None:
            self.store.setValue("backend/url", backend.base_url)
            self.store.setValue("vision/camera_index", vision.camera_index)
            self.store.setValue("vision/demo", vision.demo)
            self.store.setValue("app/sound", self.sound_enabled)
            self.store.sync()

        self.settingsChanged.emit()
        self.check_backend()

    # -- patient -----------------------------------------------------------------

    def set_patient(self, patient: Patient | None) -> None:
        self.patient = patient
        self.patientChanged.emit(patient)

    # -- backend -------------------------------------------------------------------

    def check_backend(self) -> None:
        """Probe the backend without blocking, then announce the result."""
        client = self.client

        def done(ok: bool) -> None:
            if client is self.client:  # ignore a probe for a replaced client
                self.backend_ok = ok
                self.backendChanged.emit(ok)

        run_async(client.ping, done, lambda _exc: done(False), owner=self)

    # -- camera --------------------------------------------------------------------

    @property
    def camera_label(self) -> str:
        vision = self.settings.vision
        return "Demo camera" if vision.demo else f"Camera {vision.camera_index}"

    def tracker_factory(self, vision: VisionConfig | None = None) -> Callable[[], Any]:
        """A callable that builds an opened tracker; it runs on the camera thread.

        ``vision`` overrides the saved camera settings, so Settings can test a
        camera before committing to it.
        """
        vision = vision or self.settings.vision

        if vision.demo:
            def make_demo() -> Any:
                from ..vision.demo import DemoTracker

                return DemoTracker(vision).open()

            return make_demo

        def make_camera() -> Any:
            from ..vision.hand_tracker import HandTracker

            return HandTracker(vision, draw_landmarks=False).open()

        return make_camera

    # -- sound ---------------------------------------------------------------------

    def play_chime(self) -> None:
        if not self.sound_enabled:
            return
        if self._chime is None:
            try:
                from PySide6.QtMultimedia import QSoundEffect

                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(str(SOUNDS_DIR / "score.wav")))
                effect.setVolume(0.55)
                self._chime = effect
            except Exception:
                self._chime = False
        if self._chime:
            self._chime.play()

    # -- lifecycle -----------------------------------------------------------------

    def close(self) -> None:
        self.client.close()
