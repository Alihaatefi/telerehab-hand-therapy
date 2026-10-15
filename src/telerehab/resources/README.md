# Resources

Everything the application ships with lives here, inside the package, so an
installed copy finds its files exactly as a source checkout does
(`telerehab.config.RESOURCES_DIR`).

| Path | Used by | Notes |
|------|---------|-------|
| `reference/hand_open.jpg`, `reference/hand_closed.jpg` | the demo camera, `tests/test_vision_integration.py` | reference photographs of the two postures |
| `sounds/score.wav` | both exercises | the scoring chime, 16-bit mono at 44.1 kHz, 0.68 s |

The two hand photographs are not decorative. `tests/test_vision_integration.py`
runs the real MediaPipe pipeline over them to verify that the openness metrics
separate the two postures by a margin wide enough to calibrate on, and the demo
camera (`python -m telerehab --demo`) morphs between the landmarks measured from
them. Replacing them changes what those tests assert.

## What is deliberately *not* here

There are no bitmap sprites or backgrounds. The garden, the butterfly, the
flower, the application mark and every interface icon are drawn in code
(`ui/art.py`, `ui/icons.py`), so they are sharp at any window size or display
scaling, carry no third-party artwork licence, and can respond to the exercise -
the butterfly's wings beat, the flower opens and closes to show the posture being
asked for.

## Licence

The photographs and the chime were produced for the thesis and are released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See `LICENSE` and
`THIRD_PARTY_NOTICES.md` for everything else.
