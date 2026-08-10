#!/usr/bin/env python3
"""A stand-in for the clinical backend, so this repository can be run.

The real backend is a third-party clinical platform (TypeScript / NestJS /
Prisma / PostgreSQL) that is **not** part of this project and is not publicly
distributable. This file is an independent reimplementation of just the two
endpoints the game uses, written from the client's observable contract in
``telerehab/api/client.py`` — no backend code is reproduced here.

It implements:

    POST /patients          -> create a patient, returns {"id": ...}
    GET  /patients/<id>     -> fetch a patient, 404 if unknown
    GET  /patients          -> list patients
    POST /vital-signs       -> store a session row, returns it with an id
    GET  /vital-signs       -> list every stored row

Deliberately dependency-free (standard library only) and single-file, so
reviewing it costs nothing and running it needs no install::

    python mock_server/server.py --seed

Records persist to ``mock_server/data/store.json`` between runs.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
STORE_PATH = DATA_DIR / "store.json"

_PATIENT_RE = re.compile(r"^/patients/(\d+)$")


class Store:
    """A tiny JSON-backed store with auto-incrementing ids."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.patients: dict[int, dict[str, Any]] = {}
        self.vital_signs: list[dict[str, Any]] = []
        self._next_patient_id = 1
        self._next_vital_id = 1
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.patients = {int(k): v for k, v in raw.get("patients", {}).items()}
        self.vital_signs = raw.get("vitalSigns", [])
        self._next_patient_id = max(self.patients, default=0) + 1
        self._next_vital_id = max(
            (row.get("id", 0) for row in self.vital_signs), default=0
        ) + 1

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "patients": {str(k): v for k, v in self.patients.items()},
            "vitalSigns": self.vital_signs,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add_patient(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            patient = {**payload, "id": self._next_patient_id}
            self.patients[self._next_patient_id] = patient
            self._next_patient_id += 1
            self.save()
            return patient

    def add_vital_signs(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            row = {
                **payload,
                "id": self._next_vital_id,
                "timestamp": payload.get("timestamp")
                or datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            }
            self.vital_signs.append(row)
            self._next_vital_id += 1
            self.save()
            return row

    def reset(self) -> None:
        with self._lock:
            self.patients.clear()
            self.vital_signs.clear()
            self._next_patient_id = 1
            self._next_vital_id = 1
            self.save()


def seed(store: Store, patients: int = 3, weeks: int = 6) -> None:
    """Populate a few patients with a plausible improving trend.

    Enough history that the report screens have something to draw, and enough
    of an upward trend that a progress chart looks like real rehabilitation.
    """
    rng = random.Random(20240912)
    store.reset()

    names = [("Ali", "Hatefi"), ("Sara", "Karimi"), ("Reza", "Mohammadi")]
    for index in range(patients):
        first, last = names[index % len(names)]
        patient = store.add_patient(
            {
                "doctorId": 1,
                "firstName": first,
                "lastName": last,
                "email": f"{first.lower()}{last.lower()}@telerehab.local",
                "dob": "1990-01-01T00:00:00.000Z",
            }
        )

        baseline = 4 + index
        for week in range(weeks):
            when = datetime.now(timezone.utc) - timedelta(days=(weeks - week) * 7)
            stamp = when.isoformat(timespec="milliseconds")

            # Time/Score: score climbs week over week, with some noise.
            store.add_vital_signs(
                {
                    "patientId": patient["id"],
                    "painScale": 1,
                    "bloodPressure": "120/80",
                    "heartRate": baseline + week * 2 + rng.randint(-1, 1),
                    "respiratoryRate": 1.0,
                    "temperature": 60,
                    "oxygenSaturation": 18 + week * 3 + rng.randint(-2, 2),
                    "timestamp": stamp,
                }
            )

            # Open/Close: holds get longer as control improves.
            store.add_vital_signs(
                {
                    "patientId": patient["id"],
                    "painScale": 2,
                    "bloodPressure": "120/80",
                    "heartRate": 3 + week // 2,
                    "respiratoryRate": 3 + week // 2,
                    "temperature": 5 + week,
                    "oxygenSaturation": max(0, 5 + week - rng.randint(0, 1)),
                    "timestamp": stamp,
                }
            )

    print(
        f"Seeded {len(store.patients)} patients and "
        f"{len(store.vital_signs)} sessions -> {store.path}"
    )
    print("Patient ids: " + ", ".join(str(i) for i in sorted(store.patients)))


class Handler(BaseHTTPRequestHandler):
    server_version = "TeleRehabMock/1.0"
    store: Store

    # -- helpers -----------------------------------------------------------

    def _send(self, status: HTTPStatus, payload: Any = None) -> None:
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"  {self.command:4s} {self.path} -> {args[1] if len(args) > 1 else ''}")

    # -- routes ------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/vital-signs":
            self._send(HTTPStatus.OK, self.store.vital_signs)
            return

        if self.path == "/patients":
            self._send(HTTPStatus.OK, list(self.store.patients.values()))
            return

        match = _PATIENT_RE.match(self.path)
        if match:
            patient = self.store.patients.get(int(match.group(1)))
            if patient is None:
                self._send(HTTPStatus.NOT_FOUND, {"message": "patient not found"})
            else:
                self._send(HTTPStatus.OK, patient)
            return

        self._send(HTTPStatus.NOT_FOUND, {"message": f"no route for {self.path}"})

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        payload = self._read_json()
        if payload is None:
            self._send(HTTPStatus.BAD_REQUEST, {"message": "malformed JSON body"})
            return

        if self.path == "/patients":
            if not payload.get("firstName"):
                self._send(HTTPStatus.BAD_REQUEST, {"message": "firstName is required"})
                return
            self._send(HTTPStatus.CREATED, self.store.add_patient(payload))
            return

        if self.path == "/vital-signs":
            if "patientId" not in payload:
                self._send(HTTPStatus.BAD_REQUEST, {"message": "patientId is required"})
                return
            if int(payload["patientId"]) not in self.store.patients:
                self._send(HTTPStatus.NOT_FOUND, {"message": "unknown patientId"})
                return
            self._send(HTTPStatus.CREATED, self.store.add_vital_signs(payload))
            return

        self._send(HTTPStatus.NOT_FOUND, {"message": f"no route for {self.path}"})


def build_server(host: str, port: int, store: Store) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"store": store})
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument(
        "--seed", action="store_true",
        help="replace the store with demo patients and six weeks of sessions",
    )
    parser.add_argument(
        "--reset", action="store_true", help="empty the store and exit"
    )
    args = parser.parse_args()

    store = Store(STORE_PATH)
    if args.reset:
        store.reset()
        print(f"Cleared {STORE_PATH}")
        return 0
    if args.seed:
        seed(store)

    server = build_server(args.host, args.port, store)
    print(f"Mock backend listening on http://{args.host}:{args.port}")
    print(f"  patients:  {len(store.patients)}")
    print(f"  sessions:  {len(store.vital_signs)}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
