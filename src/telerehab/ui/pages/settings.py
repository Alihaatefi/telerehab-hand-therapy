"""Settings: where the backend is, which camera to use, sound."""
from __future__ import annotations

import platform
from dataclasses import replace
from importlib import metadata

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ... import __version__
from ...api import TeleRehabClient
from ...config import BackendConfig
from ..state import AppState
from ..tasks import run_async
from ..widgets import (
    Banner,
    Card,
    Page,
    PageHeader,
    Pill,
    SpinField,
    Switch,
    TextField,
    button,
    label,
    rule,
    scrollable,
)


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not installed"


class SettingsPage(Page):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        content = QWidget()
        content.setObjectName("Page")
        column = QVBoxLayout(content)
        column.setContentsMargins(36, 30, 36, 36)
        column.setSpacing(18)

        column.addWidget(PageHeader(
            "Settings", "Where results are sent, and which camera is used.", eyebrow="Preferences"
        ))

        self.saved = Banner("Settings saved.", "success")
        self.saved.setVisible(False)
        column.addWidget(self.saved)

        column.addWidget(self._connection_card())
        column.addWidget(self._camera_card())
        column.addWidget(self._sound_card())
        column.addWidget(self._about_card())

        actions = QHBoxLayout()
        actions.addStretch(1)
        revert = button("Revert", "ghost", size="lg")
        revert.clicked.connect(self.load)
        save = button("Save changes", "primary", icon="check", size="lg")
        save.clicked.connect(self._save)
        actions.addWidget(revert)
        actions.addWidget(save)
        column.addLayout(actions)
        column.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))

        self.load()

    # -- cards ----------------------------------------------------------------------------

    @staticmethod
    def _heading(title: str, text: str) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(label(title, "h2"))
        box.addWidget(label(text, "muted", wrap=True))
        return box

    def _connection_card(self) -> Card:
        card = Card(padding=24, spacing=14)
        card.body.addLayout(self._heading(
            "Backend",
            "The server that stores patients and sessions. Use the bundled mock server "
            "for demonstrations.",
        ))
        self.url = TextField("Backend URL", placeholder="http://localhost:3000", max_length=200)
        card.body.addWidget(self.url)

        row = QHBoxLayout()
        row.setSpacing(12)
        test = button("Test connection", icon="wifi")
        test.clicked.connect(self._test_backend)
        self.backend_result = Pill("", "neutral")
        self.backend_result.setVisible(False)
        row.addWidget(test)
        row.addWidget(self.backend_result)
        row.addStretch(1)
        card.body.addLayout(row)
        return card

    def _camera_card(self) -> Card:
        card = Card(padding=24, spacing=14)
        card.body.addLayout(self._heading(
            "Camera",
            "Hand tracking runs on this computer; video is never stored or sent anywhere.",
        ))

        row = QHBoxLayout()
        row.setSpacing(24)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label("Camera number", "h3"))
        text.addWidget(label("0 is the default camera. Try 1 or 2 if you have several.", "muted", wrap=True))
        row.addLayout(text, 1)
        self.camera_index = SpinField(minimum=0, maximum=9, value=0)
        self.camera_index.setFixedWidth(170)
        row.addWidget(self.camera_index, 0, Qt.AlignmentFlag.AlignTop)
        card.body.addLayout(row)
        card.body.addWidget(rule())

        demo_row = QHBoxLayout()
        demo_row.setSpacing(24)
        demo_text = QVBoxLayout()
        demo_text.setSpacing(2)
        demo_text.addWidget(label("Demo camera", "h3"))
        demo_text.addWidget(label(
            "Use a simulated hand instead of a real camera. For demonstrations and "
            "computers without a webcam.", "muted", wrap=True,
        ))
        demo_row.addLayout(demo_text, 1)
        self.demo = Switch()
        demo_row.addWidget(self.demo, 0, Qt.AlignmentFlag.AlignTop)
        card.body.addLayout(demo_row)
        card.body.addWidget(rule())

        probe = QHBoxLayout()
        probe.setSpacing(12)
        test = button("Test camera", icon="camera")
        test.clicked.connect(self._test_camera)
        self.camera_result = Pill("", "neutral")
        self.camera_result.setVisible(False)
        probe.addWidget(test)
        probe.addWidget(self.camera_result)
        probe.addStretch(1)
        card.body.addLayout(probe)
        return card

    def _sound_card(self) -> Card:
        card = Card(padding=24, spacing=14)
        row = QHBoxLayout()
        row.setSpacing(24)
        row.addLayout(self._heading("Sound effects", "A short chime when a point is scored or a hold is completed."), 1)
        self.sound = Switch()
        row.addWidget(self.sound, 0, Qt.AlignmentFlag.AlignTop)
        card.body.addLayout(row)
        return card

    def _about_card(self) -> Card:
        card = Card(padding=24, spacing=8)
        card.body.addWidget(label("About", "h2"))
        facts = [
            ("TeleRehab - Hand Therapy", __version__),
            ("Python", platform.python_version()),
            ("PySide6 (Qt)", pyside_version),
            ("MediaPipe", _version("mediapipe")),
            ("OpenCV", _version("opencv-python")),
        ]
        for name, value in facts:
            row = QHBoxLayout()
            row.addWidget(label(name, "muted"))
            row.addStretch(1)
            row.addWidget(label(value, "mono"))
            card.body.addLayout(row)
        return card

    # -- values ----------------------------------------------------------------------------------

    def load(self) -> None:
        """Fill the controls from the saved settings."""
        settings = self.state.settings
        self.url.setText(settings.backend.base_url)
        self.camera_index.setValue(settings.vision.camera_index)
        self.demo.setChecked(settings.vision.demo)
        self.sound.setChecked(self.state.sound_enabled)
        self.saved.setVisible(False)
        self.backend_result.setVisible(False)
        self.camera_result.setVisible(False)

    def on_show(self) -> None:
        self.saved.setVisible(False)

    def _save(self) -> None:
        url = self.url.text()
        if not url.lower().startswith(("http://", "https://")):
            self.url.set_error("The URL must start with http:// or https://")
            return
        self.state.apply(
            base_url=url,
            camera_index=int(self.camera_index.value()),
            demo=self.demo.isChecked(),
            sound=self.sound.isChecked(),
        )
        self.saved.setVisible(True)

    # -- tests ---------------------------------------------------------------------------------------

    def _test_backend(self) -> None:
        url = self.url.text()
        if not url.lower().startswith(("http://", "https://")):
            self.url.set_error("The URL must start with http:// or https://")
            return

        self.backend_result.set("Checking...", "neutral")
        self.backend_result.setVisible(True)
        config = replace(BackendConfig(base_url=url.rstrip("/")), timeout=self.state.settings.backend.timeout)

        def probe() -> bool:
            with TeleRehabClient(config) as client:
                return client.ping()

        run_async(
            probe,
            lambda ok: self.backend_result.set("Connected" if ok else "Unreachable", "success" if ok else "danger"),
            lambda _exc: self.backend_result.set("Unreachable", "danger"),
            owner=self,
        )

    def _test_camera(self) -> None:
        self.camera_result.set("Checking...", "neutral")
        self.camera_result.setVisible(True)
        vision = replace(
            self.state.settings.vision,
            camera_index=int(self.camera_index.value()),
            demo=self.demo.isChecked(),
        )
        factory = self.state.tracker_factory(vision)

        def probe() -> tuple[int, int, bool]:
            tracker = factory()
            try:
                sample = tracker.read()
            finally:
                tracker.close()
            height, width = sample.frame.shape[:2]
            return width, height, sample.has_hand

        def done(result) -> None:
            width, height, hand = result
            suffix = ", hand detected" if hand else ""
            self.camera_result.set(f"Working - {width}x{height}{suffix}", "success")

        def failed(exc: Exception) -> None:
            self.camera_result.set(f"Unavailable - {exc}", "danger")

        run_async(probe, done, failed, owner=self)
