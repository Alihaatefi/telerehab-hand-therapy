# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-10-15

A new interface on the same exercise logic. The rules, calibration and scoring
that the thesis describes are unchanged; everything around them was rebuilt.

### Added

- **A Qt (PySide6) interface** with a design system (`ui/theme.py`), a sidebar
  shell, and a guided exercise flow: setup, calibration, exercise, results.
- **Live camera view with the detected hand drawn over it**, during calibration
  and as a picture-in-picture while exercising.
- **Demo camera** (`python -m telerehab --demo`, or Settings): a simulated hand
  built from the reference photographs and the real MediaPipe pipeline, for
  demonstrations and computers with no webcam.
- **Reports page**: a trend chart per metric (points spaced by real time),
  per-mode tabs, a sessions table, a single-report lookup, and CSV and PDF export.
- **Settings page**: backend URL with a connection test, camera selection with a
  camera test, sound, and persistent preferences. Command-line options still win
  for that run.
- **Results page** that keeps a finished session on screen and offers a retry if
  the backend is unreachable, instead of losing it.
- A three-second countdown before an exercise, and a confirmation before ending
  one early.
- `BackendError.status_code`, so callers branch on the HTTP status rather than a
  substring of the message.
- Tests for the exercise engines, calibration procedures, the demo camera, CSV
  export, the Qt widgets, and full end-to-end sessions through the real widgets.
- `ruff` and `mypy` configuration, a CI workflow, `THIRD_PARTY_NOTICES.md` and
  this changelog.

### Changed

- **License.** Version 2.0.0 and later are published under an Evaluation and
  Presentation License (see `LICENSE`) instead of the MIT License. Rights already
  granted under the MIT License for earlier versions are not withdrawn.
- **Exercise rules moved out of the screens.** `TimeScoreEngine`,
  `OpenCloseEngine` and the two calibration tasks are plain classes with an
  injectable clock; the logic is the same, but a whole session can now be played
  through in a unit test.
- **The camera and hand detection run on their own thread**, and backend calls no
  longer block the window.
- **Assets live inside the package** (`telerehab/resources`), so an installed
  copy finds them. Previously they were located relative to the source checkout.
- Reports no longer put a score, a duration and a repetition count on one axis;
  each metric has its own chart.
- The scene, butterfly, flower, application mark and icons are drawn in code
  rather than loaded from bitmaps.
- Python 3.10, 3.11 and 3.12 are listed as supported.

### Removed

- The pygame interface and the matplotlib charts, along with the `pygame` and
  `matplotlib` dependencies.
- The bitmap backgrounds and sprites, and the screenshots and GIFs of the
  previous interface.

### Fixed

- A 404 from the backend was recognised by searching the error message for
  `"-> 404"`; it is now read from the status code.
- The demo camera's thumb-to-index distance used to dip below both calibration
  extremes while the hand moved between them, which could make a closed hand read
  as open.

## [1.0.0] - 2024-09

The thesis version: a pygame interface over the same vision, exercise and backend
layers.
