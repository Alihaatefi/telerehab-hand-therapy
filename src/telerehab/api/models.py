"""Domain records, and their mapping onto the backend's schema.

.. warning::

   **This module encodes a known design compromise, deliberately kept visible.**

   The backend used by this project is a general-purpose clinical service owned
   by a third party (see the README). Its write surface for time-series patient
   data is a ``/vital-signs`` resource with a fixed medical schema — heart rate,
   respiratory rate, temperature, pain scale — and it could not be extended with
   a rehabilitation-session resource for this thesis.

   Exercise results are therefore *packed into vital-sign fields*. A stored
   record claiming ``heartRate: 14`` is not a heart rate; it is a game score.
   ``painScale`` is not a pain score; it is a discriminator identifying which
   exercise the row came from.

   This is a poor way to model clinical data. It is preserved because it is what
   the deployed system actually does, and inventing a cleaner schema here would
   misrepresent the work.

   The mapping is therefore declared exactly once, in :data:`FIELD_MAP` below,
   and every writer, reader and chart derives from it. Re-deriving it by hand at
   each call site invites the two modes' labels to drift apart, which mislabels
   charts silently — a wrong axis label looks exactly like a right one.

   Anyone extending this project should migrate to a purpose-built endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Mapping


class GameMode(IntEnum):
    """Which exercise a session came from.

    The values are the ``painScale`` codes used to discriminate stored rows.
    """

    TIME_SCORE = 1
    OPEN_CLOSE = 2

    @property
    def title(self) -> str:
        return {
            GameMode.TIME_SCORE: "Time / Score",
            GameMode.OPEN_CLOSE: "Open / Close",
        }[self]


@dataclass(frozen=True)
class MetricField:
    """One exercise metric and the vital-sign field it is stored in."""

    name: str
    label: str
    backend_field: str
    unit: str = ""

    @property
    def axis_label(self) -> str:
        return f"{self.label} ({self.unit})" if self.unit else self.label


#: The single source of truth for the packing described in the module docstring.
#: Report charts, session construction and parsing all read this table, so a
#: label can no longer drift out of sync with the value it describes.
FIELD_MAP: Mapping[GameMode, tuple[MetricField, ...]] = {
    GameMode.TIME_SCORE: (
        MetricField("score", "Score", "heartRate"),
        MetricField("gain", "Gain", "respiratoryRate"),
        MetricField("exercise_seconds", "Exercise Time", "temperature", "s"),
        MetricField("movements", "Movements", "oxygenSaturation"),
    ),
    GameMode.OPEN_CLOSE: (
        MetricField("open_seconds", "Open Time", "heartRate", "s"),
        MetricField("close_seconds", "Close Time", "respiratoryRate", "s"),
        MetricField("repetitions", "Repetitions", "temperature"),
        MetricField("completed_repetitions", "Completed", "oxygenSaturation"),
    ),
}

#: Sent unchanged on every write. The backend requires the field; the value is
#: meaningless here and is never read back.
_BLOOD_PRESSURE_PLACEHOLDER = "120/80"


@dataclass(frozen=True)
class Patient:
    """A patient as returned by the backend's ``/patients`` resource."""

    id: int
    first_name: str = ""
    last_name: str = ""

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Patient:
        return cls(
            id=int(payload["id"]),
            first_name=str(payload.get("firstName", "")),
            last_name=str(payload.get("lastName", "")),
        )

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or f"Patient {self.id}"


@dataclass(frozen=True)
class Session:
    """One completed exercise session.

    ``metrics`` holds the mode's values keyed by :attr:`MetricField.name`, so a
    Time/Score session carries ``score``/``gain``/``exercise_seconds``/
    ``movements`` and an Open/Close session carries its own four.
    """

    patient_id: int
    mode: GameMode
    metrics: Mapping[str, float]
    report_id: int | None = None
    timestamp: str | None = None

    # -- construction ------------------------------------------------------

    @classmethod
    def time_score(
        cls,
        patient_id: int,
        *,
        score: int,
        gain: float,
        exercise_seconds: int,
        movements: int,
    ) -> Session:
        return cls(
            patient_id=patient_id,
            mode=GameMode.TIME_SCORE,
            metrics={
                "score": float(score),
                "gain": float(gain),
                "exercise_seconds": float(exercise_seconds),
                "movements": float(movements),
            },
        )

    @classmethod
    def open_close(
        cls,
        patient_id: int,
        *,
        open_seconds: int,
        close_seconds: int,
        repetitions: int,
        completed_repetitions: int,
    ) -> Session:
        return cls(
            patient_id=patient_id,
            mode=GameMode.OPEN_CLOSE,
            metrics={
                "open_seconds": float(open_seconds),
                "close_seconds": float(close_seconds),
                "repetitions": float(repetitions),
                "completed_repetitions": float(completed_repetitions),
            },
        )

    # -- serialisation -----------------------------------------------------

    def to_payload(self) -> dict[str, Any]:
        """Pack this session into the backend's vital-signs schema."""
        payload: dict[str, Any] = {
            "patientId": self.patient_id,
            "painScale": int(self.mode),
            "bloodPressure": _BLOOD_PRESSURE_PLACEHOLDER,
        }
        for field in FIELD_MAP[self.mode]:
            payload[field.backend_field] = self.metrics[field.name]
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Session | None:
        """Unpack a stored vital-signs row, or ``None`` if it is not a session.

        The ``/vital-signs`` resource is shared with genuine clinical readings
        written by other parts of the platform. Rows whose ``painScale`` is not
        a known game mode are therefore skipped rather than misinterpreted —
        reading a real pain score as a game mode would produce a chart that
        looks perfectly plausible and is entirely wrong.
        """
        try:
            mode = GameMode(int(payload.get("painScale", -1)))
        except ValueError:
            return None

        metrics = {
            field.name: float(payload.get(field.backend_field) or 0.0)
            for field in FIELD_MAP[mode]
        }
        report_id = payload.get("id")
        return cls(
            patient_id=int(payload.get("patientId", 0)),
            mode=mode,
            metrics=metrics,
            report_id=int(report_id) if report_id is not None else None,
            timestamp=payload.get("timestamp"),
        )

    # -- presentation ------------------------------------------------------

    @property
    def fields(self) -> tuple[MetricField, ...]:
        return FIELD_MAP[self.mode]

    @property
    def date(self) -> str:
        """``YYYY-MM-DD`` from the ISO timestamp, or an empty string."""
        return self.timestamp[:10] if self.timestamp else ""

    def chart_title(self) -> str:
        suffix = f" ({self.date})" if self.date else ""
        return f"Patient {self.patient_id} - {self.mode.title}{suffix}"

    def chart_series(self) -> tuple[list[str], list[float]]:
        """Axis labels and values, always drawn from the same table."""
        fields = self.fields
        return (
            [f.axis_label for f in fields],
            [self.metrics[f.name] for f in fields],
        )


def new_patient_payload(
    doctor_id: int, first_name: str, last_name: str, date_of_birth: str
) -> dict[str, Any]:
    """Build a ``/patients`` creation payload.

    The e-mail address is synthesised from the name because the exercise app has
    no reason to ask a patient for one. Contact fields the app does not collect
    are omitted rather than filled with invented values — a placeholder phone
    number in a patient record is worse than an absent one.
    """
    slug = "".join(ch for ch in f"{first_name}{last_name}".lower() if ch.isalnum())
    return {
        "doctorId": doctor_id,
        "firstName": first_name,
        "lastName": last_name,
        "email": f"{slug or 'patient'}@telerehab.local",
        "dob": date_of_birth,
    }
