"""Backend client behaviour, against the bundled mock server.

Running the real mock server rather than mocking ``requests`` means these tests
also check that the client and the mock agree on the wire format — which is the
part most likely to drift.
"""
from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mock_server"))

from server import Store, build_server

from telerehab.api import BackendError, GameMode, Session, TeleRehabClient
from telerehab.config import BackendConfig


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def backend(tmp_path):
    """A live mock backend on a throwaway port with an isolated store."""
    store = Store(tmp_path / "store.json")
    port = _free_port()
    server = build_server("127.0.0.1", port, store)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield BackendConfig(base_url=f"http://127.0.0.1:{port}", timeout=5.0)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def client(backend):
    with TeleRehabClient(backend) as c:
        yield c


class TestPatients:
    def test_create_then_fetch(self, client):
        created = client.create_patient("Ali", "Hatefi")
        assert created.id >= 1
        assert created.display_name == "Ali Hatefi"

        fetched = client.get_patient(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_unknown_patient_is_none_not_an_exception(self, client):
        assert client.get_patient(9999) is None
        assert not client.patient_exists(9999)

    def test_ids_increment(self, client):
        first = client.create_patient("A")
        second = client.create_patient("B")
        assert second.id == first.id + 1


class TestSessions:
    def test_save_returns_a_report_id(self, client):
        patient = client.create_patient("Ali")
        session = Session.time_score(
            patient.id, score=12, gain=1.5, exercise_seconds=60, movements=30
        )

        stored = client.save_session(session)
        assert stored.report_id is not None
        assert stored.timestamp is not None
        assert stored.metrics["score"] == 12

    def test_round_trips_through_a_real_http_hop(self, client):
        """Guards the vital-signs packing across serialisation."""
        patient = client.create_patient("Ali")
        original = Session.open_close(
            patient.id, open_seconds=4, close_seconds=6,
            repetitions=8, completed_repetitions=5,
        )

        stored = client.save_session(original)
        assert stored.mode is GameMode.OPEN_CLOSE
        assert stored.metrics == pytest.approx(dict(original.metrics))

    def test_sessions_for_patient_filters_and_sorts(self, client):
        alice = client.create_patient("Alice")
        bob = client.create_patient("Bob")

        for score in (5, 9):
            client.save_session(
                Session.time_score(alice.id, score=score, gain=1.0,
                                   exercise_seconds=60, movements=1)
            )
        client.save_session(
            Session.time_score(bob.id, score=99, gain=1.0,
                               exercise_seconds=60, movements=1)
        )

        sessions = client.sessions_for_patient(alice.id)
        assert len(sessions) == 2
        assert all(s.patient_id == alice.id for s in sessions)
        assert [s.timestamp for s in sessions] == sorted(s.timestamp for s in sessions)

    def test_lookup_by_report_id(self, client):
        patient = client.create_patient("Ali")
        stored = client.save_session(
            Session.time_score(patient.id, score=3, gain=1.0,
                               exercise_seconds=30, movements=2)
        )

        found = client.session_by_report_id(stored.report_id)
        assert found is not None
        assert found.metrics["score"] == 3

    def test_unknown_report_id_is_none(self, client):
        assert client.session_by_report_id(4242) is None

    def test_saving_for_an_unknown_patient_is_reported(self, client):
        with pytest.raises(BackendError, match="unknown patientId"):
            client.save_session(
                Session.time_score(9999, score=1, gain=1.0,
                                   exercise_seconds=10, movements=0)
            )


class TestFailureModes:
    def test_unreachable_backend_gives_an_actionable_message(self):
        """A refused connection must name the cause and the way out."""
        config = BackendConfig(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
        with TeleRehabClient(config) as client, pytest.raises(BackendError) as exc_info:
            client.create_patient("Ali")

        message = str(exc_info.value)
        assert "cannot reach the backend" in message
        assert "mock_server" in message

    def test_ping_reports_false_instead_of_raising(self):
        config = BackendConfig(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
        with TeleRehabClient(config) as client:
            assert client.ping() is False

    def test_ping_is_true_when_up(self, client):
        assert client.ping() is True

    def test_an_error_response_carries_its_http_status(self, client):
        """Callers branch on the status, not on a substring of the message."""
        with pytest.raises(BackendError) as exc_info:
            client._request("GET", "/no-such-route")
        assert exc_info.value.status_code == 404

    def test_a_failure_before_any_response_has_no_status(self):
        config = BackendConfig(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
        with TeleRehabClient(config) as client, pytest.raises(BackendError) as exc_info:
            client.get_patient(1)
        assert exc_info.value.status_code is None
