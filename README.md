# TeleRehab — Hand Therapy

**Webcam-based hand rehabilitation exercises with per-patient calibration and
clinician-facing progress reports.** No wearable hardware: a laptop camera,
MediaPipe hand tracking, and two exercises designed around what a recovering
hand can actually do.

Built as the practical component of a B.Sc. thesis in Biomedical Engineering
(Amirkabir University of Technology, September 2024), then rebuilt from the
submitted scripts into the package documented here.

<p align="center">
  <img src="docs/media/demo-time-score.gif" width="49%" alt="Time/Score mode: the butterfly follows hand openness and scores by settling on the flower">
  <img src="docs/media/demo-open-close.gif" width="49%" alt="Open/Close mode: timed posture holds with live hand-state feedback">
</p>
<p align="center"><sub>Left: Time/Score mode. Right: Open/Close mode. Both driven live by hand tracking.</sub></p>

---

## What it does

Hand openness is measured from the webcam and turned into an exercise the
patient can see themselves succeeding at, while the numbers a clinician needs
are recorded in the background.

**Time/Score mode** — hand openness moves a butterfly across a garden. Settling
on the flower for half a second scores a point and the flower moves. Records
score, movement count, and the configured difficulty.

**Open/Close mode** — the patient holds the hand open, then closed, for a
prescribed duration and number of repetitions. The hold timer only advances
while the posture is actually correct.

**Reports** — per-session bar charts, and progress trends across sessions.

<p align="center">
  <img src="docs/media/shot-calibration.jpg" width="32%" alt="Calibration screen with hand landmarks overlaid">
  <img src="docs/media/chart-session.png" width="32%" alt="Bar chart of one session's metrics">
  <img src="docs/media/chart-progress.png" width="32%" alt="Line chart of score across six weekly sessions">
</p>
<p align="center"><sub>Calibration · single-session report · progress across six sessions.</sub></p>

## The idea worth stealing: calibration

Hand openness in normalised image coordinates depends on hand size and camera
distance as much as on how open the hand is. The project's own reference
photographs show the scale of the problem — the same metric on two postures
reads 36.8 vs 60.7, and both numbers would shift if the patient sat further
back.

A fixed threshold therefore cannot work across patients. Every session starts
by learning the patient's *own* achievable range and mapping it onto 0–100, so
difficulty follows the patient rather than an absolute number. A separate
`gain` setting decouples achievable range from required screen travel: at
`gain = 2.0`, a patient who can only reach 50% openness still moves the
butterfly across the whole garden.

For a patient with limited range this is the difference between a usable
exercise and an impossible one. Details in
[`docs/architecture.md`](docs/architecture.md).

## Running it

Requires **Python 3.10–3.12** (MediaPipe has no 3.13+ wheels) and a webcam.

```bash
git clone https://github.com/alihatefi/telerehab-hand-therapy
cd telerehab-hand-therapy

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python mock_server/server.py --seed    # terminal 1 — demo backend + sample data
python -m telerehab                    # terminal 2 — the application
```

Check both external dependencies before starting:

```console
$ python -m telerehab --check
[ ok ] backend      http://localhost:3000
[ ok ] camera 0     640x480  (hand detected)
```

Useful flags: `--api-url URL`, `--camera N`, `--verbose`.
`python mock_server/server.py --reset` empties the demo store.

## About the backend

The system this was written against is a general-purpose clinical platform
(TypeScript / NestJS / Fastify / Prisma / PostgreSQL) developed separately by a
third party. **It is not mine, it is not redistributable, and no part of it is
included in this repository.** My work is the client integration against it.

So that this repository runs anyway, `mock_server/server.py` is an independent
~250-line standard-library reimplementation of the two endpoints the
application uses (`/patients`, `/vital-signs`), written from the client's own
observable contract. `--seed` populates three patients with six weeks of
sessions so the report screens have something real to draw.

### A compromise worth naming

That backend's write surface for time-series data is a `/vital-signs` resource
with a fixed medical schema, and it could not be extended with a
rehabilitation-session resource for this thesis. Exercise results are therefore
**packed into vital-sign fields**: a stored row reading `heartRate: 14` is a
game score, and `painScale` is not a pain score but a discriminator saying which
exercise the row came from.

