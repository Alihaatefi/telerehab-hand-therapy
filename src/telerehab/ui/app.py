"""Start-up: create the Qt application, apply the theme, show the window."""
from __future__ import annotations

import sys
from typing import Iterable

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from ..config import Settings
from . import theme
from .state import SETTINGS_APP, SETTINGS_ORG, AppState


def build_application(argv: list[str] | None = None) -> QApplication:
    """The one QApplication, themed. Safe to call more than once."""
    existing = QApplication.instance()
    app = (
        existing
        if isinstance(existing, QApplication)
        else QApplication(argv if argv is not None else sys.argv[:1])
    )
    app.setOrganizationName(SETTINGS_ORG)
    app.setApplicationName(SETTINGS_APP)
    app.setApplicationDisplayName("TeleRehab - Hand Therapy")
    theme.apply_theme(app)
    return app


def run(settings: Settings, *, pinned: Iterable[str] = ()) -> int:
    """Open the window and run until it is closed.

    ``pinned`` names the settings given explicitly on the command line
    (``"api_url"``, ``"camera"``, ``"demo"``); those win over saved preferences
    for this run.
    """
    from .main_window import MainWindow

    app = build_application()
    state = AppState(
        settings,
        store=QSettings(SETTINGS_ORG, SETTINGS_APP),
        pinned=pinned,
    )
    window = MainWindow(state)
    window.show()
    state.check_backend()
    return app.exec()
