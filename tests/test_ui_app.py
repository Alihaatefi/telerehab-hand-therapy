"""The whole application, driven through its widgets.

Real windows (offscreen), real clicks, the real MediaPipe pipeline on the demo
camera, and the project's own mock backend on a real socket. These are the
tests that catch a page wired to the wrong signal - the kind of bug no unit test
of one piece can see.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("mediapipe")

from PySide6.QtCore import QSettings, Qt

from conftest import free_port
from telerehab.api import GameMode, Session
from telerehab.config import BackendConfig, Settings, VisionConfig
from telerehab.ui import theme
from telerehab.ui.main_window import MainWindow
from telerehab.ui.pages.results import ResultsPage
from telerehab.ui.state import AppState
from telerehab.vision.demo import DemoTracker

pytestmark = [pytest.mark.ui, pytest.mark.vision]

LEFT = Qt.MouseButton.LeftButton


def make_state(tmp_path, base_url: str, **vision) -> AppState:
    settings = Settings(
        backend=BackendConfig(base_url=base_url, timeout=2.0),
        vision=VisionConfig(demo=True, **vision),
    )
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    prefs.clear()
    return AppState(settings, store=prefs, pinned={"api_url", "demo"})


@pytest.fixture
def app(qtbot, qapp, live_backend, tmp_path):
    theme.apply_theme(qapp)
    base_url, store = live_backend
    state = make_state(tmp_path, base_url)
    window = MainWindow(state)
    qtbot.addWidget(window)
    window.show()
    yield window, state, store
    window.flow.stop()


def sign_in(qtbot, window, state, patient_id: int) -> None:
    window.show_page("patients")
    window.patients.id_field.setText(str(patient_id))
    qtbot.mouseClick(window.patients.sign_in_button, LEFT)
    qtbot.waitUntil(lambda: state.patient is not None, timeout=8000)


def saved(window) -> bool:
    return "Saved as" in window.flow.results.save_banner._text.text()


# -- navigation and sign-in ---------------------------------------------------------------------


def test_the_backend_status_reaches_the_home_page(qtbot, app):
    window, state, _store = app
    state.check_backend()
    qtbot.waitUntil(lambda: state.backend_ok is True, timeout=8000)
    assert window.home.backend_pill.text() == "Backend connected"
    assert "connected" in window.backend_text.text()
    assert window.camera_text.text() == "Demo camera"


def test_signing_in_by_id_returns_to_home(qtbot, app):
    window, state, _store = app
    patient = state.client.create_patient("Test", "Patient")

    sign_in(qtbot, window, state, patient.id)

    assert state.patient.id == patient.id
    assert window._current == "home"
    assert window.chip_name.text() == "Test Patient"
    assert "Welcome back, Test" in window.home.header.title.text()


def test_an_unknown_id_is_reported_on_the_field(qtbot, app):
    window, state, _store = app
    window.show_page("patients")
    window.patients.id_field.setText("9999")
    qtbot.mouseClick(window.patients.sign_in_button, LEFT)

    qtbot.waitUntil(lambda: not window.patients.id_field._error.isHidden(), timeout=8000)
    assert "No patient with ID 9999" in window.patients.id_field._error.text()
    assert state.patient is None


def test_an_empty_id_is_refused_without_asking_the_backend(qtbot, app):
    window, state, _store = app
    window.show_page("patients")
    qtbot.mouseClick(window.patients.sign_in_button, LEFT)
    assert not window.patients.id_field._error.isHidden()
    assert state.patient is None


def test_registering_shows_the_id_and_signs_in_on_continue(qtbot, app):
    window, state, store = app
    window.show_page("patients")
    window.patients.first_field.setText("Maryam")
    window.patients.last_field.setText("Rezaei")
    qtbot.mouseClick(window.patients.register_button, LEFT)

    qtbot.waitUntil(lambda: len(store.patients) == 1, timeout=8000)
    qtbot.waitUntil(lambda: window.patients._registered is not None, timeout=8000)
    patient = window.patients._registered
    assert patient.display_name == "Maryam Rezaei"
    assert state.patient is None  # not signed in until they have seen their ID

    window.patients._continue_after_registration()
    assert state.patient.id == patient.id
    assert window._current == "home"


def test_registering_needs_a_first_name(qtbot, app):
    window, _state, store = app
    window.show_page("patients")
    qtbot.mouseClick(window.patients.register_button, LEFT)
    assert not window.patients.first_field._error.isHidden()
    assert store.patients == {}


def test_starting_an_exercise_while_signed_out_asks_to_sign_in_first(qtbot, app):
    window, state, _store = app
    patient = state.client.create_patient("Later", "Starter")

    window.start_exercise(GameMode.OPEN_CLOSE)
    assert window._current == "patients"
    assert "Open / Close" in window.patients.notice._text.text()

    window.patients.id_field.setText(str(patient.id))
    qtbot.mouseClick(window.patients.sign_in_button, LEFT)

    # ... and signing in carries straight on into the exercise they asked for.
    qtbot.waitUntil(lambda: window._current == "flow", timeout=8000)
    assert window.flow.mode is GameMode.OPEN_CLOSE
    assert window.flow.stack.currentWidget() is window.flow.setup


def test_wandering_off_the_sign_in_page_abandons_the_pending_exercise(qtbot, app):
    window, state, _store = app
    patient = state.client.create_patient("Wanderer", "X")
    window.start_exercise(GameMode.TIME_SCORE)
    window.show_page("settings")
    sign_in(qtbot, window, state, patient.id)
    assert window._current == "home"  # not flow


# -- the exercises, end to end -------------------------------------------------------------------


def test_a_time_score_session_runs_and_reaches_the_backend(qtbot, app):
    window, state, store = app
    patient = state.client.create_patient("Time", "Score")
    sign_in(qtbot, window, state, patient.id)

    window.start_exercise(GameMode.TIME_SCORE)
    setup = window.flow.setup
    setup._fields["exercise_seconds"].setValue(5)
    setup._fields["calibration_seconds"].setValue(3)
    qtbot.mouseClick(setup.go, LEFT)

    qtbot.waitUntil(lambda: window.flow.stack.currentWidget() is window.flow.results, timeout=60000)
    qtbot.waitUntil(lambda: saved(window), timeout=8000)

    assert len(store.vital_signs) == 1
    row = store.vital_signs[0]
    assert row["patientId"] == patient.id
    assert row["painScale"] == int(GameMode.TIME_SCORE)
    assert row["temperature"] == 5  # exercise_seconds, via the single FIELD_MAP table

    # The result is on screen, with the same labels the reports will use.
    tiles = [window.flow.results.tiles.itemAt(i).widget() for i in range(window.flow.results.tiles.count())]
    assert [t.caption.text() for t in tiles] == ["Score", "Gain", "Exercise Time", "Movements"]

    # ... and "View report" lands on that patient's history.
    qtbot.mouseClick(window.flow.results.view_button, LEFT)
    qtbot.waitUntil(lambda: len(window.reports._sessions) == 1, timeout=8000)
    assert window._current == "reports"
    assert window.reports._sessions[0].mode is GameMode.TIME_SCORE
    # The camera is released the moment the exercise ends.
    assert window.flow._camera is None


def test_an_open_close_session_completes_its_repetition(qtbot, app, monkeypatch):
    window, state, store = app
    patient = state.client.create_patient("Open", "Close")
    sign_in(qtbot, window, state, patient.id)

    # A demo hand we can pose by hand, instead of the free-running animation.
    pose: dict[str, DemoTracker] = {}

    def controlled(_vision=None):
        def make():
            tracker = DemoTracker(VisionConfig(), realtime=True)
            tracker.set_openness(1.0)
            pose["hand"] = tracker
            return tracker.open()

        return make

    monkeypatch.setattr(state, "tracker_factory", controlled)

    reference = DemoTracker(realtime=False)
    reference.set_openness(1.0)
    open_pinch = reference.read().pinch
    reference.set_openness(0.0)
    closed_pinch = reference.read().pinch

    window.start_exercise(GameMode.OPEN_CLOSE)
    setup = window.flow.setup
    setup._fields["open_seconds"].setValue(1)
    setup._fields["close_seconds"].setValue(1)
    setup._fields["repetitions"].setValue(1)
    qtbot.mouseClick(setup.go, LEFT)

    cal = window.flow.calibration
    qtbot.waitUntil(lambda: cal._last is not None and "hand" in pose, timeout=30000)

    pose["hand"].set_openness(1.0)
    qtbot.waitUntil(lambda: cal._last.has_hand and abs(cal._last.pinch - open_pinch) < 1e-6, timeout=10000)
    cal._capture()
    pose["hand"].set_openness(0.0)
    qtbot.waitUntil(lambda: cal._last.has_hand and abs(cal._last.pinch - closed_pinch) < 1e-6, timeout=10000)
    cal._capture()
    assert cal._two.stage == "confirm"
    cal._confirm()

    session = window.flow.session
    qtbot.waitUntil(lambda: session.engine is not None, timeout=15000)
    assert session.engine.target_open is True

    pose["hand"].set_openness(1.0)  # hold open ...
    qtbot.waitUntil(lambda: session.engine is None or session.engine.index >= 1, timeout=10000)
    pose["hand"].set_openness(0.0)  # ... then closed
    qtbot.waitUntil(lambda: window.flow.stack.currentWidget() is window.flow.results, timeout=15000)
    qtbot.waitUntil(lambda: saved(window), timeout=8000)

    row = store.vital_signs[0]
    assert row["painScale"] == int(GameMode.OPEN_CLOSE)
    assert row["temperature"] == 1  # repetitions prescribed
    assert row["oxygenSaturation"] == 1  # repetitions completed


def test_the_wrong_posture_never_completes_a_hold(qtbot, app, monkeypatch):
    """Holding closed when asked for open must leave the timer where it was."""
    window, state, _store = app
    patient = state.client.create_patient("Wrong", "Posture")
    sign_in(qtbot, window, state, patient.id)

    pose: dict[str, DemoTracker] = {}

    def controlled(_vision=None):
        def make():
            tracker = DemoTracker(VisionConfig(), realtime=True)
            tracker.set_openness(1.0)
            pose["hand"] = tracker
            return tracker.open()

        return make

    monkeypatch.setattr(state, "tracker_factory", controlled)
    reference = DemoTracker(realtime=False)
    reference.set_openness(1.0)
    open_pinch = reference.read().pinch
    reference.set_openness(0.0)
    closed_pinch = reference.read().pinch

    window.start_exercise(GameMode.OPEN_CLOSE)
    qtbot.mouseClick(window.flow.setup.go, LEFT)
    cal = window.flow.calibration
    qtbot.waitUntil(lambda: cal._last is not None and "hand" in pose, timeout=30000)
    pose["hand"].set_openness(1.0)
    qtbot.waitUntil(lambda: cal._last.has_hand and abs(cal._last.pinch - open_pinch) < 1e-6, timeout=10000)
    cal._capture()
    pose["hand"].set_openness(0.0)
    qtbot.waitUntil(lambda: cal._last.has_hand and abs(cal._last.pinch - closed_pinch) < 1e-6, timeout=10000)
    cal._capture()
    cal._confirm()

    session = window.flow.session
    qtbot.waitUntil(lambda: session.engine is not None, timeout=15000)
    qtbot.wait(1500)  # closed hand, but open is asked for
    assert session.engine.index == 0
    assert session.engine.timer.progress == 0.0
    assert "Adjust your hand" in session.status.text()


# -- failure and settings ---------------------------------------------------------------------------


def test_an_unreachable_backend_keeps_the_result_and_offers_a_retry(qtbot, qapp, tmp_path):
    theme.apply_theme(qapp)
    state = make_state(tmp_path, f"http://127.0.0.1:{free_port()}")
    state.client.config  # noqa: B018 - the client targets a port with nobody listening

    page = ResultsPage(state)
    qtbot.addWidget(page)
    page.show()
    session = Session.time_score(1, score=7, gain=1.0, exercise_seconds=60, movements=12)
    page.show_result(session, None)

    qtbot.waitUntil(lambda: page.retry.isVisible(), timeout=10000)
    assert "not saved" in page.save_banner._text.text()
    assert "retry" in page.save_banner._text.text()
    assert not page.view_button.isEnabled()
    assert page.session is session  # still held, so nothing is lost


def test_a_camera_failure_is_reported_and_the_result_still_shown(qtbot, qapp, live_backend, tmp_path):
    theme.apply_theme(qapp)
    base_url, store = live_backend
    state = make_state(tmp_path, base_url)
    patient = state.client.create_patient("Cam", "Fail")

    page = ResultsPage(state)
    qtbot.addWidget(page)
    page.show()
    partial = Session.time_score(patient.id, score=2, gain=1.0, exercise_seconds=60, movements=3)
    page.show_result(partial, "The camera stopped working: camera stopped delivering frames")

    assert not page.camera_notice.isHidden()
    qtbot.waitUntil(lambda: "Saved as" in page.save_banner._text.text(), timeout=8000)
    assert len(store.vital_signs) == 1  # the partial session is not thrown away


def test_settings_persist_and_rebuild_the_client(qtbot, app, tmp_path, live_backend):
    window, state, _store = app
    page = window.settings_page
    old_client = state.client

    page.url.setText("http://127.0.0.1:9")
    page.sound.setChecked(False)
    page.camera_index.setValue(2)
    page._save()

    assert state.settings.backend.base_url == "http://127.0.0.1:9"
    assert state.client is not old_client
    assert state.sound_enabled is False
    assert state.settings.vision.camera_index == 2
    assert state.store.value("backend/url") == "http://127.0.0.1:9"
    assert not page.saved.isHidden()


def test_an_invalid_backend_url_is_refused(qtbot, app):
    window, state, _store = app
    page = window.settings_page
    before = state.settings.backend.base_url

    page.url.setText("localhost:3000")  # no scheme
    page._save()

    assert state.settings.backend.base_url == before
    assert not page.url._error.isHidden()


def test_saved_preferences_survive_a_restart_but_the_command_line_wins(tmp_path):
    prefs_path = tmp_path / "prefs.ini"
    first = QSettings(str(prefs_path), QSettings.Format.IniFormat)
    state = AppState(Settings(), store=first)
    state.apply(base_url="http://example.test:4000", camera_index=3, demo=True)
    first.sync()

    reopened = AppState(Settings(), store=QSettings(str(prefs_path), QSettings.Format.IniFormat))
    assert reopened.settings.backend.base_url == "http://example.test:4000"
    assert reopened.settings.vision.camera_index == 3
    assert reopened.settings.vision.demo is True

    pinned = AppState(
        Settings(backend=BackendConfig(base_url="http://cli.test:1")),
        store=QSettings(str(prefs_path), QSettings.Format.IniFormat),
        pinned={"api_url"},
    )
    assert pinned.settings.backend.base_url == "http://cli.test:1"  # CLI beat the saved one
    assert pinned.settings.vision.camera_index == 3  # not pinned, so the saved one applies