This is a poor way to model clinical data. It is documented rather than hidden
because it is what the deployed system actually does, and inventing a cleaner
schema here would misrepresent the work. The mapping is now confined to one
table — `FIELD_MAP` in [`api/models.py`](src/telerehab/api/models.py) — which
is itself a fix: the original re-typed it at four call sites, and two of them
disagreed. See [the data-model section](docs/architecture.md#data-model-and-its-known-compromise).

## Layout

```
src/telerehab/
├── config.py            settings, read once from the environment
├── vision/              camera, hand landmarks, per-patient calibration
│   ├── geometry.py        openness metrics — pure functions, no MediaPipe
│   ├── calibration.py     range / two-point calibration, movement hysteresis
│   └── hand_tracker.py    the only module that imports MediaPipe or OpenCV
├── games/
│   ├── scoring.py         dwell scoring, hold timing, pause-safe countdown
│   ├── time_score.py      butterfly garden
│   ├── open_close.py      timed posture holds
│   └── calibrating.py     the two calibration screens
├── api/                 backend client and the records exchanged with it
├── reports/             matplotlib charts, in-app viewer
├── ui/                  theme, widgets, screen scaffolding
└── app.py               window setup and navigation

mock_server/server.py    dependency-free stand-in for the clinical backend
tests/                   102 tests
legacy/                  the original scripts, as submitted
docs/                    architecture, references
```

## Tests

```console
$ pytest -q
102 passed in 7.70s
```

The logic worth testing — openness metrics, calibration, scoring rules, the
vital-signs mapping — depends on nothing heavier than the standard library, so
most of the suite needs neither a camera nor a display. Timing-dependent code
takes an injected clock, so hold timers and countdowns are tested in
milliseconds instead of waiting out real exercise durations.

Two suites go further than unit tests:

- `test_client.py` runs the mock server on a real socket and exercises the
  client over actual HTTP, so client and server cannot drift apart.
- `test_vision_integration.py` runs the real MediaPipe pipeline over the two
  reference photographs in `assets/`, checking the assumption the whole
  application rests on: that these metrics separate an open hand from a closed
  one, by a wide enough margin to calibrate on.

## About this repository

The thesis was written and submitted without version control. The code that was
handed in consisted of six near-duplicate scripts (`Game27.py` … `Game33.py`)
plus two API wrappers — about 2,900 lines, roughly 70% duplicated. Versioning
was by copying the file and bumping a number.

Rather than quietly reconstructing a history that never existed, the first
commit here is that code exactly as submitted, tagged
[`v0.1-thesis-submission`](../../releases/tag/v0.1-thesis-submission) and kept
in [`legacy/`](legacy/). Everything after it is the refactor, with today's
dates.

What that refactor found and fixed, beyond the restructuring:

| | Defect in the submitted code |
|---|---|
| 1 | `crud.py` read `response.text` inside `except RequestException`, but `response` is unbound when the connection fails — so *"backend is down"*, the likeliest failure in home use, surfaced as `UnboundLocalError` |
| 2 | `show_game_over_window` called `int(result.get("id"))` before checking `if result:` — a guaranteed crash whenever a save failed |
| 3 | Three screens read their button rectangles one statement *before* those rectangles were assigned; a click on the first frame raised `NameError` |
| 4 | Chart labels for the two modes were swapped in one of the two report paths, mislabelling every chart drawn through it |
| 5 | `show_vital_number` had no `else` branch for unexpected `painScale` values → `NameError` on rows written by other parts of the platform |
| 6 | A patient with several sessions produced several charts, but only the last was ever displayed |
| 7 | `user_input_page` and `sign_up_page` called *themselves* to go back, growing the stack on every navigation |
| 8 | Buttons fired from `mouse.get_pressed()` during drawing, so a held click repeated the action ~30×/second |
| 9 | The sign-up payload sent the patient's age in `phoneNumber` and built an email as `f"{name} + @telerahab.com"`, literal `' + '` included |
| 10 | `reset_game`, `show_confirmation_dialog` and `settings_page` were each defined **twice** in `Game33.py`; the second silently shadowed the first (~120 dead lines) |
| 11 | Plots were written into the working directory, read back, then deleted — leaving stray `plot_*.png` on every error path |
| 12 | Resuming from pause adjusted the start time in a way that lost time whenever pauses overlapped |
| 13 | A single wrong-posture frame reset the Open/Close hold timer to zero, erasing a patient's accumulated hold for one wobble |

Two behaviours were changed deliberately rather than fixed: the hold timer now
pauses instead of resetting (13), and openness is clamped to the calibrated
range instead of extrapolating. Both are noted in the code.

One constraint is worth flagging for anyone cloning this: MediaPipe removed the
`mp.solutions` API this project uses in releases after **0.10.14**, which is
also the last release with CPython 3.12 wheels — hence the exact pin. All
MediaPipe access is confined to
[`vision/hand_tracker.py`](src/telerehab/vision/hand_tracker.py), so moving to
the newer Tasks API is a single-file change.

## Thesis

**"Design of a Patient–Doctor Interface Application for Tele-rehabilitation"**
(طراحی اپلیکیشن رابط بیمار و پزشک در زمینه توانبخشی از راه دور)
B.Sc. thesis, Department of Biomedical Engineering, Amirkabir University of
Technology (Tehran Polytechnic), September 2024. Supervisor: Dr. Mohammad Ali
Ahmadi-Pajouh.

> Rehabilitation helps people who have lost abilities through injury or illness,
> but it requires repeated visits that many patients find hard to make. This
> project designs an interface application for remote rehabilitation, treating
> the therapy as a game: a biofeedback-driven system that supports recovery of
> hand movement — particularly opening and closing — through a deliberately
> pleasant interface, while storing session data in a clinical database under
> professional supervision.

The thesis document is copyright Amirkabir University of Technology and is not
redistributed here. Literature surveyed is listed in
[`docs/references.md`](docs/references.md).

## License

Source code is MIT-licensed — see [LICENSE](LICENSE).

The MIT license covers the code only. It does not extend to the thesis
document, to the third-party backend described above, or to the papers listed
in `docs/references.md`. Game artwork and audio in `assets/` were produced for
the thesis and are released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Author

**Ali Hatefi** — B.Sc. Biomedical Engineering (Bioelectrics), Amirkabir
University of Technology.
