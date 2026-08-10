"""HTTP client for the tele-rehabilitation backend.

Replaces the original ``crud.py``. Three things changed beyond tidying:

1. **Errors are reported, not masked.** ``crud.py`` inspected ``response.text``
   inside ``except RequestException``, but when the connection itself fails
   ``response`` was never assigned — so "backend is down", the single most
   likely failure in a home-rehabilitation setting, surfaced as
   ``UnboundLocalError`` with no hint of the real cause.
2. **One session, one base URL, one timeout.** The original hard-coded
   ``http://localhost:3000`` at five separate call sites and set no timeout at
   all, so an unreachable host hung the game loop indefinitely.
3. **Payload shape lives in** :mod:`telerehab.api.models`, not in UI callbacks.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

import requests

from ..config import BackendConfig
from .models import Patient, Session, new_patient_payload

logger = logging.getLogger(__name__)


class BackendError(RuntimeError):
    """The backend could not be reached, or answered with an error."""


class TeleRehabClient:
    """Thin wrapper over the backend's ``/patients`` and ``/vital-signs``.

    Usable as a context manager to close the underlying connection pool::

        with TeleRehabClient(BackendConfig.from_env()) as client:
            client.ping()
    """

    def __init__(self, config: BackendConfig | None = None):
        self.config = config or BackendConfig.from_env()
        self._session = requests.Session()
        if self.config.token:
            self._session.headers["Authorization"] = f"Bearer {self.config.token}"
        self._session.headers["Content-Type"] = "application/json"

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "TeleRehabClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- plumbing ----------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = self._url(path)
        try:
            response = self._session.request(
                method, url, timeout=self.config.timeout, **kwargs
            )
        except requests.exceptions.ConnectionError as exc:
            raise BackendError(
                f"cannot reach the backend at {self.config.base_url}. "
                "Start it, or run the bundled mock server "
                "(python mock_server/server.py)."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise BackendError(
                f"the backend did not respond within {self.config.timeout:g}s"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise BackendError(f"request to {url} failed: {exc}") from exc

        if response.status_code >= 400:
            # Unlike the original, `response` is guaranteed bound here, so the
            # server's own error body can be surfaced to the caller.
            detail = response.text.strip()[:200] or response.reason
            raise BackendError(f"{method} {url} -> {response.status_code}: {detail}")

        return response

    # -- health ------------------------------------------------------------

    def ping(self) -> bool:
        """True if the backend answers at all. Never raises."""
        try:
            self._request("GET", "/vital-signs")
        except BackendError as exc:
            logger.debug("backend ping failed: %s", exc)
            return False
        return True

    # -- patients ----------------------------------------------------------

    def create_patient(
        self,
        first_name: str,
        last_name: str = "",
        date_of_birth: str = "1990-01-01T00:00:00.000Z",
    ) -> Patient:
        payload = new_patient_payload(
            self.config.doctor_id, first_name, last_name or first_name, date_of_birth
        )
        response = self._request("POST", "/patients", json=payload)
        return Patient.from_payload(response.json())

    def get_patient(self, patient_id: int) -> Patient | None:
        """Fetch a patient, or ``None`` if no such id exists."""
        try:
            response = self._request("GET", f"/patients/{patient_id}")
        except BackendError as exc:
            if "-> 404" in str(exc):
                return None
            raise

        payload = response.json()
        if not payload:
            return None
        return Patient.from_payload(payload)

    def patient_exists(self, patient_id: int) -> bool:
        return self.get_patient(patient_id) is not None

    # -- sessions ----------------------------------------------------------

    def save_session(self, session: Session) -> Session:
        """Persist a completed session and return it with its report id filled in."""
        response = self._request("POST", "/vital-signs", json=session.to_payload())
        stored = Session.from_payload(response.json())
        if stored is None:
            raise BackendError("backend stored the session but returned an unusable row")
        return stored

    def _all_rows(self) -> Sequence[Mapping[str, Any]]:
        payload = self._request("GET", "/vital-signs").json()
        return payload if isinstance(payload, list) else []

    def sessions_for_patient(self, patient_id: int) -> list[Session]:
        """Every exercise session for one patient, oldest first.

        The endpoint has no server-side filter, so this reads the collection and
        filters client-side — as the original did. Fine at thesis scale; the
        first thing to change if this were deployed.
        """
        sessions = [
            session
            for row in self._all_rows()
            if (session := Session.from_payload(row)) is not None
            and session.patient_id == patient_id
        ]
        return sorted(sessions, key=lambda s: s.timestamp or "")

    def session_by_report_id(self, report_id: int) -> Session | None:
        """One session by its own report id, or ``None``."""
        for row in self._all_rows():
            if row.get("id") == report_id:
                return Session.from_payload(row)
        return None
