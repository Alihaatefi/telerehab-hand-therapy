"""Results: what happened, and whether it reached the backend."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...api import GameMode, Session
from ...reports import format_value
from .. import icons, theme
from ..state import AppState
from ..tasks import run_async
from ..widgets import Banner, Page, StatTile, button, clear_layout, label


class ResultsPage(Page):
    viewReports = Signal(int)  # patient id
    again = Signal()
    home = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.session: Session | None = None
        self._saving = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(36, 8, 36, 28)
        outer.addStretch(1)

        column = QVBoxLayout()
        column.setSpacing(18)
        holder = QWidget()
        holder.setObjectName("Page")
        holder.setMaximumWidth(860)
        holder.setLayout(column)
        outer.addWidget(holder, 6)
        outer.addStretch(1)

        self.badge = QLabel()
        self.badge.setFixedSize(64, 64)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(self.badge)

        self.title = label("", "display")
        self.subtitle = label("", "muted", wrap=True)
        column.addWidget(self.title)
        column.addWidget(self.subtitle)

        self.camera_notice = Banner("", "warning")
        self.camera_notice.setVisible(False)
        column.addWidget(self.camera_notice)

        self.tiles = QHBoxLayout()
        self.tiles.setSpacing(14)
        column.addLayout(self.tiles)

        self.save_banner = Banner("", "info")
        self.retry = button("Retry", "primary", icon="refresh", size="sm")
        self.retry.clicked.connect(self._save)
        self.save_banner.add_action(self.retry)
        column.addWidget(self.save_banner)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.view_button = button("View report", "primary", icon="bar-chart", size="lg")
        self.view_button.clicked.connect(self._view)
        self.again_button = button("Run again", icon="repeat", size="lg")
        self.again_button.clicked.connect(self.again)
        self.home_button = button("Back to home", "ghost", size="lg")
        self.home_button.clicked.connect(self.home)
        for widget in (self.view_button, self.again_button):
            actions.addWidget(widget)
        actions.addStretch(1)
        actions.addWidget(self.home_button)
        column.addLayout(actions)
        column.addStretch(1)

    # -- showing -------------------------------------------------------------------------

    def show_result(self, session: Session | None, error: str | None) -> None:
        self.session = session
        clear_layout(self.tiles)

        self.camera_notice.setVisible(bool(error))
        if error:
            self.camera_notice.set(error, "warning")

        if session is None:
            self._style_badge("alert", theme.WARNING, theme.WARNING_SOFT)
            self.title.setText("The exercise could not start")
            self.subtitle.setText("Nothing was recorded. Check the camera and try again.")
            self.save_banner.setVisible(False)
            self.view_button.setVisible(False)
            return

        self.view_button.setVisible(True)
        self.view_button.setEnabled(False)
        self._style_badge("check", theme.SUCCESS, theme.SUCCESS_SOFT)
        self.title.setText("Session complete")

        if session.mode is GameMode.TIME_SCORE:
            self.subtitle.setText(
                f"Time / Score - you scored {int(session.metrics['score'])} with "
                f"{int(session.metrics['movements'])} movements."
            )
        else:
            done = int(session.metrics["completed_repetitions"])
            total = int(session.metrics["repetitions"])
            self.subtitle.setText(f"Open / Close - {done} of {total} repetitions completed.")

        for field in session.fields:
            tile = StatTile(field.label, format_value(field, session.metrics[field.name]))
            self.tiles.addWidget(tile, 1)

        self._save()

    def _style_badge(self, glyph: str, colour: str, background: str) -> None:
        self.badge.setPixmap(icons.pixmap(glyph, colour, 32, stroke=2.2))
        self.badge.setStyleSheet(f"background: {background}; border-radius: 32px;")

    # -- saving ------------------------------------------------------------------------------

    def _save(self) -> None:
        session = self.session
        if session is None or self._saving:
            return
        self._saving = True
        self.retry.setVisible(False)
        self.save_banner.set("Saving to the backend...", "info")
        self.save_banner.setVisible(True)
        client = self.state.client

        def done(stored: Session) -> None:
            self._saving = False
            self.session = stored
            self.save_banner.set(f"Saved as report #{stored.report_id}.", "success")
            self.view_button.setEnabled(True)

        def failed(exc: Exception) -> None:
            self._saving = False
            self.save_banner.set(
                f"The session was not saved: {exc}\nThe results are kept here, so you can retry.",
                "danger",
            )
            self.retry.setVisible(True)

        run_async(lambda: client.save_session(session), done, failed, owner=self)

    def _view(self) -> None:
        if self.session is not None:
            self.viewReports.emit(self.session.patient_id)
