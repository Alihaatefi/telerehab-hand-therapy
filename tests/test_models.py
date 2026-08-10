"""The vital-signs packing described in telerehab/api/models.py.

These tests exist mainly to pin down the compromise documented there: exercise
metrics travel inside clinical vital-sign fields. If that mapping ever drifts,
stored history silently changes meaning, so it is asserted explicitly.
"""
from __future__ import annotations

import pytest

from telerehab.api.models import (
    FIELD_MAP,
    GameMode,
    Patient,
    Session,
    new_patient_payload,
)


class TestFieldMap:
    def test_every_mode_has_a_label_table(self):
        assert set(FIELD_MAP) == set(GameMode)

    def test_the_two_modes_do_not_share_labels(self):
        """Disjoint label sets are what keeps the two modes unconfusable."""
        time_score = {f.label for f in FIELD_MAP[GameMode.TIME_SCORE]}
        open_close = {f.label for f in FIELD_MAP[GameMode.OPEN_CLOSE]}
        assert not (time_score & open_close)

    def test_backend_fields_are_unique_within_a_mode(self):
        for mode, fields in FIELD_MAP.items():
            backend_fields = [f.backend_field for f in fields]
            assert len(backend_fields) == len(set(backend_fields)), mode

    def test_axis_label_includes_the_unit(self):
        seconds = next(
            f for f in FIELD_MAP[GameMode.TIME_SCORE] if f.name == "exercise_seconds"
        )
        assert seconds.axis_label == "Exercise Time (s)"


class TestTimeScoreSession:
    def make(self):
        return Session.time_score(
            42, score=14, gain=1.5, exercise_seconds=60, movements=27
        )

    def test_packs_metrics_into_vital_sign_fields(self):
        payload = self.make().to_payload()
        assert payload["patientId"] == 42
        assert payload["painScale"] == 1
        assert payload["heartRate"] == 14        # score
        assert payload["respiratoryRate"] == 1.5  # gain
        assert payload["temperature"] == 60       # exercise seconds
        assert payload["oxygenSaturation"] == 27  # movements

    def test_round_trips(self):
        original = self.make()
        restored = Session.from_payload({**original.to_payload(), "id": 7})

        assert restored is not None
        assert restored.mode is GameMode.TIME_SCORE
        assert restored.patient_id == 42
        assert restored.report_id == 7
        assert restored.metrics == pytest.approx(dict(original.metrics))

    def test_chart_series_labels_match_their_values(self):
        labels, values = self.make().chart_series()
        assert labels == ["Score", "Gain", "Exercise Time (s)", "Movements"]
        assert values == [14.0, 1.5, 60.0, 27.0]


class TestOpenCloseSession:
    def make(self):
        return Session.open_close(
            7, open_seconds=5, close_seconds=3, repetitions=10,
            completed_repetitions=8,
        )

    def test_packs_metrics_into_vital_sign_fields(self):
        payload = self.make().to_payload()
        assert payload["painScale"] == 2
        assert payload["heartRate"] == 5         # open seconds
        assert payload["respiratoryRate"] == 3   # close seconds
        assert payload["temperature"] == 10      # repetitions
        assert payload["oxygenSaturation"] == 8  # completed

    def test_round_trips(self):
        original = self.make()
        restored = Session.from_payload(original.to_payload())

        assert restored is not None
        assert restored.mode is GameMode.OPEN_CLOSE
        assert restored.metrics == pytest.approx(dict(original.metrics))

    def test_chart_series_labels_match_their_values(self):
        labels, values = self.make().chart_series()
        assert labels == ["Open Time (s)", "Close Time (s)", "Repetitions", "Completed"]
        assert values == [5.0, 3.0, 10.0, 8.0]


class TestModeDiscrimination:
    def test_the_two_modes_are_not_confusable(self):
        """Identical raw numbers must read differently per mode."""
        ts = Session.from_payload(
            {"patientId": 1, "painScale": 1, "heartRate": 9,
             "respiratoryRate": 2, "temperature": 30, "oxygenSaturation": 4}
        )
        oc = Session.from_payload(
            {"patientId": 1, "painScale": 2, "heartRate": 9,
             "respiratoryRate": 2, "temperature": 30, "oxygenSaturation": 4}
        )

        assert ts is not None and oc is not None
        assert ts.metrics["score"] == 9
        assert oc.metrics["open_seconds"] == 9
        assert ts.chart_series()[0] != oc.chart_series()[0]

    def test_rows_from_other_parts_of_the_platform_are_skipped(self):
        """A real vital sign shares this endpoint; it must not be read as a game."""
        assert Session.from_payload({"patientId": 1, "painScale": 7}) is None
        assert Session.from_payload({"patientId": 1}) is None

    def test_missing_fields_default_to_zero_rather_than_crashing(self):
        session = Session.from_payload({"patientId": 3, "painScale": 1})
        assert session is not None
        assert session.metrics["score"] == 0.0

    def test_chart_title_names_the_mode_and_date(self):
        session = Session.from_payload(
            {"patientId": 5, "painScale": 2, "timestamp": "2024-09-12T10:31:00.000Z"}
        )
        assert session is not None
        assert session.date == "2024-09-12"
        assert session.chart_title() == "Patient 5 - Open / Close (2024-09-12)"

    def test_chart_title_without_a_timestamp(self):
        session = Session.time_score(5, score=1, gain=1, exercise_seconds=1, movements=1)
        assert session.chart_title() == "Patient 5 - Time / Score"


class TestPatient:
    def test_parses_a_backend_payload(self):
        patient = Patient.from_payload(
            {"id": "12", "firstName": "Ali", "lastName": "Hatefi"}
        )
        assert patient.id == 12
        assert patient.display_name == "Ali Hatefi"

    def test_falls_back_to_the_id_when_unnamed(self):
        assert Patient.from_payload({"id": 3}).display_name == "Patient 3"


class TestPatientPayload:
    def test_builds_a_valid_email(self):
        """A synthesised address still has to be a valid one."""
        payload = new_patient_payload(1, "Ali", "Hatefi", "1990-01-01T00:00:00.000Z")
        assert payload["email"] == "alihatefi@telerehab.local"
        assert " " not in payload["email"]

    def test_does_not_smuggle_age_into_the_phone_number(self):
        payload = new_patient_payload(1, "Ali", "Hatefi", "1990-01-01T00:00:00.000Z")
        assert "phoneNumber" not in payload

    def test_handles_names_with_no_alphanumerics(self):
        payload = new_patient_payload(1, "-", "-", "1990-01-01T00:00:00.000Z")
        assert payload["email"] == "patient@telerehab.local"
